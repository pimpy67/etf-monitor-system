"""
optimize_l0_regime.py — Grid Search sui parametri di l0_regime (percorsi FAST/SLOW) per
equity_sviluppati, sul Golden Dataset congelato, split In-Sample/Out-of-Sample.

Motivazione: lo sweep precedente (optimize_l0.py, 2026-08-07) ha dimostrato che le 4
condizioni PRAGMATIC (dd_threshold/rsi_max/recovery_min_pct) sono invarianti sui risultati
per equity_sviluppati — gli ingressi scattano prima sui percorsi FAST/SLOW (l0_regime), che
in quello sweep erano tenuti fissi al baseline YAML. Questo script inverte il focus: fissa
PRAGMATIC al baseline e varia i parametri di l0_regime.

Solo 4 parametri di l0_regime governano davvero l'ingresso nel codice attuale
(technical_analysis.py::_analyze_l0_fast_path/_analyze_l0_slow_path):
  FAST: flash_crash_window_days, flash_crash_zscore_threshold
  SLOW: regime_min_days_below_sma200, dd_min_duration_days (nonostante il nome, e' una
        soglia di drawdown in %, non un conteggio di giorni: viene letta e divisa per 100)
Esclusi perche' MAI letti nel codice (parametri morti nello YAML):
  capitulation_volume_multiplier, reclaim_ema_fast_period, reclaim_ema_slow_period
Escluso perche' non gating (solo un campo diagnostico, non entra nella decisione booleana):
  dd_threshold_atr_multiple (usato solo per 'drawdown_normalized', mai per slow_path_valid)

Due sweep separati per tenere i tempi gestibili (stesso costo per combinazione dello sweep
precedente, ~6-7 min/combo su singolo vCPU):
  --sweep-fast : flash_crash_window_days x flash_crash_zscore_threshold (SLOW+PRAGMATIC baseline)
  --sweep-slow : regime_min_days_below_sma200 x dd_min_duration_days (FAST+PRAGMATIC baseline)

Uso:
  python3 optimize_l0_regime.py --sweep-fast
  python3 optimize_l0_regime.py --sweep-slow
"""
import sys
sys.path.insert(0, '/app')

import argparse
import io
import itertools
import json
import time
from contextlib import redirect_stdout
from datetime import datetime

from technical_analysis import ETFTechnicalAnalyzer
from backtest_l0_v2 import DEFAULT_FROZEN_BATCH, apply_costs_and_tax
from optimize_l0 import load_and_precompute, simulate_exit_for_tp, aggregate, TRAIN_START, TRAIN_END, TEST_END

MIN_TRADES_REPORT = 20

BASELINE_REGIME = {
    'regime_min_days_below_sma200': 10,
    'dd_min_duration_days': 4,
    'dd_threshold_atr_multiple': 3.0,  # non-gating, tenuto solo per completezza del dict
    'flash_crash_zscore_threshold': 4.0,
    'flash_crash_window_days': 3,
}


def find_entries_regime(item, regime_overrides, start_date, end_date):
    """Come optimize_l0.find_entries, ma varia l0_regime invece di l0_entry.
    l0_entry resta al baseline YAML (gia' il default di ETFTechnicalAnalyzer)."""
    analyzer = ETFTechnicalAnalyzer(famiglia='equity_sviluppati')
    analyzer.p = dict(analyzer.p)
    analyzer.p['l0_regime'] = dict(analyzer.p.get('l0_regime', {}))
    analyzer.p['l0_regime'].update(regime_overrides)

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
            if not result.get('l0_entry'):
                i += 1
                continue

            entry_price = float(close_slice.iloc[-1])
            entries.append({'entry_date': hist_index[pos].date().isoformat(),
                             'entry_price': entry_price, 'entry_pos': pos,
                             'entry_mode': result.get('l0_regime_mode')})

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


