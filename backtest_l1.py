#!/usr/bin/env python3
"""
Backtest L1 ETF — confronto scenari
=====================================
Testa combinazioni di trailing stop e regole di uscita,
mostra la tabella comparativa e il dettaglio dello scenario migliore.

Filtro anomalie: scarta operazioni chiuse con perdita >20%
(gap overnight estremi non rappresentativi di uno stop reale).
Commissioni: €5 acquisto + €5 vendita = €10 round trip.
"""

import os
import psycopg2
import pandas as pd
import numpy as np
from datetime import date, timedelta

INVEST        = 3000.0
BACKTEST_DAYS = 30
WARMUP_DAYS   = 250
MAX_LOSS      = 0.20
COMM_BUY      = 5.0
COMM_SELL     = 5.0
COMM_RT       = COMM_BUY + COMM_SELL

DB_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://etfmonitor:FundMonitor2026!@postgres:5432/etfs'
)

# ─── Indicatori ────────────────────────────────────────────────────────────────

def calc_rsi(s, period=14):
    d = s.diff()
    g = d.clip(lower=0)
    l = (-d).clip(lower=0)
    ag = g.ewm(com=period-1, min_periods=period).mean()
    al = l.ewm(com=period-1, min_periods=period).mean()
    rs = ag / al.replace(0, np.nan)
    return 100 - 100/(1+rs)

def calc_indicators(df):
    c = df['close'].astype(float)
    df['ema10']  = c.ewm(span=10,  adjust=False).mean()
    df['ema20']  = c.ewm(span=20,  adjust=False).mean()
    df['sma50']  = c.rolling(50).mean()
    df['rsi']    = calc_rsi(c)
    df['dist']   = (c - df['ema20']) / df['ema20'] * 100
    df['slope']  = df['ema20'] - df['ema20'].shift(5)
    ab = (c > df['ema20']).astype(int)
    df['days_above'] = ab.groupby((ab != ab.shift()).cumsum()).cumsum() * ab
    bl = (c < df['ema20']).astype(int)
    df['days_below'] = bl.groupby((bl != bl.shift()).cumsum()).cumsum() * bl
    return df

def entry_ok(row):
    if pd.isna(row['sma50']) or pd.isna(row['rsi']): return False
    if row['close'] <= row['ema20']:  return False
    if row['ema20'] <= row['sma50']:  return False
    if row['days_above'] < 3:         return False
    if row['slope'] <= 0:             return False
    if not (48 <= row['rsi'] <= 73):  return False
    if not (0 <= row['dist'] <= 6):   return False
    return True

# ─── Carica dati ───────────────────────────────────────────────────────────────

def load_data():
    cutoff = date.today() - timedelta(days=BACKTEST_DAYS + WARMUP_DAYS)
    conn   = psycopg2.connect(DB_URL)
    raw    = pd.read_sql(
        "SELECT ticker, date, close FROM etf_price_history WHERE date >= %s AND close IS NOT NULL ORDER BY ticker, date",
        conn, params=(cutoff,), parse_dates=['date']
    )
    conn.close()
    data = {}
    for tk, g in raw.groupby('ticker'):
        g = g.set_index('date').sort_index()
        if len(g) >= 55:
            data[tk] = calc_indicators(g)
    return data

# ─── Backtest singolo scenario ─────────────────────────────────────────────────

def run_scenario(data, trailing_pct, use_rule_a, use_rule_b):
    """
    trailing_pct : float o None (nessuno stop trailing)
    use_rule_a   : uscita se close < EMA20 per 3 giorni
    use_rule_b   : uscita se EMA10 < EMA20
    """
    start  = pd.Timestamp(date.today() - timedelta(days=BACKTEST_DAYS))
    trades = []

    for ticker, df in data.items():
        in_pos = False
        ep = ed = peak = None

        for dt, row in df.iterrows():
            if pd.isna(row['ema20']) or pd.isna(row['rsi']):
                continue

            if in_pos:
                if row['close'] > peak:
                    peak = row['close']

                reason = None
                if trailing_pct and row['close'] <= peak * (1 - trailing_pct):
                    reason = f"Stop{int(trailing_pct*100)}%"
                elif use_rule_b and row['ema10'] < row['ema20']:
                    reason = "RuleB"
                elif use_rule_a and row['days_below'] >= 3:
                    reason = "RuleA"

                if reason:
                    qty   = INVEST / ep
                    gross = (float(row['close']) - ep) * qty
                    net   = gross - COMM_RT
                    pct   = (float(row['close']) / ep - 1) * 100
                    trades.append({'ticker': ticker, 'entry_date': ed, 'exit_date': dt,
                                   'gross': gross, 'net': net, 'pct': pct,
                                   'days': (dt-ed).days, 'status': 'C', 'reason': reason})
                    in_pos = False

            elif dt >= start and entry_ok(row):
                in_pos, ep, ed, peak = True, float(row['close']), dt, float(row['close'])

        if in_pos:
            lp    = float(df.iloc[-1]['close'])
            qty   = INVEST / ep
            gross = (lp - ep) * qty
            net   = gross - COMM_BUY
            pct   = (lp / ep - 1) * 100
            trades.append({'ticker': ticker, 'entry_date': ed, 'exit_date': None,
                           'gross': gross, 'net': net, 'pct': pct,
                           'days': (df.index[-1]-ed).days, 'status': 'A', 'reason': '—'})

    return trades

# ─── Metriche scenario ─────────────────────────────────────────────────────────

