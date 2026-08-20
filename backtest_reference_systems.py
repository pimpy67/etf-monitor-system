"""
backtest_reference_systems.py — confronto tra il nostro sistema (native_7 / smart_6_macd /
CANDIDATE_MODEL_L0) e 4 sistemi di trading "professionali" pubblici, sullo stesso Golden
Dataset congelato e con la stessa metodologia di costi/tasse/split IS-OOS gia' usata dal
resto del progetto (backtest_l1.py, optimize_hyperparameters.py).

Sistemi implementati (definizioni fissate dall'utente, non improvvisate):

  1. GOLDEN CROSS (SMA50/SMA200)
     Entry: SMA50 > SMA200 (stato, non solo il giorno dell'incrocio — vedi nota metodologica).
     Exit:  SMA50 < SMA200.
     Nessun filtro aggiuntivo, nessuna calibrazione per famiglia.

  2. RSI2 MEAN REVERSION (Larry Connors)
     Filtro di trend: price > SMA200.
     Entry: RSI(2) < 10 mentre price > SMA200.
     Exit:  RSI(2) > 70, OPPURE timeout di sicurezza a 20 giorni di trading (scelta
            dell'implementatore, non nella regola originale di Connors — documentata qui
            e nel report finale: senza un timeout, un trade puo' restare aperto per mesi
            se il prezzo si muove lateralmente sopra RSI(2)=70 senza mai romperlo).

  3. TURTLE TRADING SYSTEM 1 + SYSTEM 2, peso 50/50, solo long
     S1 (breve): entry = nuovo massimo dei close a 20gg (esclude oggi), exit = nuovo minimo
                 dei close a 10gg. Filtro anti-whipsaw: se l'ultimo trade S1 chiuso e' stato
                 in perdita, salta il segnale S1 immediatamente successivo.
     S2 (lungo): entry = nuovo massimo dei close a 55gg, exit = nuovo minimo dei close a
                 20gg. Nessun filtro.
     Peso 50/50: ciascun sistema opera con meta' del notional per trade (es. 5.000€ ciascuno
     su un test a 10.000€ complessivi) — il drag dei 10€ Directa fissi pesa quindi il doppio
     in termini percentuali rispetto a un trade a notional pieno, correttamente.

  4. FABER TREND TIMING (per-ETF, mensile) — NON e' la vera rotazione GEM/Dual Momentum
     (quella ruota tra SPY/ACWX/AGG, non ha senso applicata a 236 ETF individuali). Qui:
     resample mensile del close di ciascun ETF, SMA a 10 mesi, hold quando
     close_mensile > SMA10m, cash altrimenti. Ogni ETF e' un libro indipendente.

## Nota metodologica — "stato" vs "evento", e niente carryover tra finestre IS/OOS

Le simulazioni IS (2023-08-05..2025-08-05) e OOS (2025-08-05..2026-08-05) girano SEPARATE,
ciascuna parte "flat" (nessuna posizione ereditata dall'altra finestra) — stessa convenzione
gia' usata da backtest_l1.py/optimize_hyperparameters.py per native_7/smart_6_macd (li' e'
un effetto collaterale del loro essere sistemi "a soglia": suggest_level() valuta le 7
condizioni fresche ogni giorno, quindi se sono gia' tutte vere al giorno 1 della finestra
si entra subito).

Per essere metodologicamente onesti E comparabili a quella stessa convenzione:
  - Golden Cross e Faber sono trattati come sistemi "a stato" (analogo a suggest_level()):
    si controlla se lo stato e' vero OGGI, non se l'incrocio e' avvenuto oggi. Quindi se lo
    stato e' gia' vero al primo giorno della finestra (es. SMA50 gia' sopra SMA200 prima
    dell'inizio della finestra), si entra comunque il primo giorno — stesso comportamento
    del gate a 7 condizioni.
  - RSI2 e' anch'esso "a stato" per l'entry (RSI2<10 oggi, non "e' appena sceso sotto 10").
  - Turtle (S1/S2) e' invece un sistema a EVENTO per costruzione originale: entra solo il
    giorno preciso in cui il close fa un nuovo massimo N-gg, non "mentre" il prezzo e' sopra
    quel massimo (altrimenti si ririentrerebbe ogni giorno). Conseguenza onesta da segnalare:
    un breakout avvenuto PRIMA dell'inizio della finestra OOS non viene ripreso in OOS anche
    se la posizione "virtuale" sarebbe ancora aperta — e' una sotto-stima dei trade Turtle in
    OOS rispetto a Golden Cross/RSI2/Faber, methodologicamente diversa ma intrinseca alla
    natura event-driven del sistema originale (non e' un bug, e' la definizione di Donchian
    breakout).

## Riuso, non reimplementazione

Tutte le metriche finali (win rate, Profit Factor, Max Drawdown, expectancy, P&L netto)
sono calcolate dalle STESSE funzioni gia' validate del progetto:
  - apply_costs_and_tax() / aggregate()  — da backtest_l1.py
  - extra_metrics()                      — da optimize_hyperparameters.py
Questo script produce solo le liste di trade (stesso formato dict di backtest_l1.py:
entry_date/entry_price/exit_date/exit_price/status/gross_pct_gain/exit_reason), poi le passa
a quelle funzioni invariate.

## Esecuzione

  python3 backtest_reference_systems.py --smoke     # 8 ticker (incl. WLDC.PA), sanity check
  python3 backtest_reference_systems.py              # run completo, tutti gli ETF in Excel
"""
import sys
sys.path.insert(0, '/app')

