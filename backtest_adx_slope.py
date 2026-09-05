"""
backtest_adx_slope.py — SCRATCH. Diagnostica dell'idea "ADX Slope" (proposta
esterna, 2026-09-05): per L1 richiedere ADX in salita (non solo sopra soglia,
come fa gia' la condizione 5 nativa) al momento dell'ingresso; per L0 il
contrario (ADX alto ma in discesa = pressione ribassista in esaurimento).

Metodo (stesso gia' usato per "un filtro ADX su min_buy_count=6 avrebbe
aiutato il 2024?", CLAUDE.md "Fase 2"): NON si costruisce subito un nuovo
gate — si prendono i trade GIA' generati dal motore reale (production
attuale: smart_6_macd per equity_sviluppati lato L1, suggest_level_0 nativo
lato L0 — le uniche configurazioni live oggi) e si segmentano per il segno
della pendenza ADX all'ingresso (ADX oggi - ADX 3gg fa). Se il segnale ha un
effetto reale, si giustifica un secondo giro con un gate vero + sweep IN/OOS;
altrimenti si chiude qui, come gia' successo per l'ipotesi ADX su 6/7.

Uso (dentro il container): python3 backtest_adx_slope.py
"""
import sys
sys.path.insert(0, '/app')

import json

import pandas as pd

from technical_analysis import ETFTechnicalAnalyzer
from backtest_l1 import FrozenDataFetcher, make_analyzer, simulate, apply_costs_and_tax as apply_costs_l1, DEFAULT_FROZEN_BATCH
from backtest_l0_v2 import simulate_l0, apply_costs_and_tax as apply_costs_l0

FAMIGLIA = 'equity_sviluppati'  # unica famiglia con smart_6_macd live (L1) e whitelist L0
POSITION_SIZE = 10000.0
SLOPE_WINDOW = 3
SPLIT_DATE = '2025-08-05'
ADX_LEVEL_THRESHOLD = 30  # soglia proposta esternamente per il lato L0


def load_universe_famiglia(excel_path='etf_monitoraggio.xlsx'):
    df = pd.read_excel(excel_path, sheet_name='ETF')
    tickers = []
    for _, row in df.iterrows():
        ticker = str(row.get('Ticker', '')).strip()
        categoria = str(row.get('Categoria', ''))
        if not ticker or ticker.lower() == 'nan':
            continue
        if ETFTechnicalAnalyzer.detect_family(categoria) == FAMIGLIA:
            tickers.append(ticker)
    return tickers


def adx_slope_at(adx_series, hist_index, entry_date_str):
    try:
        pos = hist_index.get_loc(pd.Timestamp(entry_date_str))
    except KeyError:
        return None, None
    if pos < SLOPE_WINDOW:
        return None, None
    level = adx_series.iloc[pos]
    slope = adx_series.iloc[pos] - adx_series.iloc[pos - SLOPE_WINDOW]
    if pd.isna(level) or pd.isna(slope):
        return None, None
    return float(level), float(slope)


def segment_report(label, trades, apply_costs_fn):
    """trades: lista con 'net_pct_gain' gia' calcolato e 'entry_date' per lo split IN/OOS,
    piu' 'adx_level'/'adx_slope' allegati. Stampa N/WR/PF/avg per IN e OOS, poi
    segmentato per segno della pendenza."""
    def agg(sub):
        n = len(sub)
        if n == 0:
            return {'n': 0, 'wr': None, 'pf': None, 'avg': None}
        wins = [t['net_pct_gain'] for t in sub if t['net_pct_gain'] > 0]
        losses = [t['net_pct_gain'] for t in sub if t['net_pct_gain'] <= 0]
        wr = round(100 * len(wins) / n, 1)
        avg = round(sum(t['net_pct_gain'] for t in sub) / n, 2)
        sum_win = sum(wins)
        sum_loss = -sum(losses)
        pf = round(sum_win / sum_loss, 2) if sum_loss else (float('inf') if sum_win else None)
        return {'n': n, 'wr': wr, 'pf': pf, 'avg': avg}

    print(f"\n{'='*78}\n{label}\n{'='*78}")
    for window_name, window in [('IN', lambda t: t['entry_date'] < SPLIT_DATE),
                                 ('OOS', lambda t: t['entry_date'] >= SPLIT_DATE)]:
        sub = [t for t in trades if window(t)]
        overall = agg(sub)
        rising = agg([t for t in sub if t.get('adx_slope') is not None and t['adx_slope'] > 0])
        falling = agg([t for t in sub if t.get('adx_slope') is not None and t['adx_slope'] <= 0])
        print(f"  [{window_name}] TUTTI:     N={overall['n']:3d} WR={overall['wr']}% PF={overall['pf']} avg={overall['avg']}%")
        print(f"  [{window_name}] ADX↑ (slope>0):  N={rising['n']:3d} WR={rising['wr']}% PF={rising['pf']} avg={rising['avg']}%")
        print(f"  [{window_name}] ADX↓/piatto:     N={falling['n']:3d} WR={falling['wr']}% PF={falling['pf']} avg={falling['avg']}%")