def metrics(trades):
    df = pd.DataFrame(trades)
    if df.empty:
        return {}
    # scarta anomalie (solo chiuse con perdita >20%)
    mask_anomaly = (df['status'] == 'C') & (df['pct'] < -MAX_LOSS*100)
    df = df[~mask_anomaly]
    n_tot   = len(df)
    n_close = (df['status']=='C').sum()
    n_open  = (df['status']=='A').sum()
    pnl     = df['net'].sum()
    comm    = df.apply(lambda r: COMM_RT if r['status']=='C' else COMM_BUY, axis=1).sum()
    win     = (df['net'] > 0).sum()
    cap     = n_tot * INVEST
    pnl_pct = pnl / cap * 100 if cap else 0
    avg_days_c = df[df['status']=='C']['days'].mean() if n_close else 0
    return {
        'n_tot': n_tot, 'n_close': n_close, 'n_open': n_open,
        'pnl': pnl, 'pnl_pct': pnl_pct, 'comm': comm,
        'win_rate': win/n_tot*100 if n_tot else 0,
        'avg_days': avg_days_c,
        'cap': cap,
        'df': df,
    }

# ─── Main ──────────────────────────────────────────────────────────────────────

SCENARIOS = [
    # (label,              trailing_pct, rule_a, rule_b)
    ("Solo Stop 3.5%",     0.035,        False,  False),
    ("Solo Stop 5%",       0.05,         False,  False),
    ("Solo Stop 7%",       0.07,         False,  False),
    ("Solo Stop 10%",      0.10,         False,  False),
    ("Solo A+B (no stop)", None,         True,   True),
    ("Stop 3.5% + A+B",   0.035,        True,   True),
    ("Stop 5%   + A+B",   0.05,         True,   True),
    ("Stop 5%   + A",     0.05,         True,   False),
    ("Stop 7%   + A+B",   0.07,         True,   True),
    ("Stop 10%  + A+B",   0.10,         True,   True),
    ("Nessuna uscita",     None,         False,  False),
]

if __name__ == '__main__':
    print("Caricamento dati...")
    data = load_data()
    print(f"ETF: {len(data)} | Periodo: ultimi {BACKTEST_DAYS} giorni | €{INVEST:.0f}/trade | Comm €{COMM_RT:.0f}\n")

    results = []
    for label, tp, ra, rb in SCENARIOS:
        trades = run_scenario(data, tp, ra, rb)
        m = metrics(trades)
        m['label'] = label
        results.append(m)

    # Tabella comparativa
    print(f"  {'Scenario':<22} {'Trade':>6} {'Chiu':>5} {'Aperte':>7} {'Win%':>5}  {'P&L Netto':>11}  {'%Cap':>6}  {'Comm':>7}  {'GgMedio':>8}")
    print("  " + "-"*88)
    best_pnl = max(r['pnl'] for r in results)
    for r in results:
        marker = " ◄ BEST" if r['pnl'] == best_pnl else ""
        s = '+' if r['pnl'] >= 0 else ''
        print(f"  {r['label']:<22} {r['n_tot']:>6} {r['n_close']:>5} {r['n_open']:>7} "
              f"{r['win_rate']:>4.0f}%  {s}€{r['pnl']:>9,.0f}  {r['pnl_pct']:>+5.2f}%  "
              f"-€{r['comm']:>5,.0f}  {r['avg_days']:>6.1f}gg{marker}")

    # Dettaglio scenario migliore
    best = max(results, key=lambda r: r['pnl'])
    print(f"\n{'='*74}")
    print(f"  DETTAGLIO SCENARIO MIGLIORE: {best['label']}")
    print(f"  P&L netto: +€{best['pnl']:,.0f}  |  Capitale impiegato: €{best['cap']:,.0f}  |  Win rate: {best['win_rate']:.0f}%")
    print(f"{'='*74}")

    df_best = best['df']
    closed  = df_best[df_best['status']=='C'].sort_values('net', ascending=False)
    open_   = df_best[df_best['status']=='A'].sort_values('net', ascending=False)

    if len(closed):
        print(f"\n  TOP 10 CHIUSE (migliori)")
        print(f"  {'Ticker':<14} {'Entrata':<12} {'Uscita':<12} {'Netto €':>9} {'%':>7}  {'Gg':>4}  Motivo")
        print("  " + "-"*65)
        for _, r in closed.head(10).iterrows():
            s = '+' if r['net'] >= 0 else ''
            print(f"  {r['ticker']:<14} {str(r['entry_date'].date()):<12} {str(r['exit_date'].date()):<12} "
                  f"{s}€{r['net']:>7,.0f} {r['pct']:>+7.2f}%  {r['days']:>3}  {r['reason']}")
        if len(closed) > 10:
            neg = closed[closed['net']<0]
            print(f"  ... altre {len(closed)-10} chiuse | perdenti: {len(neg)} | peggiore: €{neg['net'].min():,.0f} ({neg['pct'].min():+.2f}%)")

    if len(open_):
        print(f"\n  TOP 10 POSIZIONI APERTE")
        print(f"  {'Ticker':<14} {'Entrata':<12} {'Netto €':>9} {'%':>7}  {'Gg':>4}")
        print("  " + "-"*50)
        for _, r in open_.head(10).iterrows():
            s = '+' if r['net'] >= 0 else ''
            print(f"  {r['ticker']:<14} {str(r['entry_date'].date()):<12} "
                  f"{s}€{r['net']:>7,.0f} {r['pct']:>+7.2f}%  {r['days']:>3}")
        if len(open_) > 10:
            print(f"  ... altre {len(open_)-10} posizioni aperte")
    print()
