"""
optimize_hyperparameters.py — Grid Search / Sensitivity Analysis su smart_6_macd,
sul Golden Dataset congelato (etf_price_history_frozen), con split In-Sample/Out-of-Sample.

Motore di simulazione: RIUSA backtest_l1.py::simulate() e technical_analysis.py::suggest_level()
cosi' com'è — nessuna logica di ingresso/uscita duplicata. L'unica differenza rispetto a un
normale backtest_l1.py e' che gli indicatori (EMA/SMA/RSI/ADX/MACD/ATR) vengono calcolati UNA
VOLTA per ticker (vettorizzato sull'intera serie) invece che ricalcolati da suggest_level() a
ogni giorno del walk-forward — altrimenti una grid search di centinaia di combinazioni sarebbe
costata ore/giorni (O(n^2) per ticker per combinazione). Vedi CLAUDE.md per il dettaglio.

Cluster per volatilita' reale (sl_initial_pct dallo YAML), non per nome di famiglia:
  - difensivo:   bond_governativi, bond_corp_hy_em, settoriali_difensivi, real_estate_reit,
                 private_equity_buffer      (sl_initial_pct 2.5-4.0%)
  - core:        equity_sviluppati, oro_metalli_preziosi, mercati_emergenti,
                 settoriali_growth, metalli_industriali   (sl_initial_pct 5.0-6.0%)
  - speculativo: commodities, leva_single_stock, crypto_digital_assets (sl_initial_pct 7-12%)

Uso:
  python3 optimize_hyperparameters.py --validate            # step 1: cross-check obbligatorio
  python3 optimize_hyperparameters.py --pilot                # step 2: griglia piccola, per timing
  python3 optimize_hyperparameters.py --cluster core --pilot # solo un cluster
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
from backtest_l1 import load_universe, simulate, aggregate, DEFAULT_FROZEN_BATCH

CLUSTERS = {
    'difensivo': ['bond_governativi', 'bond_corp_hy_em', 'settoriali_difensivi',
                  'real_estate_reit', 'private_equity_buffer'],
    'core': ['equity_sviluppati', 'oro_metalli_preziosi', 'mercati_emergenti',
             'settoriali_growth', 'metalli_industriali'],
    'speculativo': ['commodities', 'leva_single_stock', 'crypto_digital_assets'],
}
FAMIGLIA_TO_CLUSTER = {f: c for c, fams in CLUSTERS.items() for f in fams}

TRAIN_START = datetime(2023, 8, 5).date()
TRAIN_END = datetime(2025, 8, 5).date()
TEST_END = datetime(2026, 8, 5).date()

MIN_TRADES_REPORT = 30


def _adx_series(analyzer, high_full, low_full, close_full):
    if high_full is not None and low_full is not None and len(high_full) == len(close_full):
        return analyzer._adx(high_full.astype(float), low_full.astype(float), close_full)
    return analyzer._adx_close_only(close_full)


def precompute_ticker(analyzer, close_full, high_full, low_full):
    """Calcola EMA10/EMA20/SMA50/SMA200/RSI/ADX/MACD/ATR UNA VOLTA sull'intera serie."""
    macd_d = analyzer._macd(close_full)
    atr_full = (analyzer._calculate_atr(high_full, low_full, close_full)
                if high_full is not None and low_full is not None else None)
    macd_h = macd_d['histogram']
    macd_hp = macd_h.shift(1)
    # Stessa formula esatta di suggest_level(): macd_positive AND macd_rising.
    # Vettorizzata una volta sola sull'intera serie, usata come skip-mask certo in
    # simulate() quando require_macd=True (vedi backtest_l1.py::simulate).
    macd_ok = (macd_h > 0) & (macd_h > macd_hp)
    return {
        'ema10': analyzer._ema(close_full, analyzer.ema10_period),
        'ema20': analyzer._ema(close_full, analyzer.ema20_period),
        'sma50': analyzer._sma(close_full, analyzer.sma50_period),
        'sma200': analyzer._sma(close_full, analyzer.sma200_period),
        'rsi': analyzer._rsi(close_full),
        'adx': _adx_series(analyzer, high_full, low_full, close_full),
        'macd_histogram': macd_h,
        'atr': atr_full,
        'macd_ok': macd_ok,
    }


