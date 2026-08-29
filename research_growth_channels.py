"""
research_growth_channels.py — SCRATCH / RESEARCH (2026-08-29)

Domanda dell'utente: partendo dai dati REALI (Golden Dataset congelato), si puo'
caratterizzare il "canale di crescita" degli ETF che hanno poi performato bene, ed
estrarne una firma ripetibile / predittiva?

Metodo (nessun impatto sulla produzione — legge solo etf_price_history_frozen):
  FASE 1 (build): per ogni (ticker, giorno) calcola un vettore di feature usando SOLO
    i dati fino a quel giorno, piu' i target FORWARD (rendimento e drawdown nei
    successivi 40/60/90 giorni di borsa). Output: data/research_growth_dataset.csv.gz
  FASE 2 (analyze): split IN/OUT-of-sample, confronta la distribuzione di ogni feature
    tra il quartile "vincente" e quello "perdente" del target, tiene solo le feature
    il cui segno REGGE anche out-of-sample, costruisce un quality-score prototipo e ne
    mostra la monotonicita' IN vs OUT.

Uso (dentro il container):
  docker exec etf_monitor_system-app-1 python3 /app/research_growth_channels.py
  docker exec etf_monitor_system-app-1 python3 /app/research_growth_channels.py --phase analyze --target fwd_ret_60 --split 2025-01-01

Nota memoria/RAM container: dataset ~250k righe x ~35 col float ~= 70 MB in pandas,
salvato gzip ~= 15 MB. Un ticker alla volta, un solo concat finale.
"""
import sys
sys.path.insert(0, '/app')

import argparse
import os
from datetime import datetime

import numpy as np
import pandas as pd

from database import PriceDatabase

FROZEN_BATCH = '2026-08-07'
OUT_DATASET = '/app/data/research_growth_dataset.csv.gz'
OUT_SUMMARY = '/app/data/research_growth_summary.csv'
EXCEL = '/app/etf_monitoraggio.xlsx'

WARMUP = 252          # servono per SMA200 + finestre canale
FWD_HORIZONS = [40, 60, 90]
MAX_FWD = max(FWD_HORIZONS)

FEATURE_COLS = [
    # allineamento / struttura
    'dist_ema20', 'dist_sma50', 'dist_sma200', 'gap_ema20_sma50', 'gap_sma50_sma200',
    'ema20_slope_10', 'sma50_slope_20',
    # momentum
    'rsi', 'rsi_chg_5', 'adx', 'adx_chg_5', 'macd_hist_norm', 'macd_hist_chg_5',
    # volatilita' / rischio
    'atr_norm', 'rvol_20', 'dd_from_peak_126', 'dd_from_peak_252',
    # canale di crescita
    'trend_r2_20', 'trend_r2_40', 'trend_r2_60',
    'trend_slope_40_ann', 'channel_width_40',
    'pct_above_ema20_60', 'up_day_ratio_20',
]


# ────────────────────────────────────────────────────────────────────────────
# FASE 1 — costruzione dataset feature + target forward
# ────────────────────────────────────────────────────────────────────────────
def _ema(s, span):
    return s.ewm(span=span, adjust=False).mean()


def _rsi(s, period=14):
    d = s.diff()
    g = d.where(d > 0, 0.0)
    l = (-d).where(d < 0, 0.0)
    ag = g.ewm(com=period - 1, min_periods=period).mean()
    al = l.ewm(com=period - 1, min_periods=period).mean()
    rs = ag / al.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _adx(high, low, close, period=14):
    tr = pd.concat([high - low, (high - close.shift(1)).abs(),
                    (low - close.shift(1)).abs()], axis=1).max(axis=1)
    dmp = high.diff()
    dmn = -low.diff()
    dmp = dmp.where((dmp > dmn) & (dmp > 0), 0.0)
    dmn = dmn.where((dmn > dmp) & (dmn > 0), 0.0)
    atr = tr.ewm(com=period - 1, min_periods=period).mean()
    safe = atr.replace(0, np.nan)
    dip = 100 * dmp.ewm(com=period - 1, min_periods=period).mean() / safe
    dim = 100 * dmn.ewm(com=period - 1, min_periods=period).mean() / safe
    dx = 100 * (dip - dim).abs() / (dip + dim).replace(0, np.nan)
    return dx.ewm(com=period - 1, min_periods=period).mean(), atr


