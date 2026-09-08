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
from directa_exit import directa_stop_today

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


def simulate_l0(analyzer, close_full, high_full, low_full, hist_index, test_dates,
                exit_model='clean'):
    """Walk-forward: ingresso via suggest_level_0(), uscita SOLO SL/TP — stesso schema
    di backtest_l1.py::simulate(). Nessuna finestra precomputata per ora (whitelist L0
    e' una sola famiglia, universo piccolo — ottimizzazione rimandata se necessaria).

    exit_model:
      'clean'   (default, retro-compatibile) — esce al primo tra Close<=SL o Close>=TP,
                fill esatto a quel prezzo. E' il modello usato da tutti i backtest/Shadow
                Monitor finora.
      'directa' (item 15, 2026-09-03) — replica l'esecuzione reale Directa: un solo
                ordine di vendita attivo (lo Stop effettivo = max(SL ufficiale, ratchet
                di avvicinamento al TP), ricalcolato ogni giorno, ratchettato). Vedi
                directa_exit.py per il razionale completo.
    """
    holding = False
    entry_price = None
    entry_date = None
    entry_mode = None
    tp_stop_max = None  # floor del ratchet Directa, persistito tra i giorni (solo exit_model='directa')
    trades = []

    def _close(exit_reason, d, close_today):
        nonlocal holding, entry_price, entry_date, entry_mode, tp_stop_max
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
        tp_stop_max = None

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
        elif exit_model == 'directa':
            atr_pct = None
            if high_slice is not None and low_slice is not None and len(close_slice) >= 14:
                atr_norm = analyzer._calculate_atr_normalized(high_slice, low_slice, close_slice)
                if atr_norm is not None:
                    atr_pct = round(atr_norm * 100, 2)
            step = directa_stop_today(
                analyzer, entry_price, close_today, 'L0',
                prev_tp_stop_max=tp_stop_max,
                sl_initial_pct=analyzer.p.get('sl_initial_pct'),
                atr_pct=atr_pct,
            )
            if step['tp_proximity_stop_max'] is not None:
                tp_stop_max = step['tp_proximity_stop_max']
            if step['hit']:
                _close(step['exit_reason'], d, close_today)
        else:
            sl_data = analyzer.calculate_sl_suggerito_l0(entry_price, close_today)
            sl = sl_data.get('sl_suggerito')
            tp_data = analyzer.calculate_tp_suggerito_l0(entry_price, close_today)
            tp_hit = bool(tp_data.get('trigger'))
            sl_hit = sl is not None and close_today <= sl

            if sl_hit or tp_hit:
                _close('SL' if sl_hit else 'TP', d, close_today)

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


def _summary(closed, open_n):
    """Metriche su una lista di trade chiusi (gia' con costi/tasse applicati)."""
    if not closed:
        return {'n_closed': 0, 'n_open': open_n, 'win_rate_pct': None, 'profit_factor': None,
                'avg_net_pct_gain': None, 'avg_duration_days': None, 'total_net_eur': 0,
                'exit_reasons': {}}

    def duration_days(t):
        ed = datetime.strptime(t['entry_date'], '%Y-%m-%d').date()
        xd = (datetime.strptime(t['exit_date'], '%Y-%m-%d').date() if t['exit_date']
              else datetime.now().date())
        return (xd - ed).days

    net_gains = [t['net_pct_gain'] for t in closed]
    wins_eur = sum(t['net_gain_eur'] for t in closed if t['net_gain_eur'] > 0)
    loss_eur = -sum(t['net_gain_eur'] for t in closed if t['net_gain_eur'] < 0)
    durations = [duration_days(t) for t in closed]

    reasons = {}
    for t in closed:
        reasons[t['exit_reason']] = reasons.get(t['exit_reason'], 0) + 1

    return {
        'n_closed': len(closed),
        'n_open': open_n,
        'win_rate_pct': round(100 * sum(1 for g in net_gains if g > 0) / len(net_gains), 1),
        'profit_factor': round(wins_eur / loss_eur, 2) if loss_eur > 0 else float('inf'),
        'avg_net_pct_gain': round(sum(net_gains) / len(net_gains), 2),
        'avg_duration_days': round(sum(durations) / len(durations), 1),
        'total_net_eur': round(sum(t['net_gain_eur'] for t in closed), 2),
        'exit_reasons': reasons,
    }


