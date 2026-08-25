"""
backtest_radars.py — Backtest dei radar informativi (Radar Anticipato, Radar Rimbalzo
EMA20) sul Golden Dataset congelato, per capire se avrebbero senso come TRIGGER di
ingresso reale invece che solo come segnalazione — idea utente 2026-08-25.

Scope deciso con l'utente:
  - Radar Anticipato (compute_approach_signal) e Radar Rimbalzo (compute_pullback_bounce_
    signal) simulati come se fossero segnali di ingresso: quando scattano, "compra" quel
    giorno. Uscita: le STESSE funzioni reali gia' usate da L1 in produzione
    (calculate_sl_suggerito_l1 + calculate_stop_gain_dynamic) — stesso costo Directa
    (5+5EUR) e stessa tassazione (26% flat), cosi' il confronto e' davvero equo, non un
    numero a parte inventato per l'occasione.
  - Riferimento "L1 reale": lo stesso identico motore usato in produzione oggi
    (suggest_level() senza override — per le 5 famiglie 'core' questo include gia' il
    bundle smart_6_macd promosso il 2026-08-24), simulato nello STESSO run sugli STESSI
    ticker/date per un confronto apples-to-apples (non i numeri certificati di un run
    precedente, che usavano un batch/universo leggermente diverso).
  - Riferimento "L0": NON risimulato qui (e' un meccanismo strutturalmente diverso —
    mean-reversion su drawdown, non trend-following su EMA20 — un confronto diretto
    trade-per-trade non sarebbe comunque omogeneo). Il report stampa solo i numeri gia'
    certificati in CLAUDE.md (CANDIDATE_MODEL_L0_20260808) come contesto.
  - Overlap: per ogni ingresso a radar, verifica se sullo stesso ticker c'e' anche un
    ingresso L1 reale entro +/- OVERLAP_WINDOW_DAYS giorni — per capire se il radar
    anticipa/conferma il gate reale o cattura opportunita' che il gate non prende mai.

Split IN/OUT identico agli altri candidati di questo progetto (vedi optimize_hyperparameters.py):
  IN  = 2023-08-05 -> 2025-08-05
  OUT = 2025-08-05 -> 2026-08-05

Uso (dentro il container):
  python3 backtest_radars.py --radar approach,bounce --position-sizes 5000,10000
"""
import sys
sys.path.insert(0, '/app')

import argparse
import io
import json
import time
from contextlib import redirect_stdout
from datetime import datetime, timedelta

from backtest_l1 import (
    load_universe, aggregate, apply_costs_and_tax, FrozenDataFetcher,
    DEFAULT_FROZEN_BATCH, DIRECTA_FEE_BUY, DIRECTA_FEE_SELL, TAX_RATE,
    simulate as simulate_gate, make_analyzer,
)
from optimize_hyperparameters import extra_metrics, TRAIN_START, TRAIN_END, TEST_END
from technical_analysis import ETFTechnicalAnalyzer

OVERLAP_WINDOW_DAYS = 10

RADAR_DEFAULTS = {
    'approach': {'lookback': 7, 'min_r2': 0.3},   # stessi default di /api/approach-radar
    'bounce':   {'lookback': 10, 'min_r2': 0.3},  # stessi default di /api/bounce-radar
}


