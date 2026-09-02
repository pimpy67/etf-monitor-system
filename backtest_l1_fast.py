"""
backtest_l1_fast.py — SCRATCH (2026-09-01). Confronto veloce O(n) per l'analisi
"allargamento gate L1". Riusa simulate()/aggregate() di backtest_l1.py e
precompute_ticker() di optimize_hyperparameters.py — nessuna logica duplicata.

Il plain backtest_l1.py ricalcola tutti gli indicatori a ogni giorno (O(n^2) per
ticker) -> impraticabile su 231 ticker / 1 vCPU. Qui gli indicatori si calcolano
UNA volta per ticker e si passano a suggest_level(precomputed=...) (stesso identico
motore, solo alimentato con serie pre-tagliate).

Varianti testate:
  prod_current    YAML as-is (= produzione oggi: smart_6_macd ON sulle 5 core)
  native_7_pure   min_buy_count=7 su tutte, use_smart_6_7_macd=False (gate storico stretto)
  override_6      min_buy_count=6 secco, nessun vincolo MACD (l'opzione gia' respinta)
  smart_6_all     min_buy_count=6 + MACD sempre obbligatorio, su TUTTE le 13 famiglie
  macd_dip_prod   prod_current + ramo MACD "buy-the-dip" (dist_EMA20 < 2%)
  macd_dip_smart6 smart_6_all + ramo MACD "buy-the-dip"

Split IN/OOS: IN 2023-08-05..2025-08-05, OOS 2025-08-05..2026-08-07 (fine dataset congelato).

Uso (nel container):
  python3 backtest_l1_fast.py --frozen-batch 2026-08-07
"""
import sys
sys.path.insert(0, '/app')

import argparse
import json
from datetime import datetime, date

import pandas as pd

from technical_analysis import ETFTechnicalAnalyzer
from database import PriceDatabase
from backtest_l1 import simulate, aggregate, load_universe
from optimize_hyperparameters import precompute_ticker

DEFAULT_FROZEN_BATCH = '2026-08-07'

IN_START = date(2023, 8, 5)
IN_END = date(2025, 8, 5)
OOS_START = date(2025, 8, 5)
OOS_END = date(2026, 8, 8)
FULL_START = date(2023, 8, 5)
FULL_END = date(2026, 8, 8)

CORE_FAMILIES = {'equity_sviluppati', 'mercati_emergenti', 'settoriali_growth',
                 'oro_metalli_preziosi', 'metalli_industriali'}

# label -> (min_buy_override | None, require_macd, {param overrides})
VARIANTS = {
    'prod_current':  (None, False, {}),
    'override_6':    (6,    False, {'use_smart_6_7_macd': False}),
    'dip05_prod':    (None, False, {'macd_dip_tolerance_pct': 0.5}),
    'dip10_prod':    (None, False, {'macd_dip_tolerance_pct': 1.0}),
}

POSITION_SIZE = 10000.0


def profit_factor(trades):
    gains = [t['net_gain_eur'] for t in trades if t['status'] == 'closed' and t['net_gain_eur'] > 0]
    losses = [-t['net_gain_eur'] for t in trades if t['status'] == 'closed' and t['net_gain_eur'] < 0]
    if not losses:
        return None if not gains else float('inf')
    return round(sum(gains) / sum(losses), 2)


def make_analyzer(famiglia, min_buy_override, overrides):
    a = ETFTechnicalAnalyzer(famiglia=famiglia)
    p = dict(a.p)
    if min_buy_override is not None:
        p['min_buy_count'] = min_buy_override
    for k, v in overrides.items():
        p[k] = v
    a.p = p
    return a


def load_all(freeze_batch, core_only=False):
    db = PriceDatabase()
    universe = load_universe()
    if core_only:
        universe = [it for it in universe if it['famiglia'] in CORE_FAMILIES]
    items, skipped = [], []
    for it in universe:
        hist = db.get_frozen_ohlcv(it['ticker'], freeze_batch)
        if hist.empty or len(hist) < 220:
            skipped.append(it['ticker'])
            continue
        has_ohlc = all(c in hist.columns for c in ['Open', 'High', 'Low'])
        close_full = hist['Close'].astype(float)
        high_full = hist['High'].astype(float) if has_ohlc else None
        low_full = hist['Low'].astype(float) if has_ohlc else None
        tmp = ETFTechnicalAnalyzer(famiglia=it['famiglia'])
        pc = precompute_ticker(tmp, close_full, high_full, low_full)
        items.append({
            'ticker': it['ticker'], 'famiglia': it['famiglia'],
            'close_full': close_full, 'high_full': high_full, 'low_full': low_full,
            'hist_index': hist.index, 'precomputed': pc,
        })
    print(f"Caricati {len(items)} ticker, {len(skipped)} scartati (<220gg)")
    return items


