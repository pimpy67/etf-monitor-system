"""
backtest_l0_relaxed_conditions.py — Follow-up al confronto con i sistemi di riferimento
(vedi backtest_reference_systems.py): RSI2 Mean Reversion e' risultato l'unico sistema
di riferimento stabile IS->OOS, con volume molto piu' alto del nostro L0 (2685/1792 trade
contro 152/62). Domanda: allentare le condizioni di ingresso L0 aumenta il volume senza
distruggere il Profit Factor?

Riusa SEMPRE la logica reale, mai duplicata:
  - Punto 0: find_entries_regime() di optimize_l0_regime.py (invariato) per contare la
    distribuzione FAST/SLOW/PRAGMATIC con i parametri CANDIDATE_MODEL_L0.
  - Punto 1: simulate_rsi2() di backtest_reference_systems.py (invariato), universo
    ristretto a equity_sviluppati (load_universe() di backtest_l0_v2.py, whitelist-aware).
  - Punto 2: PRAGMATIC relaxed — chiama suggest_level_0() REALE con l0_regime disabilitato
    (analyzer.p['l0_regime'] = {}, stesso knob gia' usato da find_entries_regime per
    l'override, qui azzerato per isolare il percorso pragmatico) cosi' cond1-4 sono SEMPRE
    calcolati dalla funzione vera; poi ricombina i booleani gia' esposti nel result dict
    (distance_from_peak, rsi_oversold, divergence, rsi_recovery, micro_breakout,
    regime_ok_for_l0, kill_switch) per simulare varianti a 2-3 condizioni invece di 4.
    Nessuna reimplementazione di RSI/drawdown/divergenza: solo ricombinazione di booleani
    gia' calcolati dal codice reale.
  - Punti 3/4: run_sweep() di optimize_l0_regime.py (invariato), griglia estesa oltre il
    range gia' esplorato l'08/08.

Uso:
  python3 backtest_l0_relaxed_conditions.py --smoke   # sanity check veloce
  python3 backtest_l0_relaxed_conditions.py --all      # tutti i 5 blocchi
"""
import sys
sys.path.insert(0, '/app')

import argparse
import io
import json
import time
from contextlib import redirect_stdout
from datetime import datetime

from technical_analysis import ETFTechnicalAnalyzer
from backtest_l0_v2 import DEFAULT_FROZEN_BATCH, load_universe as load_universe_whitelisted
from optimize_l0 import (
    load_and_precompute, simulate_exit_for_tp, aggregate as aggregate_l0,
    TRAIN_START, TRAIN_END, TEST_END,
)
from optimize_l0_regime import find_entries_regime, run_sweep as run_regime_sweep

# CANDIDATE_MODEL_L0 (certificato 2026-08-08, vedi CLAUDE.md "Grid Search L0")
CANDIDATE_REGIME = {
    'regime_min_days_below_sma200': 5,
    'dd_min_duration_days': 4,
    'dd_threshold_atr_multiple': 3.0,  # non-gating, invariato
    'flash_crash_zscore_threshold': 4.0,  # invariato per il punto 0/2 (non e' oggetto di questo test)
    'flash_crash_window_days': 3,
}
CANDIDATE_TP = 0.16

SMOKE_TICKERS_HINT = 12  # limita l'universo whitelisted ai primi N ticker per lo smoke test


# ─────────────────── Punto 0: distribuzione FAST/SLOW/PRAGMATIC ────────────────────