def _atr(high, low, close, period=14):
    tr = pd.concat([high - low, (high - close.shift(1)).abs(),
                    (low - close.shift(1)).abs()], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def _rolling_trend(logprice, window):
    """R^2 e slope (log-return/giorno) di una retta OLS su una finestra mobile.
    Usa l'identita': r2 = corr(t, y)^2 ; slope = corr * std(y)/std(t).
    corr con l'indice temporale GLOBALE == corr con la rampa interna (invarianza affine)."""
    t = pd.Series(np.arange(len(logprice), dtype=float), index=logprice.index)
    r = logprice.rolling(window).corr(t)
    std_y = logprice.rolling(window).std()
    std_t = np.sqrt((window ** 2 - 1) / 12.0)
    slope = r * std_y / std_t
    r2 = r ** 2
    resid_std = std_y * np.sqrt((1 - r2).clip(lower=0))
    return r2, slope, resid_std


_HIVOL_FAMILIES = {'crypto_digital_assets', 'leva_single_stock'}

FAMILY_PRESETS = {
    'core': ['equity_sviluppati', 'mercati_emergenti', 'settoriali_growth',
             'oro_metalli_preziosi', 'metalli_industriali'],
    'equity': ['equity_sviluppati', 'settoriali_growth', 'mercati_emergenti'],
    'all': None,
}


def resolve_families(arg):
    if not arg or arg == 'all':
        return None
    if arg in FAMILY_PRESETS:
        return FAMILY_PRESETS[arg]
    return [x.strip() for x in arg.split(',') if x.strip()]


def clean_ohlc(df, family):
    """Ripara/scarta i print corrotti del Golden Dataset (spike che si annullano
    il giorno dopo, tipo 3LAM.MI). Ritorna df pulito o None se irrecuperabile."""
    df = df.copy()
    close = df['Close'].astype(float)
    if (close <= 0).any():
        return None
    thr = 0.9 if family in _HIVOL_FAMILIES else 0.55   # log-return giornaliero max plausibile
    lr = np.log(close).diff()
    bad = lr.abs() > thr
    if not bad.any():
        return df
    idx = np.where(bad.values)[0]
    if len(idx) > 6:
        return None                                   # troppo corrotto
    lc = np.log(close.values)
    for k in idx:
        if 0 < k < len(lc) - 1:
            lc[k] = 0.5 * (lc[k - 1] + lc[k + 1])      # interpola in log
    fixed = np.exp(lc)
    if np.abs(np.diff(np.log(fixed))).max() > thr:
        return None                                   # ancora spike dopo la riparazione
    ratio = fixed / close.values
    for col in ('Open', 'High', 'Low', 'Close'):
        if col in df.columns:
            df[col] = df[col].astype(float).values * ratio
    return df


def build_features(df):
    """df: OHLCV index=Date. Ritorna DataFrame con FEATURE_COLS + target forward."""
    close = df['Close'].astype(float)
    high = df['High'].astype(float)
    low = df['Low'].astype(float)
    n = len(close)
    if n < WARMUP + 30:
        return None

    ema20 = _ema(close, 20)
    ema10 = _ema(close, 10)
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    rsi = _rsi(close)
    adx, _ = _adx(high, low, close)
    atr = _atr(high, low, close)

    macd = _ema(close, 12) - _ema(close, 26)
    macd_sig = _ema(macd, 9)
    macd_hist = macd - macd_sig

    logp = np.log(close)
    r2_20, _, _ = _rolling_trend(logp, 20)
    r2_40, slope_40, resid_40 = _rolling_trend(logp, 40)
    r2_60, _, _ = _rolling_trend(logp, 60)

    out = pd.DataFrame(index=close.index)
    out['close'] = close
    out['dist_ema20'] = (close - ema20) / ema20 * 100
    out['dist_sma50'] = (close - sma50) / sma50 * 100
    out['dist_sma200'] = (close - sma200) / sma200 * 100
    out['gap_ema20_sma50'] = (ema20 - sma50) / sma50 * 100
    out['gap_sma50_sma200'] = (sma50 - sma200) / sma200 * 100
    out['ema20_slope_10'] = (np.log(ema20) - np.log(ema20).shift(10)) / 10 * 252 * 100  # %/anno lin.
    out['sma50_slope_20'] = (np.log(sma50) - np.log(sma50).shift(20)) / 20 * 252 * 100
    out['rsi'] = rsi
    out['rsi_chg_5'] = rsi - rsi.shift(5)
    out['adx'] = adx
    out['adx_chg_5'] = adx - adx.shift(5)
    out['macd_hist_norm'] = macd_hist / close * 100
    out['macd_hist_chg_5'] = (macd_hist - macd_hist.shift(5)) / close * 100
    out['atr_norm'] = atr / close * 100
    out['rvol_20'] = close.pct_change().rolling(20).std() * np.sqrt(252) * 100
    out['dd_from_peak_126'] = (close / close.rolling(126).max() - 1) * 100
    out['dd_from_peak_252'] = (close / close.rolling(252).max() - 1) * 100
    out['trend_r2_20'] = r2_20
    out['trend_r2_40'] = r2_40
    out['trend_r2_60'] = r2_60
    out['trend_slope_40_ann'] = slope_40 * 252 * 100          # %/anno lineare (no exp -> no blow-up)
    out['channel_width_40'] = resid_40 * 100          # ~ % (spazio log)
    out['pct_above_ema20_60'] = (close > ema20).rolling(60).mean() * 100
    out['up_day_ratio_20'] = (close.diff() > 0).rolling(20).mean() * 100

    # ── target forward ──────────────────────────────────────────────────────
    arr = close.values
    for h in FWD_HORIZONS:
        fwd = close.shift(-h) / close - 1
        out[f'fwd_ret_{h}'] = fwd * 100
        # max drawdown lungo il percorso forward (incluso il punto di partenza),
        # calcolato solo dove la finestra completa esiste
        mdd = np.full(n, np.nan)
        for i in range(n - h):
            path = arr[i:i + h + 1]
            cummax = np.maximum.accumulate(path)
            mdd[i] = (path / cummax - 1).min() * 100
        out[f'fwd_maxdd_{h}'] = mdd
        out[f'fwd_mar_{h}'] = out[f'fwd_ret_{h}'] / out[f'fwd_maxdd_{h}'].abs().replace(0, np.nan)

    return out


def load_family_map():
    try:
        from technical_analysis import ETFTechnicalAnalyzer
        xl = pd.read_excel(EXCEL, sheet_name='ETF')
        m = {}
        for _, r in xl.iterrows():
            tk = str(r.get('Ticker', '')).strip()
            if tk and tk.lower() != 'nan':
                m[tk] = ETFTechnicalAnalyzer.detect_family(str(r.get('Categoria', '')))
        return m
    except Exception as e:
        print(f"  [!] family map non disponibile: {e}")
        return {}


def phase_build():
    db = PriceDatabase()
    conn = db._get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT ticker FROM etf_price_history_frozen WHERE freeze_batch=%s",
                    (FROZEN_BATCH,))
        tickers = sorted(r[0] for r in cur.fetchall())
    conn.close()
    print(f"Golden Dataset batch {FROZEN_BATCH}: {len(tickers)} ticker")

    fam_map = load_family_map()
    parts = []
    skip_short, skip_corrupt = [], []
    for i, tk in enumerate(tickers, 1):
        df = db.get_frozen_ohlcv(tk, FROZEN_BATCH)
        if df.empty or len(df) < WARMUP + 30:
            skip_short.append(tk)
            continue
        df = clean_ohlc(df, fam_map.get(tk, 'unknown'))
        if df is None:
            skip_corrupt.append(tk)
            continue
        feats = build_features(df)
        if feats is None:
            skip_short.append(tk)
            continue
        feats = feats.iloc[WARMUP:].copy()          # scarta warm-up
        feats.insert(0, 'ticker', tk)
        feats.insert(1, 'family', fam_map.get(tk, 'unknown'))
        feats.insert(2, 'date', feats.index)
        parts.append(feats.reset_index(drop=True))
        if i % 40 == 0:
            print(f"  {i}/{len(tickers)} ...")

    full = pd.concat(parts, ignore_index=True)
    os.makedirs('/app/data', exist_ok=True)
    full.to_csv(OUT_DATASET, index=False, compression='gzip', float_format='%.5f')
    print(f"\n  scartati storico corto: {len(skip_short)} {skip_short}")
    print(f"  scartati DATI CORROTTI:  {len(skip_corrupt)} {skip_corrupt}")
    print(f"\nOK — {len(full):,} righe ({full['ticker'].nunique()} ticker)")
    print(f"     range date: {full['date'].min().date()} -> {full['date'].max().date()}")
    print(f"     salvato: {OUT_DATASET}")