def run_variant(items, label, spec, win_start, win_end):
    min_buy_override, require_macd, overrides = spec
    results = []
    for e in items:
        analyzer = make_analyzer(e['famiglia'], min_buy_override, overrides)
        test_dates = [d for d in e['hist_index'] if win_start <= d.date() < win_end]
        if not test_dates:
            continue
        pc = e['precomputed']
        precomputed_full = {
            'ema10': pc['ema10'], 'ema20': pc['ema20'], 'sma50': pc['sma50'],
            'sma200': pc['sma200'], 'rsi': pc['rsi'], 'adx': pc['adx'],
            'macd_histogram': pc['macd_histogram'], 'atr': pc['atr'],
        }
        macd_skip_mask = pc['macd_ok'] if require_macd else None
        trades = simulate(analyzer, e['close_full'], e['high_full'], e['low_full'],
                          e['hist_index'], test_dates, require_macd=require_macd,
                          precomputed_full=precomputed_full, macd_skip_mask=macd_skip_mask)
        results.append({'ticker': e['ticker'], 'famiglia': e['famiglia'],
                        'variants': {label: {'n_trades': len(trades), 'trades': trades}}})
    return results


def summarize(results, label):
    agg = aggregate(results, label, POSITION_SIZE)
    closed = [t for t in agg['trades'] if t['status'] == 'closed']
    return {
        'n_total': agg['n_trades_total'],
        'n_closed': agg['n_trades_closed'],
        'n_open': agg['n_trades_open'],
        'n_sl': agg['n_exit_sl'],
        'n_tp': agg['n_exit_tp'],
        'win_rate': agg['win_rate_pct'],
        'avg_net_pct': agg['avg_net_pct_gain'],
        'pf': profit_factor(agg['trades']),
        'total_net_eur': agg['total_net_eur'],
        'avg_dur': agg['avg_duration_days'],
    }


def per_family(results, label):
    fam = {}
    for r in results:
        for t in r['variants'][label]['trades']:
            f = r['famiglia']
            fam.setdefault(f, []).append(t)
    out = {}
    for f, trades in sorted(fam.items()):
        closed = [t for t in trades if t['status'] == 'closed']
        wins = [t for t in closed if t['gross_pct_gain'] > 0]
        out[f] = {
            'n_closed': len(closed),
            'win_rate': round(100 * len(wins) / len(closed), 1) if closed else None,
            'avg_gross': round(sum(t['gross_pct_gain'] for t in closed) / len(closed), 2) if closed else None,
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frozen-batch', default=DEFAULT_FROZEN_BATCH)
    ap.add_argument('--out', default='data/backtest_l1_fast_result.json')
    ap.add_argument('--core-only', action='store_true')
    ap.add_argument('--single-window', action='store_true',
                    help='una sola finestra 2023-08..2026-08 invece dello split IN/OOS')
    args = ap.parse_args()

    if args.single_window:
        windows = [('FULL', (FULL_START, FULL_END))]
    else:
        windows = [('IN', (IN_START, IN_END)), ('OOS', (OOS_START, OOS_END))]

    print("=" * 80)
    print("BACKTEST L1 FAST — allargamento gate | size 10.000EUR | costi 5+5 | tax 26%")
    print(f"Finestre: {[w[0] for w in windows]}  |  core_only={args.core_only}  |  batch {args.frozen_batch}")
    print("=" * 80)

    items = load_all(args.frozen_batch, core_only=args.core_only)

    out = {'variants': {}, 'per_family': {}}
    for label, spec in VARIANTS.items():
        row = {}
        for wname, (ws, we) in windows:
            res = run_variant(items, label, spec, ws, we)
            row[wname] = summarize(res, label)
            out['per_family'].setdefault(label, {})[wname] = per_family(res, label)
        out['variants'][label] = row
        print(f"\n### {label}")
        for wname, _ in windows:
            s = row[wname]
            print(f"  {wname:4s}: N={s['n_closed']:3d}  WR={s['win_rate']}  PF={s['pf']}  "
                  f"avg_net={s['avg_net_pct']}%  SL/TP={s['n_sl']}/{s['n_tp']}  "
                  f"dur={s['avg_dur']}g  net={s['total_net_eur']}EUR")

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nSalvato in {args.out}")


if __name__ == '__main__':
    main()