def point0_entry_mode_distribution(items, out=None):
    print("\n" + "=" * 90)
    print("PUNTO 0 — Distribuzione FAST/SLOW/PRAGMATIC con parametri CANDIDATE_MODEL_L0")
    print("=" * 90)

    modes_in = {'FAST': 0, 'SLOW': 0, 'PRAGMATIC_4CONDITIONS': 0}
    modes_out = {'FAST': 0, 'SLOW': 0, 'PRAGMATIC_4CONDITIONS': 0}
    entries_in_by_ticker, entries_out_by_ticker = {}, {}

    for item in items:
        e_in = find_entries_regime(item, CANDIDATE_REGIME, TRAIN_START, TRAIN_END)
        e_out = find_entries_regime(item, CANDIDATE_REGIME, TRAIN_END, TEST_END)
        entries_in_by_ticker[item['ticker']] = e_in
        entries_out_by_ticker[item['ticker']] = e_out
        for e in e_in:
            m = e.get('entry_mode') or 'PRAGMATIC_4CONDITIONS'
            modes_in[m] = modes_in.get(m, 0) + 1
        for e in e_out:
            m = e.get('entry_mode') or 'PRAGMATIC_4CONDITIONS'
            modes_out[m] = modes_out.get(m, 0) + 1

    print(f"IN-SAMPLE  : {modes_in}  (totale {sum(modes_in.values())})")
    print(f"OUT-OF-SAMPLE: {modes_out}  (totale {sum(modes_out.values())})")

    if out is not None:
        out['point0'] = {'modes_in': modes_in, 'modes_out': modes_out}
    return entries_in_by_ticker, entries_out_by_ticker


# ─────────────────── Punto 1: RSI2 ristretto a equity_sviluppati ───────────────────

def point1_rsi2_equity_sviluppati(items, position_sizes, out=None):
    print("\n" + "=" * 90)
    print("PUNTO 1 — RSI2 Mean Reversion ristretto a equity_sviluppati (confronto equo)")
    print("=" * 90)
    # Import locale per non forzare la dipendenza se lo script gira senza --all
    from backtest_reference_systems import simulate_rsi2

    def run_window(start_date, end_date):
        all_trades = []
        for item in items:
            trades = simulate_rsi2(item['close_full'], item['hist_index'],
                                    [d for d in item['hist_index'] if start_date <= d.date() < end_date])
            all_trades.extend(trades)
        return all_trades

    trades_in = run_window(TRAIN_START, TRAIN_END)
    trades_out = run_window(TRAIN_END, TEST_END)

    result = {}
    for size in position_sizes:
        # aggregate_l0 (optimize_l0.aggregate) prende trade grezzi e applica costi/tasse da se':
        agg_in = aggregate_l0(trades_in, size)
        agg_out = aggregate_l0(trades_out, size)
        print(f"  Size {size:.0f}EUR | IN: N={agg_in['n_trades_closed']:4d} "
              f"WR={agg_in['win_rate_pct']}% PF={agg_in['profit_factor']} avg={agg_in['avg_net_pct_gain']}% "
              f"| OUT: N={agg_out['n_trades_closed']:4d} WR={agg_out['win_rate_pct']}% "
              f"PF={agg_out['profit_factor']} avg={agg_out['avg_net_pct_gain']}%")
        result[str(size)] = {'in': agg_in, 'out': agg_out}

    if out is not None:
        out['point1_rsi2_equity_sviluppati'] = result
    return result


# ─────────────────── Punto 2: PRAGMATIC relaxed (2-3 condizioni) ───────────────────

CONDITION_SETS = {
    'baseline_4cond': {'cond1', 'cond2', 'cond3', 'cond4'},   # = PRAGMATIC_4CONDITIONS originale
    'drop_divergence': {'cond1', 'cond2', 'cond4'},           # drawdown + RSI oversold + recovery
    'drop_recovery': {'cond1', 'cond2', 'cond3'},             # drawdown + RSI oversold + divergenza
    'core_2cond': {'cond1', 'cond2'},                         # solo drawdown + RSI oversold (stile RSI2)
}


