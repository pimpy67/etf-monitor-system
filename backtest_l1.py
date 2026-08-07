"""
backtest_l1.py — Replay walk-forward del PORTAFOGLIO REALE (v4, 2026-08-05).

Scope: tutte le 13 famiglie tradabili (esclusa monetario_liquidita, vedi TARGET_FAMILIES)

MODELLO CONFERMATO (precisato dall'utente il 2026-08-04/05) — il sistema NON esegue mai
ordini in automatico:
  - Un ETF entra in L1 (7/7 condizioni + fondamenta, via suggest_level()) -> acquisto
    manuale, aggiunto al portafoglio.
  - Ogni giorno il monitor ricalcola SL (calculate_sl_suggerito_l1) e TP
    (calculate_stop_gain_dynamic — l'UNICA funzione TP usata in produzione dopo il
    cleanup del 2026-08-05; calculate_sg_suggerito_l1 esisteva in parallelo con
    parametri diversi ma non era collegata a nessuna decisione reale, solo a
    check_l1_exit() che a sua volta non guida piu' l'uscita nel DB).
  - La posizione esce SOLO quando il prezzo tocca SL o TP — controllato UNA volta al
    giorno sul Close (come fa il monitor reale, non intraday su High/Low).
  - B (trailing), C (stanchezza), E (ADX debole), F (kill switch) NON sono vendite
    reali — sono solo segnali "interni" della dashboard (L1 -> L2/L3 nell'universo
    monitorato), non toccano il portafoglio. Il kill switch non e' un ordine a se':
    se il crollo buca lo SL gia' impostato esce da li', altrimenti nulla.
  - Costi: 5 EUR Directa acquisto + 5 EUR vendita (flat, indipendenti dalla size).
  - Tassazione: 26% flat sulle plusvalenze (solo sui trade in guadagno).
  - Size reale confermata dall'utente: si testano sia 5.000 EUR che 10.000 EUR
    per operazione (--position-sizes).

Uso (dentro il container):
  python3 backtest_l1.py --start 2025-08-01 --days 800 --compare-min-buy 6 --position-sizes 5000,10000
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
from database import Database

# Default: tutti i backtest leggono dal Golden Dataset congelato (etf_price_history_frozen),
# non da Yahoo Finance live — vedi CLAUDE.md "L1 -- Come Si Esce" per il perche' (indagine
# 3 vs 80 vs 1 trade, 2026-08-07: stesso codice+parametri, rifetch live = risultati diversi
# ogni run). Usa --live per il vecchio comportamento (fetch Yahoo diretto).
DEFAULT_FROZEN_BATCH = '2026-08-07'


class FrozenDataFetcher:
    """Legge OHLCV dal Golden Dataset congelato invece che da Yahoo Finance live.
    Stessa interfaccia di ETFDataFetcher.get_historical_data() cosi' backtest_ticker()
    non deve sapere quale fetcher sta usando."""

    def __init__(self, freeze_batch: str):
        self.freeze_batch = freeze_batch
        self.db = Database()
        self._live_fallback = ETFDataFetcher()

    def get_historical_data(self, ticker: str, days: int = 250) -> pd.DataFrame:
        df = self.db.get_frozen_ohlcv(ticker, self.freeze_batch)
        if df.empty:
            print(f"    [!] {ticker}: assente dal batch congelato '{self.freeze_batch}' "
                  f"— fallback su fetch live (risultato non riproducibile per questo ticker)")
            return self._live_fallback.get_historical_data(ticker, days=days)
        return df.tail(days) if days else df

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

CONDITION_KEYS = ['allineamento_ok', 'persistenza_ok', 'rsi_ok', 'distance_ok',
                   'adx_ok', 'macd_ok', 'space_residuo_ok']

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


def simulate(analyzer, close_full, high_full, low_full, hist_index, test_dates, require_macd=False):
    """Ingresso via suggest_level() (7/7 o 6/7). Uscita: SOLO SL o TP, ricalcolati e
    controllati una volta al giorno sul Close (come il monitor reale). Nessuna regola B/C/E/F.

    require_macd=True (2026-08-05, test "smart 6/7"): oltre a buy_count>=min_buy_count,
    richiede che macd_ok sia SEMPRE tra le condizioni vere — la condizione che puo'
    mancare deve essere un'altra. Test per verificare se rendere il MACD obbligatorio
    anche sotto 7/7 migliora la qualita' dei trade (ipotesi emersa dalla segmentazione
    win-rate per condizione mancante, vedi CLAUDE.md)."""
    holding = False
    entry_price = None
    entry_date = None
    entry_buy_count = None
    entry_missing = None
    entry_features = None
    trades = []

    quiet = io.StringIO()
    for d in test_dates:
        pos = hist_index.get_loc(d)
        close_slice = close_full.iloc[:pos + 1]
        high_slice = high_full.iloc[:pos + 1] if high_full is not None else None
        low_slice = low_full.iloc[:pos + 1] if low_full is not None else None
        close_today = float(close_slice.iloc[-1])

        if not holding:
            with redirect_stdout(quiet):  # silenzia i print [L1-CHECK] della libreria
                result = analyzer.suggest_level(close_slice, current_level=3,
                                                 high=high_slice, low=low_slice)
            if result.get('suggested_level') == 1:
                c = result.get('conditions', {})
                if require_macd and not c.get('macd_ok', False):
                    continue  # smart 6/7: la condizione mancante non puo' essere il MACD
                holding = True
                entry_price = close_today
                entry_date = d.date().isoformat()
                entry_buy_count = result.get('buy_count')
                entry_missing = [k for k in CONDITION_KEYS if not c.get(k, True)]
                # Feature extraction (2026-08-05): valori numerici assoluti all'ingresso,
                # gia' calcolati da suggest_level() e presenti in 'conditions' — nessuna
                # modifica al motore reale, solo cattura di dati gia' esistenti per poter
                # confrontare dopo le "impronte digitali" di trade vincenti vs perdenti.
                sma200_v = c.get('sma200_current')
                entry_features = {
                    'adx':            c.get('adx'),
                    'rsi':            c.get('rsi'),
                    'ema20_slope':    c.get('ema20_slope'),
                    'dist_ema20':     c.get('dist_ema20'),
                    'dist_sma200':    round(100 * (close_today - sma200_v) / sma200_v, 2)
                                      if sma200_v else None,
                    'atr_normalized': c.get('atr_normalized'),
                }
        else:
            # Stesse funzioni e stessa logica di monitor.py::_update_portfolio_l1_suggerito()
            # dopo il fix 2026-08-05: SL = calculate_sl_suggerito_l1, TP = calculate_stop_gain_dynamic
            # (unica funzione TP usata in produzione — calculate_sg_suggerito_l1 non e' piu'
            # collegata a nessuna decisione reale). Check una volta al giorno sul Close, come
            # fa il monitor (non intraday su High/Low: il sistema valuta una volta al giorno).
            ema20_series = analyzer._ema(close_slice, 20).tail(10)
            ema20_today = float(ema20_series.iloc[-1])

            sl_data = analyzer.calculate_sl_suggerito_l1(entry_price, close_today, ema20_today)
            sl = sl_data.get('sl_suggerito')

            sg_data = analyzer.calculate_stop_gain_dynamic(entry_price, close_today, ema20_series, analyzer.p)
            tp = entry_price * (1 + sg_data.get('target_pct', 0.0))

            sl_hit = sl is not None and close_today <= sl
            tp_hit = bool(sg_data.get('trigger'))

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
                    'exit_reason': exit_reason,
                    'entry_buy_count': entry_buy_count, 'entry_missing': entry_missing,
                    'entry_features': entry_features,
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
            'entry_buy_count': entry_buy_count, 'entry_missing': entry_missing,
            'entry_features': entry_features,
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


def backtest_ticker(fetcher, ticker, famiglia, start_date, fetch_days, min_buy_variants):
    """Simula UNA volta per ticker/variante (solo % lordi) — i costi/tasse si
    applicano dopo, per size diverse, senza dover ri-simulare."""
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
    for label, override, require_macd in min_buy_variants:
        analyzer = make_analyzer(famiglia, override)
        trades = simulate(analyzer, close_full, high_full, low_full, hist.index, test_dates,
                           require_macd=require_macd)
        per_variant[label] = {'n_trades': len(trades), 'trades': trades}

    return {'ticker': ticker, 'famiglia': famiglia, 'variants': per_variant}, None


def aggregate(results, label, position_size):
    all_trades = []
    for r in results:
        for t in r['variants'][label]['trades']:
            t = apply_costs_and_tax(dict(t), position_size)  # copia: non mutare il trade condiviso tra size diverse
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


def analyze_missing_conditions(results, label):
    """FASE 2 — per i trade entrati a 6/7 (non 7/7), quale delle 7 condizioni
    mancava all'ingresso? Serve a capire se un'eventuale futura condizione ADX
    piu' stretta avrebbe davvero filtrato i falsi segnali del 2024, invece di
    assumerlo. Non tocca la simulazione: e' solo diagnostica sui trade gia' aperti."""
    all_trades = []
    for r in results:
        for t in r['variants'][label]['trades']:
            all_trades.append({**t, 'ticker': r['ticker'], 'famiglia': r['famiglia']})

    six_of_seven = [t for t in all_trades if t.get('entry_buy_count') == 6]
    print(f"Trade entrati esattamente a 6/7 (esclusi quelli a 7/7): {len(six_of_seven)} su {len(all_trades)} totali\n")

    cond_count = {}
    for t in six_of_seven:
        missing = t.get('entry_missing') or []
        for c in missing:
            cond_count[c] = cond_count.get(c, 0) + 1
    print("Condizione mancante — distribuzione su tutti i trade 6/7:")
    for c, n in sorted(cond_count.items(), key=lambda kv: -kv[1]):
        pct = round(100 * n / len(six_of_seven), 1) if six_of_seven else 0
        print(f"  {c:20s} mancante in {n:4d} trade ({pct}%)")

    print("\nCondizione mancante — per anno di ingresso:")
    years = sorted(set(t['entry_date'][:4] for t in six_of_seven))
    for y in years:
        yr_trades = [t for t in six_of_seven if t['entry_date'][:4] == y]
        yr_cond = {}
        for t in yr_trades:
            for c in (t.get('entry_missing') or []):
                yr_cond[c] = yr_cond.get(c, 0) + 1
        top = sorted(yr_cond.items(), key=lambda kv: -kv[1])
        top_str = ', '.join(f"{c}={n}" for c, n in top)
        print(f"  {y}: {len(yr_trades)} trade — {top_str}")
    print()


def analyze_entry_features(results, label):
    """Feature extraction (2026-08-05, proposta utente): confronta i valori numerici
    assoluti all'ingresso (ADX, RSI, pendenza EMA20, distanza da EMA20/SMA200, ATR%
    normalizzato) tra i trade 6/7 finiti in Take Profit e quelli finiti in Stop Loss —
    per capire se esiste una combinazione di soglie continue che discrimina i trade
    vincenti meglio del semplice conteggio booleano di condizioni vere/false. I valori
    sono gia' calcolati da suggest_level() (nessuna modifica al motore reale), solo
    catturati in piu' per ogni trade in simulate()."""
    all_trades = []
    for r in results:
        for t in r['variants'][label]['trades']:
            if t.get('status') == 'closed' and t.get('entry_buy_count') == 6:
                all_trades.append(t)

    tp_trades = [t for t in all_trades if t.get('exit_reason') == 'TP']
    sl_trades = [t for t in all_trades if t.get('exit_reason') == 'SL']
    print(f"Feature extraction sui trade 6/7 chiusi: {len(tp_trades)} finiti in TP vs "
          f"{len(sl_trades)} finiti in SL\n")

    feature_keys = ['adx', 'rsi', 'ema20_slope', 'dist_ema20', 'dist_sma200', 'atr_normalized']

    def avg(trades, key):
        vals = [t['entry_features'][key] for t in trades
                if t.get('entry_features') and t['entry_features'].get(key) is not None]
        return (round(sum(vals) / len(vals), 4) if vals else None), len(vals)

    print(f"{'Parametro ingresso':20s} {'Media TP':>14s} {'Media SL':>14s} {'Divario (TP-SL)':>18s}")
    for k in feature_keys:
        avg_tp, n_tp = avg(tp_trades, k)
        avg_sl, n_sl = avg(sl_trades, k)
        divario = round(avg_tp - avg_sl, 4) if (avg_tp is not None and avg_sl is not None) else None
        tp_str = f"{avg_tp} (n={n_tp})" if avg_tp is not None else f"n/d (n={n_tp})"
        sl_str = f"{avg_sl} (n={n_sl})" if avg_sl is not None else f"n/d (n={n_sl})"
        print(f"{k:20s} {tp_str:>20s} {sl_str:>20s} {str(divario):>12s}")
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', default=None, help='YYYY-MM-DD, default = oggi - 365 giorni')
    parser.add_argument('--days', type=int, default=800, help='giorni di storico da scaricare per ticker')
    parser.add_argument('--compare-min-buy', type=int, default=None,
                         help='se fornito, esegue anche una simulazione con min_buy_count forzato a questo valore')
    parser.add_argument('--position-sizes', default='5000,10000',
                         help='capitali ipotetici per trade (EUR, separati da virgola), per costi/tasse in valore assoluto')
    parser.add_argument('--live', action='store_true',
                         help='usa fetch Yahoo Finance live invece del Golden Dataset congelato '
                              '(risultati NON riproducibili run-to-run, vedi CLAUDE.md)')
    parser.add_argument('--frozen-batch', default=DEFAULT_FROZEN_BATCH,
                         help=f'quale snapshot congelato usare (default: {DEFAULT_FROZEN_BATCH})')
    args = parser.parse_args()
    position_sizes = [float(x) for x in args.position_sizes.split(',')]

    start_date = (datetime.strptime(args.start, '%Y-%m-%d').date()
                  if args.start else (datetime.now() - timedelta(days=365)).date())

    variants = [('native_7', None, False)]
    if args.compare_min_buy is not None:
        variants.append((f'override_{args.compare_min_buy}', args.compare_min_buy, False))
        # Test 2026-08-05: "smart 6/7" — stessa soglia, ma MACD non puo' mai essere
        # la condizione mancante (vedi CLAUDE.md, follow-up segmentazione win rate).
        variants.append((f'smart_{args.compare_min_buy}_macd', args.compare_min_buy, True))

    print(f"BACKTEST L1 v4 — portafoglio reale (SL/TP giornalieri su Close, no B/C/E/F) — dal {start_date.isoformat()} a oggi")
    print(f"Famiglie: {', '.join(sorted(TARGET_FAMILIES))}")
    print(f"Varianti: {[v[0] for v in variants]}  |  Position sizes: {position_sizes}EUR  |  "
          f"Costi Directa: {DIRECTA_FEE_BUY}+{DIRECTA_FEE_SELL}EUR  |  Tax: {TAX_RATE:.0%}")
    if args.live:
        print("Fonte dati: Yahoo Finance LIVE — risultati NON riproducibili run-to-run")
    else:
        print(f"Fonte dati: Golden Dataset congelato, batch '{args.frozen_batch}' — riproducibile")
    print("=" * 78)

    universe = load_universe()
    print(f"ETF nell'universo target: {len(universe)}\n")

    fetcher = ETFDataFetcher() if args.live else FrozenDataFetcher(args.frozen_batch)
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

    if args.compare_min_buy is not None:
        print("=" * 78)
        print(f"FASE 2 — ANALISI CONDIZIONI MANCANTI (variante override_{args.compare_min_buy})")
        print("=" * 78)
        analyze_missing_conditions(results, f'override_{args.compare_min_buy}')

        print("=" * 78)
        print(f"FASE 2 — FEATURE EXTRACTION TP vs SL (variante override_{args.compare_min_buy})")
        print("=" * 78)
        analyze_entry_features(results, f'override_{args.compare_min_buy}')

    agg_by_size = {}
    for size in position_sizes:
        agg_by_variant = {}
        for label, _, _ in variants:
            agg = aggregate(results, label, size)
            agg_by_variant[label] = agg
            print(f"--- Variante {label} | Size {size}EUR ---")
            print(f"  Trade totali: {agg['n_trades_total']}  (chiusi: {agg['n_trades_closed']}, ancora aperti: {agg['n_trades_open']})")
            print(f"  Uscite: {agg['n_exit_sl']} via SL, {agg['n_exit_tp']} via TP")
            print(f"  Durata media posizione chiusa: {agg['avg_duration_days']} giorni")
            print(f"  Rendimento medio LORDO per trade: {agg['avg_gross_pct_gain']}%")
            print(f"  Rendimento medio NETTO per trade (dopo costi+tasse): {agg['avg_net_pct_gain']}%")
            print(f"  Win rate (netto): {agg['win_rate_pct']}%")
            print(f"  Somma rendimenti LORDI (equal-weight, non compounded): {agg['sum_gross_pct_gain']}%")
            print(f"  Somma rendimenti NETTI (equal-weight, non compounded): {agg['sum_net_pct_gain']}%")
            print(f"  P&L netto totale su {size}EUR/trade: {agg['total_net_eur']}EUR "
                  f"(costi Directa: {agg['total_fees_eur']}EUR, tasse: {agg['total_tax_eur']}EUR)")
            print()
        agg_by_size[size] = agg_by_variant

        if len(variants) > 1:
            print(f"--- CONFRONTO DIRETTO (size {size}EUR) ---")
            labels = [v[0] for v in variants]
            for k, nice in [('n_trades_total', 'Trade totali'), ('avg_duration_days', 'Durata media (gg)'),
                             ('avg_gross_pct_gain', 'Rendimento medio LORDO/trade (%)'),
                             ('avg_net_pct_gain', 'Rendimento medio NETTO/trade (%)'),
                             ('win_rate_pct', 'Win rate netto (%)'),
                             ('total_net_eur', f'P&L netto totale su {size}EUR/trade (EUR)')]:
                vals = '  vs  '.join(f"{lbl}={agg_by_variant[lbl][k]}" for lbl in labels)
                print(f"  {nice:45s}: {vals}")
            print()

    with open('data/backtest_l1_result.json', 'w', encoding='utf-8') as f:
        json.dump({
            'start_date': start_date.isoformat(),
            'position_sizes': position_sizes,
            'directa_fee_buy': DIRECTA_FEE_BUY,
            'directa_fee_sell': DIRECTA_FEE_SELL,
            'tax_rate': TAX_RATE,
            'variants': [v[0] for v in variants],
            'aggregates_by_size': {str(s): a for s, a in agg_by_size.items()},
            'errors': errors,
        }, f, indent=2, ensure_ascii=False)
    print("\nRisultato completo salvato in data/backtest_l1_result.json")


if __name__ == '__main__':
    main()
