"""
backtest_growth_score.py — SCRATCH / RESEARCH (2026-08-29)

Testa il "quality-score canali di crescita" (vedi research_growth_channels.py) come
VERO trigger d'ingresso, con uscita SL/TP giornaliera identica al modello reale L1.

Modello (come backtest_l1.py):
  - Ingresso: score nel top X% (soglia calibrata SOLO su IN) + filtro trend SMA50>SMA200
              + famiglia in 'core'. Cooldown 3gg dopo un'uscita sullo stesso ticker.
  - Uscita:  SL = calculate_sl_suggerito_l1 ; TP = calculate_stop_gain_dynamic
             (le due funzioni reali di produzione), controllate 1 volta/giorno sul Close.
  - Costi:   5 EUR acquisto + 5 EUR vendita ; tasse 26% sulle plusvalenze.
  - Size:    5.000 e 10.000 EUR/trade (riportate entrambe).

Lo score e' fittato SOLO su IN (feature con |Spearman_IN| >= --min-sp, segno da IN,
z-score con mu/sd di IN). Il periodo OUT e' quindi genuinamente out-of-sample.

Baseline di confronto:
  --mode score  : ingresso quando score >= soglia top X%  (il test)
  --mode always : ingresso appena flat + trend OK           (nessun timing)
  --mode worst  : ingresso quando score <= soglia bottom X% (lo score al contrario)

Uso (dentro il container):
  docker exec etf_monitor_system-app-1 python3 /app/backtest_growth_score.py --families core --pct 0.85
"""
import sys
sys.path.insert(0, '/app')

import argparse
from datetime import datetime

import numpy as np
import pandas as pd

from technical_analysis import ETFTechnicalAnalyzer

DATASET = '/app/data/research_growth_dataset.csv.gz'
SPLIT = pd.Timestamp('2025-01-01')
FEE_BUY = FEE_SELL = 5.0
TAX = 0.26
COOLDOWN = 3

CORE = ['equity_sviluppati', 'mercati_emergenti', 'settoriali_growth',
        'oro_metalli_preziosi', 'metalli_industriali']
EQUITY = ['equity_sviluppati', 'settoriali_growth', 'mercati_emergenti']

FEATURES = [
    'dist_ema20', 'dist_sma50', 'dist_sma200', 'gap_ema20_sma50', 'gap_sma50_sma200',
    'ema20_slope_10', 'sma50_slope_20', 'rsi', 'rsi_chg_5', 'adx', 'adx_chg_5',
    'macd_hist_norm', 'macd_hist_chg_5', 'atr_norm', 'rvol_20',
    'dd_from_peak_126', 'dd_from_peak_252', 'trend_r2_20', 'trend_r2_40', 'trend_r2_60',
    'trend_slope_40_ann', 'channel_width_40', 'pct_above_ema20_60', 'up_day_ratio_20',
]


def fit_score(IN, min_sp):
    """Feature con |Spearman IN vs fwd_ret_60| >= min_sp. Ritorna (feats, sign, mu, sd)."""
    tgt = IN['fwd_ret_60']
    chosen, signs = [], {}
    for f in FEATURES:
        m = IN[f].notna() & tgt.notna()
        if m.sum() < 200:
            continue
        sp = IN.loc[m, f].rank().corr(tgt[m].rank())
        if abs(sp) >= min_sp:
            chosen.append(f)
            signs[f] = np.sign(sp)
    mu = IN[chosen].mean()
    sd = IN[chosen].std(ddof=0).replace(0, np.nan)
    return chosen, signs, mu, sd


def score_series(df, feats, signs, mu, sd):
    z = (df[feats] - mu) / sd
    for f in feats:
        z[f] = z[f] * signs[f]
    return z.sum(axis=1)


def simulate_ticker(g, analyzer, thr, mode):
    """g: righe di UN ticker, ordinate per data, con colonne close, score, gap_sma50_sma200,
    dist_ema20. Ritorna lista di trade."""
    close = g['close'].to_numpy(float)
    dist_ema20 = g['dist_ema20'].to_numpy(float)
    ema20_col = close / (1 + dist_ema20 / 100.0)      # ema20 vero, ricavato da close+dist
    gap = g['gap_sma50_sma200'].to_numpy(float)
    sc = g['score'].to_numpy(float)
    dates = g['date'].to_numpy()
    n = len(close)

    trades = []
    holding = False
    entry_price = entry_i = None
    cooldown_until = -1

    for i in range(n):
        if np.isnan(sc[i]):
            continue
        if not holding:
            if i <= cooldown_until:
                continue
            trend_ok = gap[i] > 0
            if mode == 'score':
                enter = trend_ok and sc[i] >= thr
            elif mode == 'worst':
                enter = trend_ok and sc[i] <= thr
            else:  # always
                enter = trend_ok
            if enter:
                holding = True
                entry_price = close[i]
                entry_i = i
        else:
            cp = close[i]
            ema20_today = ema20_col[i]
            ema20_series = pd.Series(ema20_col[max(0, i - 9):i + 1])

            sl = analyzer.calculate_sl_suggerito_l1(entry_price, cp, ema20_today).get('sl_suggerito')
            sg = analyzer.calculate_stop_gain_dynamic(entry_price, cp, ema20_series, analyzer.p)

            sl_hit = sl is not None and cp <= sl
            tp_hit = bool(sg.get('trigger'))
            if sl_hit or tp_hit:
                trades.append({
                    'entry_date': pd.Timestamp(dates[entry_i]).date().isoformat(),
                    'exit_date': pd.Timestamp(dates[i]).date().isoformat(),
                    'entry_price': entry_price, 'exit_price': cp,
                    'gross_pct': (cp / entry_price - 1) * 100,
                    'days': i - entry_i,
                    'reason': 'SL' if sl_hit else 'TP',
                    'status': 'closed',
                })
                holding = False
                cooldown_until = i + COOLDOWN

    if holding:
        cp = close[-1]
        trades.append({
            'entry_date': pd.Timestamp(dates[entry_i]).date().isoformat(),
            'exit_date': None, 'entry_price': entry_price, 'exit_price': cp,
            'gross_pct': (cp / entry_price - 1) * 100, 'days': n - 1 - entry_i,
            'reason': None, 'status': 'open',
        })
    return trades


