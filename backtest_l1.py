"""
backtest_l1.py — Replay walk-forward del PORTAFOGLIO REALE (2026-08-04, v3).

Scope: tutte le 13 famiglie tradabili (esclusa monetario_liquidita, vedi TARGET_FAMILIES)

MODELLO CORRETTO (precisato dall'utente il 2026-08-04) — il sistema NON esegue mai
ordini in automatico:
  - Un ETF entra in L1 (7/7 condizioni + fondamenta, via suggest_level()) -> acquisto
    manuale, aggiunto al portafoglio.
  - Ogni giorno il monitor ricalcola SL (calculate_sl_suggerito_l1) e TP
    (calculate_sg_suggerito_l1) e li manda via email. L'utente li aggiorna
    manualmente su Directa.
  - La posizione esce SOLO quando il prezzo tocca SL o TP a mercato (intraday,
    quindi confrontato contro Low/High del giorno, non solo il Close).
  - B (trailing), C (stanchezza), E (ADX debole), F (kill switch) NON sono vendite
    reali — fanno solo uscire l'ETF dalla lista L1 in dashboard (non e' piu' un
    candidato per un NUOVO acquisto). Il kill switch non e' un ordine a se': se il
    crollo e' abbastanza forte da bucare lo SL gia' impostato, esce da li'.
  - Costi: 5 EUR Directa acquisto + 5 EUR vendita (flat, indipendenti dalla size).
  - Tassazione: 26% flat sulle plusvalenze (solo sui trade in guadagno).

Uso (dentro il container):
  python3 backtest_l1.py --start 2025-08-01 --days 800 --compare-min-buy 6 --position-size 5000
"""
import sys
sys.path.insert(0, '/app')

import argparse
import io
import json
import time
from contextlib import redirect_stdout
from datetime import datetime, timedelta

import pandas as pd

from technical_analysis import ETFTechnicalAnalyzer
from data_fetcher import ETFDataFetcher

TARGET_FAMILIES = {
    'equity_sviluppati', 'mercati_emergenti', 'settoriali_growth',
    'settoriali_difensivi', 'commodities', 'oro_metalli_preziosi',
    'metalli_industriali', 'bond_governativi', 'bond_corp_hy_em',
    'real_estate_reit', 'crypto_digital_assets', 'leva_single_stock',
    'private_equity_buffer',
    # monetario_liquidita esclusa: rsi_entry_low/adx_entry sono null nello YAML,
    # suggest_level() andrebbe in errore sul confronto RSI (stesso motivo per cui
    # analyze_etf() la esclude esplicitamente via money_market_tickers). XEON non
    # e' comunque un candidato L1, e' il parcheggio "piede dentro" del sistema.
}

DIRECTA_FEE_BUY = 5.0
DIRECTA_FEE_SELL = 5.0
TAX_RATE = 0.26


def load_universe(excel_path='etf_monitoraggio.xlsx'):
    df = pd.read_excel(excel_path, sheet_name='ETF')
    rows = []
    for _, row in df.iterrows():
        ticker = str(row.get('Ticker', '')).strip()
        categoria = str(row.get('Categoria', ''))
        if not ticker or ticker.lower() == 'nan':
            continue
        famiglia = ETFTechnicalAnalyzer.detect_family(categoria)
        if famiglia in TARGET_FAMILIES:
            rows.append({'ticker': ticker, 'famiglia': famiglia})
    return rows


def make_analyzer(famiglia, min_buy_override=None):
    analyzer = ETFTechnicalAnalyzer(famiglia=famiglia)
    if min_buy_override is not None:
        analyzer.p = dict(analyzer.p)  # copia locale, non tocca la cache di classe condivisa
        analyzer.p['min_buy_count'] = min_buy_override
    return analyzer


def _rsi_period(series: pd.Series, period: int = 5) -> pd.Series:
    delta  = series.diff()
    gains  = delta.where(delta > 0, 0.0)
    losses = (-delta).where(delta < 0, 0.0)
    ag = gains.ewm(com=period - 1, min_periods=period).mean()
    al = losses.ewm(com=period - 1, min_periods=period).mean()
    rs = ag / al.replace(0, float('nan'))
    return 100 - (100 / (1 + rs))


