"""
optimize_l0_sl_structural.py — SCRATCH, non committare.

Confronta lo Stop L0 a % fissa (baseline attuale) con candidati STRUTTURALI
(swing-low, ATR, ibrido) sullo stesso campione, stesso split IN/OUT, Golden
Dataset congelato. Idea utente 2026-08-28: invece di scegliere una % a priori,
testare una regola che mette lo stop sulla struttura di prezzo di ogni ETF.

Cosa varia SOLO lo scaglione "protezione capitale" (profit < 5%). Gli scaglioni
tier2/tier3 (pareggio a +5%, protezione-guadagno a +15%) restano identici alla
formula reale `calculate_sl_suggerito_l0`, per un confronto pulito.

Tutti i candidati strutturali hanno:
  - FLOOR: mai peggio di -8% dall'entry (perdita massima per trade limitata)
  - CAP:   mai piu' stretto di -1.5% (la struttura non puo' mettere lo stop a ridosso dell'entry)

Ingresso: `suggest_level_0()` reale (gate whitelist/blacklist bypassati).
TP: `calculate_tp_suggerito_l0()` reale, invariato.

Ottimizzazione: il segnale d'ingresso non dipende dal candidato SL, quindi si
calcola UNA volta per ticker (pass costoso) e poi si rigioca solo l'uscita per
ogni candidato (pass cheap) — evita di chiamare suggest_level_0 N volte.

Uso:
  docker cp optimize_l0_sl_structural.py etf_monitor_system-app-1:/app/
  docker exec -d etf_monitor_system-app-1 sh -c \
    'python3 /app/optimize_l0_sl_structural.py --family equity_sviluppati > /app/data/l0_struct.log 2>&1'
  tail -f data/l0_struct.log
"""
import sys
sys.path.insert(0, '/app')

import argparse
from datetime import datetime, date

import pandas as pd

from technical_analysis import ETFTechnicalAnalyzer
from database import PriceDatabase

FROZEN_BATCH = '2026-08-07'
IN_START, IN_END = date(2023, 8, 5), date(2025, 8, 5)
OUT_START, OUT_END = date(2025, 8, 5), date(2026, 8, 5)
FEE_BUY, FEE_SELL, TAX = 5.0, 5.0, 0.26
POSITION = 10000.0

TIER1_THRESHOLD = 0.05   # sotto questo profitto = fase "protezione capitale"
TIER2_THRESHOLD = 0.15
TIER2_MARKUP = 0.01
TIER3_GIVEBACK = 0.08
FLOOR_MAX_LOSS = 0.08    # SL protettivo mai sotto entry*(1-0.08)
CAP_MIN_LOSS = 0.015     # SL protettivo mai sopra entry*(1-0.015)


# ---------- candidati per lo scaglione "protezione capitale" ----------
# firma: fn(entry_price, cur_idx, close_full, low_roll, atr_abs) -> livello SL grezzo
def make_fixed(pct):
    return lambda ep, i, cf, lr, atr: ep * (1 - pct)

def make_swinglow(N, buf):
    key = f'min{N}'
    return lambda ep, i, cf, lr, atr: (lr[key].iloc[i] * (1 - buf)) if pd.notna(lr[key].iloc[i]) else ep * 0.95

def make_atr(k):
    return lambda ep, i, cf, lr, atr: (ep - k * atr.iloc[i]) if pd.notna(atr.iloc[i]) else ep * 0.95

def make_hybrid(N, atr_mult, cap_pct):
    key = f'min{N}'
    def fn(ep, i, cf, lr, atr):
        cand = ep * (1 - cap_pct)
        sl_struct = None
        sw = lr[key].iloc[i]
        a = atr.iloc[i]
        if pd.notna(sw) and pd.notna(a):
            sl_struct = sw - atr_mult * a
        return min(cand, sl_struct) if sl_struct is not None else cand
    return fn