def load_cluster_data(freeze_batch, cluster_name=None, min_rows=220):
    """Carica dal Golden Dataset tutti i ticker dei cluster richiesti, con precompute."""
    db = PriceDatabase()
    universe = load_universe()
    by_cluster = {}
    skipped = []

    for item in universe:
        famiglia = item['famiglia']
        cluster = FAMIGLIA_TO_CLUSTER.get(famiglia)
        if cluster is None:
            continue
        if cluster_name and cluster != cluster_name:
            continue

        ticker = item['ticker']
        hist = db.get_frozen_ohlcv(ticker, freeze_batch)
        if hist.empty or len(hist) < min_rows:
            skipped.append((ticker, len(hist)))
            continue

        has_ohlc = all(c in hist.columns for c in ['Open', 'High', 'Low'])
        close_full = hist['Close'].astype(float)
        high_full = hist['High'].astype(float) if has_ohlc else None
        low_full = hist['Low'].astype(float) if has_ohlc else None

        analyzer_tmp = ETFTechnicalAnalyzer(famiglia=famiglia)
        precomputed = precompute_ticker(analyzer_tmp, close_full, high_full, low_full)

        entry = {
            'ticker': ticker, 'famiglia': famiglia,
            'close_full': close_full, 'high_full': high_full, 'low_full': low_full,
            'hist_index': hist.index, 'precomputed': precomputed,
            'baseline_p': dict(analyzer_tmp.p),
        }
        by_cluster.setdefault(cluster, []).append(entry)

    print(f"Caricati: {sum(len(v) for v in by_cluster.values())} ticker su "
          f"{len(universe)} nell'universo, {len(skipped)} scartati (storico <{min_rows}gg)")
    for c, items in by_cluster.items():
        print(f"  {c}: {len(items)} ticker")
    return by_cluster


def make_analyzer_for_combo(entry, param_overrides, min_buy_count=6):
    """Copia locale di self.p (come make_analyzer in backtest_l1.py), con gli override
    del combo applicati SOPRA la baseline della famiglia — non un valore assoluto condiviso
    tra famiglie diverse, ma un delta/moltiplicatore sulla calibrazione gia' esistente."""
    analyzer = ETFTechnicalAnalyzer(famiglia=entry['famiglia'])
    p = dict(entry['baseline_p'])
    p['min_buy_count'] = min_buy_count

    if 'mm200_delta' in param_overrides:
        p['mm200_distance_max'] = max(0.1, p.get('mm200_distance_max', 4.0) + param_overrides['mm200_delta'])
    if 'adx_delta' in param_overrides:
        p['adx_entry'] = max(1, p.get('adx_entry', 20) + param_overrides['adx_delta'])
    if 'rsi_low_delta' in param_overrides:
        p['rsi_entry_low'] = p.get('rsi_entry_low', 45) + param_overrides['rsi_low_delta']
    if 'rsi_high_delta' in param_overrides:
        p['rsi_entry_high'] = p.get('rsi_entry_high', 58) + param_overrides['rsi_high_delta']
    if 'sl_buffer_mult' in param_overrides and 'sl_buffer_wide' in p:
        p['sl_buffer_wide'] = p['sl_buffer_wide'] * param_overrides['sl_buffer_mult']

    analyzer.p = p
    return analyzer


def run_combo(cluster_items, param_overrides, start_date, end_date):
    """Esegue simulate() su tutti i ticker del cluster per UNA combinazione di parametri,
    nel range [start_date, end_date), e restituisce la struttura 'results' compatibile
    con aggregate() di backtest_l1.py."""
    results = []
    for entry in cluster_items:
        analyzer = make_analyzer_for_combo(entry, param_overrides, min_buy_count=6)
        test_dates = [d for d in entry['hist_index']
                      if start_date <= d.date() < end_date]
        if not test_dates:
            continue
        precomputed_series = {k: v for k, v in entry['precomputed'].items() if k != 'macd_ok'}
        trades = simulate(analyzer, entry['close_full'], entry['high_full'], entry['low_full'],
                           entry['hist_index'], test_dates, require_macd=True,
                           precomputed_full=precomputed_series,
                           macd_skip_mask=entry['precomputed']['macd_ok'])
        results.append({'ticker': entry['ticker'], 'famiglia': entry['famiglia'],
                         'variants': {'combo': {'n_trades': len(trades), 'trades': trades}}})
    return results


