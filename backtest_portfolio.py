"""
backtest_portfolio.py — SCRATCH / RESEARCH (2026-08-29)

Backtest di PORTAFOGLIO con vincolo di capitale reale — a differenza di
backtest_growth_score.py (che aggrega trade indipendenti ignorando la concorrenza),
qui si simula un portafoglio vero:

  - capitale fisso, max N posizioni contemporanee, size fissa per posizione (niente
    compounding — l'utente traда ticket fissi ~5-10k)
  - quando scatta un segnale e c'e' uno slot libero -> entra; altrimenti si perde
    (realistico). Se piu' candidati che slot: si sceglie per --rank (score desc / random)
  - lo slot si libera quando la posizione esce (SL o TP di L1, check giornaliero sul Close)
  - le perdite erodono la cassa ridispiegabile (capitale reale, non infinito)
  - costi 5+5 EUR/trade, tasse 26% sulle plusvalenze realizzate
  - metrica CHIAVE: max drawdown della CURVA EQUITY del portafoglio (mai visto nei
    backtest per-trade), oltre a rendimento totale, CAGR, utilizzo, segnali persi

Confronto sempre incluso: buy & hold equipesato dell'universo core (il "indicizzalo").

Uso (dentro il container):
  docker exec etf_monitor_system-app-1 python3 /app/backtest_portfolio.py --families core --mode all --max-positions 8 --position-size 10000
"""
import sys
sys.path.insert(0, '/app')

import argparse
from datetime import datetime

import numpy as np
import pandas as pd

from technical_analysis import ETFTechnicalAnalyzer
from backtest_growth_score import (fit_score, score_series, get_trade_ret,
                                    FEATURES, CORE, EQUITY, SPLIT, DATASET,
                                    FEE_BUY, FEE_SELL, TAX, COOLDOWN)


def build_signal(df, mode, pct, min_sp):
    """Aggiunge df['sig'] (bool) e df['rankval'] (per scegliere quando capacity-limited)."""
    df['ema20'] = df['close'] / (1 + df['dist_ema20'] / 100.0)
    df['trend_ok'] = df['gap_sma50_sma200'] > 0

    if mode in ('strength', 'score', 'worst'):
        fit_target = 'fwd_trade_ret' if mode == 'strength' else 'fwd_ret_60'
        IN = df[df['date'] < SPLIT]
        feats, signs, mu, sd = fit_score(IN, min_sp, fit_target)
        df['score'] = score_series(df, feats, signs, mu, sd)
        sc_in = df.loc[df['date'] < SPLIT, 'score'].dropna()
        if mode == 'worst':          # compra la FORZA: score basso sul modello fwd_ret
            thr = sc_in.quantile(1 - pct)
            df['sig'] = df['trend_ok'] & (df['score'] <= thr)
            df['rankval'] = -df['score']       # piu' basso lo score, piu' alta la priorita'
            print(f"  worst({fit_target}): {len(feats)} feat, soglia bottom {(1-pct)*100:.0f}% = {thr:.2f}")
        else:
            thr = sc_in.quantile(pct)
            df['sig'] = df['trend_ok'] & (df['score'] >= thr)
            df['rankval'] = df['score']
            print(f"  {mode}({fit_target}): {len(feats)} feat, soglia top {(1-pct)*100:.0f}% = {thr:.2f}")
    else:  # always / random
        df['score'] = np.nan
        df['sig'] = df['trend_ok']
        # quando i candidati superano gli slot: preferisci il trend di fondo piu' forte
        df['rankval'] = df['gap_sma50_sma200']
    return df


