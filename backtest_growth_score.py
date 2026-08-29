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


def fit_score(IN, min_sp, fit_target='fwd_ret_60'):
    """Feature con |Spearman IN vs fit_target| >= min_sp. Ritorna (feats, sign, mu, sd)."""
    tgt = IN[fit_target]
    chosen, signs = [], {}
    for f in FEATURES:
        m = IN[f].notna() & tgt.notna() & np.isfinite(tgt)
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


def summ(trades):
    """Riga compatta per la tabella di confronto."""
    if not trades:
        return dict(n=0, wr=np.nan, pf=np.nan, gross=np.nan, dur=np.nan,
                    net5=0.0, net10=0.0, per10=np.nan)
    df = pd.DataFrame(trades)
    closed = df[df['status'] == 'closed']
    wr = (closed['gross_pct'] > 0).mean() * 100 if len(closed) else np.nan
    g = closed.loc[closed['gross_pct'] > 0, 'gross_pct'].sum()
    l = -closed.loc[closed['gross_pct'] < 0, 'gross_pct'].sum()
    pf = g / l if l > 0 else np.inf
    net10 = sum(net_eur(t, 10000) for t in trades)
    return dict(n=len(df), wr=wr, pf=pf, gross=df['gross_pct'].mean(),
                dur=df['days'].median(),
                net5=sum(net_eur(t, 5000) for t in trades), net10=net10,
                per10=net10 / len(df))


def run_mode(df, analyzers, fams, mode, fit_target, min_sp, pct):
    """Fitta lo score (su IN, target=fit_target), simula, ritorna (feats, trIN, trOUT)."""
    IN = df[df['date'] < SPLIT]
    feats, signs, mu, sd = fit_score(IN, min_sp, fit_target)
    d = df.copy()
    d['score'] = score_series(d, feats, signs, mu, sd)
    sc_in = d.loc[d['date'] < SPLIT, 'score'].dropna()
    thr = sc_in.quantile(1 - pct) if mode == 'worst' else sc_in.quantile(pct)

    trades = []
    for tk, g in d.groupby('ticker'):
        g = g.reset_index(drop=True)
        fam = g['family'].iloc[0]
        trades += [dict(t, ticker=tk, family=fam)
                   for t in simulate_ticker(g, analyzers[fam], thr, mode)]
    tr = pd.DataFrame(trades)
    if tr.empty:
        return feats, [], []
    tr['entry_dt'] = pd.to_datetime(tr['entry_date'])
    return (feats,
            tr[tr['entry_dt'] < SPLIT].to_dict('records'),
            tr[tr['entry_dt'] >= SPLIT].to_dict('records'))