import argparse
import json
import time
from datetime import datetime

import numpy as np
import pandas as pd

from technical_analysis import ETFTechnicalAnalyzer
from backtest_l1 import FrozenDataFetcher, DEFAULT_FROZEN_BATCH, apply_costs_and_tax, aggregate
from optimize_hyperparameters import extra_metrics

IS_START = datetime(2023, 8, 5).date()
IS_END   = datetime(2025, 8, 5).date()
OOS_END  = datetime(2026, 8, 5).date()

SMOKE_TICKERS = ['WLDC.PA', 'SWDA.L', 'IWDA.AS', 'CSSPX.MI', 'VWCE.DE',
                  'EIMI.L', 'IUSA.L', 'PHAU.L']


# ─────────────────────────────── Universo ──────────────────────────────────

def load_universe_all(excel_path='etf_monitoraggio.xlsx'):
    """Tutti gli ETF in Excel, nessun filtro di famiglia — questi 4 sistemi non
    usano parametri per famiglia. detect_family() e' solo per breakdown nel report."""
    df = pd.read_excel(excel_path, sheet_name='ETF')
    rows = []
    for _, row in df.iterrows():
        ticker = str(row.get('Ticker', '')).strip()
        categoria = str(row.get('Categoria', ''))
        if not ticker or ticker.lower() == 'nan':
            continue
        try:
            famiglia = ETFTechnicalAnalyzer.detect_family(categoria)
        except Exception:
            famiglia = 'unknown'
        rows.append({'ticker': ticker, 'famiglia': famiglia})
    return rows


# ────────────────────────── Indicatori vettorizzati ─────────────────────────
# Stessa convenzione RSI Wilder-smoothing di technical_analysis.py::_rsi()
# (com=period-1), solo parametrizzata sul periodo.

def _sma(s, period):
    return s.rolling(window=period).mean()


def _rsi_wilder(s, period):
    delta = s.diff()
    gains = delta.where(delta > 0, 0.0)
    losses = (-delta).where(delta < 0, 0.0)
    ag = gains.ewm(com=period - 1, min_periods=period).mean()
    al = losses.ewm(com=period - 1, min_periods=period).mean()
    rs = ag / al.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _open_trade_dict(entry_date, entry_price):
    return {'entry_date': entry_date, 'entry_price': entry_price}