# ────────────────────────────────────────────────────────────────────────────
# FASE 1b — LEADERBOARD: i piu' performanti + i loro "episodi di crescita"
# ────────────────────────────────────────────────────────────────────────────
def _episodes(close, min_gain=0.15, min_days=20):
    """Segmenta i tratti in cui close > EMA50: per ognuno misura gain, max
    drawdown interno, durata. Tiene solo quelli >= min_gain e >= min_days.
    Ritorna lista di dict con posizioni indice i0/i1."""
    ema50 = close.ewm(span=50, adjust=False).mean()
    up = (close > ema50).values
    arr = close.values
    eps, i = [], 0
    n = len(arr)
    while i < n:
        if not up[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and up[j + 1]:
            j += 1
        seg = arr[i:j + 1]
        if len(seg) >= min_days:
            gain = seg[-1] / seg[0] - 1
            mdd = (seg / np.maximum.accumulate(seg) - 1).min()
            if gain >= min_gain:
                eps.append({'i0': i, 'i1': j, 'gain': gain, 'maxdd': mdd,
                            'days': j - i})
        i = j + 1
    return eps


def phase_leaderboard(entry_lag=3, min_gain=0.15, top_episodes=30, families=None):
    keep = ['ticker', 'family', 'date', 'close'] + FEATURE_COLS
    df = pd.read_csv(OUT_DATASET, parse_dates=['date'], usecols=keep)
    if families:
        df = df[df['family'].isin(families)]
        print(f"  (filtro famiglie: {families} -> {df['ticker'].nunique()} ticker)")
    df = df.sort_values(['ticker', 'date']).reset_index(drop=True)
    for c in FEATURE_COLS:                              # winsorize per la firma d'ingresso
        df[c] = df[c].clip(df[c].quantile(0.005), df[c].quantile(0.995))

    # ── 1. classifica per ETF sull'intera finestra congelata ────────────────
    perf_rows, all_eps = [], []
    for tk, g in df.groupby('ticker'):
        g = g.reset_index(drop=True)
        c = g['close']
        if len(c) < 200:
            continue
        yrs = (g['date'].iloc[-1] - g['date'].iloc[0]).days / 365.25
        tot = c.iloc[-1] / c.iloc[0] - 1
        cagr = (1 + tot) ** (1 / yrs) - 1 if yrs > 0 else np.nan
        mdd = (c / c.cummax() - 1).min()
        mar = cagr / abs(mdd) if mdd < 0 else np.nan
        eps = _episodes(c, min_gain=min_gain)
        for e in eps:
            e2 = {'ticker': tk, 'family': g['family'].iloc[0],
                  'start': g['date'].iloc[e['i0']].date(),
                  'end': g['date'].iloc[e['i1']].date(),
                  'gain_pct': e['gain'] * 100, 'maxdd_pct': e['maxdd'] * 100,
                  'days': e['days']}
            # firma d'ingresso: feature entry_lag giorni dopo l'inizio episodio
            k = min(e['i0'] + entry_lag, e['i1'])
            for f in FEATURE_COLS:
                e2[f] = g[f].iloc[k]
            all_eps.append(e2)
        perf_rows.append({'ticker': tk, 'family': g['family'].iloc[0],
                          'cagr_pct': cagr * 100, 'maxdd_pct': mdd * 100,
                          'mar': mar, 'tot_ret_pct': tot * 100,
                          'n_episodi': len(eps),
                          'gain_medio_ep_pct': np.mean([e['gain'] for e in eps]) * 100 if eps else np.nan})

    perf = pd.DataFrame(perf_rows)
    eps_df = pd.DataFrame(all_eps)
    pd.set_option('display.width', 220); pd.set_option('display.max_columns', 30)

    print("\n" + "=" * 78 + "\n  CLASSIFICA ETF — intera finestra congelata (per MAR = CAGR/|maxDD|)\n" + "=" * 78)
    show = ['ticker', 'family', 'cagr_pct', 'maxdd_pct', 'mar', 'tot_ret_pct', 'n_episodi', 'gain_medio_ep_pct']
    top = perf.sort_values('mar', ascending=False).head(25)
    print(top[show].to_string(index=False, float_format=lambda x: f"{x:8.2f}"))
    print("\n  --- coda (peggiori 10 per MAR) ---")
    print(perf.sort_values('mar', ascending=False).tail(10)[show].to_string(index=False, float_format=lambda x: f"{x:8.2f}"))

    print("\n  Performance mediana per FAMIGLIA:")
    fam = perf.groupby('family')[['cagr_pct', 'maxdd_pct', 'mar', 'n_episodi']].median().sort_values('mar', ascending=False)
    print(fam.to_string(float_format=lambda x: f"{x:8.2f}"))

    if eps_df.empty:
        print("\nNessun episodio di crescita trovato con la soglia data.")
        return
    eps_df.to_csv('/app/data/research_growth_episodes.csv', index=False)
    print(f"\n{len(eps_df)} episodi di crescita (gain >= {min_gain*100:.0f}%, >= 20gg) "
          f"su {eps_df['ticker'].nunique()} ETF -> data/research_growth_episodes.csv")

    print("\n" + "=" * 78 + f"\n  TOP {top_episodes} EPISODI DI CRESCITA (per gain%)\n" + "=" * 78)
    cols = ['ticker', 'family', 'start', 'end', 'days', 'gain_pct', 'maxdd_pct']
    best = eps_df.sort_values('gain_pct', ascending=False).head(top_episodes)
    print(best[cols].to_string(index=False, float_format=lambda x: f"{x:8.2f}"))

    # ── 2. firma d'ingresso: media feature nei top episodi vs baseline ──────
    base_mu = df[FEATURE_COLS].mean()
    base_sd = df[FEATURE_COLS].std(ddof=0)
    topN = eps_df.sort_values('gain_pct', ascending=False).head(max(top_episodes, 40))
    print("\n" + "=" * 78 +
          f"\n  FIRMA D'INGRESSO — media feature all'inizio dei top {len(topN)} episodi\n"
          "  (z = (media_episodi - media_universo) / sd_universo ; |z|>0.4 = marcato)\n" + "=" * 78)
    sig = pd.DataFrame({
        'feature': FEATURE_COLS,
        'media_episodi': [topN[f].mean() for f in FEATURE_COLS],
        'media_universo': [base_mu[f] for f in FEATURE_COLS],
    })
    sig['z'] = (sig['media_episodi'] - sig['media_universo']) / base_sd[FEATURE_COLS].values
    sig = sig.sort_values('z', key=lambda s: s.abs(), ascending=False)
    print(sig.to_string(index=False, float_format=lambda x: f"{x:9.3f}"))
    sig.to_csv('/app/data/research_growth_entry_signature.csv', index=False)
    print("\n  -> data/research_growth_entry_signature.csv")
    print("\n  Lettura: le feature con |z| alto e coerente sono il 'canale' tipico da cui")
    print("  parte una corsa reale. Vanno poi verificate come filtro OOS nella FASE 2.")


# ────────────────────────────────────────────────────────────────────────────
# FASE 2 — analisi winners vs losers, IN/OUT split
# ────────────────────────────────────────────────────────────────────────────
def _cohen_d(a, b):
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return np.nan
    va, vb = a.var(ddof=1), b.var(ddof=1)
    pooled = np.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    if pooled == 0:
        return np.nan
    return (a.mean() - b.mean()) / pooled


def _winsor(s, p=0.005):
    lo, hi = s.quantile(p), s.quantile(1 - p)
    return s.clip(lo, hi)


def _spearman(a, b):
    m = a.notna() & b.notna()
    if m.sum() < 30:
        return np.nan
    return a[m].rank().corr(b[m].rank())


def phase_analyze(target, split_date, top_q, families=None):
    keep = ['ticker', 'family', 'date'] + FEATURE_COLS + [target]
    df = pd.read_csv(OUT_DATASET, parse_dates=['date'], usecols=keep)
    if families:
        df = df[df['family'].isin(families)]
        print(f"FILTRO FAMIGLIE: {families}  ({df['ticker'].nunique()} ticker)")
    print(f"Dataset: {len(df):,} righe, {df['ticker'].nunique()} ticker, "
          f"{df['date'].min().date()} -> {df['date'].max().date()}")

    need = FEATURE_COLS + [target]
    df = df.dropna(subset=need).copy()
    df = df[np.isfinite(df[need]).all(axis=1)].copy()

    # WINSORIZE globale: target + ogni feature a [0.5%, 99.5%] — neutralizza i print
    # corrotti residui senza buttare righe.
    df[target] = _winsor(df[target])
    for c in FEATURE_COLS:
        df[c] = _winsor(df[c])
    print(f"Dopo dropna/finite + winsorize su target={target}: {len(df):,} righe\n")

    split = pd.Timestamp(split_date)
    IN = df[df['date'] < split].copy()
    OUT = df[df['date'] >= split].copy()
    print(f"IN  (< {split.date()}): {len(IN):,} righe, {IN['ticker'].nunique()} ticker  "
          f"mediana {target}={IN[target].median():.2f}%")
    print(f"OUT (>= {split.date()}): {len(OUT):,} righe, {OUT['ticker'].nunique()} ticker  "
          f"mediana {target}={OUT[target].median():.2f}%")

    hi = IN[target].quantile(1 - top_q)
    lo = IN[target].quantile(top_q)
    win_in, los_in = IN[IN[target] >= hi], IN[IN[target] <= lo]
    win_out, los_out = OUT[OUT[target] >= hi], OUT[OUT[target] <= lo]

    print("\n── Famiglie nel bucket WINNER (IN, soglia {:.1f}%) ──".format(hi))
    fam = (win_in['family'].value_counts(normalize=True) * 100).round(1)
    base = (IN['family'].value_counts(normalize=True) * 100).round(1)
    for f in fam.index[:10]:
        print(f"   {f:<26} {fam[f]:5.1f}%   (baseline {base.get(f, 0):5.1f}%)")

    # ── metrica robusta: Spearman feature-vs-target, IN e OUT ──────────────
    rows = []
    for c in FEATURE_COLS:
        sp_in = _spearman(IN[c], IN[target])
        sp_out = _spearman(OUT[c], OUT[target])
        d_in = _cohen_d(win_in[c], los_in[c])
        holds = bool(np.sign(sp_in) == np.sign(sp_out) and abs(sp_out) >= 0.03)
        rows.append({'feature': c, 'sp_IN': sp_in, 'sp_OUT': sp_out,
                     'd_IN(win-los)': d_in,
                     'win_IN': win_in[c].mean(), 'los_IN': los_in[c].mean(),
                     'HOLDS_OOS': holds})
    res = pd.DataFrame(rows).sort_values('sp_IN', key=lambda s: s.abs(), ascending=False)
    pd.set_option('display.width', 220)
    pd.set_option('display.max_columns', 20)
    print("\n── Correlazione di rango (Spearman) feature -> " + target + " ──")
    print("   sp>0 = feature alta -> rendimento forward alto. HOLDS_OOS = segno regge IN&OUT e |sp_OUT|>=0.03")
    print(res.to_string(index=False, float_format=lambda x: f"{x:8.3f}"))
    res.to_csv(OUT_SUMMARY, index=False)
    print(f"\n   salvato: {OUT_SUMMARY}")

    kept = res[res['HOLDS_OOS']].copy()
    if kept.empty:
        print("\n*** Nessuna feature regge out-of-sample. Nessuna firma ripetibile trovata "
              "con questo target/split. ***")
        return

    # quality-score prototipo: z-score (mean/std da IN) delle feature che reggono,
    # segno = segno della Spearman IN, sommati.
    print(f"\n── Quality-score prototipo da {len(kept)} feature che reggono OOS ──")
    print("   " + ", ".join(f"{r.feature}({'+' if r.sp_IN > 0 else '-'})"
                            for r in kept.itertuples()))
    mu = IN[kept['feature']].mean()
    sd = IN[kept['feature']].std(ddof=0).replace(0, np.nan)
    sign = np.sign(kept.set_index('feature')['sp_IN'])

    def score(d):
        z = (d[kept['feature']] - mu) / sd
        return (z * sign.values).sum(axis=1)

    for name, d in [('IN', IN), ('OUT', OUT)]:
        dd = d.copy()
        dd['score'] = score(dd)
        dd = dd.dropna(subset=['score'])
        dd['decile'] = pd.qcut(dd['score'], 10, labels=False, duplicates='drop')
        g = dd.groupby('decile')[target].agg(['median', 'mean', 'count'])
        print(f"\n   [{name}] {target} per decile di score (0=peggiore, 9=migliore):")
        for dec, r in g.iterrows():
            print(f"     dec {int(dec)}:  median {r['median']:6.2f}%   mean {r['mean']:6.2f}%   N={int(r['count']):,}")
        top, bot = g.loc[g.index.max()], g.loc[g.index.min()]
        print(f"     spread top-bottom decile: median {top['median'] - bot['median']:+.2f}%  |  mean {top['mean'] - bot['mean']:+.2f}%")

    # tenuta per ANNO (regime-dependence): spread mediano top-bottom decile
    print("\n── Tenuta per anno (spread mediano decile 9 - decile 0) ──")
    allsc = df.copy()
    allsc['score'] = score(allsc)
    allsc = allsc.dropna(subset=['score'])
    for yr, gy in allsc.groupby(allsc['date'].dt.year):
        if len(gy) < 200:
            continue
        gy = gy.assign(dec=pd.qcut(gy['score'], 10, labels=False, duplicates='drop'))
        gg = gy.groupby('dec')[target].median()
        d0, d9 = gg.loc[gg.index.min()], gg.loc[gg.index.max()]
        print(f"   {yr}:  dec0 {d0:+6.2f}%   dec9 {d9:+6.2f}%   spread {d9 - d0:+6.2f}%   N={len(gy):,}")

    # controllo autocorrelazione: 1 riga per ticker per mese
    print("\n── Robustezza: campione ridotto a 1 riga / ticker / mese ──")
    samp = df.copy()
    samp['ym'] = samp['date'].dt.to_period('M')
    samp = samp.sort_values('date').groupby(['ticker', 'ym']).first().reset_index()
    s_in = samp[samp['date'] < split]
    s_out = samp[samp['date'] >= split]
    print(f"   N effettivo IN={len(s_in):,}  OUT={len(s_out):,} (vs {len(IN):,}/{len(OUT):,} grezzi)")
    for name, d in [('IN', s_in), ('OUT', s_out)]:
        dd = d.copy()
        dd['score'] = score(dd)
        dd = dd.dropna(subset=['score'])
        if len(dd) < 40:
            print(f"   [{name}] troppo pochi dati ({len(dd)})")
            continue
        dd['q'] = pd.qcut(dd['score'], 4, labels=False, duplicates='drop')
        g = dd.groupby('q')[target].median()
        print(f"   [{name}] {target} MEDIANO per quartile di score: " +
              "  ".join(f"Q{int(q)}={v:+.1f}%" for q, v in g.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['build', 'leaderboard', 'analyze', 'both'], default='both')
    ap.add_argument('--min-gain', type=float, default=0.15,
                    help='gain minimo per contare come episodio di crescita (default 0.15)')
    ap.add_argument('--target', default='fwd_ret_60',
                    help='fwd_ret_40/60/90 | fwd_mar_40/60/90')
    ap.add_argument('--split', default='2025-01-01', help='data split IN/OUT (YYYY-MM-DD)')
    ap.add_argument('--top-q', type=float, default=0.20, help='quantile winner/loser (0.20)')
    ap.add_argument('--families', default='all',
                    help="'all' | 'core' (5 famiglie smart_6_macd) | 'equity' | lista csv")
    args = ap.parse_args()
    fams = resolve_families(args.families)

    t0 = datetime.now()
    if args.phase in ('build', 'both'):
        print("=" * 78 + "\nFASE 1 — BUILD DATASET\n" + "=" * 78)
        phase_build()
    if args.phase in ('leaderboard', 'both'):
        print("\n" + "=" * 78 + "\nFASE 1b — LEADERBOARD (piu' performanti + episodi di crescita)\n" + "=" * 78)
        phase_leaderboard(min_gain=args.min_gain, families=fams)
    if args.phase in ('analyze', 'both'):
        print("\n" + "=" * 78 + f"\nFASE 2 — ANALYZE (target={args.target}, split={args.split})\n" + "=" * 78)
        phase_analyze(args.target, args.split, args.top_q, families=fams)
    print(f"\nTempo totale: {datetime.now() - t0}")


if __name__ == '__main__':
    main()