def simulate_portfolio(df, analyzers, capital, size, max_pos, rank, seed=1):
    """Loop giornaliero globale su tutti i ticker. Ritorna (trades, equity_curve, stats)."""
    rng = np.random.default_rng(seed)
    # serie per-ticker (date -> close, ema20) per il check di uscita
    series = {tk: g.set_index('date')[['close', 'ema20']] for tk, g in df.groupby('ticker')}
    # righe per data
    by_date = {d: sub for d, sub in df.groupby('date')}
    dates = sorted(by_date.keys())

    # parametri uscita L1 (per famiglia)
    exitp = {}
    for fam, an in analyzers.items():
        p = an.p.get('l1_stop_gain_dynamic', {})
        exitp[fam] = dict(buf=an.p.get('sl_buffer_wide', 0.02),
                          tmax=p.get('target_max_pct', 0.12), tfloor=p.get('target_floor_pct', 0.03),
                          sw=int(p.get('slope_window', 3)), ssens=p.get('slope_sensitivity', 0.0))
    fam_of = df.groupby('ticker')['family'].first().to_dict()

    cash = float(capital)
    positions = {}          # ticker -> dict(entry_price, entry_date, fam)
    cooldown = {}            # ticker -> date-index until blocked
    trades, equity_curve = [], []
    skipped_no_slot = 0

    for di, d in enumerate(dates):
        sub = by_date[d]
        px_today = dict(zip(sub['ticker'], sub['close']))

        # 1) USCITE
        for tk in list(positions.keys()):
            s = series[tk]
            if d not in s.index:
                continue
            pos_i = s.index.get_loc(d)
            cp = float(s['close'].iloc[pos_i])
            e = positions[tk]
            ep = exitp[e['fam']]
            gain = cp / e['entry_price'] - 1
            sl = s['ema20'].iloc[pos_i] * (1 - ep['buf']) if gain < 0.02 else s['ema20'].iloc[pos_i] * 0.99
            slope = 0.0
            if pos_i - ep['sw'] >= 0:
                a, b = s['ema20'].iloc[pos_i], s['ema20'].iloc[pos_i - ep['sw']]
                slope = (a - b) / b
            tp_pct = max(ep['tmax'] + slope * ep['ssens'], ep['tfloor'])
            if cp <= sl or gain >= tp_pct:
                cash += size * (cp / e['entry_price'])
                gross = size * gain
                fees = FEE_BUY + FEE_SELL
                net = gross - fees - (TAX * (gross - fees) if gross - fees > 0 else 0.0)
                trades.append(dict(ticker=tk, family=e['fam'], entry_date=e['entry_date'],
                                   exit_date=d, gross_pct=gain * 100, net_eur=net,
                                   days=(d - e['entry_date']).days,
                                   reason='SL' if cp <= sl else 'TP'))
                cooldown[tk] = di + COOLDOWN
                del positions[tk]

        # 2) EQUITY mark-to-market
        mtm = sum(size * (px_today[tk] / e['entry_price'])
                  for tk, e in positions.items() if tk in px_today)
        equity_curve.append((d, cash + mtm))

        # 3) INGRESSI
        free = max_pos - len(positions)
        if free > 0:
            cands = sub[sub['sig'] & ~sub['ticker'].isin(positions)]
            cands = [r for r in cands.itertuples()
                     if cooldown.get(r.ticker, -1) <= di and r.ticker in px_today]
            if len(cands) > free:
                skipped_no_slot += len(cands) - free
                if rank == 'random':
                    rng.shuffle(cands)
                else:
                    cands.sort(key=lambda r: -(r.rankval if np.isfinite(r.rankval) else -1e9))
            for r in cands[:free]:
                if cash < size:
                    break
                cash -= size
                positions[r.ticker] = dict(entry_price=px_today[r.ticker], entry_date=d,
                                           fam=fam_of[r.ticker])

    # chiusura forzata finale
    d = dates[-1]
    for tk, e in positions.items():
        s = series[tk]
        cp = float(s['close'].iloc[-1])
        gain = cp / e['entry_price'] - 1
        cash += size * (cp / e['entry_price'])
        gross = size * gain
        fees = FEE_BUY
        net = gross - fees - (TAX * (gross - fees) if gross - fees > 0 else 0.0)
        trades.append(dict(ticker=tk, family=e['fam'], entry_date=e['entry_date'],
                           exit_date=d, gross_pct=gain * 100, net_eur=net,
                           days=(d - e['entry_date']).days, reason='END'))

    eq = pd.DataFrame(equity_curve, columns=['date', 'equity']).set_index('date')
    return pd.DataFrame(trades), eq, skipped_no_slot


def benchmark_equalweight(df, capital):
    """Buy & hold equipesato: compra tutti i ticker disponibili al primo giorno, tiene."""
    first = df['date'].min()
    start_px = df[df['date'] == first].set_index('ticker')['close']
    tickers = start_px.index
    per = capital / len(tickers)
    curve = []
    for d, sub in df.groupby('date'):
        p = sub.set_index('ticker')['close']
        val = sum(per * (p[tk] / start_px[tk]) for tk in tickers if tk in p.index)
        curve.append((d, val))
    return pd.DataFrame(curve, columns=['date', 'equity']).set_index('date')