def extra_metrics(agg):
    """Profit Factor, Expectancy netta, Max Drawdown (equity curve equal-weight non
    compounded, ordinata per exit_date) — non gia' calcolati da aggregate()."""
    closed = [t for t in agg['trades'] if t['status'] == 'closed' and t.get('exit_date')]
    wins = [t['net_pct_gain'] for t in closed if t['net_pct_gain'] > 0]
    losses = [t['net_pct_gain'] for t in closed if t['net_pct_gain'] <= 0]

    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = round(gross_win / gross_loss, 2) if gross_loss > 0 else (
        float('inf') if gross_win > 0 else None)

    n = len(closed)
    win_rate = len(wins) / n if n else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    expectancy = round(win_rate * avg_win + (1 - win_rate) * avg_loss, 3)

    curve = sorted(closed, key=lambda t: t['exit_date'])
    running, peak, max_dd = 0.0, 0.0, 0.0
    for t in curve:
        running += t['net_pct_gain']
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)

    return {'profit_factor': profit_factor, 'expectancy_pct': expectancy,
            'max_drawdown_pct': round(max_dd, 2)}


def validate_fast_path(n_tickers=8, n_dates=60, seed=42):
    """Step 2 richiesto: confronta il motore veloce (indicatori pre-calcolati) contro
    suggest_level() nel suo comportamento originale (nessun precompute), sugli STESSI
    ticker/date/parametri. Criterio di blocco: 0 discrepanze su suggested_level/buy_count."""
    print("=" * 78)
    print(f"VALIDAZIONE INCROCIATA — {n_tickers} ticker x fino a {n_dates} date ciascuno")
    print("=" * 78)

    db = PriceDatabase()
    universe = load_universe()
    rnd = random.Random(seed)
    sample = rnd.sample(universe, min(n_tickers, len(universe)))

    mismatches = 0
    total_checks = 0
    quiet = io.StringIO()

    for item in sample:
        ticker, famiglia = item['ticker'], item['famiglia']
        hist = db.get_frozen_ohlcv(ticker, DEFAULT_FROZEN_BATCH)
        if hist.empty or len(hist) < 220:
            print(f"  [skip] {ticker}: storico insufficiente nel batch congelato")
            continue

        has_ohlc = all(c in hist.columns for c in ['Open', 'High', 'Low'])
        close_full = hist['Close'].astype(float)
        high_full = hist['High'].astype(float) if has_ohlc else None
        low_full = hist['Low'].astype(float) if has_ohlc else None

        analyzer = ETFTechnicalAnalyzer(famiglia=famiglia)
        precomputed = precompute_ticker(analyzer, close_full, high_full, low_full)

        test_positions = rnd.sample(range(220, len(hist)), min(n_dates, len(hist) - 220))

        for pos in test_positions:
            close_slice = close_full.iloc[:pos + 1]
            high_slice = high_full.iloc[:pos + 1] if high_full is not None else None
            low_slice = low_full.iloc[:pos + 1] if low_full is not None else None
            precomputed_slice = {k: v.iloc[:pos + 1] for k, v in precomputed.items()
                                  if k != 'macd_histogram'}
            precomputed_slice['macd'] = {'histogram': precomputed['macd_histogram'].iloc[:pos + 1]}

            with redirect_stdout(quiet):
                slow = analyzer.suggest_level(close_slice, current_level=3,
                                               high=high_slice, low=low_slice)
                fast = analyzer.suggest_level(close_slice, current_level=3,
                                               high=high_slice, low=low_slice,
                                               precomputed=precomputed_slice)

            total_checks += 1
            keys_to_check = ['suggested_level']
            slow_c = slow.get('conditions', {})
            fast_c = fast.get('conditions', {})
            cond_keys = ['allineamento_ok', 'persistenza_ok', 'rsi_ok', 'distance_ok',
                         'adx_ok', 'macd_ok', 'space_residuo_ok']
            diverge = (slow.get('suggested_level') != fast.get('suggested_level') or
                       any(slow_c.get(k) != fast_c.get(k) for k in cond_keys))
            if diverge:
                mismatches += 1
                print(f"  [MISMATCH] {ticker} pos={pos} date={hist.index[pos].date()}")
                print(f"    slow: level={slow.get('suggested_level')} conditions={{{', '.join(f'{k}={slow_c.get(k)}' for k in cond_keys)}}}")
                print(f"    fast: level={fast.get('suggested_level')} conditions={{{', '.join(f'{k}={fast_c.get(k)}' for k in cond_keys)}}}")

    print("-" * 78)
    print(f"Check totali: {total_checks}  |  Mismatch: {mismatches}")
    if mismatches == 0 and total_checks > 0:
        print("PASS — motore veloce identico al motore originale su tutti i check.")
        ok1 = True
    else:
        print("FAIL — NON procedere con lo sweep finche' non e' risolto.")
        ok1 = False

    ok2 = validate_macd_skip()
    return ok1 and ok2