CANDIDATES = {
    'fixed_4%':       make_fixed(0.04),
    'fixed_5%':       make_fixed(0.05),
    'fixed_6%':       make_fixed(0.06),
    'swinglow_10_0':  make_swinglow(10, 0.0),
    'swinglow_20_0':  make_swinglow(20, 0.0),
    'swinglow_20_1%': make_swinglow(20, 0.01),
    'swinglow_30_1%': make_swinglow(30, 0.01),
    'atr_2.0':        make_atr(2.0),
    'atr_2.5':        make_atr(2.5),
    'atr_3.0':        make_atr(3.0),
    'hybrid_20_0.5':  make_hybrid(20, 0.5, 0.08),
}
SWING_WINDOWS = [10, 20, 30]


def bypass_l0_gates(family):
    ETFTechnicalAnalyzer(famiglia='equity_sviluppati')
    cfg = ETFTechnicalAnalyzer._FAMILIES_CONFIG
    gp = cfg.setdefault('global_params', {})
    gp['l0_whitelist'] = []
    gp['l0_blacklist'] = []
    assert family in cfg.get('families', {}), f"{family} non nella config YAML"
    print(f"Gate L0 bypassati. Famiglia: {family}")


def load_universe(family, excel_path='/app/etf_monitoraggio.xlsx'):
    df = pd.read_excel(excel_path, sheet_name='ETF')
    out = []
    for _, row in df.iterrows():
        ticker = str(row.get('Ticker', '')).strip()
        categoria = str(row.get('Categoria', ''))
        if not ticker or ticker.lower() == 'nan':
            continue
        if ETFTechnicalAnalyzer.detect_family(categoria) == family:
            out.append(ticker)
    return out


def compute_entry_signals(analyzer, close_full, high_full, low_full, index, test_dates):
    """Pass costoso: per ogni test_date, suggest_level_0 direbbe 'entra'? (bool)."""
    sig = []
    for d in test_dates:
        pos = index.get_loc(d)
        cs = close_full.iloc[:pos + 1]
        hs = high_full.iloc[:pos + 1] if high_full is not None else None
        ls = low_full.iloc[:pos + 1] if low_full is not None else None
        r = analyzer.suggest_level_0(cs, hs, ls, current_level=3)
        sig.append(bool(r.get('l0_entry')))
    return sig


def sl_level(entry_price, cur_idx, close_full, low_roll, atr_abs, cur_price, slfn):
    profit = (cur_price - entry_price) / entry_price
    if profit < TIER1_THRESHOLD:
        raw = slfn(entry_price, cur_idx, close_full, low_roll, atr_abs)
        raw = max(raw, entry_price * (1 - FLOOR_MAX_LOSS))
        raw = min(raw, entry_price * (1 - CAP_MIN_LOSS))
        return raw
    if profit < TIER2_THRESHOLD:
        return entry_price * (1 + TIER2_MARKUP)
    return entry_price * (1 + profit - TIER3_GIVEBACK)


def replay(entry_sig, test_dates, index, close_full, low_roll, atr_abs, tp_pct, slfn):
    holding = False
    entry_price = entry_idx = entry_date = None
    trades = []
    for k, d in enumerate(test_dates):
        pos = index.get_loc(d)
        cur = float(close_full.iloc[pos])
        if not holding:
            if entry_sig[k]:
                holding = True
                entry_price, entry_idx, entry_date = cur, pos, d.date().isoformat()
        else:
            sl = sl_level(entry_price, pos, close_full, low_roll, atr_abs, cur, slfn)
            tp = entry_price * (1 + tp_pct) if tp_pct else None
            tp_hit = tp is not None and cur >= tp
            sl_hit = cur <= sl
            if sl_hit or tp_hit:
                trades.append({
                    'entry_date': entry_date, 'entry_price': entry_price,
                    'exit_price': cur, 'status': 'closed',
                    'reason': 'TP' if tp_hit else 'SL',
                })
                holding = False
                entry_price = entry_idx = entry_date = None
    if holding:
        trades.append({
            'entry_date': entry_date, 'entry_price': entry_price,
            'exit_price': float(close_full.iloc[-1]), 'status': 'open', 'reason': None,
        })
    return trades


def net_eur(t):
    gross = POSITION * (t['exit_price'] / t['entry_price'] - 1)
    fees = FEE_BUY + (FEE_SELL if t['status'] == 'closed' else 0)
    after = gross - fees
    tax = TAX * after if after > 0 else 0.0
    return after - tax


