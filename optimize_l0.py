"""
optimize_l0.py — Grid Search per L0 su equity_sviluppati (unica famiglia whitelisted),
sul Golden Dataset congelato, con split In-Sample/Out-of-Sample.

Motore: riusa suggest_level_0()/calculate_sl_suggerito_l0()/calculate_tp_suggerito_l0()
reali (vedi backtest_l0_v2.py) — nessuna logica duplicata.

Design per i tempi (universo piu' piccolo di L1 ma comunque non banale, 107 ticker):
- RSI/EMA20/SMA50 precalcolati UNA VOLTA per ticker (stesso pattern di suggest_level(),
  vedi CLAUDE.md "Grid Search smart_6_macd"), passati a suggest_level_0() via
  'precomputed' invece di essere ricalcolati ogni giorno.
- dd_threshold / rsi_max / recovery_min_pct sono la parte "costosa" (cambiano QUALI
  giorni sono validi per un ingresso, serve rifare la scansione completa per ognuno).
- l0_take_profit_pct e' DISACCOPPIATO dalla scansione ingressi: non cambia mai *quali*
  trade partono (l'ingresso non dipende dal TP), solo *dove* escono. Per ogni combo
  (dd,rsi,recovery) si scansiona UNA VOLTA la lista di ingressi, poi per ogni valore di
  TP si ri-simula solo l'uscita da quegli ingressi (walk breve, non un nuovo scan
  completo). Approssimazione nota: un'uscita anticipata con TP piu' stretto potrebbe in
  teoria liberare spazio per un ingresso successivo che con TP piu' largo non ci sarebbe
  stato — effetto atteso piccolo dato che L0 e' un segnale raro (in media <2 trade per
  ticker in 3 anni), esplicitamente accettato per il primo giro coarse-to-fine.

Uso:
  python3 optimize_l0.py --validate    # cross-check obbligatorio prima di tutto
  python3 optimize_l0.py --sweep       # griglia completa
"""
import sys
sys.path.insert(0, '/app')

import argparse
import io
import itertools
import json
import random
import time
from contextlib import redirect_stdout
from datetime import datetime

import pandas as pd

from technical_analysis import ETFTechnicalAnalyzer
from database import PriceDatabase
from backtest_l0_v2 import load_universe, DEFAULT_FROZEN_BATCH, apply_costs_and_tax

TRAIN_START = datetime(2023, 8, 5).date()
TRAIN_END = datetime(2025, 8, 5).date()
TEST_END = datetime(2026, 8, 5).date()

MIN_TRADES_REPORT = 20  # L0 e' un segnale raro — soglia piu' bassa che per L1 (era 30)

BASELINE = {'dd_threshold': 0.065, 'rsi_max': 45, 'recovery_min_pct': 0.015,
            'l0_take_profit_pct': 0.16}


def precompute_ticker(analyzer, close_full):
    return {
        'rsi': analyzer._rsi(close_full),
        'ema20': analyzer._ema(close_full, analyzer.ema20_period),
        'sma50': analyzer._sma(close_full, 50),
    }


def load_and_precompute(freeze_batch, min_rows=220):
    db = PriceDatabase()
    universe = load_universe()
    items = []
    skipped = []
    for u in universe:
        ticker = u['ticker']
        hist = db.get_frozen_ohlcv(ticker, freeze_batch)
        if hist.empty or len(hist) < min_rows:
            skipped.append(ticker)
            continue
        has_ohlc = all(c in hist.columns for c in ['Open', 'High', 'Low'])
        close_full = hist['Close'].astype(float)
        high_full = hist['High'].astype(float) if has_ohlc else None
        low_full = hist['Low'].astype(float) if has_ohlc else None
        analyzer_tmp = ETFTechnicalAnalyzer(famiglia='equity_sviluppati')
        precomputed = precompute_ticker(analyzer_tmp, close_full)
        items.append({
            'ticker': ticker, 'close_full': close_full, 'high_full': high_full,
            'low_full': low_full, 'hist_index': hist.index, 'precomputed': precomputed,
        })
    print(f"Caricati: {len(items)} ticker su {len(universe)} nell'universo, "
          f"{len(skipped)} scartati (storico <{min_rows}gg)")
    return items


def find_entries(item, dd_threshold, rsi_max, recovery_min_pct, start_date, end_date):
    """Scansione ingressi (indipendente dal TP). Ritorna lista di dict con
    entry_date/entry_price/entry_pos (posizione nell'indice, per la fase di uscita)."""
    analyzer = ETFTechnicalAnalyzer(famiglia='equity_sviluppati')
    analyzer.p = dict(analyzer.p)
    analyzer.p['l0_entry'] = dict(analyzer.p.get('l0_entry', {}))
    analyzer.p['l0_entry']['dd_threshold'] = dd_threshold
    analyzer.p['l0_entry']['rsi_max'] = rsi_max
    analyzer.p['l0_entry']['recovery_min_pct'] = recovery_min_pct

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
                             'entry_price': entry_price, 'entry_pos': pos})

            # Trova dove uscirebbe con il TP di baseline — serve solo a sapere da quando
            # riprendere a cercare il PROSSIMO ingresso (il vero risultato per ogni valore
            # di TP si calcola dopo in simulate_exit_for_tp). Tetto largo di 365gg.
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