def _close_trade(entry_date, entry_price, exit_date, exit_price, exit_reason):
    gross_pct = round((exit_price / entry_price - 1) * 100, 3)
    return {'entry_date': entry_date, 'entry_price': entry_price,
            'exit_date': exit_date, 'exit_price': exit_price,
            'status': 'closed', 'gross_pct_gain': gross_pct, 'exit_reason': exit_reason}


def _open_trade_final(entry_date, entry_price, last_date, last_price):
    gross_pct = round((last_price / entry_price - 1) * 100, 3)
    return {'entry_date': entry_date, 'entry_price': entry_price,
            'exit_date': None, 'exit_price': last_price,
            'status': 'open', 'gross_pct_gain': gross_pct, 'exit_reason': None}


# ───────────────────────── Sistema 1: Golden Cross ──────────────────────────

def simulate_golden_cross(close, hist_index, test_dates):
    sma50 = _sma(close, 50)
    sma200 = _sma(close, 200)
    state = (sma50 > sma200)  # NaN compares False, safe prima che le medie siano calcolabili

    holding = False
    entry_price = entry_date = None
    trades = []
    last_pos = None
    for d in test_dates:
        pos = hist_index.get_loc(d)
        if pos < 200:
            continue
        last_pos = pos
        price_today = float(close.iloc[pos])
        is_up = bool(state.iloc[pos])
        if not holding:
            if is_up:
                holding = True
                entry_price = price_today
                entry_date = d.date().isoformat()
        else:
            if not is_up:
                trades.append(_close_trade(entry_date, entry_price, d.date().isoformat(),
                                            price_today, 'DEATH_CROSS'))
                holding = False
                entry_price = entry_date = None

    if holding and last_pos is not None:
        last_price = float(close.iloc[last_pos])
        last_date = hist_index[last_pos].date().isoformat()
        trades.append(_open_trade_final(entry_date, entry_price, last_date, last_price))
    return trades


# ────────────────────── Sistema 2: RSI2 Mean Reversion ──────────────────────

def simulate_rsi2(close, hist_index, test_dates, timeout_days=20):
    rsi2 = _rsi_wilder(close, 2)
    sma200 = _sma(close, 200)

    holding = False
    entry_price = entry_date = None
    days_held = 0
    trades = []
    last_pos = None
    for d in test_dates:
        pos = hist_index.get_loc(d)
        if pos < 200:
            continue
        last_pos = pos
        price_today = float(close.iloc[pos])
        r = rsi2.iloc[pos]
        s200 = sma200.iloc[pos]
        if not holding:
            if pd.notna(r) and pd.notna(s200) and r < 10 and price_today > s200:
                holding = True
                entry_price = price_today
                entry_date = d.date().isoformat()
                days_held = 0
        else:
            days_held += 1
            overbought = pd.notna(r) and r > 70
            timed_out = days_held >= timeout_days
            if overbought or timed_out:
                reason = 'RSI2_OVERBOUGHT' if overbought else 'TIMEOUT_20D'
                trades.append(_close_trade(entry_date, entry_price, d.date().isoformat(),
                                            price_today, reason))
                holding = False
                entry_price = entry_date = None

    if holding and last_pos is not None:
        last_price = float(close.iloc[last_pos])
        last_date = hist_index[last_pos].date().isoformat()
        trades.append(_open_trade_final(entry_date, entry_price, last_date, last_price))
    return trades


# ───────────────────── Sistema 3: Turtle System 1 / 2 ───────────────────────

