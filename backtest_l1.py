"""
backtest_l1.py — Replay walk-forward con la VERA regola di uscita del portafoglio reale.

Scope: solo le famiglie toccate dallo Step 4 (2026-08-04):
  equity_sviluppati, mercati_emergenti, settoriali_growth, settoriali_difensivi,
  commodities, oro_metalli_preziosi, metalli_industriali

IMPORTANTE — due motori di uscita distinti nel codice:
  1) suggest_level() ha una propria logica di uscita (Regole A-F + downgrade per
     score/regime) usata SOLO per classificare il livello sulla dashboard
     (L1<->L2/L3 nell'universo monitorato). NON e' quella del portafoglio reale.
  2) check_l1_exit() e' la regola usata su etf_portfolio_entries (acquisti reali,
     monitor.py::_update_portfolio_l1_suggerito) — kill switch, poi STOP LOSS
     dinamico (calculate_sl_suggerito_l1, chiamato internamente da check_l1_exit),
     trailing EMA10<EMA20, stanchezza RSI, STOP GAIN dinamico (calculate_sg_suggerito_l1,
     anch'esso interno), ADX debole.

Questo script usa (2), la regola vera, per determinare quanto dura una posizione e
il suo rendimento. Replica fedelmente due comportamenti di produzione (non "corretti",
cosi' come girano oggi davvero):
  - ema20_series non e' mai popolato in monitor.py -> lo Stop Gain e' di fatto STATICO
    (nessun decadimento temporale, nessun aggiustamento sullo slope EMA20).
  - rsi_5 non e' mai popolato -> il trigger SG "rsi_momentum_esaurito" non scatta mai.
  - is_equity_commodity in check_l1_exit() confronta contro nomi di famiglia legacy
    (es. 'commodity') che non coincidono coi nomi YAML attuali (es. 'commodities') ->
    la Regola E (ADX debole) di fatto non scatta mai per le famiglie YAML.

L'INGRESSO resta invece guidato da suggest_level() (7/7 o 6/7 override + fondamenta),
perche' quella e' la logica che decide quando comprare.

Uso (dentro il container):
  python3 backtest_l1.py --start 2025-08-01 --days 800 --compare-min-buy 6
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
    'metalli_industriali',
}


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


def classify_exit(reason):
    if not reason:
        return 'UNKNOWN'
    prefix = reason.split(':')[0].split('_')[0]
    if reason.startswith('SL_'):
        return 'SL_dinamico'
    if reason.startswith('SG_'):
        return 'SG_dinamico'
    if reason.startswith('F_'):
        return 'F_kill_switch'
    if reason.startswith('B_'):
        return 'B_trailing'
    if reason.startswith('C_'):
        return 'C_stanchezza'
    if reason.startswith('E_'):
        return 'E_adx_debole'
    return reason


def simulate(analyzer, close_full, high_full, low_full, hist_index, test_dates):
    """Ingresso via suggest_level() (7/7 o 6/7), uscita via check_l1_exit() (vera regola portafoglio)."""
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
        price_today = float(close_slice.iloc[-1])

        with redirect_stdout(quiet):  # silenzia i print [L1-CHECK] della libreria
            result = analyzer.suggest_level(close_slice, current_level=3,
                                             high=high_slice, low=low_slice)
        c = result.get('conditions', {})

        if not holding:
            if result.get('suggested_level') == 1:
                holding = True
                entry_price = price_today
                entry_date = d.date().isoformat()
        else:
            market_data = {
                'close': price_today,
                'ema10': c.get('ema10_current'),
                'ema20': c.get('ema20_current'),
                'rsi_14': c.get('rsi'),
                'rsi_5': None,       # replica prod: mai popolato in monitor.py
                'rsi_14_prev': c.get('rsi_prev'),
                'adx': c.get('adx'),
                'daily_change_pct': c.get('daily_change_pct'),
                'ema20_series': None,  # replica prod: mai popolato -> SG statico
            }
            position_data = {'entry_price': entry_price, 'famiglia': analyzer.famiglia}
            with redirect_stdout(quiet):
                exit_check = analyzer.check_l1_exit(market_data, position_data)

            if exit_check.get('exit'):
                pct_gain = round((price_today / entry_price - 1) * 100, 3)
                trades.append({
                    'entry_date': entry_date, 'entry_price': entry_price,
                    'exit_date': d.date().isoformat(), 'exit_price': price_today,
                    'status': 'closed', 'pct_gain': pct_gain,
                    'exit_reason': exit_check.get('reason'),
                    'exit_rule': classify_exit(exit_check.get('reason')),
                })
                holding = False
                entry_price = None
                entry_date = None

    if holding:
        last_price = float(close_full.iloc[-1])
        pct_gain = round((last_price / entry_price - 1) * 100, 3)
        trades.append({
            'entry_date': entry_date, 'entry_price': entry_price,
            'exit_date': None, 'exit_price': last_price,
            'status': 'open', 'pct_gain': pct_gain,
            'exit_reason': None, 'exit_rule': None,
        })

    return trades


def backtest_ticker(fetcher, ticker, famiglia, start_date, fetch_days, min_buy_variants):
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
    gains = [t['pct_gain'] for t in closed]

    exit_rule_dist, exit_rule_duration, exit_rule_gain = {}, {}, {}
    for t in closed:
        code = t['exit_rule']
        exit_rule_dist[code] = exit_rule_dist.get(code, 0) + 1
        exit_rule_duration.setdefault(code, []).append(duration_days(t))
        exit_rule_gain.setdefault(code, []).append(t['pct_gain'])

    exit_rule_stats = {
        code: {
            'n': n,
            'pct_of_closed': round(100 * n / len(closed), 1) if closed else 0,
            'avg_duration_days': round(sum(exit_rule_duration[code]) / n, 1),
            'avg_pct_gain': round(sum(exit_rule_gain[code]) / n, 2),
        }
        for code, n in sorted(exit_rule_dist.items(), key=lambda kv: -kv[1])
    }

    return {
        'n_trades_total': len(all_trades),
        'n_trades_closed': len(closed),
        'n_trades_open': len(open_),
        'avg_duration_days': round(sum(durations) / len(durations), 1) if durations else None,
        'avg_pct_gain_closed': round(sum(gains) / len(gains), 2) if gains else None,
        'win_rate_pct': round(100 * sum(1 for g in gains if g > 0) / len(gains), 1) if gains else None,
        'sum_pct_gain_closed': round(sum(gains), 2) if gains else 0,
        'exit_rule_stats': exit_rule_stats,
        'trades': sorted(all_trades, key=lambda t: t['entry_date']),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', default=None, help='YYYY-MM-DD, default = oggi - 365 giorni')
    parser.add_argument('--days', type=int, default=800, help='giorni di storico da scaricare per ticker')
    parser.add_argument('--compare-min-buy', type=int, default=None,
                         help='se fornito, esegue anche una simulazione con min_buy_count forzato a questo valore')
    args = parser.parse_args()

    start_date = (datetime.strptime(args.start, '%Y-%m-%d').date()
                  if args.start else (datetime.now() - timedelta(days=365)).date())

    variants = [('native_7', None)]
    if args.compare_min_buy is not None:
        variants.append((f'override_{args.compare_min_buy}', args.compare_min_buy))

    print(f"BACKTEST L1 (uscita = check_l1_exit(), come il portafoglio reale) — dal {start_date.isoformat()} a oggi")
    print(f"Famiglie: {', '.join(sorted(TARGET_FAMILIES))}")
    print(f"Varianti: {[v[0] for v in variants]}")
    print("=" * 78)

    universe = load_universe()
    print(f"ETF nell'universo target: {len(universe)}\n")

    fetcher = ETFDataFetcher()
    results, errors = [], []

    for i, item in enumerate(universe, 1):
        ticker = item['ticker']
        print(f"[{i}/{len(universe)}] {ticker:14s} ({item['famiglia']})...", end=' ')
        try:
            res, err = backtest_ticker(fetcher, ticker, item['famiglia'], start_date, args.days, variants)
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
        print(f"  Durata media posizione chiusa: {agg['avg_duration_days']} giorni")
        print(f"  Rendimento medio per trade chiuso: {agg['avg_pct_gain_closed']}%")
        print(f"  Win rate: {agg['win_rate_pct']}%")
        print(f"  Somma rendimenti (equal-weight, non compounded): {agg['sum_pct_gain_closed']}%")
        print(f"  Distribuzione regole di uscita (su {agg['n_trades_closed']} chiusi):")
        for code, s in agg['exit_rule_stats'].items():
            print(f"    {code:16s} n={s['n']:4d} ({s['pct_of_closed']:5.1f}%)  "
                  f"durata media={s['avg_duration_days']:5.1f}gg  gain medio={s['avg_pct_gain']:+.2f}%")
        print()

    if len(variants) > 1:
        print("=" * 78)
        print("CONFRONTO DIRETTO")
        labels = [v[0] for v in variants]
        for k, nice in [('n_trades_total', 'Trade totali'), ('avg_duration_days', 'Durata media (gg)'),
                         ('avg_pct_gain_closed', 'Rendimento medio/trade (%)'),
                         ('win_rate_pct', 'Win rate (%)'),
                         ('sum_pct_gain_closed', 'Somma rendimenti equal-weight (%)')]:
            vals = '  vs  '.join(f"{lbl}={agg_by_variant[lbl][k]}" for lbl in labels)
            print(f"  {nice:35s}: {vals}")

    with open('data/backtest_l1_result.json', 'w', encoding='utf-8') as f:
        json.dump({
            'start_date': start_date.isoformat(),
            'variants': [v[0] for v in variants],
            'aggregates': agg_by_variant,
            'errors': errors,
        }, f, indent=2, ensure_ascii=False)
    print("\nRisultato completo salvato in data/backtest_l1_result.json")


if __name__ == '__main__':
    main()
