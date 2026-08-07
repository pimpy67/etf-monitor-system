"""
shadow_monitor.py — Shadow Monitor per CANDIDATE_MODEL_B_20260807.

Durante il lockdown parametri (fino al 06/09/2026) il sistema live decide solo con
native_7 (min_buy_count=7, YAML invariato). Questo modulo calcola in parallelo, ogni
giorno, cosa avrebbe fatto CANDIDATE_MODEL_B_20260807 sulle 5 famiglie del cluster
'core' — senza toccare NESSUNA decisione reale, solo log su etf_shadow_positions
(migration 003) per il confronto a fine lockdown. Vedi CLAUDE.md, sezione
"CANDIDATE_MODEL_B_20260807".

Chiamato da monitor.py::run() come step aggiuntivo, avvolto in try/except — un errore
qui non deve mai bloccare il ciclo di monitoraggio reale (stesso principio delle altre
sezioni "informative" già presenti, es. l1_seven_conditions/l1_tiered_entry).

NON invia email — solo log su DB, come deciso esplicitamente (2026-08-07). Il confronto
va estratto manualmente a fine lockdown con get_shadow_positions().
"""
from datetime import date

from technical_analysis import ETFTechnicalAnalyzer

MODEL_NAME = 'candidate_model_b_20260807'

CORE_FAMILIES = {
    'equity_sviluppati', 'oro_metalli_preziosi', 'mercati_emergenti',
    'settoriali_growth', 'metalli_industriali',
}

# Parametri fissi del candidato — vedi CLAUDE.md CANDIDATE_MODEL_B_20260807 per la
# provenienza (sweep ampio + Fase 2 + micro-sweep TP, 2026-08-07).
MM200_ABSOLUTE = 7.0
ADX_DELTA = -4
TARGET_MAX_PCT = 0.15


def make_candidate_b_analyzer(famiglia: str) -> ETFTechnicalAnalyzer:
    """Copia locale di self.p con gli override del candidato — stesso pattern sicuro
    (mai muta la baseline condivisa) già usato in optimize_hyperparameters.py."""
    analyzer = ETFTechnicalAnalyzer(famiglia=famiglia)
    p = dict(analyzer.p)
    p['min_buy_count'] = 6
    p['mm200_distance_max'] = MM200_ABSOLUTE
    p['adx_entry'] = max(1, p.get('adx_entry', 20) + ADX_DELTA)
    if 'l1_stop_gain_dynamic' in p:
        sg = dict(p['l1_stop_gain_dynamic'])
        sg['target_max_pct'] = TARGET_MAX_PCT
        p['l1_stop_gain_dynamic'] = sg
    analyzer.p = p
    return analyzer


def run_shadow_monitor(db, results: list, add_log=print):
    """results: la stessa lista già calcolata da monitor.py::run() nel ciclo principale
    (analyze_etf() per ogni ETF) — riusata per evitare un secondo giro di fetch."""
    candidates = [r for r in results if r.get('etf_type') in CORE_FAMILIES]
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
            analyzer = make_candidate_b_analyzer(famiglia)

            if open_pos:
                # Posizione ombra aperta — controlla SL/TP con la stessa logica reale
                # (calculate_sl_suggerito_l1 / calculate_stop_gain_dynamic), parametri
                # del candidato invece della baseline di famiglia.
                entry_price = float(open_pos['entry_price'])
                ema20 = a.get('ema20')

                hist_recent = db.get_ohlc_by_isin(isin, days=40)
                ema20_series = None
                if not hist_recent.empty and len(hist_recent) >= 20:
                    close_recent = hist_recent['Close'].astype(float).dropna()
                    if len(close_recent) >= 20:
                        ema20_series = analyzer._ema(close_recent, 20).tail(10)

                sl_data = analyzer.calculate_sl_suggerito_l1(entry_price, current_price, ema20)
                sl = sl_data.get('sl_suggerito')
                sg_data = analyzer.calculate_stop_gain_dynamic(entry_price, current_price,
                                                                 ema20_series, analyzer.p)

                sl_hit = sl is not None and current_price <= sl
                tp_hit = bool(sg_data.get('trigger'))

                if sl_hit or tp_hit:
                    gross_pct = round((current_price / entry_price - 1) * 100, 3)
                    db.close_shadow_position(open_pos['id'], today, current_price,
                                              'SL' if sl_hit else 'TP', gross_pct)
                    closed += 1
                    add_log(f"    🟣 SHADOW EXIT {ticker} | {'SL' if sl_hit else 'TP'} | "
                            f"{gross_pct:+.2f}%")
            else:
                # Nessuna posizione ombra aperta — valuta ingresso con i parametri del
                # candidato. Serve lo storico completo (non solo il prezzo di oggi) per
                # calcolare EMA/SMA/RSI/ADX/MACD.
                hist = db.get_ohlc_by_isin(isin, days=250)
                if hist.empty or len(hist) < 220:
                    continue
                close = hist['Close'].astype(float)
                high = hist['High'].astype(float) if 'High' in hist else None
                low = hist['Low'].astype(float) if 'Low' in hist else None

                result_b = analyzer.suggest_level(close, current_level=3, high=high, low=low)
                if result_b.get('suggested_level') == 1:
                    conditions = result_b.get('conditions', {})
                    if conditions.get('macd_ok', False):  # macd_ok sempre obbligatorio, smart_6_macd
                        db.open_shadow_position(MODEL_NAME, ticker, isin, famiglia,
                                                 today, current_price)
                        opened += 1
                        new_entries.append({
                            'ticker': ticker, 'isin': isin,
                            'nome': result.get('nome', ticker),
                            'famiglia': famiglia, 'price': current_price,
                        })
                        add_log(f"    🟣 SHADOW ENTRY {ticker} @ {current_price:.2f} "
                                f"({famiglia})")
        except Exception as e:
            add_log(f"    ⚠️  Shadow monitor errore {ticker}: {type(e).__name__}: {e}")
            continue

    if opened or closed:
        add_log(f"  Shadow Monitor ({MODEL_NAME}): {checked} controllati, "
                f"{opened} nuovi ingressi, {closed} uscite")

    return new_entries
