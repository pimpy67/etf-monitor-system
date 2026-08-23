"""
shadow_monitor_l0_metalli.py — Shadow Monitor per l'ipotesi "L0 su metalli_industriali"
(CANDIDATE_L0_METALLI_20260824).

Stesso principio e stessa origine di shadow_monitor_l0_oro.py (2026-08-24): il survey
delle 14 famiglie ha confermato che metalli_industriali non raggiunge mai L1 (0 giorni
in 3 anni sia nativo 7/7 che smart_6_macd — vedi
memory/etf_family_viability_survey_2026_08_24.md). Il backtest di L0 (mean-reversion)
sulla stessa famiglia, con la whitelist L0 bypassata SOLO nello script di test, ha
dato un segnale piu' solido di quello dell'oro: 13 trade in 3 anni (6 ticker: AIGI,
ALUM, BATE, COPA, ZINC — COPM escluso, storico troppo corto), win rate 53.8% (7 TP
~+13/15%, 6 SL ~-4/-7% tranne un outlier verificato reale -20.85% su COPA.MI
2025-07-31, non corruzione dati), P&L netto +5.088€ (10k€/trade). Ancora sotto la
soglia di fiducia N>=30 di questo progetto, ma il candidato piu' solido tra i due
testati finora (oro N=3).

Diversamente dagli altri Shadow Monitor, metalli_industriali NON e' nella whitelist
L0 reale (config/etf_families.yaml -> global_params.l0_whitelist resta
['equity_sviluppati'] soltanto — NON modificato da questo modulo). Stesso schema di
shadow_monitor_l0_oro.py: la whitelist viene aperta temporaneamente SOLO IN MEMORIA
(mutazione del dict di classe condiviso ETFTechnicalAnalyzer._FAMILIES_CONFIG), SOLO
per la durata della chiamata — un blocco try/finally la ripristina sempre, anche in
caso di eccezione. Nessuna scrittura su YAML, nessun impatto sulla produzione reale.

Nessun parametro cambiato rispetto al nativo (dd_threshold, rsi_max,
l0_take_profit_pct, SL trailing) — l'unica differenza rispetto alla produzione e' la
whitelist. Log sempre su etf_shadow_positions (stessa tabella degli altri candidati,
differenziata da model_name). Email sui nuovi ingressi tramite
alerts.py::send_shadow_entries(variant='L0_METALLI').

Chiamato da monitor.py::run() come STEP 8e, avvolto in try/except — un errore qui non
deve mai bloccare il ciclo di monitoraggio reale.
"""
from datetime import date

from technical_analysis import ETFTechnicalAnalyzer

MODEL_NAME = 'candidate_l0_metalli_20260824'
L0_METALLI_FAMILIES = {'metalli_industriali'}


def _whitelist_metalli_temporarily():
    """Aggiunge metalli_industriali alla whitelist L0 SOLO in memoria (mutazione del
    dict di classe condiviso). Restituisce una funzione di ripristino da chiamare
    sempre in finally — non scrive mai su config/etf_families.yaml."""
    if ETFTechnicalAnalyzer._FAMILIES_CONFIG is None:
        ETFTechnicalAnalyzer._FAMILIES_CONFIG = ETFTechnicalAnalyzer._load_families_config()
    gp = ETFTechnicalAnalyzer._FAMILIES_CONFIG.setdefault('global_params', {})
    original_whitelist = list(gp.get('l0_whitelist', ['equity_sviluppati']))
    temp_whitelist = list(original_whitelist)
    if 'metalli_industriali' not in temp_whitelist:
        temp_whitelist.append('metalli_industriali')
    gp['l0_whitelist'] = temp_whitelist

    def restore():
        gp['l0_whitelist'] = original_whitelist

    return restore


def run_shadow_monitor_l0_metalli(db, results: list, add_log=print):
    """results: la stessa lista gia' calcolata da monitor.py::run() nel ciclo
    principale (analyze_etf() per ogni ETF) — riusata per evitare un secondo fetch."""
    candidates = [r for r in results if r.get('etf_type') in L0_METALLI_FAMILIES]
    if not candidates:
        return []

    today = date.today()
    opened, closed, checked = 0, 0, 0
    new_entries = []

    restore_whitelist = _whitelist_metalli_temporarily()
    try:
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
                    sl_data = analyzer.calculate_sl_suggerito_l0(entry_price, current_price)
                    tp_data = analyzer.calculate_tp_suggerito_l0(entry_price, current_price)

                    sl = sl_data.get('sl_suggerito')
                    sl_hit = sl is not None and current_price <= sl
                    tp_hit = bool(tp_data.get('trigger'))

                    if sl_hit or tp_hit:
                        gross_pct = round((current_price / entry_price - 1) * 100, 3)
                        db.close_shadow_position(open_pos['id'], today, current_price,
                                                  'TP' if tp_hit else 'SL', gross_pct)
                        closed += 1
                        add_log(f"    🟤 SHADOW L0-METALLI EXIT {ticker} | {'TP' if tp_hit else 'SL'} | "
                                f"{gross_pct:+.2f}%")
                else:
                    hist = db.get_ohlc_by_isin(isin, days=250)
                    if hist.empty or len(hist) < 220:
                        continue
                    close = hist['Close'].astype(float)
                    high = hist['High'].astype(float) if 'High' in hist else close
                    low = hist['Low'].astype(float) if 'Low' in hist else close

                    result_l0 = analyzer.suggest_level_0(close, high, low, current_level=3)
                    if result_l0.get('l0_entry'):
                        db.open_shadow_position(MODEL_NAME, ticker, isin, famiglia,
                                                 today, current_price)
                        opened += 1
                        new_entries.append({
                            'ticker': ticker, 'isin': isin,
                            'nome': result.get('nome', ticker),
                            'famiglia': famiglia, 'price': current_price,
                            'regime_mode': result_l0.get('l0_regime_mode'),
                        })
                        add_log(f"    🟤 SHADOW L0-METALLI ENTRY {ticker} @ {current_price:.2f} "
                                f"({result_l0.get('l0_regime_mode', '?')})")
            except Exception as e:
                add_log(f"    ⚠️  Shadow L0-metalli monitor errore {ticker}: {type(e).__name__}: {e}")
                continue
    finally:
        restore_whitelist()

    if opened or closed:
        add_log(f"  Shadow Monitor L0-metalli ({MODEL_NAME}): {checked} controllati, "
                f"{opened} nuovi ingressi, {closed} uscite")

    return new_entries