def _simulate_turtle(close, hist_index, test_dates, entry_window, exit_window, anti_whipsaw):
    """entry: nuovo massimo dei close a entry_window gg (esclude oggi).
    exit: nuovo minimo dei close a exit_window gg (esclude oggi).
    anti_whipsaw: se True, salta il segnale immediatamente dopo un trade chiuso in perdita."""
    roll_max_entry = close.shift(1).rolling(window=entry_window).max()
    roll_min_exit = close.shift(1).rolling(window=exit_window).min()

    holding = False
    entry_price = entry_date = None
    trades = []
    last_pos = None
    skip_next = False
    for d in test_dates:
        pos = hist_index.get_loc(d)
        if pos < max(entry_window, exit_window) + 1:
            continue
        last_pos = pos
        price_today = float(close.iloc[pos])
        if not holding:
            breakout = price_today > roll_max_entry.iloc[pos] if pd.notna(roll_max_entry.iloc[pos]) else False
            if breakout:
                if anti_whipsaw and skip_next:
                    skip_next = False
                    continue
                holding = True
                entry_price = price_today
                entry_date = d.date().isoformat()
        else:
            breakdown = price_today < roll_min_exit.iloc[pos] if pd.notna(roll_min_exit.iloc[pos]) else False
            if breakdown:
                t = _close_trade(entry_date, entry_price, d.date().isoformat(), price_today, 'DONCHIAN_EXIT')
                trades.append(t)
                if anti_whipsaw:
                    skip_next = t['gross_pct_gain'] < 0
                holding = False
                entry_price = entry_date = None

    if holding and last_pos is not None:
        last_price = float(close.iloc[last_pos])
        last_date = hist_index[last_pos].date().isoformat()
        trades.append(_open_trade_final(entry_date, entry_price, last_date, last_price))
    return trades


def simulate_turtle_s1(close, hist_index, test_dates):
    return _simulate_turtle(close, hist_index, test_dates, entry_window=20, exit_window=10, anti_whipsaw=True)


def simulate_turtle_s2(close, hist_index, test_dates):
    return _simulate_turtle(close, hist_index, test_dates, entry_window=55, exit_window=20, anti_whipsaw=False)


# ───────────────────── Sistema 4: Faber Trend Timing ────────────────────────

def simulate_faber_monthly(close, hist_index, window_start, window_end):
    """Resample mensile (ultimo close disponibile di ogni mese), SMA a 10 mesi.
    A differenza degli altri sistemi qui lavoriamo su una serie mensile a parte,
    non su test_dates giornalieri — i trade avvengono solo a fine mese."""
    df = pd.DataFrame({'close': close.values}, index=hist_index)
    monthly = df['close'].resample('ME').last().dropna()
    sma10m = monthly.rolling(window=10).mean()
    state = (monthly > sma10m)

    month_dates = [d for d in monthly.index if window_start <= d.date() < window_end]

    holding = False
    entry_price = entry_date = None
    trades = []
    last_date_used = None
    last_price_used = None
    for d in month_dates:
        price_today = float(monthly.loc[d])
        st = state.loc[d]
        if pd.isna(st):
            continue
        last_date_used = d.date().isoformat()
        last_price_used = price_today
        is_up = bool(st)
        if not holding:
            if is_up:
                holding = True
                entry_price = price_today
                entry_date = d.date().isoformat()
        else:
            if not is_up:
                trades.append(_close_trade(entry_date, entry_price, d.date().isoformat(),
                                            price_today, 'BELOW_SMA10M'))
                holding = False
                entry_price = entry_date = None

    if holding and last_date_used is not None:
        trades.append(_open_trade_final(entry_date, entry_price, last_date_used, last_price_used))
    return trades


# ──────────────────────────── Backtest per ticker ────────────────────────────

SYSTEMS_DAILY = {
    'golden_cross': simulate_golden_cross,
    'rsi2_mean_reversion': simulate_rsi2,
    'turtle_s1': simulate_turtle_s1,
    'turtle_s2': simulate_turtle_s2,
}


def backtest_ticker(fetcher, ticker, famiglia, window_start, window_end, fetch_days=1300):
    hist = fetcher.get_historical_data(ticker, days=fetch_days)
    if hist.empty or len(hist) < 220:
        return None, f'Storico insufficiente ({len(hist)}gg, servono >=220 per SMA200)'

    close_full = hist['Close'].astype(float)
    test_dates = [d for d in hist.index if window_start <= d.date() < window_end]
    if not test_dates:
        return None, 'Nessuna data nel range di backtest'

    per_system = {}
    for label, fn in SYSTEMS_DAILY.items():
        trades = fn(close_full, hist.index, test_dates)
        per_system[label] = {'n_trades': len(trades), 'trades': trades}

    faber_trades = simulate_faber_monthly(close_full, hist.index, window_start, window_end)
    per_system['faber_monthly'] = {'n_trades': len(faber_trades), 'trades': faber_trades}

    return {'ticker': ticker, 'famiglia': famiglia, 'variants': per_system}, None