def aggregate(all_results, position_size, split_date=None):
    all_trades = []
    for r in all_results:
        for t in r['trades']:
            t = apply_costs_and_tax(dict(t), position_size)
            all_trades.append({**t, 'ticker': r['ticker'], 'famiglia': r['famiglia']})

    closed = [t for t in all_trades if t['status'] == 'closed']
    open_n = sum(1 for t in all_trades if t['status'] == 'open')

    out = {'n_trades_total': len(all_trades),
           'all': _summary(closed, open_n),
           'trades': sorted(all_trades, key=lambda t: t['entry_date'])}

    if split_date:
        sd = datetime.strptime(split_date, '%Y-%m-%d').date()
        in_c = [t for t in closed if datetime.strptime(t['entry_date'], '%Y-%m-%d').date() < sd]
        out_c = [t for t in closed if datetime.strptime(t['entry_date'], '%Y-%m-%d').date() >= sd]
        out['in_sample'] = _summary(in_c, 0)
        out['out_sample'] = _summary(out_c, 0)

    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', default=None)
    parser.add_argument('--days', type=int, default=1120)
    parser.add_argument('--position-sizes', default='5000,10000')
    parser.add_argument('--frozen-batch', default=DEFAULT_FROZEN_BATCH)
    parser.add_argument('--exit-model', choices=['clean', 'directa', 'both'], default='clean',
                        help="'clean' (default) = SL/TP primo toccato, fill esatto. "
                             "'directa' = Stop unico effettivo con ratchet (item 15). "
                             "'both' = gira entrambi e stampa il confronto.")
    parser.add_argument('--candidate-l0', action='store_true',
                        help="Applica l'override CANDIDATE_MODEL_L0_20260808 "
                             "(regime_min_days_below_sma200=5 invece del baseline YAML 10).")
    parser.add_argument('--split-date', default=None,
                        help="Se dato (YYYY-MM-DD), separa i trade chiusi in In-Sample "
                             "(entry < data) e Out-of-Sample (entry >= data).")
    parser.add_argument('--limit', type=int, default=None,
                        help="Analizza solo i primi N ticker dell'universo (smoke test).")
    args = parser.parse_args()
    position_sizes = [float(x) for x in args.position_sizes.split(',')]
    start_date = (datetime.strptime(args.start, '%Y-%m-%d').date()
                  if args.start else (datetime.now() - timedelta(days=365)).date())

    models = ['clean', 'directa'] if args.exit_model == 'both' else [args.exit_model]

    whitelist = get_l0_whitelist()
    print(f"BACKTEST L0 v2 — portafoglio reale (SL trailing/TP fisso, no alfa/beta) — "
          f"dal {start_date.isoformat()} a oggi")
    print(f"Whitelist L0: {whitelist}")
    print(f"Exit model: {', '.join(models)}"
          + ("  |  ingressi: CANDIDATE_MODEL_L0_20260808 (regime_min_days=5)" if args.candidate_l0
             else "  |  ingressi: native YAML"))
    if args.split_date:
        print(f"Split IN/OUT: entry < {args.split_date} = In-Sample, >= = Out-of-Sample")

    universe = load_universe()
    if args.limit:
        universe = universe[:args.limit]
    print(f"ETF nell'universo whitelisted: {len(universe)}\n")

    db = PriceDatabase()
    # results per modello: {'clean': [...], 'directa': [...]}
    results = {m: [] for m in models}
    errors = []

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
        if args.candidate_l0:
            p = dict(analyzer.p)
            p['l0_regime'] = dict(p.get('l0_regime', {}))
            p['l0_regime']['regime_min_days_below_sma200'] = 5
            analyzer.p = p

        counts = []
        for m in models:
            trades = simulate_l0(analyzer, close_full, high_full, low_full, hist.index,
                                 test_dates, exit_model=m)
            results[m].append({'ticker': ticker, 'famiglia': famiglia, 'trades': trades})
            counts.append(f"{m}:{len(trades)}")
        print(", ".join(counts))

    n_ok = len(results[models[0]])
    print(f"\nAnalisi: {n_ok} OK, {len(errors)} errori")
    print("=" * 78)

    def _print_block(label, s):
        if s['n_closed'] == 0:
            print(f"  {label}: 0 trade chiusi")
            return
        print(f"  {label}: N={s['n_closed']} (aperti {s['n_open']})  "
              f"WR={s['win_rate_pct']}%  PF={s['profit_factor']}  "
              f"avg_net={s['avg_net_pct_gain']}%  dur={s['avg_duration_days']}gg  "
              f"P&L_netto={s['total_net_eur']}EUR")
        print(f"       exit: {s['exit_reasons']}")

    for size in position_sizes:
        print(f"\n############ Size {size:.0f}EUR ############")
        for m in models:
            agg = aggregate(results[m], size, split_date=args.split_date)
            print(f"\n=== exit_model = {m} ===")
            _print_block("TUTTO ", agg['all'])
            if args.split_date:
                _print_block("IN    ", agg['in_sample'])
                _print_block("OUT   ", agg['out_sample'])


if __name__ == '__main__':
    main()
