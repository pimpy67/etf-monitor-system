"""
shadow_monitor_breadth.py — Shadow Monitor per la "terza via" Market Breadth/Super-Bull
(2026-08-20, vedi memory/etf_post_lockdown_todo_20260906.md sezione 3 per il backtest e
lo sweep di soglie che l'hanno preceduto).

CANDIDATO: quando la % di ETF nell'intero universo tradabile (13 famiglie) con
EMA20>SMA50 ("breadth") supera l'80% (isteresi: esce solo sotto il 65%), si allenta il
gate L1 SOLO per il cluster 'core' da 7/7 a 6/7+MACD-obbligatorio (stesso smart_6_macd
gia' usato da CANDIDATE_MODEL_B_20260807, ma SENZA gli altri override mm200/adx di quel
candidato — solo il gate, per isolare l'effetto della breadth in se'). Soglie
(enter=80%/exit=65%) scelte perche' cadono nella zona centrale, stabile, dello sweep di
13 combinazioni del 2026-08-20 (tutte profittevoli, nessuna dipendenza da un punto
fortunato — vedi memoria).

⚠️ Premessa da verificare, non ancora confermata: nel backtest il regime SUPER_BULL era
acceso il 46-89% dei giorni a seconda della soglia — MAI una minoranza rara. Questo
Shadow Monitor server anche a osservare live quanto spesso scatta, non solo se il gate
allentato produce buoni trade.

Stesso principio delle altre due Shadow Monitor gia' live (shadow_monitor.py per
CANDIDATE_MODEL_B, shadow_monitor_l0.py per CANDIDATE_MODEL_L0): calcola in parallelo
cosa avrebbe fatto il candidato, logga su etf_shadow_positions
(model_name='candidate_breadth_20260820'), MAI tocca una decisione reale. Avvolto in
try/except da monitor.py — un errore qui non deve mai bloccare il ciclo vero.

Isola SOLO l'incremento: traccia esclusivamente i trade che il sistema reale (native_7)
NON avrebbe gia' aperto — cioe' solo i casi buy_count==6+MACD durante SUPER_BULL. I
trade nativi 7/7 sono gia' il portafoglio reale, non serve duplicarli qui.

Differenza dagli altri due Shadow Monitor: ha bisogno di UNO STATO PERSISTENTE aggiuntivo
(il regime di ieri, per l'isteresi giorno-su-giorno) — etf_breadth_regime_state,
migrations/005_add_breadth_regime_state.sql.
"""
from datetime import date

from technical_analysis import ETFTechnicalAnalyzer

MODEL_NAME = 'candidate_breadth_20260820'

CORE_FAMILIES = {
    'equity_sviluppati', 'oro_metalli_preziosi', 'mercati_emergenti',
    'settoriali_growth', 'metalli_industriali',
}

ENTER_THRESHOLD = 0.80
EXIT_THRESHOLD = 0.65


def compute_today_breadth(results: list):
    """% di ETF (sull'INTERO universo processato oggi, non solo 'core') con
    EMA20>SMA50 — stessa definizione cross-sezionale del backtest
    (backtest_market_breadth.py::compute_breadth_timeline), calcolata per un solo
    giorno invece che su una serie storica."""
    above = 0
    total = 0
    for r in results:
        a = r.get('analysis') or {}
        ema20 = a.get('ema20')
        sma50 = a.get('sma50')
        if ema20 is None or sma50 is None:
            continue
        total += 1
        if ema20 > sma50:
            above += 1
    return (above / total) if total else None, total


def update_regime_state(db, breadth_pct) -> str:
    """Isteresi a doppia soglia — legge lo stato di ieri dal DB, applica la stessa
    logica di backtest_market_breadth.py::apply_hysteresis(), salva lo stato di oggi.
    Nessuna dipendenza dal codice del backtest (duplicato apposta, e' 4 righe): tenere
    lo stato persistito nel modulo live separato dallo script di backtest offline."""
    prev_state = db.get_breadth_regime_state(MODEL_NAME) or 'NORMAL'
    if breadth_pct is None:
        new_state = prev_state
    elif prev_state == 'NORMAL' and breadth_pct >= ENTER_THRESHOLD:
        new_state = 'SUPER_BULL'
    elif prev_state == 'SUPER_BULL' and breadth_pct < EXIT_THRESHOLD:
        new_state = 'NORMAL'
    else:
        new_state = prev_state
    db.set_breadth_regime_state(MODEL_NAME, new_state, breadth_pct)
    return new_state


