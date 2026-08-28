"""
optimize_l0_sl_tier1_em.py — SCRATCH, non committare.

Sweep del primo scaglione dello Stop L0 (`l0_sl_tier1_buffer_pct`, oggi 4% di
default) per la famiglia `mercati_emergenti`, stesso metodo di
CANDIDATE_MODEL_L0_SL_20260820 (che fu fatto solo per equity_sviluppati).

- Motore: backtest_l0_v2.simulate_l0 (logica reale: suggest_level_0 per l'ingresso,
  calculate_sl_suggerito_l0 / calculate_tp_suggerito_l0 per l'uscita).
- Universo: solo ticker la cui Categoria Excel -> detect_family == 'mercati_emergenti'.
- Whitelist E blacklist L0 bypassate (entrambe: bug del 2026-08-24 = bypassare solo
  la whitelist lascia tutto bloccato dalla blacklist).
- Split IN 2023-08-05->2025-08-05 / OUT 2025-08-05->2026-08-05 (stesso di
  backtest_l1.py / CANDIDATE_MODEL_L0_SL_20260820).
- Golden Dataset congelato batch 2026-08-07.

Uso (dentro il container):
  docker cp optimize_l0_sl_tier1_em.py etf_monitor_system-app-1:/app/
  docker exec etf_monitor_system-app-1 python3 /app/optimize_l0_sl_tier1_em.py
"""
import sys
sys.path.insert(0, '/app')

from datetime import datetime, date

import pandas as pd

from technical_analysis import ETFTechnicalAnalyzer
from database import PriceDatabase
from backtest_l0_v2 import simulate_l0

FROZEN_BATCH = '2026-08-07'
FAMILY = 'mercati_emergenti'
BUFFERS = [0.02, 0.03, 0.04, 0.05, 0.06, 0.07]
IN_START, IN_END = date(2023, 8, 5), date(2025, 8, 5)
OUT_START, OUT_END = date(2025, 8, 5), date(2026, 8, 5)
FEE_BUY, FEE_SELL, TAX = 5.0, 5.0, 0.26
POSITION = 10000.0


def bypass_l0_gates():
    """Svuota whitelist E blacklist L0 nella config di classe (condivisa da tutte
    le istanze) — cosi' suggest_level_0 valuta le condizioni per qualunque famiglia."""
    ETFTechnicalAnalyzer(famiglia='equity_sviluppati')  # forza il lazy-load di _FAMILIES_CONFIG
    cfg = ETFTechnicalAnalyzer._FAMILIES_CONFIG
    gp = cfg.get('global_params')
    if gp is None:
        gp = {}
        cfg['global_params'] = gp
    gp['l0_whitelist'] = []
    gp['l0_blacklist'] = []
    # sanity: la famiglia esiste nella config?
    assert FAMILY in cfg.get('families', {}), f"{FAMILY} non nella config YAML"
    print(f"Gate L0 bypassati: whitelist={gp['l0_whitelist']} blacklist={gp['l0_blacklist']}")


def load_em_universe(excel_path='/app/etf_monitoraggio.xlsx'):
    df = pd.read_excel(excel_path, sheet_name='ETF')
    rows = []
    for _, row in df.iterrows():
        ticker = str(row.get('Ticker', '')).strip()
        categoria = str(row.get('Categoria', ''))
        if not ticker or ticker.lower() == 'nan':
            continue
        if ETFTechnicalAnalyzer.detect_family(categoria) == FAMILY:
            rows.append({'ticker': ticker, 'categoria': categoria})
    return rows


def net_gain_eur(trade):
    gross = POSITION * (trade['exit_price'] / trade['entry_price'] - 1)
    fees = FEE_BUY + (FEE_SELL if trade['status'] == 'closed' else 0)
    after = gross - fees
    tax = TAX * after if after > 0 else 0.0
    return after - tax


def split_bucket(entry_date_iso):
    d = datetime.strptime(entry_date_iso, '%Y-%m-%d').date()
    if IN_START <= d < IN_END:
        return 'IN'
    if OUT_START <= d < OUT_END:
        return 'OUT'
    return None


def metrics(trades):
    closed = [t for t in trades if t['status'] == 'closed']
    if not closed:
        return {'N': 0, 'WR': None, 'PF': None, 'avg': None, 'pnl': 0.0}
    gains = [net_gain_eur(t) for t in closed]
    wins = sum(1 for g in gains if g > 0)
    pos = sum(g for g in gains if g > 0)
    neg = -sum(g for g in gains if g < 0)
    return {
        'N': len(closed),
        'WR': round(100 * wins / len(closed), 1),
        'PF': round(pos / neg, 2) if neg > 0 else float('inf'),
        'avg': round(sum(gains) / len(closed) / POSITION * 100, 2),
        'pnl': round(sum(gains), 0),
    }


def main():
    bypass_l0_gates()
    universe = load_em_universe()
    print(f"Ticker '{FAMILY}': {len(universe)}")
    for u in universe:
        print(f"  {u['ticker']:12s}  {u['categoria']}")
    print()

    db = PriceDatabase()

    # Carica lo storico una volta sola per ticker
    loaded = []
    for item in universe:
        tk = item['ticker']
        hist = db.get_frozen_ohlcv(tk, FROZEN_BATCH)
        if hist.empty or len(hist) < 220:
            print(f"  SKIP {tk}: storico {len(hist)}gg")
            continue
        has_ohlc = all(c in hist.columns for c in ['Open', 'High', 'Low'])
        loaded.append({
            'ticker': tk,
            'close': hist['Close'].astype(float),
            'high': hist['High'].astype(float) if has_ohlc else None,
            'low': hist['Low'].astype(float) if has_ohlc else None,
            'index': hist.index,
            'test_dates': [d for d in hist.index if d.date() >= IN_START],
        })
    print(f"Ticker con storico valido: {len(loaded)}\n")
    print("=" * 84)
    print(f"{'buffer':>7} | {'IN  N':>6} {'WR':>6} {'PF':>6} {'avg%':>6} {'PnL10k':>9} | "
          f"{'OUT N':>6} {'WR':>6} {'PF':>6} {'avg%':>6} {'PnL10k':>9}")
    print("-" * 84)

    for buf in BUFFERS:
        all_trades = []
        for L in loaded:
            an = ETFTechnicalAnalyzer(famiglia=FAMILY)
            an.p['l0_sl_tier1_buffer_pct'] = buf
            trades = simulate_l0(an, L['close'], L['high'], L['low'], L['index'], L['test_dates'])
            all_trades.extend(trades)

        in_tr = [t for t in all_trades if split_bucket(t['entry_date']) == 'IN']
        out_tr = [t for t in all_trades if split_bucket(t['entry_date']) == 'OUT']
        mi, mo = metrics(in_tr), metrics(out_tr)
        print(f"{buf*100:>6.0f}% | {mi['N']:>6} {str(mi['WR']):>6} {str(mi['PF']):>6} "
              f"{str(mi['avg']):>6} {str(mi['pnl']):>9} | "
              f"{mo['N']:>6} {str(mo['WR']):>6} {str(mo['PF']):>6} "
              f"{str(mo['avg']):>6} {str(mo['pnl']):>9}")

    print("=" * 84)
    print("Nota: PF migliore + WR migliore NON basta — guardare se OUT tiene rispetto a IN")
    print("(overfitting = bello dentro, crolla fuori). N<30 IN o OUT = non conclusivo.")


if __name__ == '__main__':
    main()
