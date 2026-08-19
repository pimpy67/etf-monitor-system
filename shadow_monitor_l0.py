"""
shadow_monitor_l0.py — Shadow Monitor per CANDIDATE_MODEL_L0_20260808.

Stesso principio di shadow_monitor.py (CANDIDATE_MODEL_B_20260807, L1): durante il
lockdown parametri (fino al 06/09/2026) il sistema live decide L0 solo con i
parametri YAML nativi (regime_min_days_below_sma200=10 per equity_sviluppati).
Questo modulo calcola in parallelo, ogni giorno, cosa avrebbe fatto
CANDIDATE_MODEL_L0_20260808 (regime_min_days_below_sma200=5, tutto il resto
invariato — SL, TP=16%, PRAGMATIC, FAST) sull'unica famiglia raggiungibile da L0
(equity_sviluppati, per via del whitelist gate in suggest_level_0()) — senza
toccare NESSUNA decisione reale, solo log su etf_shadow_positions (stessa tabella
del candidato L1, differenziata da model_name) per il confronto a fine lockdown.
Vedi CLAUDE.md, sezione "CANDIDATE_MODEL_L0_20260808".

Chiamato da monitor.py::run() come step aggiuntivo, avvolto in try/except — un errore
qui non deve mai bloccare il ciclo di monitoraggio reale (stesso principio delle altre
sezioni "informative" già presenti, es. lo Shadow Monitor L1).

Log su DB sempre (etf_shadow_positions). Email sui nuovi ingressi (alerts.py::
send_shadow_entries, variant='L0') collegata il 2026-08-19 su richiesta esplicita —
prima "nessuna email" era la scelta deliberata (stessa del candidato L1, 2026-08-07),
superata. Il confronto completo va comunque estratto manualmente a fine lockdown con
get_shadow_positions().
"""
from datetime import date

from technical_analysis import ETFTechnicalAnalyzer

MODEL_NAME = 'candidate_model_l0_20260808'

# Unica famiglia raggiungibile da L0 — il whitelist gate in suggest_level_0() blocca
# tutte le altre 13 a monte, quindi filtrare qui evita solo lavoro/log inutili.
L0_FAMILIES = {'equity_sviluppati'}

# Parametro del candidato — vedi CLAUDE.md CANDIDATE_MODEL_L0_20260808 per la
# provenienza (optimize_l0_regime.py --sweep-slow, 2026-08-08: IN N=152 PF=3.38
# WR=44.1%, OUT N=62 PF=4.84 WR=51.6%, batte il baseline YAML=10 su ogni metrica).
# Tutto il resto (l0_take_profit_pct, l0_entry PRAGMATIC, SL trailing) resta al
# valore YAML nativo — non sweepato, non è parte del candidato.
REGIME_MIN_DAYS_BELOW_SMA200 = 5


def make_candidate_l0_analyzer(famiglia: str) -> ETFTechnicalAnalyzer:
    """Copia locale di self.p con l'override del candidato — stesso pattern sicuro
    (mai muta la baseline condivisa) già usato in optimize_l0_regime.py."""
    analyzer = ETFTechnicalAnalyzer(famiglia=famiglia)
    p = dict(analyzer.p)
    p['l0_regime'] = dict(p.get('l0_regime', {}))
    p['l0_regime']['regime_min_days_below_sma200'] = REGIME_MIN_DAYS_BELOW_SMA200
    analyzer.p = p
    return analyzer


def run_shadow_monitor_l0(db, results: list, add_log=print):
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
            analyzer = make_candidate_l0_analyzer(famiglia)

            if open_pos:
                # Posizione ombra aperta — stesse funzioni reali di L0 (SL e TP non
                # sono toccati dal candidato: SL è hardcoded, TP legge
                # l0_take_profit_pct invariato dallo YAML).
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
                    add_log(f"    🟣 SHADOW L0 EXIT {ticker} | {'TP' if tp_hit else 'SL'} | "
                            f"{gross_pct:+.2f}%")
            else:
                # Nessuna posizione ombra aperta — valuta ingresso con
                # regime_min_days_below_sma200=5 invece del baseline di famiglia
                # (10 per equity_sviluppati). Serve lo storico OHLC completo (non solo
                # il prezzo di oggi) per SMA200/percorso SLOW, coerente con la soglia
                # 220gg usata in backtest_l0_v2.py.
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
                    add_log(f"    🟣 SHADOW L0 ENTRY {ticker} @ {current_price:.2f} "
                            f"({result_l0.get('l0_regime_mode', '?')})")
        except Exception as e:
            add_log(f"    ⚠️  Shadow L0 monitor errore {ticker}: {type(e).__name__}: {e}")
            continue

    if opened or closed:
        add_log(f"  Shadow Monitor L0 ({MODEL_NAME}): {checked} controllati, "
                f"{opened} nuovi ingressi, {closed} uscite")

    return new_entries
