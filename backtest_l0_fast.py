"""
backtest_l0_fast.py — SCRATCH (2026-09-02). Analisi "ripensare L0".

Domanda: il gate regime BULL su tutti e 3 i percorsi L0 (FAST/SLOW/PRAGMATIC) impedisce
a L0 di entrare su drawdown VERI (che rompono EMA20>SMA50 → regime non BULL). Oggi L0
entra solo su pullback poco profondi dentro un uptrend — contraddice "Deep Recovery".

Varianti (IN 2023-08-05..2025-08-05 / OOS 2025-08-05..2026-08-08, batch congelato):
  l0_prod          whitelist=[equity_sviluppati], regime BULL           (= produzione)
  l0_regime_BL     whitelist=[equity_sviluppati], regime BULL+LATERALE
  l0_regime_all    whitelist=[equity_sviluppati], nessun gate regime
  l0_wl5_prod      whitelist=5 core, regime BULL
  l0_wl5_BL        whitelist=5 core, regime BULL+LATERALE

Il ramo regime usa l'override guardato `global_params.l0_regime_allowed` (lista) aggiunto
a suggest_level_0() — assente nello YAML → comportamento invariato in produzione.

Uso (nel container):  python3 backtest_l0_fast.py
"""
import sys
sys.path.insert(0, '/app')

import argparse
import json
from datetime import date

import pandas as pd

from technical_analysis import ETFTechnicalAnalyzer
from database import PriceDatabase
from backtest_l0_v2 import aggregate

DEFAULT_FROZEN_BATCH = '2026-08-07'
POSITION_SIZE = 10000.0

IN_START, IN_END = date(2023, 8, 5), date(2025, 8, 5)
OOS_START, OOS_END = date(2025, 8, 5), date(2026, 8, 8)

CORE5 = ['equity_sviluppati', 'mercati_emergenti', 'settoriali_growth',
         'oro_metalli_preziosi', 'metalli_industriali']

# label -> (whitelist, regime_allowed | None)
VARIANTS = {
    'l0_prod':       (['equity_sviluppati'], None),
    'l0_regime_BL':  (['equity_sviluppati'], ['BULL', 'LATERALE']),
    'l0_regime_all': (['equity_sviluppati'], ['BULL', 'LATERALE', 'BEAR']),
    'l0_wl5_BL':     (CORE5, ['BULL', 'LATERALE']),
}


def precompute_l0(analyzer, close_full, high_full, low_full):
    """Indicatori causali calcolati UNA volta sull'intera serie. suggest_level_0() e i
    percorsi FAST/SLOW ricalcolano RSI/EMA/SMA/ATR da zero a ogni giorno (142 ms/call
    misurati — 52% in _calculate_atr) → O(n^2) per ticker. Qui si patchano i metodi
    dell'istanza per restituire fette pre-calcolate. Indicatori causali: fetta[:n] ==
    ricalcolo su serie[:n], nessun cambio di risultato."""
    return {
        'rsi': analyzer._rsi(close_full),
        'atr': analyzer._calculate_atr(high_full, low_full, close_full),
        'ema': {p: analyzer._ema(close_full, p) for p in (10, 20, 50)},
        'sma': {p: analyzer._sma(close_full, p) for p in (50, 200)},
    }


def patch_analyzer(analyzer, pc):
    rsi_f, atr_f, ema_f, sma_f = pc['rsi'], pc['atr'], pc['ema'], pc['sma']
    o_ema, o_sma = analyzer._ema, analyzer._sma
    analyzer._rsi = lambda s: rsi_f.iloc[:len(s)]
    analyzer._calculate_atr = lambda h, l, c, period=14: atr_f.iloc[:len(c)]

    def _atrn(h, l, c, period=14):
        if h is None or l is None or c is None or len(c) < period:
            return None
        a = atr_f.iloc[len(c) - 1]
        cp = float(c.iloc[-1])
        return float(a) / cp if (cp > 0 and pd.notna(a)) else None
    analyzer._calculate_atr_normalized = _atrn
    analyzer._ema = lambda s, period: (ema_f[period].iloc[:len(s)] if period in ema_f else o_ema(s, period))
    analyzer._sma = lambda s, period: (sma_f[period].iloc[:len(s)] if period in sma_f else o_sma(s, period))