def print_table(rows):
    hdr = f"{'variante':<28}{'N':>6}{'WR':>7}{'PF':>7}{'gross':>8}{'dur':>6}{'net/tr 10k':>12}{'net tot 10k':>14}"
    print(hdr)
    print("-" * len(hdr))
    for name, s in rows:
        if s['n'] == 0:
            print(f"{name:<28}{'0':>6}")
            continue
        print(f"{name:<28}{s['n']:>6}{s['wr']:>6.1f}%{s['pf']:>7.2f}{s['gross']:>+7.2f}%"
              f"{s['dur']:>5.0f}g{s['per10']:>+11.0f}E{s['net10']:>+13,.0f}E")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--families', default='core', choices=['core', 'equity'])
    ap.add_argument('--pct', type=float, default=0.85, help='percentile soglia (0.85 = top/bottom 15 percento)')
    ap.add_argument('--min-sp', type=float, default=0.04, help='|Spearman IN| minimo per una feature')
    ap.add_argument('--fit-target', default='fwd_ret_60', choices=['fwd_ret_60', 'fwd_mar_60'],
                    help='fwd_mar_60 = rendimento/drawdown (penalizza il percorso), consigliato per "strength"')
    ap.add_argument('--mode', default='all',
                    choices=['all', 'score', 'always', 'worst'])
    ap.add_argument('--sweep', action='store_true', help='sweep pct in {0.70..0.92} su score e worst')
    args = ap.parse_args()

    fams = CORE if args.families == 'core' else EQUITY
    t0 = datetime.now()

    usecols = ['ticker', 'family', 'date', 'close', 'fwd_ret_60', 'fwd_mar_60'] + FEATURES
    df = pd.read_csv(DATASET, parse_dates=['date'], usecols=usecols)
    df = df[df['family'].isin(fams)].copy()
    df = df.dropna(subset=FEATURES).sort_values(['ticker', 'date'])
    df['fwd_mar_60'] = df['fwd_mar_60'].replace([np.inf, -np.inf], np.nan).clip(-30, 30)
    IN = df[df['date'] < SPLIT]
    print(f"Famiglie {args.families} ({fams})")
    print(f"Dataset: {len(df):,} righe, {df['ticker'].nunique()} ticker  "
          f"| IN {len(IN):,}  OUT {len(df) - len(IN):,}  | fit-target={args.fit_target}\n")

    analyzers = {f: ETFTechnicalAnalyzer(famiglia=f) for f in fams}

    if args.sweep:
        for mode in ('score', 'worst'):
            print(f"\n### SWEEP pct — mode={mode}, fit-target={args.fit_target}")
            rows = []
            for pct in (0.70, 0.75, 0.80, 0.85, 0.90, 0.92):
                _, _, o = run_mode(df, analyzers, fams, mode, args.fit_target, args.min_sp, pct)
                rows.append((f"pct={pct:.2f}  (OUT)", summ(o)))
            print_table(rows)
        print(f"\nTempo: {datetime.now() - t0}")
        return

    if args.mode == 'all':
        combos = [
            ('always', 'fwd_ret_60'),
            ('score  (ret)', 'fwd_ret_60'),
            ('score  (mar)=strength', 'fwd_mar_60'),
            ('worst  (ret)', 'fwd_ret_60'),
            ('worst  (mar)', 'fwd_mar_60'),
        ]
        rows_in, rows_out = [], []
        for label, ft in combos:
            m = 'always' if label.startswith('always') else ('worst' if 'worst' in label else 'score')
            _, i, o = run_mode(df, analyzers, fams, m, ft, args.min_sp, args.pct)
            rows_in.append((label, summ(i)))
            rows_out.append((label, summ(o)))
        print(f"=== CONFRONTO — famiglie {args.families}, pct={args.pct} ===\n")
        print("IN  (2023-02 -> 2025-01)")
        print_table(rows_in)
        print("\nOUT (2025-01 -> 2026-08)")
        print_table(rows_out)
        print(f"\nTempo: {datetime.now() - t0}")
        return

    # modalita' singola: report dettagliato
    feats, trIN, trOUT = run_mode(df, analyzers, fams, args.mode, args.fit_target, args.min_sp, args.pct)
    print(f"Score: {len(feats)} feature  {', '.join(feats)}")
    print(f"\n{'='*70}\nMODE={args.mode}  fit={args.fit_target}  pct={args.pct}\n{'='*70}")
    report(trIN, 'IN ')
    report(trOUT, 'OUT')
    print("\n   -- OUT per famiglia --")
    for fam in fams:
        report([t for t in trOUT if t['family'] == fam], f'OUT/{fam}')
    if trOUT:
        by_tk = {}
        for t in trOUT:
            by_tk.setdefault(t['ticker'], []).append(t)
        rank = sorted(((tk, sum(net_eur(x, 10000) for x in v), len(v)) for tk, v in by_tk.items()),
                      key=lambda x: -x[1])
        print("\n   -- OUT: 8 migliori / 5 peggiori (netto 10k/trade) --")
        for tk, tot, k in rank[:8] + rank[-5:]:
            print(f"      {tk:<10} {tot:+9,.0f}EUR  ({k} trade)")
    print(f"\nTempo: {datetime.now() - t0}")


if __name__ == '__main__':
    main()