def simulate_radar(analyzer, close_full, high_full, low_full, hist_index, test_dates,
                    radar_type, lookback, min_r2):
    """Ingresso via compute_approach_signal()/compute_pullback_bounce_signal() (radar
    puramente informativi in produzione, qui usati come trigger simulato). Uscita:
    STESSA identica logica di backtest_l1.py::simulate() — SL/TP reali, check
    giornaliero sul Close, nessuna regola B/C/E/F. Copiata (non importata) perche'
    backtest_l1.simulate() e' agganciata a suggest_level(), non a un segnale esterno —
    duplicare 8 righe di uscita e' piu' chiaro che forzare un'interfaccia comune."""
    holding = False
    entry_price = None
    entry_date = None
    entry_score = None
    trades = []

    for d in test_dates:
        pos = hist_index.get_loc(d)
        close_slice = close_full.iloc[:pos + 1]
        high_slice = high_full.iloc[:pos + 1] if high_full is not None else None
        low_slice = low_full.iloc[:pos + 1] if low_full is not None else None
        close_today = float(close_slice.iloc[-1])

        if not holding:
            if radar_type == 'approach':
                signal = analyzer.compute_approach_signal(close_slice, high_slice, low_slice,
                                                            lookback=lookback, min_r2=min_r2)
                fired = bool(signal.get('approaching'))
            else:
                signal = analyzer.compute_pullback_bounce_signal(close_slice, high_slice, low_slice,
                                                                   lookback=lookback, min_r2=min_r2)
                fired = bool(signal.get('bouncing'))
            if fired:
                holding = True
                entry_price = close_today
                entry_date = d.date().isoformat()
                entry_score = signal.get('score')
                continue
        else:
            # Stesse funzioni e stessa logica di monitor.py::_update_portfolio_l1_suggerito()
            # e di backtest_l1.py::simulate() — SL = calculate_sl_suggerito_l1,
            # TP = calculate_stop_gain_dynamic, check una volta al giorno sul Close.
            ema20_series = analyzer._ema(close_slice, 20).tail(10)
            ema20_today = float(ema20_series.iloc[-1])

            sl_data = analyzer.calculate_sl_suggerito_l1(entry_price, close_today, ema20_today)
            sl = sl_data.get('sl_suggerito')

            sg_data = analyzer.calculate_stop_gain_dynamic(entry_price, close_today, ema20_series, analyzer.p)
            tp_hit = bool(sg_data.get('trigger'))
            sl_hit = sl is not None and close_today <= sl

            exit_price = None
            exit_reason = None
            if sl_hit:
                exit_price = close_today
                exit_reason = 'SL'
            elif tp_hit:
                exit_price = close_today
                exit_reason = 'TP'

            if exit_reason:
                gross_pct = round((exit_price / entry_price - 1) * 100, 3)
                trades.append({
                    'entry_date': entry_date, 'entry_price': entry_price,
                    'exit_date': d.date().isoformat(), 'exit_price': exit_price,
                    'status': 'closed', 'gross_pct_gain': gross_pct,
                    'exit_reason': exit_reason, 'entry_score': entry_score,
                })
                holding = False
                entry_price = None
                entry_date = None

    if holding:
        last_price = float(close_full.iloc[-1])
        gross_pct = round((last_price / entry_price - 1) * 100, 3)
        trades.append({
            'entry_date': entry_date, 'entry_price': entry_price,
            'exit_date': None, 'exit_price': last_price,
            'status': 'open', 'gross_pct_gain': gross_pct,
            'exit_reason': None, 'entry_score': entry_score,
        })

    return trades


def backtest_ticker(fetcher, ticker, famiglia, start_date, fetch_days, radar_types):
    """Simula, per UN ticker: i radar richiesti + il riferimento L1 reale (suggest_level()
    di produzione, nessun override — include gia' smart_6_macd per le famiglie core)."""
    hist = fetcher.get_historical_data(ticker, days=fetch_days)
    if hist.empty or len(hist) < 220:
        return None, f'Storico insufficiente ({len(hist)}gg, servono >=220 per SMA200)'

    has_ohlc = all(c in hist.columns for c in ['Open', 'High', 'Low'])
    close_full = hist['Close'].astype(float)
    high_full = hist['High'].astype(float) if has_ohlc else None
    low_full = hist['Low'].astype(float) if has_ohlc else None

    test_dates = [d for d in hist.index if d.date() >= start_date]
    if not test_dates:
        return None, 'Nessuna data nel range di backtest'

    out = {'ticker': ticker, 'famiglia': famiglia, 'radars': {}, 'l1_ref': None}

    quiet = io.StringIO()
    with redirect_stdout(quiet):
        analyzer_l1 = make_analyzer(famiglia, min_buy_override=None)
        l1_trades = simulate_gate(analyzer_l1, close_full, high_full, low_full,
                                   hist.index, test_dates, require_macd=False)
        out['l1_ref'] = l1_trades

        for radar_type in radar_types:
            defaults = RADAR_DEFAULTS[radar_type]
            analyzer_r = ETFTechnicalAnalyzer(famiglia=famiglia)
            trades = simulate_radar(analyzer_r, close_full, high_full, low_full,
                                     hist.index, test_dates, radar_type,
                                     defaults['lookback'], defaults['min_r2'])
            out['radars'][radar_type] = trades

    return out, None