def simulate(analyzer, close_full, high_full, low_full, hist_index, test_dates):
    """Ingresso via suggest_level() (7/7 o 6/7). Uscita: SOLO SL o TP, ricalcolati
    ogni giorno, toccati intraday (Low<=SL o High>=TP). Nessuna regola B/C/E/F."""
    holding = False
    entry_price = None
    entry_date = None
    trades = []

    quiet = io.StringIO()
    for d in test_dates:
        pos = hist_index.get_loc(d)
        close_slice = close_full.iloc[:pos + 1]
        high_slice = high_full.iloc[:pos + 1] if high_full is not None else None
        low_slice = low_full.iloc[:pos + 1] if low_full is not None else None
        close_today = float(close_slice.iloc[-1])
        high_today = float(high_slice.iloc[-1]) if high_slice is not None else close_today
        low_today = float(low_slice.iloc[-1]) if low_slice is not None else close_today

        if not holding:
            with redirect_stdout(quiet):  # silenzia i print [L1-CHECK] della libreria
                result = analyzer.suggest_level(close_slice, current_level=3,
                                                 high=high_slice, low=low_slice)
            if result.get('suggested_level') == 1:
                holding = True
                entry_price = close_today
                entry_date = d.date().isoformat()
        else:
            ema20_series = analyzer._ema(close_slice, 20)
            ema20_today = float(ema20_series.iloc[-1])

            sl_data = analyzer.calculate_sl_suggerito_l1(entry_price, close_today, ema20_today)
            sl = sl_data.get('sl_suggerito')

            rsi5_series = _rsi_period(close_slice, period=5)
            rsi_5 = float(rsi5_series.iloc[-1]) if pd.notna(rsi5_series.iloc[-1]) else None
            sg_data = analyzer.calculate_sg_suggerito_l1(entry_price, close_today,
                                                           ema20_series.tail(10), rsi_5)
            tp = sg_data.get('sg_suggerito')

            sl_hit = sl is not None and low_today <= sl
            tp_hit = (tp is not None and high_today >= tp) or sg_data.get('should_exit', False)

            exit_price = None
            exit_reason = None
            if sl_hit:
                exit_price = sl  # esecuzione stop: si assume eseguito al livello SL
                exit_reason = 'SL'
            elif tp_hit:
                exit_price = tp if (tp is not None and high_today >= tp) else close_today
                exit_reason = 'TP'

            if exit_reason:
                gross_pct = round((exit_price / entry_price - 1) * 100, 3)
                trades.append({
                    'entry_date': entry_date, 'entry_price': entry_price,
                    'exit_date': d.date().isoformat(), 'exit_price': exit_price,
                    'status': 'closed', 'gross_pct_gain': gross_pct,
                    'exit_reason': exit_reason,
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
            'exit_reason': None,
        })

    return trades


def apply_costs_and_tax(trade, position_size):
    """Calcola rendimento netto: costi Directa fissi + tassazione 26% sulle plusvalenze."""
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


def backtest_ticker(fetcher, ticker, famiglia, start_date, fetch_days, min_buy_variants, position_size):
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

    per_variant = {}
    for label, override in min_buy_variants:
        analyzer = make_analyzer(famiglia, override)
        trades = simulate(analyzer, close_full, high_full, low_full, hist.index, test_dates)
        trades = [apply_costs_and_tax(t, position_size) for t in trades]
        per_variant[label] = {'n_trades': len(trades), 'trades': trades}

    return {'ticker': ticker, 'famiglia': famiglia, 'variants': per_variant}, None