def run_sweep(grid_name, param_grid, freeze_batch, out_path, tp_grid=(0.10, 0.12, 0.14, 0.16)):
    items = load_and_precompute(freeze_batch)

    keys = list(param_grid.keys())
    value_lists = [param_grid[k] for k in keys]
    combos = list(itertools.product(*value_lists))
    print(f"[{grid_name}] Combinazioni ingresso (costose): {len(combos)}  |  "
          f"valori TP (economici, per ognuna): {len(tp_grid)}")

    all_rows = []
    t0 = time.time()
    for combo_values in combos:
        overrides = dict(BASELINE_REGIME)
        overrides.update(dict(zip(keys, combo_values)))
        t_combo = time.time()

        entries_in_by_ticker = {}
        entries_out_by_ticker = {}
        for item in items:
            entries_in_by_ticker[item['ticker']] = find_entries_regime(
                item, overrides, TRAIN_START, TRAIN_END)
            entries_out_by_ticker[item['ticker']] = find_entries_regime(
                item, overrides, TRAIN_END, TEST_END)

        for tp in tp_grid:
            trades_in, trades_out = [], []
            modes_in = {'FAST': 0, 'SLOW': 0, 'PRAGMATIC_4CONDITIONS': 0}
            for item in items:
                for e in entries_in_by_ticker[item['ticker']]:
                    trades_in.append(simulate_exit_for_tp(item, e, tp))
                    modes_in[e.get('entry_mode', 'PRAGMATIC_4CONDITIONS')] = \
                        modes_in.get(e.get('entry_mode', 'PRAGMATIC_4CONDITIONS'), 0) + 1
                for e in entries_out_by_ticker[item['ticker']]:
                    trades_out.append(simulate_exit_for_tp(item, e, tp))

            agg_in = aggregate(trades_in, 10000.0)
            agg_out = aggregate(trades_out, 10000.0)
            row = {**{k: v for k, v in zip(keys, combo_values)}, 'tp': tp,
                   'n_in': agg_in['n_trades_closed'], 'wr_in': agg_in['win_rate_pct'],
                   'pf_in': agg_in['profit_factor'], 'avg_in': agg_in['avg_net_pct_gain'],
                   'n_out': agg_out['n_trades_closed'], 'wr_out': agg_out['win_rate_pct'],
                   'pf_out': agg_out['profit_factor'], 'avg_out': agg_out['avg_net_pct_gain'],
                   'entry_modes_in': modes_in}
            all_rows.append(row)
            combo_str = ' '.join(f'{k}={v}' for k, v in zip(keys, combo_values))
            print(f"  {combo_str} tp={tp:.2f} | IN: N={row['n_in']:3d} WR={row['wr_in']} "
                  f"PF={row['pf_in']} modes={modes_in} | OUT: N={row['n_out']:3d} "
                  f"WR={row['wr_out']} PF={row['pf_out']}")

        elapsed = time.time() - t_combo
        combo_str = ' '.join(f'{k}={v}' for k, v in zip(keys, combo_values))
        print(f"  [combo {combo_str} completata in {elapsed:.1f}s]\n")

    total_elapsed = time.time() - t0
    print(f"\nTempo totale sweep {grid_name}: {total_elapsed / 60:.1f} minuti "
          f"({len(all_rows)} righe totali)")

    with open(out_path, 'w') as f:
        json.dump({'grid_name': grid_name, 'rows': all_rows, 'total_seconds': total_elapsed,
                    'generated_at': datetime.now().isoformat()}, f, indent=2)
    print(f"Salvato: {out_path}")

    reportable = [r for r in all_rows if r['n_in'] >= MIN_TRADES_REPORT]
    reportable.sort(key=lambda r: (r['pf_in'] if r['pf_in'] not in (None, float('inf')) else -1),
                     reverse=True)
    print(f"\nTop combinazioni per Profit Factor In-Sample (N>={MIN_TRADES_REPORT}):")
    for r in reportable[:10]:
        combo_str = ' '.join(f'{k}={r[k]}' for k in keys)
        print(f"  {combo_str} tp={r['tp']:.2f} | IN: N={r['n_in']} PF={r['pf_in']} "
              f"WR={r['wr_in']}% | OUT: N={r['n_out']} PF={r['pf_out']} WR={r['wr_out']}%")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sweep-fast', action='store_true')
    parser.add_argument('--sweep-slow', action='store_true')
    parser.add_argument('--frozen-batch', default=DEFAULT_FROZEN_BATCH)
    parser.add_argument('--out', default=None)
    args = parser.parse_args()

    if args.sweep_fast:
        grid = {
            'flash_crash_window_days': [2, 3, 4],
            'flash_crash_zscore_threshold': [3.0, 3.5, 4.0, 4.5],
        }
        out_path = args.out or 'data/optimize_l0_regime_fast_result.json'
        run_sweep('FAST', grid, args.frozen_batch, out_path)
        return

    if args.sweep_slow:
        grid = {
            'regime_min_days_below_sma200': [5, 8, 10, 15],
            'dd_min_duration_days': [2, 3, 4, 6],
        }
        out_path = args.out or 'data/optimize_l0_regime_slow_result.json'
        run_sweep('SLOW', grid, args.frozen_batch, out_path)
        return

    print("Specifica --sweep-fast oppure --sweep-slow.")


if __name__ == '__main__':
    main()
