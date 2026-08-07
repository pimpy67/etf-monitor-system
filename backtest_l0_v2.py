"""
backtest_l0_v2.py — Backtest L0 "portafoglio reale" (stessa filosofia di backtest_l1.py).

A differenza di backtest_l0.py/backtest_l0_full.py/backtest_l0_rigorous.py (preesistenti,
NON riusati qui: hanno una copia locale della formula SL con soglie diverse da quella vera
— 2%/5% invece di 5%/15% — e non applicano whitelist/regime/divergenza/percorsi FAST-SLOW),
questo motore chiama la logica REALE:
  - Ingresso: ETFTechnicalAnalyzer.suggest_level_0() (whitelist, regime gate, percorsi
    FAST/SLOW/PRAGMATIC — tutto incluso, nessuna riscrittura)
  - Uscita: SOLO SL (calculate_sl_suggerito_l0, trailing) o TP (calculate_tp_suggerito_l0,
    fisso per famiglia) — stessa filosofia "nessun automatismo" gia' documentata per L1
    (le regole alfa/beta della dashboard non chiudono le posizioni reali, vedi CLAUDE.md).

Legge dal Golden Dataset congelato (stesso di backtest_l1.py) per riproducibilita'.

Uso:
  python3 backtest_l0_v2.py --start 2023-08-05 --days 1120
"""
import sys
sys.path.insert(0, '/app')

import argparse
from datetime import datetime, timedelta

import pandas as pd

from technical_analysis import ETFTechnicalAnalyzer
from database import PriceDatabase

DEFAULT_FROZEN_BATCH = '2026-08-07'
DIRECTA_FEE_BUY = 5.0
DIRECTA_FEE_SELL = 5.0
TAX_RATE = 0.26


def get_l0_whitelist():
    """Legge la whitelist L0 direttamente dallo YAML — oggi una sola famiglia."""
    analyzer = ETFTechnicalAnalyzer(famiglia='equity_sviluppati')
    return analyzer.p.get('global_params', {}).get('l0_whitelist', ['equity_sviluppati'])


def load_universe(excel_path='etf_monitoraggio.xlsx'):
    whitelist = set(get_l0_whitelist())
    df = pd.read_excel(excel_path, sheet_name='ETF')
    rows = []
    for _, row in df.iterrows():
        ticker = str(row.get('Ticker', '')).strip()
        categoria = str(row.get('Categoria', ''))
        if not ticker or ticker.lower() == 'nan':
            continue
        famiglia = ETFTechnicalAnalyzer.detect_family(categoria)
        if famiglia in whitelist:
            rows.append({'ticker': ticker, 'famiglia': famiglia})
    return rows


def simulate_l0(analyzer, close_full, high_full, low_full, hist_index, test_dates):
    """Walk-forward: ingresso via suggest_level_0(), uscita SOLO SL/TP — stesso schema
    di backtest_l1.py::simulate(). Nessuna finestra precomputata per ora (whitelist L0
    e' una sola famiglia, universo piccolo — ottimizzazione rimandata se necessaria)."""
    holding = False
    entry_price = None
    entry_date = None
    entry_mode = None
    trades = []

    for d in test_dates:
        pos = hist_index.get_loc(d)
        close_slice = close_full.iloc[:pos + 1]
        high_slice = high_full.iloc[:pos + 1] if high_full is not None else None
        low_slice = low_full.iloc[:pos + 1] if low_full is not None else None
        close_today = float(close_slice.iloc[-1])

        if not holding:
            result = analyzer.suggest_level_0(close_slice, high_slice, low_slice, current_level=3)
            if result.get('l0_entry'):
                holding = True
                entry_price = close_today
                entry_date = d.date().isoformat()
                entry_mode = result.get('l0_regime_mode')
        else:
            sl_data = analyzer.calculate_sl_suggerito_l0(entry_price, close_today)
            sl = sl_data.get('sl_suggerito')
            tp_data = analyzer.calculate_tp_suggerito_l0(entry_price, close_today)
            tp_hit = bool(tp_data.get('trigger'))
            sl_hit = sl is not None and close_today <= sl

            if sl_hit or tp_hit:
                exit_reason = 'SL' if sl_hit else 'TP'
                gross_pct = round((close_today / entry_price - 1) * 100, 3)
                trades.append({
                    'entry_date': entry_date, 'entry_price': entry_price,
                    'exit_date': d.date().isoformat(), 'exit_price': close_today,
                    'status': 'closed', 'gross_pct_gain': gross_pct,
                    'exit_reason': exit_reason, 'entry_mode': entry_mode,
                })
                holding = False
                entry_price = None
                entry_date = None
                entry_mode = None

    if holding:
        last_price = float(close_full.iloc[-1])
        gross_pct = round((last_price / entry_price - 1) * 100, 3)
        trades.append({
            'entry_date': entry_date, 'entry_price': entry_price,
            'exit_date': None, 'exit_price': last_price,
            'status': 'open', 'gross_pct_gain': gross_pct,
            'exit_reason': None, 'entry_mode': entry_mode,
        })

    return trades


