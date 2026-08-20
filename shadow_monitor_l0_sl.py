"""
shadow_monitor_l0_sl.py — Shadow Monitor per CANDIDATE_MODEL_L0_SL_20260820.

Stesso principio di shadow_monitor_l0.py (CANDIDATE_MODEL_L0_20260808), ma isola
una variabile diversa: non i parametri di regime (FAST/SLOW), bensì il primo
scaglione della formula SL (calculate_sl_suggerito_l0), oggi entry×0.98 (2% flat,
hardcoded, mai backtestato). Ingresso identico alla produzione reale (nessun
override su suggest_level_0()) — solo l'uscita cambia.

Origine (2026-08-20): l'utente ha notato un whipsaw reale su BRES/LBRE.DE
(LU1834983550) — uscito oggi da un vero stop del 2% a -2,35% netto, poi rimbalzato
quasi al pareggio nello stesso pomeriggio. Backtest one-shot su Golden Dataset
congelato (batch 2026-08-07), stesso split IN/OUT di CANDIDATE_MODEL_L0_20260808,
stessi ingressi di baseline (dd/rsi/recovery YAML default, l0_regime YAML default):
ogni buffer testato (2%→6%) migliora monotonicamente WR/PF/P&L netto sia IN che OUT,
nessun segno di overfitting. Scelto 4% come miglior compromesso rischio/rendimento
(ginocchio della curva): IN N=142 PF=4.68 WR=64.8% P&L=+91.715€ (10k€/trade,
baseline 2%: N=146 PF=3.18 WR=42.5% P&L=+53.602€); OUT N=37 PF=6.18 WR=70.3%
P&L=+27.819€ (baseline 2%: N=44 PF=4.51 WR=50.0% P&L=+22.032€). Script di sweep
scratch-only (docker cp, eseguito, cancellato — non è mai entrato nel repo).

Chiamato da monitor.py::run() come step aggiuntivo, avvolto in try/except — un
errore qui non deve mai bloccare il ciclo di monitoraggio reale (stesso principio
di ogni altro Shadow Monitor). Log su DB sempre (etf_shadow_positions, differenziato
da model_name). Nessuna email dedicata per ora — riusa send_shadow_entries() con
variant='L0_SL' se/quando si vuole collegarla, stesso pattern degli altri due.
"""
from datetime import date

from technical_analysis import ETFTechnicalAnalyzer

MODEL_NAME = 'candidate_model_l0_sl_20260820'

# Unica famiglia raggiungibile da L0 — whitelist gate in suggest_level_0() blocca
# tutte le altre 13 a monte, filtrare qui evita solo lavoro/log inutili.
L0_FAMILIES = {'equity_sviluppati'}

# Parametro del candidato — vedi doc sopra per la provenienza (sweep 2026-08-20).
# Baseline produzione: 0.02 (entry*0.98, primo scaglione di calculate_sl_suggerito_l0).
TIER1_BUFFER = 0.04


def calculate_sl_suggerito_l0_wide_tier1(entry_price: float, current_price: float) -> dict:
    """Stessa formula a scaglioni di calculate_sl_suggerito_l0 (technical_analysis.py) —
    solo il primo scaglione (profitto<5%) usa TIER1_BUFFER invece del 2% hardcoded di
    produzione. Scaglioni 2/3 (pareggio, protezione guadagno) invariati."""
    if entry_price is None or entry_price <= 0:
        return {'sl_suggerito': None, 'profit_pct': 0, 'stage': None}

    profit_pct = (current_price - entry_price) / entry_price

    if profit_pct < 0.05:
        sl = entry_price * (1 - TIER1_BUFFER)
        stage = 'protezione_capitale_wide'
    elif profit_pct < 0.15:
        sl = entry_price * 1.01
        stage = 'pareggio'
    else:
        sl = entry_price * (1 + profit_pct - 0.08)
        stage = 'protezione_guadagno'

    return {
        'sl_suggerito': round(sl, 4),
        'profit_pct': round(profit_pct * 100, 2),
        'stage': stage,
    }


def run_shadow_monitor_l0_sl(db, results: list, add_log=print):
    """results: la stessa lista già calcolata da monitor.py::run() nel ciclo principale
    (analyze_etf() per ogni ETF) — riusata per evitare un secondo giro di fetch."""
    candidates = [r for r in results if r.get('etf_type') in L0_FAMILIES]
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
                # Posizione ombra aperta — SL a scaglioni con primo gradino allargato,
                # TP invariato (calculate_tp_suggerito_l0 reale, legge l0_take_profit_pct
                # dallo YAML, non toccato da questo candidato).
                entry_price = float(open_pos['entry_price'])
                sl_data = calculate_sl_suggerito_l0_wide_tier1(entry_price, current_price)
                tp_data = analyzer.calculate_tp_suggerito_l0(entry_price, current_price)

                sl = sl_data.get('sl_suggerito')
                sl_hit = sl is not None and current_price <= sl
                tp_hit = bool(tp_data.get('trigger'))

                if sl_hit or tp_hit:
                    gross_pct = round((current_price / entry_price - 1) * 100, 3)
                    db.close_shadow_position(open_pos['id'], today, current_price,
                                              'TP' if tp_hit else 'SL', gross_pct)
                    closed += 1
                    add_log(f"    🟠 SHADOW L0-SL EXIT {ticker} | {'TP' if tp_hit else 'SL'} | "
                            f"{gross_pct:+.2f}%")
            else:
                # Nessuna posizione ombra aperta — ingresso IDENTICO alla produzione
                # reale (nessun override su suggest_level_0()): questo candidato isola
                # solo la variabile di uscita, non l'ingresso.
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
                    add_log(f"    🟠 SHADOW L0-SL ENTRY {ticker} @ {current_price:.2f} "
                            f"({result_l0.get('l0_regime_mode', '?')})")
        except Exception as e:
            add_log(f"    ⚠️  Shadow L0-SL monitor errore {ticker}: {type(e).__name__}: {e}")
            continue

    if opened or closed:
        add_log(f"  Shadow Monitor L0-SL ({MODEL_NAME}): {checked} controllati, "
                f"{opened} nuovi ingressi, {closed} uscite")

    return new_entries