def main():
    tickers = load_universe_famiglia()
    print(f"BACKTEST ADX SLOPE — famiglia: {FAMIGLIA} ({len(tickers)} ticker)")
    print(f"Size: {POSITION_SIZE}EUR | Slope window: {SLOPE_WINDOW}gg | Split: {SPLIT_DATE}")

    fetcher = FrozenDataFetcher(DEFAULT_FROZEN_BATCH)
    l1_trades, l0_trades = [], []

    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] {ticker}...", end=' ')
        hist = fetcher.get_historical_data(ticker, days=1100)
        if hist.empty or len(hist) < 220 or not all(c in hist.columns for c in ['High', 'Low']):
            print("SKIP (storico insufficiente)")
            continue

        close_full = hist['Close'].astype(float)
        high_full = hist['High'].astype(float)
        low_full = hist['Low'].astype(float)

        analyzer_l1 = make_analyzer(FAMIGLIA)
        adx_series = analyzer_l1._adx(high_full, low_full, close_full)

        test_dates = list(hist.index)

        # ── L1: smart_6_macd nativo (gia' in YAML per equity_sviluppati) ──
        trades = simulate(analyzer_l1, close_full, high_full, low_full, hist.index, test_dates)
        for t in trades:
            if t['status'] != 'closed':
                continue
            t = apply_costs_l1(dict(t), POSITION_SIZE)
            level, slope = adx_slope_at(adx_series, hist.index, t['entry_date'])
            t['adx_level'] = level
            t['adx_slope'] = slope
            l1_trades.append(t)

        # ── L0: nativo (whitelist gia' rispettata da suggest_level_0) ──
        analyzer_l0 = make_analyzer(FAMIGLIA)
        trades0 = simulate_l0(analyzer_l0, close_full, high_full, low_full, hist.index, test_dates)
        for t in trades0:
            if t['status'] != 'closed':
                continue
            t = apply_costs_l0(dict(t), POSITION_SIZE)
            level, slope = adx_slope_at(adx_series, hist.index, t['entry_date'])
            t['adx_level'] = level
            t['adx_slope'] = slope
            l0_trades.append(t)

        print(f"L1={len([t for t in trades if t['status']=='closed'])} L0={len([t for t in trades0 if t['status']=='closed'])}")

    segment_report("L1 — smart_6_macd (equity_sviluppati) — segmentato per pendenza ADX", l1_trades, apply_costs_l1)

    print(f"\n{'='*78}\nL0 — nativo (equity_sviluppati) — segmentato per LIVELLO e PENDENZA ADX\n{'='*78}")
    for window_name, window in [('IN', lambda t: t['entry_date'] < SPLIT_DATE),
                                 ('OOS', lambda t: t['entry_date'] >= SPLIT_DATE)]:
        sub = [t for t in l0_trades if window(t)]

        def agg(s):
            n = len(s)
            if n == 0:
                return {'n': 0, 'wr': None, 'pf': None, 'avg': None}
            wins = [t['net_pct_gain'] for t in s if t['net_pct_gain'] > 0]
            losses = [t['net_pct_gain'] for t in s if t['net_pct_gain'] <= 0]
            wr = round(100 * len(wins) / n, 1)
            avg = round(sum(t['net_pct_gain'] for t in s) / n, 2)
            sum_win = sum(wins); sum_loss = -sum(losses)
            pf = round(sum_win / sum_loss, 2) if sum_loss else (float('inf') if sum_win else None)
            return {'n': n, 'wr': wr, 'pf': pf, 'avg': avg}

        overall = agg(sub)
        proposta = agg([t for t in sub if t.get('adx_level') is not None and t.get('adx_slope') is not None
                         and t['adx_level'] >= ADX_LEVEL_THRESHOLD and t['adx_slope'] < 0])
        resto = agg([t for t in sub if not (t.get('adx_level') is not None and t.get('adx_slope') is not None
                     and t['adx_level'] >= ADX_LEVEL_THRESHOLD and t['adx_slope'] < 0)])
        print(f"  [{window_name}] TUTTI:                          N={overall['n']:3d} WR={overall['wr']}% PF={overall['pf']} avg={overall['avg']}%")
        print(f"  [{window_name}] ADX>={ADX_LEVEL_THRESHOLD} E in discesa (proposta): N={proposta['n']:3d} WR={proposta['wr']}% PF={proposta['pf']} avg={proposta['avg']}%")
        print(f"  [{window_name}] Resto (non soddisfa la proposta):N={resto['n']:3d} WR={resto['wr']}% PF={resto['pf']} avg={resto['avg']}%")

    with open('data/backtest_adx_slope_result.json', 'w', encoding='utf-8') as f:
        json.dump({'l1_trades': l1_trades, 'l0_trades': l0_trades}, f, indent=2, ensure_ascii=False, default=str)
    print("\nSalvato in data/backtest_adx_slope_result.json")


if __name__ == '__main__':
    main()
