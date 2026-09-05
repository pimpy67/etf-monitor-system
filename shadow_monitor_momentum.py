"""
shadow_monitor_momentum.py — Shadow Monitor per CANDIDATE_MOMENTUM_20260905 (item 18b).

Origine: il test esplorativo del 2026-09-03 (backtest_momentum_explore.py, cancellato)
aveva mostrato che un'entrata Donchian breakout + ADX cattura le mosse a parabola che
le 7 condizioni L1 rifiutano strutturalmente (silver PHAG.MI +57.7% gen-2026), ma come
sistema pooled su 7 famiglie era marginale (OOS PF ~1.1-1.2, decadimento IN->OOS).

Decisione utente (2026-09-03, memory/etf_post_lockdown_todo_20260906.md sezione 18b):
opzione (b) — ripetere SOLO su settoriali_growth + oro_metalli_preziosi, con uno stop
PERCENTUALE FISSO in trailing (non lo chandelier ATR, che su prodotti volatili puo'
"gappare" quando l'ATR stesso si gonfia — worst trade leva -83/-87% nel test esplorativo).

Backtest per-famiglia (backtest_momentum_narrow.py, scratch, cancellato dopo l'uso,
Golden Dataset batch 2026-08-07, split IN 2023-08-05->2025-08-05/OOS 2025-08-05->fine
dataset, size 5.000EUR/trade): su 16 combinazioni (Donchian N in {20,55} x ADX_min in
{20,25} x stop% in {6,8,10,12}), 9 superano la barra OOS PF>=1.3 su ENTRAMBE le famiglie,
ma solo le combinazioni con ADX_min=20 mostrano un pattern pulito (IN e OOS entrambi
solidamente positivi su entrambe le famiglie, nessun collasso/segnale sospetto) — le
combinazioni ADX_min=25 nascondevano un in-sample debole o negativo su settoriali_growth
mascherato da un OOS eccellente (stessa firma di overfitting gia' vista altrove nel
progetto). Scelta la combinazione N20_ADX20_STOP8 (la piu' bilanciata, nessun artefatto
da campione piccolo tipo PF=inf):

  oro_metalli_preziosi:  IN N=23 PF=2.73 WR=43.5% avg=+6.79%  | OOS N=7  PF=4.81 WR=71.4% avg=+9.42%
  settoriali_growth:     IN N=46 PF=1.70 WR=50.0% avg=+2.34%  | OOS N=12 PF=1.65 WR=50.0% avg=+2.37%

Entrata: Close > max(High) delle 20 sessioni precedenti (esclusa oggi) + ADX>=20.
Nessun cap RSI/distanza EMA20/SMA200 (a differenza di L1 — l'obiettivo e' proprio
catturare cio' che L1 esclude strutturalmente).

Uscita: SOLO trailing stop percentuale — stop = max(Close) da ingresso * (1-8%).
Nessun TP fisso, si lascia correre il winner (il trailing protegge il guadagno via
via che il massimo sale). Controllo una volta al giorno sul Close.

Stessa filosofia "no automazione" e stesso pattern non invasivo degli altri Shadow
Monitor: logga solo su etf_shadow_positions, NESSUN cambio a config/etf_families.yaml
o a suggest_level() — meccanismo completamente separato, mai promosso senza N>=30
chiuse e una decisione esplicita dell'utente allo stesso checkpoint ricorrente degli
altri candidati (vedi memory/etf_post_lockdown_todo_20260906.md).

Chiamato da monitor.py::run() come STEP 8L, avvolto in try/except non bloccante.
"""
from datetime import date

import pandas as pd

from technical_analysis import ETFTechnicalAnalyzer

MODEL_NAME = 'candidate_momentum_20260905'

TARGET_FAMILIES = {'settoriali_growth', 'oro_metalli_preziosi'}
DONCHIAN_N = 20
ADX_MIN = 20
HARD_STOP_PCT = 0.08


def run_shadow_monitor_momentum(db, results: list, add_log=print):
    """results: la stessa lista gia' calcolata da monitor.py::run() nel ciclo
    principale (analyze_etf() per ogni ETF) — riusata per evitare un secondo fetch."""
    candidates = [r for r in results if r.get('etf_type') in TARGET_FAMILIES]
    if not candidates:
        return []

    today = date.today()
    opened, closed, checked = 0, 0, 0
    new_entries = []

    for result in candidates:
        ticker = result.get('ticker')
        isin = result.get('isin') or ticker
        famiglia = result.get('etf_type')
        a = result.get('analysis') or {}
        current_price = a.get('current_price')
        if not ticker or not current_price:
            continue
        current_price = float(current_price)
        checked += 1

        try:
            open_pos = db.get_open_shadow_position(MODEL_NAME, ticker)

            days_needed = DONCHIAN_N + 60  # margine per ADX (warmup) + Donchian window
            hist = db.get_ohlc_by_isin(isin, days=max(days_needed, 120))
            if hist.empty or len(hist) < DONCHIAN_N + 30:
                continue
            if hist['High'].isna().any() or hist['Low'].isna().any():
                continue  # niente OHLC reale per questo ETF, non calcolabile

            close = hist['Close'].astype(float)
            high = hist['High'].astype(float)

            if open_pos:
                entry_date = open_pos['entry_date']
                entry_price = float(open_pos['entry_price'])
                # Picco di Close dalla data di ingresso (inclusa) a oggi — ricalcolato
                # ogni volta dallo storico, nessuno stato aggiuntivo da persistere.
                since_entry = close[close.index.date >= entry_date]
                peak_close = float(since_entry.max()) if not since_entry.empty else current_price
                stop_price = peak_close * (1 - HARD_STOP_PCT)

                if current_price <= stop_price:
                    gross_pct = round((current_price / entry_price - 1) * 100, 3)
                    db.close_shadow_position(open_pos['id'], today, current_price,
                                              'TRAIL_STOP', gross_pct)
                    closed += 1
                    add_log(f"    🟠 SHADOW MOMENTUM EXIT {ticker} | TRAIL_STOP | {gross_pct:+.2f}%")
            else:
                analyzer = ETFTechnicalAnalyzer(famiglia=famiglia)
                low = hist['Low'].astype(float)
                adx_series = analyzer._adx(high, low, close)
                donchian_high = high.rolling(DONCHIAN_N).max().shift(1)

                adx_today = adx_series.iloc[-1]
                dh_today = donchian_high.iloc[-1]
                if pd.isna(adx_today) or pd.isna(dh_today):
                    continue

                if current_price > float(dh_today) and float(adx_today) >= ADX_MIN:
                    db.open_shadow_position(MODEL_NAME, ticker, isin, famiglia,
                                             today, current_price)
                    opened += 1
                    new_entries.append({
                        'ticker': ticker, 'isin': isin,
                        'nome': result.get('nome', ticker),
                        'famiglia': famiglia, 'price': current_price,
                    })
                    add_log(f"    🟠 SHADOW MOMENTUM ENTRY {ticker} @ {current_price:.4f} "
                            f"(breakout {DONCHIAN_N}gg, ADX={float(adx_today):.1f})")
        except Exception as e:
            add_log(f"    ⚠️  Shadow momentum monitor errore {ticker}: {type(e).__name__}: {e}")
            continue

    if opened or closed:
        add_log(f"  Shadow Monitor Momentum ({MODEL_NAME}): {checked} controllati, "
                f"{opened} nuovi ingressi, {closed} uscite")

    return new_entries