def validate_macd_skip(n_tickers=8, seed=42):
    """Confronta simulate() CON e SENZA macd_skip_mask sugli stessi ticker/parametri
    (require_macd=True, come nello sweep). Criterio di blocco: liste di trade identiche
    (stesse date/prezzi di entrata e uscita) — non solo lo stesso conteggio."""
    print("\n" + "=" * 78)
    print(f"VALIDAZIONE SKIP-MASK MACD — {n_tickers} ticker, require_macd=True")
    print("=" * 78)

    db = PriceDatabase()
    universe = load_universe()
    rnd = random.Random(seed)
    sample = rnd.sample(universe, min(n_tickers, len(universe)))

    mismatches = 0
    checked = 0

    for item in sample:
        ticker, famiglia = item['ticker'], item['famiglia']
        hist = db.get_frozen_ohlcv(ticker, DEFAULT_FROZEN_BATCH)
        if hist.empty or len(hist) < 220:
            continue

        has_ohlc = all(c in hist.columns for c in ['Open', 'High', 'Low'])
        close_full = hist['Close'].astype(float)
        high_full = hist['High'].astype(float) if has_ohlc else None
        low_full = hist['Low'].astype(float) if has_ohlc else None

        analyzer_tmp = ETFTechnicalAnalyzer(famiglia=famiglia)
        precomputed = precompute_ticker(analyzer_tmp, close_full, high_full, low_full)
        precomputed_series = {k: v for k, v in precomputed.items() if k != 'macd_ok'}

        test_dates = list(hist.index)

        analyzer_a = ETFTechnicalAnalyzer(famiglia=famiglia)
        analyzer_a.p = dict(analyzer_a.p)
        analyzer_a.p['min_buy_count'] = 6
        trades_with_mask = simulate(analyzer_a, close_full, high_full, low_full, hist.index,
                                     test_dates, require_macd=True,
                                     precomputed_full=precomputed_series,
                                     macd_skip_mask=precomputed['macd_ok'])

        analyzer_b = ETFTechnicalAnalyzer(famiglia=famiglia)
        analyzer_b.p = dict(analyzer_b.p)
        analyzer_b.p['min_buy_count'] = 6
        trades_without_mask = simulate(analyzer_b, close_full, high_full, low_full, hist.index,
                                        test_dates, require_macd=True,
                                        precomputed_full=precomputed_series,
                                        macd_skip_mask=None)

        checked += 1
        key = lambda t: (t['entry_date'], t['exit_date'], t['exit_price'], t['status'])
        if [key(t) for t in trades_with_mask] != [key(t) for t in trades_without_mask]:
            mismatches += 1
            print(f"  [MISMATCH] {ticker}: con-mask {len(trades_with_mask)} trade, "
                  f"senza-mask {len(trades_without_mask)} trade")
            print(f"    con-mask:    {[key(t) for t in trades_with_mask]}")
            print(f"    senza-mask:  {[key(t) for t in trades_without_mask]}")

    print("-" * 78)
    print(f"Ticker verificati: {checked}  |  Mismatch: {mismatches}")
    if mismatches == 0 and checked > 0:
        print("PASS — skip-mask MACD produce esattamente le stesse liste di trade.")
        return True
    else:
        print("FAIL — NON usare macd_skip_mask finche' non e' risolto.")
        return False