def simulate_l0(analyzer, close_full, high_full, low_full, hist_index, test_dates):
    """Walk-forward L0: ingresso via suggest_level_0(), uscita SOLO SL/TP giornalieri sul
    Close. Identico a backtest_l0_v2.simulate_l0 — l'analyzer arriva gia' patchato."""
    holding = False
    entry_price = entry_date = entry_mode = None
    trades = []
    for d in test_dates:
        pos = hist_index.get_loc(d)
        close_slice = close_full.iloc[:pos + 1]
        close_today = float(close_slice.iloc[-1])
        if not holding:
            r = analyzer.suggest_level_0(close_slice,
                                         high_full.iloc[:pos + 1] if high_full is not None else None,
                                         low_full.iloc[:pos + 1] if low_full is not None else None,
                                         current_level=3)
            if r.get('l0_entry'):
                holding, entry_price, entry_date = True, close_today, d.date().isoformat()
                entry_mode = r.get('l0_regime_mode')
        else:
            sl = analyzer.calculate_sl_suggerito_l0(entry_price, close_today).get('sl_suggerito')
            tp_hit = bool(analyzer.calculate_tp_suggerito_l0(entry_price, close_today).get('trigger'))
            sl_hit = sl is not None and close_today <= sl
            if sl_hit or tp_hit:
                trades.append({
                    'entry_date': entry_date, 'entry_price': entry_price,
                    'exit_date': d.date().isoformat(), 'exit_price': close_today,
                    'status': 'closed',
                    'gross_pct_gain': round((close_today / entry_price - 1) * 100, 3),
                    'exit_reason': 'SL' if sl_hit else 'TP', 'entry_mode': entry_mode,
                })
                holding, entry_price, entry_date, entry_mode = False, None, None, None
    if holding:
        lp = float(close_full.iloc[-1])
        trades.append({
            'entry_date': entry_date, 'entry_price': entry_price, 'exit_date': None,
            'exit_price': lp, 'status': 'open',
            'gross_pct_gain': round((lp / entry_price - 1) * 100, 3),
            'exit_reason': None, 'entry_mode': entry_mode,
        })
    return trades


def profit_factor(trades):
    g = sum(t['net_gain_eur'] for t in trades if t['status'] == 'closed' and t['net_gain_eur'] > 0)
    l = -sum(t['net_gain_eur'] for t in trades if t['status'] == 'closed' and t['net_gain_eur'] < 0)
    if l == 0:
        return None if g == 0 else float('inf')
    return round(g / l, 2)


def load_all(freeze_batch):
    """Carica TUTTI i ticker delle 5 famiglie core (superset di ogni whitelist testata)."""
    db = PriceDatabase()
    df = pd.read_excel('etf_monitoraggio.xlsx', sheet_name='ETF')
    items, skipped = [], []
    for _, row in df.iterrows():
        ticker = str(row.get('Ticker', '')).strip()
        if not ticker or ticker.lower() == 'nan':
            continue
        fam = ETFTechnicalAnalyzer.detect_family(str(row.get('Categoria', '')))
        if fam not in CORE5:
            continue
        hist = db.get_frozen_ohlcv(ticker, freeze_batch)
        if hist.empty or len(hist) < 220:
            skipped.append(ticker)
            continue
        has_ohlc = all(c in hist.columns for c in ['Open', 'High', 'Low'])
        close_full = hist['Close'].astype(float)
        high_full = hist['High'].astype(float) if has_ohlc else None
        low_full = hist['Low'].astype(float) if has_ohlc else None
        tmp = ETFTechnicalAnalyzer(famiglia=fam)
        items.append({
            'ticker': ticker, 'famiglia': fam,
            'close_full': close_full, 'high_full': high_full, 'low_full': low_full,
            'hist_index': hist.index,
            'precomputed': precompute_l0(tmp, close_full, high_full, low_full),
        })
    print(f"Caricati {len(items)} ticker core, {len(skipped)} scartati (<220gg)")
    return items