def compute_overlap(radar_trades, l1_trades, window_days=OVERLAP_WINDOW_DAYS):
    """Per ogni ingresso radar sul ticker, c'e' anche un ingresso L1 reale entro
    +/- window_days giorni sullo STESSO ticker? Ritorna (n_overlap, n_unique)."""
    if not radar_trades:
        return 0, 0
    l1_dates = [datetime.strptime(t['entry_date'], '%Y-%m-%d').date() for t in l1_trades]
    n_overlap = 0
    for rt in radar_trades:
        rd = datetime.strptime(rt['entry_date'], '%Y-%m-%d').date()
        if any(abs((rd - ld).days) <= window_days for ld in l1_dates):
            n_overlap += 1
    return n_overlap, len(radar_trades) - n_overlap


def split_in_out(per_ticker_trades):
    """per_ticker_trades: list of (ticker, famiglia, trades). Ritorna (results_in, results_out)
    nel formato annidato richiesto da aggregate() di backtest_l1.py."""
    results_in, results_out = [], []
    for ticker, famiglia, trades in per_ticker_trades:
        in_trades = [t for t in trades
                     if TRAIN_START <= datetime.strptime(t['entry_date'], '%Y-%m-%d').date() < TRAIN_END]
        out_trades = [t for t in trades
                      if TRAIN_END <= datetime.strptime(t['entry_date'], '%Y-%m-%d').date() < TEST_END]
        if in_trades:
            results_in.append({'ticker': ticker, 'famiglia': famiglia,
                                'variants': {'x': {'n_trades': len(in_trades), 'trades': in_trades}}})
        if out_trades:
            results_out.append({'ticker': ticker, 'famiglia': famiglia,
                                 'variants': {'x': {'n_trades': len(out_trades), 'trades': out_trades}}})
    return results_in, results_out