def run_pilot(cluster_name=None, freeze_batch=DEFAULT_FROZEN_BATCH):
    by_cluster = load_cluster_data(freeze_batch, cluster_name)

    mm200_grid = [-1.0, 0.0, 1.0]
    adx_grid = [-4, 0, 4]
    combos = list(itertools.product(mm200_grid, adx_grid))

    all_rows = []
    t0 = time.time()
    for cluster, items in by_cluster.items():
        print(f"\n{'=' * 78}\nCLUSTER: {cluster} ({len(items)} ticker)\n{'=' * 78}")
        for mm200_delta, adx_delta in combos:
            overrides = {'mm200_delta': mm200_delta, 'adx_delta': adx_delta}
            t_combo = time.time()

            results_in = run_combo(items, overrides, TRAIN_START, TRAIN_END)
            agg_in = aggregate(results_in, 'combo', 10000.0)
            extra_in = extra_metrics(agg_in)

            results_out = run_combo(items, overrides, TRAIN_END, TEST_END)
            agg_out = aggregate(results_out, 'combo', 10000.0)
            extra_out = extra_metrics(agg_out)

            elapsed = time.time() - t_combo
            row = {
                'cluster': cluster, 'mm200_delta': mm200_delta, 'adx_delta': adx_delta,
                'n_trades_in': agg_in['n_trades_closed'], 'win_rate_in': agg_in['win_rate_pct'],
                'profit_factor_in': extra_in['profit_factor'], 'expectancy_in': extra_in['expectancy_pct'],
                'max_dd_in': extra_in['max_drawdown_pct'],
                'n_trades_out': agg_out['n_trades_closed'], 'win_rate_out': agg_out['win_rate_pct'],
                'profit_factor_out': extra_out['profit_factor'], 'expectancy_out': extra_out['expectancy_pct'],
                'max_dd_out': extra_out['max_drawdown_pct'],
                'seconds': round(elapsed, 1),
            }
            all_rows.append(row)
            print(f"  mm200Δ={mm200_delta:+.1f} adxΔ={adx_delta:+d} | "
                  f"IN: N={row['n_trades_in']:3d} WR={row['win_rate_in']} PF={row['profit_factor_in']} | "
                  f"OUT: N={row['n_trades_out']:3d} WR={row['win_rate_out']} PF={row['profit_factor_out']} | "
                  f"{elapsed:.1f}s")

    total_elapsed = time.time() - t0
    print(f"\nTempo totale pilota: {total_elapsed / 60:.1f} minuti "
          f"({len(all_rows)} combinazioni)")

    out_path = 'data/optimize_pilot_result.json'
    with open(out_path, 'w') as f:
        json.dump({'rows': all_rows, 'total_seconds': total_elapsed,
                    'generated_at': datetime.now().isoformat()}, f, indent=2)
    print(f"Salvato: {out_path}")

    reportable = [r for r in all_rows if r['n_trades_in'] >= MIN_TRADES_REPORT]
    reportable.sort(key=lambda r: (r['profit_factor_in'] if r['profit_factor_in'] not in (None, float('inf')) else -1),
                     reverse=True)
    print(f"\nTop combinazioni per Profit Factor In-Sample (N>={MIN_TRADES_REPORT}):")
    for r in reportable[:10]:
        print(f"  {r['cluster']:12s} mm200Δ={r['mm200_delta']:+.1f} adxΔ={r['adx_delta']:+d} "
              f"| IN: N={r['n_trades_in']} PF={r['profit_factor_in']} WR={r['win_rate_in']}% "
              f"| OUT: N={r['n_trades_out']} PF={r['profit_factor_out']} WR={r['win_rate_out']}%")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--validate', action='store_true', help='cross-check motore veloce vs originale')
    parser.add_argument('--pilot', action='store_true', help='griglia pilota (9 combo/cluster)')
    parser.add_argument('--cluster', default=None, choices=list(CLUSTERS.keys()),
                         help='limita a un solo cluster')
    parser.add_argument('--frozen-batch', default=DEFAULT_FROZEN_BATCH)
    args = parser.parse_args()

    if args.validate:
        ok = validate_fast_path()
        sys.exit(0 if ok else 1)

    if args.pilot:
        run_pilot(cluster_name=args.cluster, freeze_batch=args.frozen_batch)
        return

    print("Specifica --validate oppure --pilot (vedi docstring del file).")


if __name__ == '__main__':
    main()