def make_breadth_analyzer(famiglia: str) -> ETFTechnicalAnalyzer:
    """Solo gate allentato (min_buy_count=6, MACD sempre obbligatorio via il check
    esplicito sotto) — NESSUN altro override, a differenza di CANDIDATE_MODEL_B
    (mm200/adx/TP). Isola l'effetto della sola breadth, come nel backtest."""
    analyzer = ETFTechnicalAnalyzer(famiglia=famiglia)
    p = dict(analyzer.p)
    p['min_buy_count'] = 6
    analyzer.p = p
    return analyzer


def run_shadow_monitor_breadth(db, results: list, add_log=print) -> list:
    """results: la stessa lista gia' calcolata da monitor.py::run() nel ciclo
    principale — riusata sia per la breadth (intero universo) sia per gli ingressi
    (solo cluster 'core'), stesso pattern degli altri due Shadow Monitor."""
    breadth_pct, n_total = compute_today_breadth(results)
    regime = update_regime_state(db, breadth_pct)
    breadth_str = f"{breadth_pct:.1%}" if breadth_pct is not None else "n/d"
    add_log(f"  Breadth oggi: {breadth_str} ({n_total} ETF) — regime {regime}")

    if regime != 'SUPER_BULL':
        return []  # gate resta 7/7 nativo, nessun ingresso candidato da valutare oggi

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
            analyzer = make_breadth_analyzer(famiglia)

            if open_pos:
                # Posizione ombra aperta — stessa uscita reale di L1 (SL/TP), parametri
                # famiglia invariati (solo il gate d'ingresso e' diverso per questo candidato).
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
                    add_log(f"    🟡 SHADOW BREADTH EXIT {ticker} | {'SL' if sl_hit else 'TP'} | "
                            f"{gross_pct:+.2f}%")
            else:
                # Nessuna posizione ombra — valuta ingresso: buy_count==6 + MACD +
                # fondamenta (regime BULL, prezzo>SMA50, no kill switch), SOLO perche'
                # oggi siamo in SUPER_BULL (7/7 nativo e' gia' il sistema reale, non
                # va duplicato qui — vedi docstring del modulo).
                hist = db.get_ohlc_by_isin(isin, days=250)
                if hist.empty or len(hist) < 220:
                    continue
                close = hist['Close'].astype(float)
                high = hist['High'].astype(float) if 'High' in hist else None
                low = hist['Low'].astype(float) if 'Low' in hist else None

                result_b = analyzer.suggest_level(close, current_level=3, high=high, low=low)
                conditions = result_b.get('conditions', {})
                bc = result_b.get('buy_count', 0)
                sma50_v = conditions.get('sma50_current')
                fondamenta_ok = (not conditions.get('kill_switch', False)) and conditions.get('regime_ok', False) \
                    and (sma50_v is not None and current_price >= sma50_v)

                if bc == 6 and conditions.get('macd_ok') and fondamenta_ok:
                    db.open_shadow_position(MODEL_NAME, ticker, isin, famiglia, today, current_price)
                    opened += 1
                    new_entries.append({
                        'ticker': ticker, 'isin': isin, 'nome': result.get('nome', ticker),
                        'famiglia': famiglia, 'price': current_price,
                    })
                    add_log(f"    🟡 SHADOW BREADTH ENTRY {ticker} @ {current_price:.2f} ({famiglia})")
        except Exception as e:
            add_log(f"    ⚠️  Shadow Breadth errore {ticker}: {type(e).__name__}: {e}")
            continue

    if opened or closed:
        add_log(f"  Shadow Monitor Breadth ({MODEL_NAME}): {checked} controllati, "
                f"{opened} nuovi ingressi, {closed} uscite")

    return new_entries