def bucket(iso):
    dd = datetime.strptime(iso, '%Y-%m-%d').date()
    if IN_START <= dd < IN_END:
        return 'IN'
    if OUT_START <= dd < OUT_END:
        return 'OUT'
    return None


def metrics(trades):
    closed = [t for t in trades if t['status'] == 'closed']
    if not closed:
        return dict(N=0, WR=None, PF=None, avg=None, pnl=0.0)
    g = [net_eur(t) for t in closed]
    pos = sum(x for x in g if x > 0)
    neg = -sum(x for x in g if x < 0)
    return dict(
        N=len(closed),
        WR=round(100 * sum(1 for x in g if x > 0) / len(closed), 1),
        PF=(round(pos / neg, 2) if neg > 0 else 999.0),
        avg=round(sum(g) / len(closed) / POSITION * 100, 2),
        pnl=round(sum(g), 0),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--family', default='equity_sviluppati')
    args = ap.parse_args()
    fam = args.family

    bypass_l0_gates(fam)
    tickers = load_universe(fam)
    print(f"Ticker '{fam}': {len(tickers)}")

    db = PriceDatabase()
    per_ticker = []
    for tk in tickers:
        hist = db.get_frozen_ohlcv(tk, FROZEN_BATCH)
        if hist.empty or len(hist) < 220:
            print(f"  SKIP {tk} ({len(hist)}gg)")
            continue
        has_ohlc = all(c in hist.columns for c in ['Open', 'High', 'Low'])
        cf = hist['Close'].astype(float)
        hf = hist['High'].astype(float) if has_ohlc else None
        lf = hist['Low'].astype(float) if has_ohlc else None
        idx = hist.index
        test_dates = [d for d in idx if d.date() >= IN_START]
        if not test_dates:
            continue
        an = ETFTechnicalAnalyzer(famiglia=fam)
        tp_pct = an.p.get('l0_take_profit_pct')
        # precompute (candidate-independent)
        low_roll = {f'min{N}': (lf.rolling(N).min() if lf is not None else cf.rolling(N).min())
                    for N in SWING_WINDOWS}
        atr_abs = (an._calculate_atr(hf, lf, cf, 14) if has_ohlc
                   else pd.Series(index=idx, dtype=float))
        print(f"  {tk}: calcolo segnali ingresso...", flush=True)
        sig = compute_entry_signals(an, cf, hf, lf, idx, test_dates)
        n_sig = sum(sig)
        print(f"    {n_sig} bar con segnale L0", flush=True)
        per_ticker.append(dict(tk=tk, sig=sig, test_dates=test_dates, idx=idx,
                               cf=cf, low_roll=low_roll, atr_abs=atr_abs, tp_pct=tp_pct))

    print(f"\nTicker validi: {len(per_ticker)}")
    print("=" * 92)
    hdr = f"{'candidato':>16} | {'IN  N':>6} {'WR':>6} {'PF':>6} {'avg%':>7} {'PnL10k':>10} | " \
          f"{'OUT N':>6} {'WR':>6} {'PF':>6} {'avg%':>7} {'PnL10k':>10}"
    print(hdr)
    print("-" * 92)

    for name, slfn in CANDIDATES.items():
        all_tr = []
        for pt in per_ticker:
            tr = replay(pt['sig'], pt['test_dates'], pt['idx'], pt['cf'],
                        pt['low_roll'], pt['atr_abs'], pt['tp_pct'], slfn)
            all_tr.extend(tr)
        mi = metrics([t for t in all_tr if bucket(t['entry_date']) == 'IN'])
        mo = metrics([t for t in all_tr if bucket(t['entry_date']) == 'OUT'])
        print(f"{name:>16} | {mi['N']:>6} {str(mi['WR']):>6} {str(mi['PF']):>6} "
              f"{str(mi['avg']):>7} {str(mi['pnl']):>10} | "
              f"{mo['N']:>6} {str(mo['WR']):>6} {str(mo['PF']):>6} "
              f"{str(mo['avg']):>7} {str(mo['pnl']):>10}", flush=True)

    print("=" * 92)
    print("Leggere: un candidato vale SOLO se OUT tiene rispetto a IN (no crollo).")
    print("N<30 IN o OUT = non conclusivo. floor -8% / cap -1.5% applicati a tutti gli strutturali.")


if __name__ == '__main__':
    main()