def set_global(whitelist, regime_allowed):
    gp = ETFTechnicalAnalyzer._FAMILIES_CONFIG.setdefault('global_params', {})
    gp['l0_whitelist'] = list(whitelist)
    gp['l0_blacklist'] = []          # svuota: whitelist e blacklist sono controllate indipendentemente
    if regime_allowed is None:
        gp.pop('l0_regime_allowed', None)
    else:
        gp['l0_regime_allowed'] = list(regime_allowed)


def run_variant(items, whitelist, regime_allowed, win_start, win_end):
    set_global(whitelist, regime_allowed)
    wl = set(whitelist)
    results = []
    for e in items:
        if e['famiglia'] not in wl:
            continue
        analyzer = ETFTechnicalAnalyzer(famiglia=e['famiglia'])
        patch_analyzer(analyzer, e['precomputed'])
        test_dates = [d for d in e['hist_index'] if win_start <= d.date() < win_end]
        if not test_dates:
            continue
        trades = simulate_l0(analyzer, e['close_full'], e['high_full'], e['low_full'],
                             e['hist_index'], test_dates)
        results.append({'ticker': e['ticker'], 'famiglia': e['famiglia'], 'trades': trades})
    return results


def summarize(results):
    agg = aggregate(results, POSITION_SIZE)
    return {
        'n_closed': agg['n_trades_closed'], 'n_open': agg['n_trades_open'],
        'n_sl': agg['n_exit_sl'], 'n_tp': agg['n_exit_tp'],
        'wr': agg['win_rate_pct'], 'avg_net': agg['avg_net_pct_gain'],
        'pf': profit_factor(agg['trades']), 'net_eur': agg['total_net_eur'],
        'dur': agg['avg_duration_days'],
    }


def per_family(results):
    fam = {}
    for r in results:
        fam.setdefault(r['famiglia'], []).extend(r['trades'])
    out = {}
    for f, trades in sorted(fam.items()):
        closed = [t for t in trades if t['status'] == 'closed']
        wins = [t for t in closed if t['gross_pct_gain'] > 0]
        out[f] = {'n': len(closed),
                  'wr': round(100 * len(wins) / len(closed), 1) if closed else None,
                  'avg_gross': round(sum(t['gross_pct_gain'] for t in closed) / len(closed), 2) if closed else None}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frozen-batch', default=DEFAULT_FROZEN_BATCH)
    ap.add_argument('--out', default='data/backtest_l0_fast_result.json')
    args = ap.parse_args()

    print("=" * 80)
    print("BACKTEST L0 FAST — ripensare L0 | size 10.000EUR | costi 5+5 | tax 26%")
    print(f"IN {IN_START}..{IN_END}  |  OOS {OOS_START}..{OOS_END}  |  batch {args.frozen_batch}")
    print("=" * 80)

    items = load_all(args.frozen_batch)
    out = {'variants': {}, 'per_family_oos': {}}

    for label, (wl, ra) in VARIANTS.items():
        row = {}
        for wname, (ws, we) in [('IN', (IN_START, IN_END)), ('OOS', (OOS_START, OOS_END))]:
            res = run_variant(items, wl, ra, ws, we)
            row[wname] = summarize(res)
            if wname == 'OOS':
                out['per_family_oos'][label] = per_family(res)
        out['variants'][label] = row
        print(f"\n### {label}   whitelist={wl}  regime_allowed={ra or 'BULL(default)'}")
        for w in ('IN', 'OOS'):
            s = row[w]
            print(f"  {w:4s}: N={s['n_closed']:3d}  WR={s['wr']}  PF={s['pf']}  "
                  f"avg_net={s['avg_net']}%  SL/TP={s['n_sl']}/{s['n_tp']}  "
                  f"dur={s['dur']}g  net={s['net_eur']}EUR")

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nSalvato in {args.out}")


if __name__ == '__main__':
    main()