def scan_pragmatic_relaxed(item, condition_set, start_date, end_date):
    """Isola il percorso PRAGMATIC disabilitando l0_regime (FAST/SLOW), cosi'
    suggest_level_0() calcola SEMPRE cond1-4 (mai un return anticipato). Poi ricombina
    i booleani gia' esposti nel result per il condition_set richiesto. 'Trattato come
    sistema standalone' (skip-ahead dopo ogni ingresso via simulazione uscita reale),
    stesso schema di find_entries/find_entries_regime."""
    analyzer = ETFTechnicalAnalyzer(famiglia='equity_sviluppati')
    analyzer.p = dict(analyzer.p)
    analyzer.p['l0_regime'] = {}  # forza regime_check_enabled=False -> sempre PRAGMATIC

    close_full = item['close_full']
    high_full = item['high_full']
    low_full = item['low_full']
    hist_index = item['hist_index']
    precomputed = item['precomputed']
    test_positions = [hist_index.get_loc(d) for d in hist_index if start_date <= d.date() < end_date]

    entries = []
    quiet = io.StringIO()
    i = 0
    with redirect_stdout(quiet):
        while i < len(test_positions):
            pos = test_positions[i]
            close_slice = close_full.iloc[:pos + 1]
            high_slice = high_full.iloc[:pos + 1] if high_full is not None else None
            low_slice = low_full.iloc[:pos + 1] if low_full is not None else None
            precomputed_slice = {k: v.iloc[:pos + 1] for k, v in precomputed.items()}

            result = analyzer.suggest_level_0(close_slice, high_slice, low_slice,
                                               current_level=3, precomputed=precomputed_slice)
            dist_peak = result.get('distance_from_peak')
            dd_threshold = analyzer.p.get('l0_entry', {}).get('dd_threshold', 0.065)
            cond1 = dist_peak is not None and dist_peak <= -(dd_threshold * 100)
            cond2 = bool(result.get('rsi_oversold'))
            cond3 = bool(result.get('divergence'))
            cond4 = bool(result.get('rsi_recovery')) or bool(result.get('micro_breakout'))
            regime_ok = bool(result.get('regime_ok_for_l0'))
            kill_switch = bool(result.get('kill_switch'))

            flags = {'cond1': cond1, 'cond2': cond2, 'cond3': cond3, 'cond4': cond4}
            entry_ok = all(flags[c] for c in condition_set) and regime_ok and not kill_switch

            if not entry_ok:
                i += 1
                continue

            entry_price = float(close_slice.iloc[-1])
            entries.append({'entry_date': hist_index[pos].date().isoformat(),
                             'entry_price': entry_price, 'entry_pos': pos})

            # Trova dove uscirebbe (stesso schema find_entries: solo per sapere da dove
            # riprendere la scansione del prossimo ingresso indipendente).
            exit_pos = None
            for future_pos in range(pos + 1, min(pos + 366, len(close_full))):
                future_price = float(close_full.iloc[future_pos])
                sl_data = analyzer.calculate_sl_suggerito_l0(entry_price, future_price)
                sl = sl_data.get('sl_suggerito')
                tp_data = analyzer.calculate_tp_suggerito_l0(entry_price, future_price)
                if (sl is not None and future_price <= sl) or tp_data.get('trigger'):
                    exit_pos = future_pos
                    break

            resume_pos = exit_pos if exit_pos is not None else min(pos + 365, len(close_full) - 1)
            while i < len(test_positions) and test_positions[i] <= resume_pos:
                i += 1

    return entries


def point2_pragmatic_relaxed(items, position_sizes, out=None):
    print("\n" + "=" * 90)
    print("PUNTO 2 — PRAGMATIC relaxed (drop 1-2 delle 4 condizioni), TP fisso 16% (CANDIDATE)")
    print("=" * 90)

    result = {}
    for label, cond_set in CONDITION_SETS.items():
        entries_in_by_ticker, entries_out_by_ticker = {}, {}
        for item in items:
            entries_in_by_ticker[item['ticker']] = scan_pragmatic_relaxed(
                item, cond_set, TRAIN_START, TRAIN_END)
            entries_out_by_ticker[item['ticker']] = scan_pragmatic_relaxed(
                item, cond_set, TRAIN_END, TEST_END)

        trades_in, trades_out = [], []
        for item in items:
            for e in entries_in_by_ticker[item['ticker']]:
                trades_in.append(simulate_exit_for_tp(item, e, CANDIDATE_TP))
            for e in entries_out_by_ticker[item['ticker']]:
                trades_out.append(simulate_exit_for_tp(item, e, CANDIDATE_TP))

        result[label] = {'conditions': sorted(cond_set)}
        for size in position_sizes:
            agg_in = aggregate_l0(trades_in, size)
            agg_out = aggregate_l0(trades_out, size)
            print(f"  [{label:16s} {sorted(cond_set)}] Size {size:.0f}EUR | "
                  f"IN: N={agg_in['n_trades_closed']:4d} WR={agg_in['win_rate_pct']}% "
                  f"PF={agg_in['profit_factor']} avg={agg_in['avg_net_pct_gain']}% "
                  f"| OUT: N={agg_out['n_trades_closed']:4d} WR={agg_out['win_rate_pct']}% "
                  f"PF={agg_out['profit_factor']} avg={agg_out['avg_net_pct_gain']}%")
            result[label][str(size)] = {'in': agg_in, 'out': agg_out}

    if out is not None:
        out['point2_pragmatic_relaxed'] = result
    return result


