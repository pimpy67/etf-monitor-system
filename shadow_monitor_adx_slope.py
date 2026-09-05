"""
shadow_monitor_adx_slope.py — Shadow Monitor per CANDIDATE_ADX_SLOPE_20260905.

Origine (2026-09-05): idea esterna ("ADX Slope" — richiedere che l'ADX sia in
salita, non solo sopra soglia come fa gia' la condizione 5 nativa). Diagnosticata
PRIMA su equity_sviluppati (unica famiglia con smart_6_macd live) segmentando i
trade GIA' generati dalla produzione per il segno della pendenza ADX (ADX oggi -
ADX 3gg fa) al momento dell'ingresso — stesso metodo gia' usato per "un filtro ADX
su min_buy_count=6 avrebbe aiutato il 2024?" (CLAUDE.md "Fase 2").

Risultato (Golden Dataset batch 2026-08-07, split IN 2023-08-05->2025-08-05/OOS
2025-08-05->fine dataset, equity_sviluppati, smart_6_macd nativo):
  ADX in salita     IN N=40 WR=45.0% PF=1.41 avg=+0.96% | OOS N=4 WR=100% PF=inf avg=+5.29%
  ADX in discesa/piatto IN N=17 WR=41.2% PF=0.83 avg=-0.47% | OOS N=4 WR=50.0% PF=1.49 avg=+1.18%
Effetto reale e coerente nella stessa direzione IN e OOS (il sottogruppo "in
discesa/piatto" e' sotto breakeven in-sample) — a differenza della proposta
gemella sul lato L0 (ADX>=30 in discesa su oro/metalli), che mostrava lo stesso
pattern IN ma si ribaltava OOS (firma di overfitting, RESPINTA, vedi CLAUDE.md).
N ancora molto sotto la soglia di 30 (specialmente OOS, N=4) -> Shadow Monitor
prima di qualunque promozione, stessa disciplina di ogni altro candidato.

Meccanismo: quando suggest_level() nativo gia' assegna L1 (equity_sviluppati,
smart_6_macd), il candidato aggiunge un requisito in piu' — ADX in salita
(pendenza a 3 giorni > 0) — prima di accettare l'ingresso ombra. Per ogni altro
caso (suggested_level != 1) e' identico alla produzione, cioe' non entra affatto
(stesso schema di shadow_monitor_tighten_rsi.py). Uscita via le stesse funzioni
reali di L1 (calculate_sl_suggerito_l1 / calculate_stop_gain_dynamic), nessun
override di famiglia — identico al motore usato nel backtest diagnostico.

Stesso pattern non invasivo degli altri Shadow Monitor: logga solo su
etf_shadow_positions, non tocca mai config/etf_families.yaml ne' alcuna
decisione reale.

Chiamato da monitor.py::run() come STEP 8N, avvolto in try/except non bloccante.
"""
from datetime import date

import pandas as pd

from technical_analysis import ETFTechnicalAnalyzer

MODEL_NAME = 'candidate_adx_slope_20260905'
TARGET_FAMILY = 'equity_sviluppati'
SLOPE_WINDOW = 3  # giorni, stesso usato nel backtest diagnostico


def run_shadow_monitor_adx_slope(db, results: list, add_log=print):
    """results: la stessa lista gia' calcolata da monitor.py::run() nel ciclo
    principale (analyze_etf() per ogni ETF) — riusata per evitare un secondo fetch."""
    candidates = [r for r in results if r.get('etf_type') == TARGET_FAMILY]
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
            analyzer = ETFTechnicalAnalyzer(famiglia=famiglia)

            if open_pos:
                entry_price = float(open_pos['entry_price'])
                hist = db.get_ohlc_by_isin(isin, days=40)
                if hist.empty or len(hist) < 25:
                    continue
                close = hist['Close'].astype(float)
                ema20_series = analyzer._ema(close, analyzer.ema20_period)
                ema20_today = float(ema20_series.iloc[-1])

                sl_data = analyzer.calculate_sl_suggerito_l1(entry_price, current_price, ema20_today)
                sl = sl_data.get('sl_suggerito')
                sl_hit = sl is not None and current_price <= sl

                tp_data = analyzer.calculate_stop_gain_dynamic(entry_price, current_price,
                                                                 ema20_series, analyzer.p)
                tp_hit = bool(tp_data.get('trigger'))

                if sl_hit or tp_hit:
                    gross_pct = round((current_price / entry_price - 1) * 100, 3)
                    db.close_shadow_position(open_pos['id'], today, current_price,
                                              'TP' if tp_hit else 'SL', gross_pct)
                    closed += 1
                    add_log(f"    🔵 SHADOW ADX-SLOPE EXIT {ticker} | {'TP' if tp_hit else 'SL'} | "
                            f"{gross_pct:+.2f}%")
            else:
                if a.get('suggested_level') != 1:
                    continue  # la produzione non entrerebbe nemmeno lei, niente da testare

                days_needed = SLOPE_WINDOW + 60  # margine per warmup ADX (~40gg tipico)
                hist = db.get_ohlc_by_isin(isin, days=max(days_needed, 120))
                if hist.empty or len(hist) < SLOPE_WINDOW + 40:
                    continue
                if hist['High'].isna().any() or hist['Low'].isna().any():
                    continue  # niente OHLC reale, non calcolabile

                close = hist['Close'].astype(float)
                high = hist['High'].astype(float)
                low = hist['Low'].astype(float)
                adx_series = analyzer._adx(high, low, close)
                if len(adx_series) <= SLOPE_WINDOW:
                    continue

                adx_today = adx_series.iloc[-1]
                adx_prev = adx_series.iloc[-1 - SLOPE_WINDOW]
                if pd.isna(adx_today) or pd.isna(adx_prev):
                    continue

                adx_slope = float(adx_today) - float(adx_prev)
                if adx_slope <= 0:
                    continue  # produzione entrerebbe, il candidato no (ADX non in salita)

                db.open_shadow_position(MODEL_NAME, ticker, isin, famiglia,
                                         today, current_price)
                opened += 1
                new_entries.append({
                    'ticker': ticker, 'isin': isin,
                    'nome': result.get('nome', ticker),
                    'famiglia': famiglia, 'price': current_price,
                })
                add_log(f"    🔵 SHADOW ADX-SLOPE ENTRY {ticker} @ {current_price:.4f} "
                        f"(ADX slope={adx_slope:+.2f})")
        except Exception as e:
            add_log(f"    ⚠️  Shadow ADX-slope monitor errore {ticker}: {type(e).__name__}: {e}")
            continue

    if opened or closed:
        add_log(f"  Shadow Monitor ADX-Slope ({MODEL_NAME}): {checked} controllati, "
                f"{opened} nuovi ingressi, {closed} uscite")

    return new_entries