def run_window(fetcher, universe, window_start, window_end, label):
    results, errors = [], []
    for i, item in enumerate(universe, 1):
        ticker = item['ticker']
        try:
            res, err = backtest_ticker(fetcher, ticker, item['famiglia'], window_start, window_end)
        except Exception as e:
            res, err = None, str(e)
        if err:
            errors.append({'ticker': ticker, 'error': err})
            continue
        results.append(res)
        if i % 20 == 0 or i == len(universe):
            print(f"  [{label}] {i}/{len(universe)} ticker processati...", flush=True)
    return results, errors


# ─────────────────────────── Aggregazione / report ───────────────────────────

def summarize(results, label, position_size):
    """Wrapper su aggregate()+extra_metrics() (riuso invariato) per un singolo sistema."""
    agg = aggregate(results, label, position_size)
    extra = extra_metrics(agg)
    return {**agg, **extra}


def pool_summary(costed_trade_lists):
    """Combina piu' liste di trade GIA' costati (post apply_costs_and_tax, es. Turtle
    S1+S2) in un unico riepilogo. Stessa formula di aggregate()/extra_metrics(), applicata
    a trade gia' costati invece che a 'results' grezzi — necessario perche' S1 e S2 usano
    ciascuno meta' notional (peso 50/50), quindi vanno costati separatamente PRIMA di essere
    sommati (il fee fisso Directa pesa diversamente su una posizione dimezzata)."""
    pooled = []
    for lst in costed_trade_lists:
        pooled.extend(lst)
    closed = [t for t in pooled if t['status'] == 'closed']
    net_gains = [t['net_pct_gain'] for t in closed]
    net_eur = [t['net_gain_eur'] for t in closed]  # stessa convenzione di aggregate(): solo chiusi, no P&L non realizzato
    win_rate = round(100 * sum(1 for g in net_gains if g > 0) / len(net_gains), 1) if net_gains else None
    avg_net = round(sum(net_gains) / len(net_gains), 2) if net_gains else None
    total_net_eur = round(sum(net_eur), 2) if net_eur else 0
    extra = extra_metrics({'trades': pooled})
    return {
        'n_trades_total': len(pooled), 'n_trades_closed': len(closed),
        'win_rate_pct': win_rate, 'avg_net_pct_gain': avg_net,
        'total_net_eur': total_net_eur, **extra,
        'trades': pooled,
    }


