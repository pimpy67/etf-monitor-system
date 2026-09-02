"""
shadow_monitor_l0_regime_baseline.py — Shadow Monitor INVERSO (2026-09-02).

Dal 2026-09-02 la produzione L0 ha il gate regime RILASSATO (global_params
.l0_regime_allowed = [BULL, LATERALE, BEAR], vedi config/etf_families.yaml e
suggest_level_0()). Questo modulo traccia in parallelo, ogni giorno, cosa avrebbe
fatto il **vecchio gate BULL-only** — cioe' entra in una posizione ombra SOLO quando
suggest_level_0() (produzione, rilassato) segnala l'ingresso *E* il regime e' BULL.
Quello e' esattamente il comportamento pre-2026-09-02 (l'unica differenza tra vecchio
e nuovo e' il gate regime).

Serve al digest mensile per dire, dal vivo, se rilassare il gate ha aiutato o
peggiorato rispetto alla vecchia regola. Nessun impatto sulle decisioni reali —
log su etf_shadow_positions, model_name='baseline_l0_regime_bull'.

Chiamato da monitor.py::run() in try/except (un errore qui non blocca mai il ciclo
reale), stesso pattern di shadow_monitor_l0.py.
"""
from datetime import date

from technical_analysis import ETFTechnicalAnalyzer

MODEL_NAME = 'baseline_l0_regime_bull'

# Unica famiglia raggiungibile da L0 (whitelist gate in suggest_level_0()).
L0_FAMILIES = {'equity_sviluppati'}


def run_shadow_monitor_l0_regime_baseline(db, results: list, add_log=print):
    """results: la lista gia' calcolata da monitor.py::run() (analyze_etf per ETF)."""
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
            analyzer = ETFTechnicalAnalyzer(famiglia=famiglia)
            open_pos = db.get_open_shadow_position(MODEL_NAME, ticker)

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
                    add_log(f"    ⚪ SHADOW L0-BASELINE EXIT {ticker} | "
                            f"{'TP' if tp_hit else 'SL'} | {gross_pct:+.2f}%")
            else:
                hist = db.get_ohlc_by_isin(isin, days=250)
                if hist.empty or len(hist) < 220:
                    continue
                close = hist['Close'].astype(float)
                high = hist['High'].astype(float) if 'High' in hist else close
                low = hist['Low'].astype(float) if 'Low' in hist else close

                r0 = analyzer.suggest_level_0(close, high, low, current_level=3)
                # Vecchio gate BULL-only: ingresso valido SOLO se il nuovo motore
                # entrerebbe E il regime e' BULL (l'unica condizione che il gate
                # rilassato ha rimosso).
                if r0.get('l0_entry') and r0.get('regime_str') == 'BULL':
                    db.open_shadow_position(MODEL_NAME, ticker, isin, famiglia,
                                            today, current_price)
                    opened += 1
                    new_entries.append({
                        'ticker': ticker, 'isin': isin,
                        'nome': result.get('nome', ticker),
                        'famiglia': famiglia, 'price': current_price,
                        'regime_mode': r0.get('l0_regime_mode'),
                    })
                    add_log(f"    ⚪ SHADOW L0-BASELINE ENTRY {ticker} @ {current_price:.2f} "
                            f"({r0.get('l0_regime_mode', '?')})")
        except Exception as e:
            add_log(f"    ⚠️  Shadow L0-baseline errore {ticker}: {type(e).__name__}: {e}")
            continue

    if opened or closed:
        add_log(f"  Shadow Monitor L0-baseline ({MODEL_NAME}): {checked} controllati, "
                f"{opened} nuovi ingressi, {closed} uscite")

    return new_entries