def report_window(label, results, position_size):
    agg = aggregate(results, 'x', position_size)
    extra = extra_metrics(agg)
    print(f"  {label}: N={agg['n_trades_closed']:3d} (aperti: {agg['n_trades_open']}) "
          f"WR={agg['win_rate_pct']}% PF={extra['profit_factor']} "
          f"MaxDD={extra['max_drawdown_pct']}% "
          f"Rend.medio netto/trade={agg['avg_net_pct_gain']}% "
          f"P&L netto totale ({position_size:.0f}EUR/trade)={agg['total_net_eur']}EUR")
    return agg, extra


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--radar', default='approach,bounce',
                         help='radar da testare, separati da virgola (approach, bounce)')
    parser.add_argument('--start', default=TRAIN_START.isoformat(),
                         help='YYYY-MM-DD, default = inizio finestra IN (2023-08-05)')
    parser.add_argument('--days', type=int, default=1300, help='giorni di storico da leggere per ticker')
    parser.add_argument('--position-sizes', default='5000,10000')
    parser.add_argument('--frozen-batch', default=DEFAULT_FROZEN_BATCH)
    parser.add_argument('--overlap-window', type=int, default=OVERLAP_WINDOW_DAYS)
    parser.add_argument('--limit', type=int, default=None,
                         help='testa solo i primi N ticker dell\'universo (sanity check veloce)')
    args = parser.parse_args()

    radar_types = [r.strip() for r in args.radar.split(',') if r.strip()]
    for r in radar_types:
        if r not in RADAR_DEFAULTS:
            raise SystemExit(f"Radar sconosciuto: {r} (validi: {list(RADAR_DEFAULTS)})")
    position_sizes = [float(x) for x in args.position_sizes.split(',')]
    start_date = datetime.strptime(args.start, '%Y-%m-%d').date()

    print(f"BACKTEST RADAR — {radar_types} vs riferimento L1 reale (produzione, live YAML)")
    print(f"Split: IN {TRAIN_START}->{TRAIN_END}  OUT {TRAIN_END}->{TEST_END}")
    print(f"Golden Dataset batch: {args.frozen_batch}  |  Overlap window: +/-{args.overlap_window}gg")
    print(f"Costi Directa: {DIRECTA_FEE_BUY}+{DIRECTA_FEE_SELL}EUR  |  Tax: {TAX_RATE:.0%}")
    print("=" * 78)

    universe = load_universe()
    if args.limit:
        universe = universe[:args.limit]
    print(f"ETF nell'universo target: {len(universe)}\n")
    fetcher = FrozenDataFetcher(args.frozen_batch)

    per_ticker_radar = {r: [] for r in radar_types}
    per_ticker_l1 = []
    overlap_counts = {r: [0, 0] for r in radar_types}  # [n_overlap, n_unique]
    errors = []
    t0 = time.time()

    for i, item in enumerate(universe, 1):
        ticker, famiglia = item['ticker'], item['famiglia']
        try:
            res, err = backtest_ticker(fetcher, ticker, famiglia, start_date, args.days, radar_types)
        except Exception as e:
            res, err = None, str(e)
        if err:
            errors.append({'ticker': ticker, 'error': err})
            continue

        per_ticker_l1.append((ticker, famiglia, res['l1_ref']))
        for r in radar_types:
            trades = res['radars'][r]
            per_ticker_radar[r].append((ticker, famiglia, trades))
            ov, uniq = compute_overlap(trades, res['l1_ref'], args.overlap_window)
            overlap_counts[r][0] += ov
            overlap_counts[r][1] += uniq

        if i % 20 == 0 or i == len(universe):
            elapsed = time.time() - t0
            print(f"  [{i}/{len(universe)}] processati — {elapsed:.0f}s trascorsi")

    print(f"\nETF testati: {len(per_ticker_l1)}  |  skip: {len(errors)}\n")
    print("=" * 78)

    all_results = {}
    for size in position_sizes:
        print(f"\n{'=' * 78}\nPosition size: {size:.0f}EUR/trade\n{'=' * 78}")

        print("\n--- Riferimento: L1 reale (produzione) ---")
        results_in, results_out = split_in_out(per_ticker_l1)
        agg_in, extra_in = report_window('IN ', results_in, size)
        agg_out, extra_out = report_window('OUT', results_out, size)
        all_results.setdefault(str(size), {})['l1_ref'] = {
            'in': {**agg_in, **extra_in}, 'out': {**agg_out, **extra_out}}

        for r in radar_types:
            print(f"\n--- Radar: {r} ---")
            results_in, results_out = split_in_out(per_ticker_radar[r])
            agg_in, extra_in = report_window('IN ', results_in, size)
            agg_out, extra_out = report_window('OUT', results_out, size)
            all_results[str(size)][r] = {
                'in': {**agg_in, **extra_in}, 'out': {**agg_out, **extra_out}}

    print(f"\n{'=' * 78}\nOVERLAP con L1 reale (stesso ticker, +/-{args.overlap_window}gg dall'ingresso)\n{'=' * 78}")
    for r in radar_types:
        ov, uniq = overlap_counts[r]
        total = ov + uniq
        pct = round(100 * ov / total, 1) if total else None
        print(f"  {r:10s}: {ov}/{total} ingressi ({pct}%) coincidono con un ingresso L1 reale nella finestra — "
              f"{uniq} opportunita' uniche non catturate dal gate 7/7")

    print(f"\n{'=' * 78}\nRIFERIMENTO L0 (non risimulato qui — meccanismo diverso, mean-reversion "
          f"su drawdown — numeri gia' certificati in CLAUDE.md, CANDIDATE_MODEL_L0_20260808):\n"
          f"  IN  N=152 PF=3.38 WR=44.1%  |  OUT N=62 PF=4.84 WR=51.6%\n{'=' * 78}")

    out_path = 'data/backtest_radars_result.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            'radar_types': radar_types, 'position_sizes': position_sizes,
            'overlap_window_days': args.overlap_window,
            'overlap_counts': {r: {'overlap': overlap_counts[r][0], 'unique': overlap_counts[r][1]}
                                for r in radar_types},
            'results_by_size': all_results,
            'errors': errors,
        }, f, indent=2, ensure_ascii=False)
    print(f"\nRisultato completo salvato in {out_path}")


if __name__ == '__main__':
    main()