def net_eur(t, size):
    gross = size * (t['exit_price'] / t['entry_price'] - 1)
    fees = FEE_BUY + (FEE_SELL if t['status'] == 'closed' else 0)
    after = gross - fees
    tax = TAX * after if after > 0 else 0.0
    return after - tax


def report(trades, label):
    if not trades:
        print(f"   [{label}] nessun trade")
        return
    df = pd.DataFrame(trades)
    closed = df[df['status'] == 'closed']
    wr = (closed['gross_pct'] > 0).mean() * 100 if len(closed) else np.nan
    gains = closed.loc[closed['gross_pct'] > 0, 'gross_pct'].sum()
    losses = -closed.loc[closed['gross_pct'] < 0, 'gross_pct'].sum()
    pf = gains / losses if losses > 0 else np.inf
    line = (f"   [{label}] N={len(df)} (chiusi {len(closed)})  "
            f"WR={wr:.1f}%  PF={pf:.2f}  "
            f"gross medio={df['gross_pct'].mean():+.2f}%  durata med={df['days'].median():.0f}gg")
    print(line)
    for size in (5000, 10000):
        tot = sum(net_eur(t, size) for t in trades)
        per = tot / len(trades)
        print(f"        {size:>6}EUR/trade -> netto totale {tot:+,.0f}EUR  ({per:+.0f}EUR/trade)")
    print(f"        motivi uscita: {df['reason'].value_counts().to_dict()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--families', default='core', choices=['core', 'equity'])
    ap.add_argument('--pct', type=float, default=0.85, help='percentile soglia score (0.85 = top 15 percento)')
    ap.add_argument('--min-sp', type=float, default=0.04, help='|Spearman IN| minimo per includere una feature')
    ap.add_argument('--mode', default='score', choices=['score', 'always', 'worst'])
    args = ap.parse_args()

    fams = CORE if args.families == 'core' else EQUITY
    t0 = datetime.now()

    df = pd.read_csv(DATASET, parse_dates=['date'],
                     usecols=['ticker', 'family', 'date', 'close', 'fwd_ret_60'] + FEATURES)
    df = df[df['family'].isin(fams)].copy()
    df = df.dropna(subset=FEATURES).sort_values(['ticker', 'date'])
    IN = df[df['date'] < SPLIT]
    print(f"Famiglie {args.families} ({fams})")
    print(f"Dataset: {len(df):,} righe, {df['ticker'].nunique()} ticker  "
          f"| IN {len(IN):,}  OUT {len(df) - len(IN):,}")

    feats, signs, mu, sd = fit_score(IN, args.min_sp)
    print(f"\nScore fittato su IN: {len(feats)} feature")
    print("   " + ", ".join(f"{f}({'+' if signs[f] > 0 else '-'})" for f in feats))

    df['score'] = score_series(df, feats, signs, mu, sd)
    sc_in = df.loc[df['date'] < SPLIT, 'score'].dropna()
    if args.mode == 'worst':
        thr = sc_in.quantile(1 - args.pct)
        print(f"Soglia score (bottom {(1-args.pct)*100:.0f}%, da IN): {thr:.2f}")
    else:
        thr = sc_in.quantile(args.pct)
        print(f"Soglia score (top {(1-args.pct)*100:.0f}%, da IN): {thr:.2f}")

    analyzers = {f: ETFTechnicalAnalyzer(famiglia=f) for f in fams}

    all_trades = []
    for tk, g in df.groupby('ticker'):
        g = g.reset_index(drop=True)
        fam = g['family'].iloc[0]
        all_trades += [dict(t, ticker=tk, family=fam)
                       for t in simulate_ticker(g, analyzers[fam], thr, args.mode)]

    tr = pd.DataFrame(all_trades)
    if tr.empty:
        print("\nNessun trade generato.")
        return
    tr['entry_dt'] = pd.to_datetime(tr['entry_date'])
    trIN = tr[tr['entry_dt'] < SPLIT].to_dict('records')
    trOUT = tr[tr['entry_dt'] >= SPLIT].to_dict('records')

    print(f"\n{'='*70}\nMODE={args.mode}  famiglie={args.families}  pct={args.pct}\n{'='*70}")
    report(trIN, 'IN  2023-02 -> 2025-01')
    report(trOUT, 'OUT 2025-01 -> 2026-08')

    # per famiglia (solo OUT)
    print("\n   -- OUT per famiglia --")
    for fam in fams:
        report([t for t in trOUT if t['family'] == fam], f'OUT/{fam}')

    # top ticker per netto (OUT, 10k)
    if trOUT:
        by_tk = {}
        for t in trOUT:
            by_tk.setdefault(t['ticker'], []).append(t)
        rank = sorted(((tk, sum(net_eur(x, 10000) for x in v), len(v)) for tk, v in by_tk.items()),
                      key=lambda x: -x[1])
        print("\n   -- OUT: 8 ticker migliori / 5 peggiori (netto 10k/trade) --")
        for tk, tot, k in rank[:8] + rank[-5:]:
            print(f"      {tk:<10} {tot:+9,.0f}EUR  ({k} trade)")

    print(f"\nTempo: {datetime.now() - t0}")


if __name__ == '__main__':
    main()