def aggregate(results, label):
    all_trades = []
    for r in results:
        for t in r['variants'][label]['trades']:
            all_trades.append({**t, 'ticker': r['ticker'], 'famiglia': r['famiglia']})

    closed = [t for t in all_trades if t['status'] == 'closed']
    open_ = [t for t in all_trades if t['status'] == 'open']

    def duration_days(t):
        ed = datetime.strptime(t['entry_date'], '%Y-%m-%d').date()
        xd = (datetime.strptime(t['exit_date'], '%Y-%m-%d').date() if t['exit_date']
              else datetime.now().date())
        return (xd - ed).days

    durations = [duration_days(t) for t in closed]
    gross_gains = [t['gross_pct_gain'] for t in closed]
    net_gains = [t['net_pct_gain'] for t in closed]
    net_eur = [t['net_gain_eur'] for t in closed]

    sl_trades = [t for t in closed if t['exit_reason'] == 'SL']
    tp_trades = [t for t in closed if t['exit_reason'] == 'TP']

    return {
        'n_trades_total': len(all_trades),
        'n_trades_closed': len(closed),
        'n_trades_open': len(open_),
        'n_exit_sl': len(sl_trades),
        'n_exit_tp': len(tp_trades),
        'avg_duration_days': round(sum(durations) / len(durations), 1) if durations else None,
        'avg_gross_pct_gain': round(sum(gross_gains) / len(gross_gains), 2) if gross_gains else None,
        'avg_net_pct_gain': round(sum(net_gains) / len(net_gains), 2) if net_gains else None,
        'win_rate_pct': round(100 * sum(1 for g in net_gains if g > 0) / len(net_gains), 1) if net_gains else None,
        'sum_gross_pct_gain': round(sum(gross_gains), 2) if gross_gains else 0,
        'sum_net_pct_gain': round(sum(net_gains), 2) if net_gains else 0,
        'total_net_eur': round(sum(net_eur), 2) if net_eur else 0,
        'total_fees_eur': round(sum(t['fees_eur'] for t in closed), 2) if closed else 0,
        'total_tax_eur': round(sum(t['tax_eur'] for t in closed), 2) if closed else 0,
        'trades': sorted(all_trades, key=lambda t: t['entry_date']),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', default=None, help='YYYY-MM-DD, default = oggi - 365 giorni')
    parser.add_argument('--days', type=int, default=800, help='giorni di storico da scaricare per ticker')
    parser.add_argument('--compare-min-buy', type=int, default=None,
                         help='se fornito, esegue anche una simulazione con min_buy_count forzato a questo valore')
    parser.add_argument('--position-size', type=float, default=5000.0,
                         help='capitale ipotetico per trade (EUR), per calcolare costi/tasse in valore assoluto')
    args = parser.parse_args()

    start_date = (datetime.strptime(args.start, '%Y-%m-%d').date()
                  if args.start else (datetime.now() - timedelta(days=365)).date())

    variants = [('native_7', None)]
    if args.compare_min_buy is not None:
        variants.append((f'override_{args.compare_min_buy}', args.compare_min_buy))

    print(f"BACKTEST L1 v3 — portafoglio reale (SL/TP giornalieri, no B/C/E/F) — dal {start_date.isoformat()} a oggi")
    print(f"Famiglie: {', '.join(sorted(TARGET_FAMILIES))}")
    print(f"Varianti: {[v[0] for v in variants]}  |  Position size: {args.position_size}EUR  |  "
          f"Costi Directa: {DIRECTA_FEE_BUY}+{DIRECTA_FEE_SELL}EUR  |  Tax: {TAX_RATE:.0%}")
    print("=" * 78)

    universe = load_universe()
    print(f"ETF nell'universo target: {len(universe)}\n")

    fetcher = ETFDataFetcher()
    results, errors = [], []

    for i, item in enumerate(universe, 1):
        ticker = item['ticker']
        print(f"[{i}/{len(universe)}] {ticker:14s} ({item['famiglia']})...", end=' ')
        try:
            res, err = backtest_ticker(fetcher, ticker, item['famiglia'], start_date, args.days,
                                        variants, args.position_size)
        except Exception as e:
            res, err = None, str(e)
        if err:
            print(f"SKIP — {err}")
            errors.append({'ticker': ticker, 'error': err})
            continue
        summary = ' | '.join(f"{lbl}: {res['variants'][lbl]['n_trades']} trade" for lbl in res['variants'])
        print(summary)
        results.append(res)
        time.sleep(0.3)

    print("\n" + "=" * 78)
    print(f"ETF testati: {len(results)}  |  skip per storico insufficiente: {len(errors)}\n")

    agg_by_variant = {}
    for label, _ in variants:
        agg = aggregate(results, label)
        agg_by_variant[label] = agg
        print(f"--- Variante {label} ---")
        print(f"  Trade totali: {agg['n_trades_total']}  (chiusi: {agg['n_trades_closed']}, ancora aperti: {agg['n_trades_open']})")
        print(f"  Uscite: {agg['n_exit_sl']} via SL, {agg['n_exit_tp']} via TP")
        print(f"  Durata media posizione chiusa: {agg['avg_duration_days']} giorni")
        print(f"  Rendimento medio LORDO per trade: {agg['avg_gross_pct_gain']}%")
        print(f"  Rendimento medio NETTO per trade (dopo costi+tasse): {agg['avg_net_pct_gain']}%")
        print(f"  Win rate (netto): {agg['win_rate_pct']}%")
        print(f"  Somma rendimenti LORDI (equal-weight, non compounded): {agg['sum_gross_pct_gain']}%")
        print(f"  Somma rendimenti NETTI (equal-weight, non compounded): {agg['sum_net_pct_gain']}%")
        print(f"  P&L netto totale su {args.position_size}EUR/trade: {agg['total_net_eur']}EUR "
              f"(costi Directa: {agg['total_fees_eur']}EUR, tasse: {agg['total_tax_eur']}EUR)")
        print()

    if len(variants) > 1:
        print("=" * 78)
        print("CONFRONTO DIRETTO")
        labels = [v[0] for v in variants]
        for k, nice in [('n_trades_total', 'Trade totali'), ('avg_duration_days', 'Durata media (gg)'),
                         ('avg_gross_pct_gain', 'Rendimento medio LORDO/trade (%)'),
                         ('avg_net_pct_gain', 'Rendimento medio NETTO/trade (%)'),
                         ('win_rate_pct', 'Win rate netto (%)'),
                         ('total_net_eur', f'P&L netto totale su {args.position_size}EUR/trade (EUR)')]:
            vals = '  vs  '.join(f"{lbl}={agg_by_variant[lbl][k]}" for lbl in labels)
            print(f"  {nice:45s}: {vals}")

    with open('data/backtest_l1_result.json', 'w', encoding='utf-8') as f:
        json.dump({
            'start_date': start_date.isoformat(),
            'position_size': args.position_size,
            'directa_fee_buy': DIRECTA_FEE_BUY,
            'directa_fee_sell': DIRECTA_FEE_SELL,
            'tax_rate': TAX_RATE,
            'variants': [v[0] for v in variants],
            'aggregates': agg_by_variant,
            'errors': errors,
        }, f, indent=2, ensure_ascii=False)
    print("\nRisultato completo salvato in data/backtest_l1_result.json")


if __name__ == '__main__':
    main()