def print_summary_row(sys_label, window_label, size, s):
    pf = s.get('profit_factor')
    dd = s.get('max_drawdown_pct')
    print(f"  [{window_label} @ {size:.0f}EUR] {sys_label:22s} "
          f"N={s['n_trades_total']:4d}  chiusi={s.get('n_trades_closed', s['n_trades_total']):4d}  "
          f"WR={s.get('win_rate_pct')}%  PF={pf}  MaxDD={dd}%  "
          f"P&L_netto={s.get('total_net_eur')}EUR")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', action='store_true', help='run su un sottoinsieme di ticker per sanity check')
    parser.add_argument('--frozen-batch', default=DEFAULT_FROZEN_BATCH)
    parser.add_argument('--position-sizes', default='5000,10000')
    parser.add_argument('--out', default='data/backtest_reference_systems_result.json')
    args = parser.parse_args()
    position_sizes = [float(x) for x in args.position_sizes.split(',')]

    print("=" * 90)
    print("BACKTEST SISTEMI DI RIFERIMENTO — Golden Cross / RSI2 / Turtle S1+S2 / Faber Monthly")
    print(f"Golden Dataset batch: {args.frozen_batch}")
    print(f"IS: {IS_START} -> {IS_END}   OOS: {IS_END} -> {OOS_END}")
    print("=" * 90)

    universe = load_universe_all()
    if args.smoke:
        universe = [u for u in universe if u['ticker'] in SMOKE_TICKERS]
        print(f"[SMOKE TEST] {len(universe)} ticker: {[u['ticker'] for u in universe]}\n")
    else:
        print(f"Universo completo: {len(universe)} ETF\n")

    fetcher = FrozenDataFetcher(args.frozen_batch)

    print(">>> Simulazione finestra IS...")
    results_is, errors_is = run_window(fetcher, universe, IS_START, IS_END, 'IS')
    print(f"IS: {len(results_is)} ticker ok, {len(errors_is)} skip\n")

    print(">>> Simulazione finestra OOS...")
    results_oos, errors_oos = run_window(fetcher, universe, IS_END, OOS_END, 'OOS')
    print(f"OOS: {len(results_oos)} ticker ok, {len(errors_oos)} skip\n")

    report = {'is_start': IS_START.isoformat(), 'is_end': IS_END.isoformat(), 'oos_end': OOS_END.isoformat(),
              'n_universe': len(universe), 'errors_is': errors_is, 'errors_oos': errors_oos,
              'by_size': {}}

    single_systems = ['golden_cross', 'rsi2_mean_reversion', 'faber_monthly']

    for size in position_sizes:
        print(f"\n{'=' * 90}\nSIZE {size:.0f} EUR/trade\n{'=' * 90}")
        size_report = {}

        for sys_label in single_systems:
            s_is = summarize(results_is, sys_label, size)
            s_oos = summarize(results_oos, sys_label, size)
            print_summary_row(sys_label, 'IS', size, s_is)
            print_summary_row(sys_label, 'OOS', size, s_oos)
            size_report[sys_label] = {
                'IS': {k: v for k, v in s_is.items() if k != 'trades'},
                'OOS': {k: v for k, v in s_oos.items() if k != 'trades'},
            }

        # Turtle: S1 e S2 separati (a size/2 ciascuno, il vero peso 50/50), poi combinato
        half = size / 2.0
        s1_is = summarize(results_is, 'turtle_s1', half)
        s1_oos = summarize(results_oos, 'turtle_s1', half)
        s2_is = summarize(results_is, 'turtle_s2', half)
        s2_oos = summarize(results_oos, 'turtle_s2', half)
        combined_is = pool_summary([s1_is['trades'], s2_is['trades']])
        combined_oos = pool_summary([s1_oos['trades'], s2_oos['trades']])

        print_summary_row('turtle_s1 (half-size)', 'IS', half, s1_is)
        print_summary_row('turtle_s1 (half-size)', 'OOS', half, s1_oos)
        print_summary_row('turtle_s2 (half-size)', 'IS', half, s2_is)
        print_summary_row('turtle_s2 (half-size)', 'OOS', half, s2_oos)
        print_summary_row('turtle_COMBINED_50_50', 'IS', size, combined_is)
        print_summary_row('turtle_COMBINED_50_50', 'OOS', size, combined_oos)

        size_report['turtle_s1_half'] = {
            'IS': {k: v for k, v in s1_is.items() if k != 'trades'},
            'OOS': {k: v for k, v in s1_oos.items() if k != 'trades'},
        }
        size_report['turtle_s2_half'] = {
            'IS': {k: v for k, v in s2_is.items() if k != 'trades'},
            'OOS': {k: v for k, v in s2_oos.items() if k != 'trades'},
        }
        size_report['turtle_combined_50_50'] = {
            'IS': {k: v for k, v in combined_is.items() if k != 'trades'},
            'OOS': {k: v for k, v in combined_oos.items() if k != 'trades'},
        }

        report['by_size'][str(size)] = size_report

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSalvato: {args.out}")


if __name__ == '__main__':
    main()
