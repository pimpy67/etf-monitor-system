"""
shadow_monitor_l0_oro.py — Shadow Monitor per l'ipotesi "L0 su oro_metalli_preziosi"
(CANDIDATE_L0_ORO_20260824).

Origine (2026-08-24): survey completo delle 14 famiglie ha confermato che
oro_metalli_preziosi non raggiunge mai L1 (0 giorni in 3 anni, ne' nativo 7/7 ne'
smart_6_macd — vedi memory/etf_family_viability_survey_2026_08_24.md). Il backtest di
L0 (mean-reversion) sulla stessa famiglia, con la whitelist L0 bypassata SOLO nello
script di test, ha dato un segnale opposto e incoraggiante: 3 trade in 3 anni, win
rate 66.7% (2 TP +13.37%/+12.12%, 1 SL -4.52%), P&L netto +2.096,77€ (10k€/trade) —
ma N=3 e' troppo piccolo per essere conclusivo (stesso identico problema gia' visto
con "3 trade, 100% win rate" su equity_sviluppati native_7). Questo modulo traccia
in avanti, su dati reali, per accumulare campione prima di decidere se aprire
davvero la whitelist L0 a questa famiglia.

Diversamente dagli altri Shadow Monitor, oro_metalli_preziosi NON e' nella whitelist
L0 reale (config/etf_families.yaml -> global_params.l0_whitelist resta
['equity_sviluppati'] soltanto — NON modificato da questo modulo). Per valutare
l'ipotesi senza toccare la produzione, questa funzione aggiunge temporaneamente
'oro_metalli_preziosi' alla whitelist SOLO IN MEMORIA (mutazione del dict di classe
condiviso ETFTechnicalAnalyzer._FAMILIES_CONFIG), SOLO per la durata della chiamata —
un blocco try/finally la ripristina sempre, anche in caso di eccezione. La valutazione
reale di produzione per equity_sviluppati (unica famiglia davvero whitelisted) chiama
suggest_level_0() molto prima nel ciclo principale di analyze_etf() per ogni ETF,
in un processo sincrono a thread singolo — nessun rischio di sovrapposizione con
questa mutazione temporanea, che avviene qui, dopo, in STEP 8d.

Nessun parametro cambiato rispetto al nativo (dd_threshold, rsi_max,
l0_take_profit_pct, SL trailing) — l'unica differenza rispetto alla produzione e'
la whitelist. Log sempre su etf_shadow_positions (stessa tabella degli altri
candidati, differenziata da model_name). Email sui nuovi ingressi tramite
alerts.py::send_shadow_entries(variant='L0_ORO'), stesso meccanismo gia' attivo
per gli altri 3 candidati dal 2026-08-19.

Chiamato da monitor.py::run() come STEP 8d (slot libero dal 2026-08-20, quando
CANDIDATE_MODEL_L0_SL_20260820 e' stato promosso in produzione e il suo Shadow
Monitor rimosso), avvolto in try/except — un errore qui non deve mai bloccare il
ciclo di monitoraggio reale.
"""
from datetime import date

from technical_analysis import ETFTechnicalAnalyzer

MODEL_NAME = 'candidate_l0_oro_20260824'
L0_ORO_FAMILIES = {'oro_metalli_preziosi'}


def _whitelist_gold_temporarily():
    """Aggiunge oro_metalli_preziosi alla whitelist L0 SOLO in memoria (mutazione del
    dict di classe condiviso). Restituisce una funzione di ripristino da chiamare
    sempre in finally — non scrive mai su config/etf_families.yaml.

    FIX 2026-08-24 (bug reale, mai emerso finche' non e' stato notato che questo Shadow
    Monitor non aveva MAI aperto una posizione): suggest_level_0() controlla whitelist E
    blacklist in modo indipendente (technical_analysis.py:927-933) — bypassare solo la
    whitelist non basta se la famiglia e' ANCHE nella blacklist, che la blocca comunque
    (L0_DISABLED_BLACKLISTED). oro_metalli_preziosi e' in ENTRAMBE le liste nello YAML
    attuale. Ora bypassa anche la blacklist per la durata della chiamata."""
    if ETFTechnicalAnalyzer._FAMILIES_CONFIG is None:
        ETFTechnicalAnalyzer._FAMILIES_CONFIG = ETFTechnicalAnalyzer._load_families_config()
    gp = ETFTechnicalAnalyzer._FAMILIES_CONFIG.setdefault('global_params', {})
    original_whitelist = list(gp.get('l0_whitelist', ['equity_sviluppati']))
    original_blacklist = list(gp.get('l0_blacklist', []))
    temp_whitelist = list(original_whitelist)
    if 'oro_metalli_preziosi' not in temp_whitelist:
        temp_whitelist.append('oro_metalli_preziosi')
    gp['l0_whitelist'] = temp_whitelist
    gp['l0_blacklist'] = [f for f in original_blacklist if f != 'oro_metalli_preziosi']

    def restore():
        gp['l0_whitelist'] = original_whitelist
        gp['l0_blacklist'] = original_blacklist

    return restore


def run_shadow_monitor_l0_oro(db, results: list, add_log=print):
    """results: la stessa lista gia' calcolata da monitor.py::run() nel ciclo
    principale (analyze_etf() per ogni ETF) — riusata per evitare un secondo fetch."""
    candidates = [r for r in results if r.get('etf_type') in L0_ORO_FAMILIES]
    if not candidates:
        return []

    today = date.today()
    opened, closed, checked = 0, 0, 0
    new_entries = []

    restore_whitelist = _whitelist_gold_temporarily()
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
                    # Posizione ombra aperta — SL/TP nativi di famiglia, invariati.
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
                        add_log(f"    🟡 SHADOW L0-ORO EXIT {ticker} | {'TP' if tp_hit else 'SL'} | "
                                f"{gross_pct:+.2f}%")
                else:
                    # Nessuna posizione ombra aperta — valuta ingresso con whitelist
                    # temporaneamente aperta. Serve lo storico OHLC completo (non solo
                    # il prezzo di oggi) per SMA200/percorso SLOW.
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
                        add_log(f"    🟡 SHADOW L0-ORO ENTRY {ticker} @ {current_price:.2f} "
                                f"({result_l0.get('l0_regime_mode', '?')})")
            except Exception as e:
                add_log(f"    ⚠️  Shadow L0-oro monitor errore {ticker}: {type(e).__name__}: {e}")
                continue
    finally:
        restore_whitelist()

    if opened or closed:
        add_log(f"  Shadow Monitor L0-oro ({MODEL_NAME}): {checked} controllati, "
                f"{opened} nuovi ingressi, {closed} uscite")

    return new_entries