def stats_from_equity(eq, label):
    e = eq['equity']
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    tot = e.iloc[-1] / e.iloc[0] - 1
    cagr = (1 + tot) ** (1 / yrs) - 1 if yrs > 0 else np.nan
    mdd = (e / e.cummax() - 1).min()
    return dict(label=label, tot=tot * 100, cagr=cagr * 100, mdd=mdd * 100,
                start=e.iloc[0], end=e.iloc[-1])


def report(trades, eq, skipped, capital, size, max_pos, label):
    st = stats_from_equity(eq, label)
    n = len(trades)
    if n:
        wr = (trades['gross_pct'] > 0).mean() * 100
        net = trades['net_eur'].sum()
        dur = trades['days'].median()
    else:
        wr = net = dur = np.nan
    # utilizzo medio: quanti giorni-posizione / (giorni * max_pos)
    print(f"\n  [{label}]")
    print(f"    equity {st['start']:,.0f} -> {st['end']:,.0f}EUR   tot {st['tot']:+.1f}%   "
          f"CAGR {st['cagr']:+.1f}%   maxDD {st['mdd']:.1f}%")
    print(f"    trade N={n}  WR={wr:.1f}%  durata med={dur:.0f}gg  "
          f"P&L netto realizzato {net:+,.0f}EUR  ({net/n:+.0f}EUR/trade)" if n else "    nessun trade")
    print(f"    segnali persi per slot pieno: {skipped:,}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--families', default='core', choices=['core', 'equity'])
    ap.add_argument('--mode', default='all',
                    choices=['all', 'always', 'strength', 'worst', 'score', 'random'])
    ap.add_argument('--max-positions', type=int, default=8)
    ap.add_argument('--position-size', type=float, default=10000)
    ap.add_argument('--rank', default='score', choices=['score', 'random'],
                    help='come scegliere quando i candidati superano gli slot liberi')
    ap.add_argument('--pct', type=float, default=0.85)
    ap.add_argument('--min-sp', type=float, default=0.04)
    args = ap.parse_args()

    fams = CORE if args.families == 'core' else EQUITY
    capital = args.max_positions * args.position_size
    t0 = datetime.now()

    usecols = ['ticker', 'family', 'date', 'close', 'fwd_ret_60', 'fwd_mar_60'] + FEATURES
    base = pd.read_csv(DATASET, parse_dates=['date'], usecols=usecols)
    base = base[base['family'].isin(fams)].copy()
    base = base.dropna(subset=FEATURES).sort_values(['ticker', 'date'])
    analyzers = {f: ETFTechnicalAnalyzer(famiglia=f) for f in fams}
    base = get_trade_ret(base, analyzers, args.families)

    print(f"Famiglie {args.families} | capitale {capital:,.0f}EUR = {args.max_positions} x "
          f"{args.position_size:,.0f}EUR | rank={args.rank}")
    print(f"Universo: {base['ticker'].nunique()} ticker, {base['date'].min().date()} -> {base['date'].max().date()}")

    bench = benchmark_equalweight(base, capital)
    print("\n" + "=" * 78)
    report(pd.DataFrame(), bench, 0, capital, args.position_size, args.max_positions,
           'BENCHMARK buy&hold equipesato')

    modes = ['always', 'strength', 'worst', 'random'] if args.mode == 'all' else [args.mode]
    for m in modes:
        df = build_signal(base.copy(), m, args.pct, args.min_sp)
        rank = 'random' if m == 'random' else args.rank
        tr, eq, skipped = simulate_portfolio(df, analyzers, capital, args.position_size,
                                             args.max_positions, rank)
        report(tr, eq, skipped, capital, args.position_size, args.max_positions, f'MODE={m}')
        # split IN/OUT sull'equity
        for tag, mask in [('IN <2025-01', eq.index < SPLIT), ('OUT >=2025-01', eq.index >= SPLIT)]:
            sub = eq[mask]
            if len(sub) > 20:
                s = stats_from_equity(sub, tag)
                print(f"      {tag}: tot {s['tot']:+.1f}%  CAGR {s['cagr']:+.1f}%  maxDD {s['mdd']:.1f}%")

    print(f"\nTempo: {datetime.now() - t0}")


if __name__ == '__main__':
    main()
