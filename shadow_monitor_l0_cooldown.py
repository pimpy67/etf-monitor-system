"""
shadow_monitor_l0_cooldown.py — Shadow Monitor per CANDIDATE_L0_COOLDOWN_20260827.

Origine (2026-08-27): approfondimento di una pista di consulenza esterna
("re-entry a conferma"). Trovato che suggest_level_0() e' level-triggered: il
segnale d'ingresso resta 'True' per molti giorni di fila (non e' un evento
puntuale), quindi uno stop SL preso mentre il segnale e' ancora vero produce
un rientro immediato il giorno lavorativo successivo, senza nessuna memoria
dello stop appena preso. Caso reale verificato: LBRE.DE (LU1834983550),
entry=True continuo dal 13/08 al 20/08/2026, SL toccato il 14/08, rientro il
15/08 — in quel caso specifico il rientro ha aiutato (base di costo piu'
bassa proprio prima del recupero a +7.19%), ma il meccanismo di fondo non ha
nessuna protezione contro il whipsaw opposto (rientro immediato in una
gamba ancora debole).

Backtestate due varianti (backtest_l0_cooldown.py, scratch, mai entrato nel
repo — cancellato dopo l'uso) sull'universo reale equity_sviluppati (105
ticker, Golden Dataset batch 2026-08-07, split IN 2023-08-05->2025-08-05 /
OOS 2025-08-05->2026-08-05, SL/TP reali invariati):
- 'reclaim' (blocca il re-ingresso finche' il prezzo non richiude sopra
  l'entry del trade stoppato): SCARTATA — IN migliora (PF 4.23->5.18) ma OOS
  crolla (PF 2.02->1.42, WR 45.5%->36.4%), firma classica di overfitting gia'
  vista altre volte in questo progetto.
- 'cooldown N giorni di trading' (blocca il re-ingresso sullo stesso ticker
  per N giorni dopo uno stop SL, nessun altro parametro toccato): 10gg batte
  il baseline su OGNI metrica OOS senza il pattern di overfitting — IN N=97
  PF=4.38 WR=62.9%, OOS N=12 PF=2.41 WR=50.0% P&L=+4.404EUR/10k, contro il
  baseline OOS N=11 PF=2.02 WR=45.5% P&L=+3.179EUR/10k. Primo candidato di
  re-entry-gate che supera il baseline coerentemente IN+OOS in questo
  progetto (cooldown 3gg quasi identico: OOS N=12 PF=2.39 WR=50.0%).

N ancora troppo piccolo (12 OOS) per qualunque promozione (soglia N>=30 di
questo progetto, vedi CLAUDE.md "checkpoint ricorrente") — questo modulo
traccia in avanti, su dati reali, per accumulare campione prima di
decidere. Nessun parametro d'ingresso/uscita cambiato rispetto al nativo:
l'UNICA differenza e' che, dopo uno stop SL su un ticker, il candidato salta
la valutazione d'ingresso per COOLDOWN_TRADING_DAYS giorni di trading
(contati sullo storico OHLC reale del ticker via get_last_shadow_sl_exit +
_trading_days_since — stessa unita' di misura del backtest, non giorni di
calendario).

Chiamato da monitor.py::run() come STEP 8j, avvolto in try/except — un
errore qui non deve mai bloccare il ciclo di monitoraggio reale. Log sempre
su etf_shadow_positions (stessa tabella degli altri candidati, differenziata
da model_name). Email sui nuovi ingressi tramite
alerts.py::send_shadow_entries(variant='L0_COOLDOWN'), stesso meccanismo
gia' attivo per gli altri candidati dal 2026-08-19.
"""
from datetime import date

from technical_analysis import ETFTechnicalAnalyzer

MODEL_NAME = 'candidate_l0_cooldown_20260827'

# Unica famiglia raggiungibile da L0 — il whitelist gate in suggest_level_0()
# blocca tutte le altre 13 a monte, filtrare qui evita solo lavoro/log inutili.
L0_FAMILIES = {'equity_sviluppati'}

# Parametro del candidato — vedi CLAUDE.md CANDIDATE_L0_COOLDOWN_20260827.
COOLDOWN_TRADING_DAYS = 10


def _trading_days_since(hist_index, since_date) -> int:
    """Conta i giorni di trading nello storico del ticker strettamente dopo
    since_date — stessa unita' di misura del backtest (avanzamento per
    posizione in hist.index), non giorni di calendario."""
    return sum(1 for d in hist_index if d.date() > since_date)


def run_shadow_monitor_l0_cooldown(db, results: list, add_log=print):
    """results: la stessa lista gia' calcolata da monitor.py::run() nel ciclo
    principale (analyze_etf() per ogni ETF) — riusata per evitare un secondo
    giro di fetch."""
    candidates = [r for r in results if r.get('etf_type') in L0_FAMILIES]
    if not candidates:
        return []

    today = date.today()
    opened, closed, checked, on_cooldown = 0, 0, 0, 0
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
                # Posizione ombra aperta — SL/TP nativi di famiglia, invariati
                # (il candidato tocca solo il gate d'ingresso, mai l'uscita).
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
                    add_log(f"    🔵 SHADOW L0-COOLDOWN EXIT {ticker} | "
                            f"{'TP' if tp_hit else 'SL'} | {gross_pct:+.2f}%")
            else:
                # Nessuna posizione ombra aperta — serve lo storico OHLC completo
                # (non solo il prezzo di oggi) sia per SMA200/percorso SLOW sia
                # per contare i giorni di trading dall'ultimo stop SL.
                hist = db.get_ohlc_by_isin(isin, days=250)
                if hist.empty or len(hist) < 220:
                    continue

                last_sl_exit = db.get_last_shadow_sl_exit(MODEL_NAME, ticker)
                if last_sl_exit is not None:
                    days_since = _trading_days_since(hist.index, last_sl_exit)
                    if days_since < COOLDOWN_TRADING_DAYS:
                        on_cooldown += 1
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
                    add_log(f"    🔵 SHADOW L0-COOLDOWN ENTRY {ticker} @ {current_price:.2f} "
                            f"({result_l0.get('l0_regime_mode', '?')})")
        except Exception as e:
            add_log(f"    ⚠️  Shadow L0-cooldown monitor errore {ticker}: {type(e).__name__}: {e}")
            continue

    if opened or closed:
        add_log(f"  Shadow Monitor L0-cooldown ({MODEL_NAME}): {checked} controllati, "
                f"{opened} nuovi ingressi, {closed} uscite, {on_cooldown} in cooldown")

    return new_entries