def simulate_exit_for_tp(item, entry, tp_pct):
    """Rigioca SOLO l'uscita (SL fisso + TP=tp_pct) da un ingresso gia' trovato — walk
    breve, non un nuovo scan degli ingressi."""
    analyzer = ETFTechnicalAnalyzer(famiglia='equity_sviluppati')
    analyzer.p = dict(analyzer.p)
    analyzer.p['l0_take_profit_pct'] = tp_pct

    close_full = item['close_full']
    hist_index = item['hist_index']
    entry_pos = entry['entry_pos']
    entry_price = entry['entry_price']

    for future_pos in range(entry_pos + 1, len(close_full)):
        future_price = float(close_full.iloc[future_pos])
        sl_data = analyzer.calculate_sl_suggerito_l0(entry_price, future_price)
        sl = sl_data.get('sl_suggerito')
        tp_data = analyzer.calculate_tp_suggerito_l0(entry_price, future_price)
        sl_hit = sl is not None and future_price <= sl
        tp_hit = bool(tp_data.get('trigger'))
        if sl_hit or tp_hit:
            gross_pct = round((future_price / entry_price - 1) * 100, 3)
            return {
                'entry_date': entry['entry_date'], 'entry_price': entry_price,
                'exit_date': hist_index[future_pos].date().isoformat(), 'exit_price': future_price,
                'status': 'closed', 'gross_pct_gain': gross_pct,
                'exit_reason': 'SL' if sl_hit else 'TP',
            }

    last_price = float(close_full.iloc[-1])
    gross_pct = round((last_price / entry_price - 1) * 100, 3)
    return {
        'entry_date': entry['entry_date'], 'entry_price': entry_price,
        'exit_date': None, 'exit_price': last_price,
        'status': 'open', 'gross_pct_gain': gross_pct, 'exit_reason': None,
    }