def apply_costs_and_tax(trade, position_size):
    entry_price = trade['entry_price']
    exit_price = trade['exit_price']
    gross_gain_eur = position_size * (exit_price / entry_price - 1)
    fees = DIRECTA_FEE_BUY + (DIRECTA_FEE_SELL if trade['status'] == 'closed' else 0)
    gain_after_fees = gross_gain_eur - fees
    tax = TAX_RATE * gain_after_fees if gain_after_fees > 0 else 0.0
    net_gain_eur = gain_after_fees - tax
    trade['net_gain_eur'] = round(net_gain_eur, 2)
    trade['net_pct_gain'] = round(100 * net_gain_eur / position_size, 3)
    trade['fees_eur'] = round(fees, 2)
    trade['tax_eur'] = round(tax, 2)
    return trade


def aggregate(all_results, position_size):
    all_trades = []
    for r in all_results:
        for t in r['trades']:
            t = apply_costs_and_tax(dict(t), position_size)
            all_trades.append({**t, 'ticker': r['ticker'], 'famiglia': r['famiglia']})

    closed = [t for t in all_trades if t['status'] == 'closed']
    open_ = [t for t in all_trades if t['status'] == 'open']

    def duration_days(t):
        ed = datetime.strptime(t['entry_date'], '%Y-%m-%d').date()
        xd = (datetime.strptime(t['exit_date'], '%Y-%m-%d').date() if t['exit_date']
              else datetime.now().date())
        return (xd - ed).days

    durations = [duration_days(t) for t in closed]
    net_gains = [t['net_pct_gain'] for t in closed]
    sl_trades = [t for t in closed if t['exit_reason'] == 'SL']
    tp_trades = [t for t in closed if t['exit_reason'] == 'TP']

    return {
        'n_trades_total': len(all_trades),
        'n_trades_closed': len(closed),
        'n_trades_open': len(open_),
        'n_exit_sl': len(sl_trades),
        'n_exit_tp': len(tp_trades),
        'avg_duration_days': round(sum(durations) / len(durations), 1) if durations else None,
        'avg_net_pct_gain': round(sum(net_gains) / len(net_gains), 2) if net_gains else None,
        'win_rate_pct': round(100 * sum(1 for g in net_gains if g > 0) / len(net_gains), 1) if net_gains else None,
        'total_net_eur': round(sum(t['net_gain_eur'] for t in closed), 2) if closed else 0,
        'trades': sorted(all_trades, key=lambda t: t['entry_date']),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', default=None)
    parser.add_argument('--days', type=int, default=1120)
    parser.add_argument('--position-sizes', default='5000,10000')
    parser.add_argument('--frozen-batch', default=DEFAULT_FROZEN_BATCH)
    args = parser.parse_args()
    position_sizes = [float(x) for x in args.position_sizes.split(',')]
    start_date = (datetime.strptime(args.start, '%Y-%m-%d').date()
                  if args.start else (datetime.now() - timedelta(days=365)).date())

    whitelist = get_l0_whitelist()
    print(f"BACKTEST L0 v2 — portafoglio reale (SL trailing/TP fisso, no alfa/beta) — "
          f"dal {start_date.isoformat()} a oggi")
    print(f"Whitelist L0: {whitelist}")

    universe = load_universe()
    print(f"ETF nell'universo whitelisted: {len(universe)}\n")

    db = PriceDatabase()
    results, errors = [], []

    for i, item in enumerate(universe, 1):
        ticker, famiglia = item['ticker'], item['famiglia']
        print(f"[{i}/{len(universe)}] {ticker:14s} ({famiglia})...", end=' ')
        hist = db.get_frozen_ohlcv(ticker, args.frozen_batch)
        if hist.empty or len(hist) < 220:
            print(f"SKIP — storico insufficiente ({len(hist)}gg)")
            errors.append({'ticker': ticker, 'error': 'storico insufficiente'})
            continue

        has_ohlc = all(c in hist.columns for c in ['Open', 'High', 'Low'])
        close_full = hist['Close'].astype(float)
        high_full = hist['High'].astype(float) if has_ohlc else None
        low_full = hist['Low'].astype(float) if has_ohlc else None
        test_dates = [d for d in hist.index if d.date() >= start_date]
        if not test_dates:
            print("SKIP — nessuna data nel range")
            continue

        analyzer = ETFTechnicalAnalyzer(famiglia=famiglia)
        trades = simulate_l0(analyzer, close_full, high_full, low_full, hist.index, test_dates)
        results.append({'ticker': ticker, 'famiglia': famiglia, 'trades': trades})
        print(f"{len(trades)} trade")

    print(f"\nAnalisi: {len(results)} OK, {len(errors)} errori")
    print("=" * 78)

    for size in position_sizes:
        agg = aggregate(results, size)
        print(f"\n--- Size {size:.0f}EUR ---")
        print(f"  Trade totali: {agg['n_trades_total']}  (chiusi: {agg['n_trades_closed']}, "
              f"ancora aperti: {agg['n_trades_open']})")
        print(f"  Uscite: {agg['n_exit_sl']} via SL, {agg['n_exit_tp']} via TP")
        print(f"  Durata media posizione chiusa: {agg['avg_duration_days']} giorni")
        print(f"  Rendimento medio NETTO per trade: {agg['avg_net_pct_gain']}%")
        print(f"  Win rate (netto): {agg['win_rate_pct']}%")
        print(f"  P&L netto totale su {size:.0f}EUR/trade: {agg['total_net_eur']}EUR")


if __name__ == '__main__':
    main()