# ─────────────────── Punti 3/4: SLOW/FAST oltre il range gia' esplorato ────────────

def point3_slow_extended(freeze_batch, out_path_hint):
    print("\n" + "=" * 90)
    print("PUNTO 3 — SLOW path, griglia estesa oltre l'optimum (5,4) gia' trovato l'08/08")
    print("=" * 90)
    grid = {
        'regime_min_days_below_sma200': [2, 3, 4, 5],
        'dd_min_duration_days': [2, 3, 4],
    }
    out_path = f'data/{out_path_hint}_slow_extended.json'
    run_regime_sweep('SLOW_EXTENDED', grid, freeze_batch, out_path, tp_grid=(0.16,))


def point4_fast_extended(freeze_batch, out_path_hint):
    print("\n" + "=" * 90)
    print("PUNTO 4 — FAST path, zscore piu' permissivo del range gia' esplorato (3.0-4.5)")
    print("=" * 90)
    grid = {
        'flash_crash_window_days': [2, 3, 4],
        'flash_crash_zscore_threshold': [1.5, 2.0, 2.5, 3.0],
    }
    out_path = f'data/{out_path_hint}_fast_extended.json'
    run_regime_sweep('FAST_EXTENDED', grid, freeze_batch, out_path, tp_grid=(0.16,))


# ────────────────────────────────── Main ───────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--point0', action='store_true')
    parser.add_argument('--point1', action='store_true')
    parser.add_argument('--point2', action='store_true')
    parser.add_argument('--point3', action='store_true')
    parser.add_argument('--point4', action='store_true')
    parser.add_argument('--frozen-batch', default=DEFAULT_FROZEN_BATCH)
    parser.add_argument('--position-sizes', default='5000,10000')
    parser.add_argument('--out', default='data/backtest_l0_relaxed_result.json')
    args = parser.parse_args()
    position_sizes = [float(x) for x in args.position_sizes.split(',')]

    print("=" * 90)
    print("BACKTEST L0 — Condizioni allentate (follow-up al confronto con sistemi di riferimento)")
    print(f"Golden Dataset batch: {args.frozen_batch}")
    print(f"IS: {TRAIN_START} -> {TRAIN_END}   OOS: {TRAIN_END} -> {TEST_END}")
    print("=" * 90)

    t_start = time.time()
    out_report = {'generated_at': datetime.now().isoformat()}

    items = load_and_precompute(args.frozen_batch)
    if args.smoke:
        items = items[:SMOKE_TICKERS_HINT]
        print(f"[SMOKE TEST] {len(items)} ticker: {[it['ticker'] for it in items]}\n")

    run_p0 = args.all or args.point0 or args.smoke
    run_p1 = args.all or args.point1 or args.smoke
    run_p2 = args.all or args.point2 or args.smoke
    run_p3 = args.all or args.point3
    run_p4 = args.all or args.point4

    if run_p0:
        point0_entry_mode_distribution(items, out=out_report)
    if run_p1:
        point1_rsi2_equity_sviluppati(items, position_sizes, out=out_report)
    if run_p2:
        point2_pragmatic_relaxed(items, position_sizes, out=out_report)
    if run_p3 and not args.smoke:
        point3_slow_extended(args.frozen_batch, 'backtest_l0_relaxed')
    if run_p4 and not args.smoke:
        point4_fast_extended(args.frozen_batch, 'backtest_l0_relaxed')

    with open(args.out, 'w') as f:
        json.dump(out_report, f, indent=2, default=str)
    print(f"\nSalvato: {args.out}")
    print(f"Tempo totale: {(time.time() - t_start) / 60:.1f} minuti")


if __name__ == '__main__':
    main()