def aggregate(all_trades, position_size):
    trades = [apply_costs_and_tax(dict(t), position_size) for t in all_trades]
    closed = [t for t in trades if t['status'] == 'closed']
    net_gains = [t['net_pct_gain'] for t in closed]
    wins = [g for g in net_gains if g > 0]
    losses = [g for g in net_gains if g <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = round(gross_win / gross_loss, 2) if gross_loss > 0 else (
        float('inf') if gross_win > 0 else None)
    return {
        'n_trades_total': len(trades), 'n_trades_closed': len(closed),
        'win_rate_pct': round(100 * len(wins) / len(net_gains), 1) if net_gains else None,
        'avg_net_pct_gain': round(sum(net_gains) / len(net_gains), 2) if net_gains else None,
        'profit_factor': profit_factor,
        'total_net_eur': round(sum(t['net_gain_eur'] for t in closed), 2) if closed else 0,
    }


def validate_l0_fast_path(items, n_tickers=8, n_dates=40, seed=42):
    print("=" * 78)
    print(f"VALIDAZIONE INCROCIATA L0 — {n_tickers} ticker x fino a {n_dates} date ciascuno")
    print("=" * 78)
    rnd = random.Random(seed)
    sample = rnd.sample(items, min(n_tickers, len(items)))
    mismatches, total = 0, 0
    quiet = io.StringIO()

    for item in sample:
        close_full = item['close_full']
        high_full = item['high_full']
        low_full = item['low_full']
        hist_index = item['hist_index']
        precomputed = item['precomputed']
        positions = rnd.sample(range(220, len(close_full)), min(n_dates, len(close_full) - 220))

        for pos in positions:
            close_slice = close_full.iloc[:pos + 1]
            high_slice = high_full.iloc[:pos + 1] if high_full is not None else None
            low_slice = low_full.iloc[:pos + 1] if low_full is not None else None
            precomputed_slice = {k: v.iloc[:pos + 1] for k, v in precomputed.items()}

            analyzer = ETFTechnicalAnalyzer(famiglia='equity_sviluppati')
            with redirect_stdout(quiet):
                slow = analyzer.suggest_level_0(close_slice, high_slice, low_slice, current_level=3)
                fast = analyzer.suggest_level_0(close_slice, high_slice, low_slice, current_level=3,
                                                 precomputed=precomputed_slice)
            total += 1
            keys = ['l0_entry', 'rsi_oversold', 'divergence', 'rsi_recovery', 'micro_breakout']
            if any(slow.get(k) != fast.get(k) for k in keys):
                mismatches += 1
                print(f"  [MISMATCH] {item['ticker']} pos={pos}")
                print(f"    slow: {{{', '.join(f'{k}={slow.get(k)}' for k in keys)}}}")
                print(f"    fast: {{{', '.join(f'{k}={fast.get(k)}' for k in keys)}}}")

    print("-" * 78)
    print(f"Check totali: {total}  |  Mismatch: {mismatches}")
    ok = mismatches == 0 and total > 0
    print("PASS" if ok else "FAIL — NON procedere con lo sweep")
    return ok


def run_sweep(freeze_batch=DEFAULT_FROZEN_BATCH, out_path=None):
    items = load_and_precompute(freeze_batch)

    dd_grid = [0.05, 0.065, 0.08]
    rsi_grid = [40, 45, 50]
    recovery_grid = [0.010, 0.015, 0.020]
    tp_grid = [0.10, 0.12, 0.14, 0.16]

    entry_combos = list(itertools.product(dd_grid, rsi_grid, recovery_grid))
    print(f"Combinazioni ingresso (costose): {len(entry_combos)}  |  "
          f"valori TP (economici, per ognuna): {len(tp_grid)}")

    all_rows = []
    t0 = time.time()
    for dd, rsi_max, recovery in entry_combos:
        t_combo = time.time()

        entries_in_by_ticker = {}
        entries_out_by_ticker = {}
        for item in items:
            entries_in_by_ticker[item['ticker']] = find_entries(
                item, dd, rsi_max, recovery, TRAIN_START, TRAIN_END)
            entries_out_by_ticker[item['ticker']] = find_entries(
                item, dd, rsi_max, recovery, TRAIN_END, TEST_END)

        for tp in tp_grid:
            trades_in, trades_out = [], []
            for item in items:
                for e in entries_in_by_ticker[item['ticker']]:
                    trades_in.append(simulate_exit_for_tp(item, e, tp))
                for e in entries_out_by_ticker[item['ticker']]:
                    trades_out.append(simulate_exit_for_tp(item, e, tp))

            agg_in = aggregate(trades_in, 10000.0)
            agg_out = aggregate(trades_out, 10000.0)
            row = {
                'dd_threshold': dd, 'rsi_max': rsi_max, 'recovery_min_pct': recovery, 'tp': tp,
                'n_in': agg_in['n_trades_closed'], 'wr_in': agg_in['win_rate_pct'],
                'pf_in': agg_in['profit_factor'], 'avg_in': agg_in['avg_net_pct_gain'],
                'n_out': agg_out['n_trades_closed'], 'wr_out': agg_out['win_rate_pct'],
                'pf_out': agg_out['profit_factor'], 'avg_out': agg_out['avg_net_pct_gain'],
            }
            all_rows.append(row)
            print(f"  dd={dd:.3f} rsi={rsi_max} rec={recovery:.3f} tp={tp:.2f} | "
                  f"IN: N={row['n_in']:3d} WR={row['wr_in']} PF={row['pf_in']} | "
                  f"OUT: N={row['n_out']:3d} WR={row['wr_out']} PF={row['pf_out']}")

        elapsed = time.time() - t_combo
        print(f"  [combo dd={dd} rsi={rsi_max} rec={recovery} completata in {elapsed:.1f}s]\n")

    total_elapsed = time.time() - t0
    print(f"\nTempo totale sweep L0: {total_elapsed / 60:.1f} minuti "
          f"({len(all_rows)} combinazioni totali)")

    out_path = out_path or 'data/optimize_l0_result.json'
    with open(out_path, 'w') as f:
        json.dump({'rows': all_rows, 'total_seconds': total_elapsed,
                    'generated_at': datetime.now().isoformat()}, f, indent=2)
    print(f"Salvato: {out_path}")

    reportable = [r for r in all_rows if r['n_in'] >= MIN_TRADES_REPORT]
    reportable.sort(key=lambda r: (r['pf_in'] if r['pf_in'] not in (None, float('inf')) else -1),
                     reverse=True)
    print(f"\nTop combinazioni per Profit Factor In-Sample (N>={MIN_TRADES_REPORT}):")
    for r in reportable[:10]:
        print(f"  dd={r['dd_threshold']:.3f} rsi={r['rsi_max']} rec={r['recovery_min_pct']:.3f} "
              f"tp={r['tp']:.2f} | IN: N={r['n_in']} PF={r['pf_in']} WR={r['wr_in']}% "
              f"| OUT: N={r['n_out']} PF={r['pf_out']} WR={r['wr_out']}%")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--validate', action='store_true')
    parser.add_argument('--sweep', action='store_true')
    parser.add_argument('--frozen-batch', default=DEFAULT_FROZEN_BATCH)
    parser.add_argument('--out', default=None)
    args = parser.parse_args()

    if args.validate:
        items = load_and_precompute(args.frozen_batch)
        ok = validate_l0_fast_path(items)
        sys.exit(0 if ok else 1)

    if args.sweep:
        run_sweep(freeze_batch=args.frozen_batch, out_path=args.out)
        return

    print("Specifica --validate oppure --sweep.")


if __name__ == '__main__':
    main()
