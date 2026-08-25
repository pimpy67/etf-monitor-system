"""
shadow_monitor_radars.py — Shadow Monitor per i due radar informativi come
CANDIDATI di trigger d'ingresso reale (idea utente 2026-08-25).

Origine: Radar Anticipato (compute_approach_signal) e Radar Rimbalzo EMA20
(compute_pullback_bounce_signal) sono nati puramente informativi (dashboard,
nessun impatto su L0/L1/L2/L3). Backtest su Golden Dataset (backtest_radars.py,
2026-08-25, batch 2026-08-07) li ha confrontati con L1 reale, sugli stessi
ticker/date, stessa uscita (calculate_sl_suggerito_l1 + calculate_stop_gain_
dynamic), stessi costi/tasse:

  IN (2023-08-05->2025-08-05):  L1 N=37 WR=59.5% PF=1.90 | approach N=932
    WR=43.1% PF=1.54 | bounce N=1085 WR=52.5% PF=1.38 (dopo esclusione del
    ticker 3LAM.MI, dato corrotto nel Golden Dataset — stesso problema gia'
    documentato in memory/etf_family_viability_survey_2026_08_24.md)
  OUT (2025-08-05->2026-08-05): L1 N=17 WR=52.9% PF=1.45 | approach N=381
    WR=49.1% PF=1.93 | bounce N=435 WR=54.9% PF=1.56

PF che MIGLIORA out-of-sample per entrambi i radar (non lo schema tipico
dell'overfitting), overlap quasi nullo con gli ingressi L1 reali (0% approach,
1.2% bounce — vedi backtest_radars.py) — opportunita' genuinamente diverse, non
solo rumore attorno al gate 7/7. Volume di trade molto piu' alto di L1 (~25-30x)
ma qualita' per trade piu' bassa (WR/PF inferiori). Non promosso: stessa
disciplina di ogni altro candidato in questo progetto — Shadow Monitor prima,
promozione solo dopo N>=30 su dati forward reali e decisione esplicita
dell'utente.

Universo candidato: stesso filtro di livello gia' usato dagli endpoint live
/api/approach-radar (L2/L3 — non ancora sopra EMA20) e /api/bounce-radar
(L1/L2/L3 — deve essere sopra EMA20), per restare coerenti con cio' che
l'utente vede davvero nella dashboard. Uscita: riusa le stesse funzioni reali
di L1 (nessuna duplicazione di logica) — solo il trigger di ingresso cambia.

Chiamato da monitor.py::run() come step aggiuntivo, avvolto in try/except —
un errore qui non deve mai bloccare il ciclo di monitoraggio reale (stesso
principio degli altri Shadow Monitor).
"""
from datetime import date

from technical_analysis import ETFTechnicalAnalyzer

RADAR_PARAMS = {
    # Stessi default usati dagli endpoint live /api/approach-radar e
    # /api/bounce-radar (app.py) e dal backtest — nessun parametro nuovo.
    'approach': {'lookback': 7, 'min_r2': 0.3},
    'bounce':   {'lookback': 10, 'min_r2': 0.3},
}
MODEL_NAMES = {
    'approach': 'candidate_radar_approach_20260825',
    'bounce':   'candidate_radar_bounce_20260825',
}
# Stesso filtro di livello degli endpoint live — vedi app.py get_approach_radar()/get_bounce_radar()
CANDIDATE_LEVELS = {
    'approach': {2, 3},
    'bounce':   {1, 2, 3},
}
HIST_DAYS = 60  # coerente con max(60, lookback+30) usato dagli endpoint live


def _run(radar_type, db, results, add_log):
    model_name = MODEL_NAMES[radar_type]
    params = RADAR_PARAMS[radar_type]
    levels = CANDIDATE_LEVELS[radar_type]

    candidates = []
    for r in results:
        a = r.get('analysis') or {}
        lvl = a.get('suggested_level')
        if lvl is not None and int(lvl) in levels:
            candidates.append(r)
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
        if not ticker or not isin or not current_price:
            continue
        current_price = float(current_price)
        checked += 1

        try:
            hist = db.get_ohlc_by_isin(isin, days=HIST_DAYS)
            if hist.empty or len(hist) < 30:
                continue
            close = hist['Close'].astype(float)
            has_ohlc = 'High' in hist and 'Low' in hist and hist['High'].notna().any()
            high = hist['High'].astype(float) if has_ohlc else None
            low = hist['Low'].astype(float) if has_ohlc else None

            analyzer = ETFTechnicalAnalyzer(famiglia=famiglia)
            open_pos = db.get_open_shadow_position(model_name, ticker)

            if open_pos:
                # Stesse funzioni e stessa logica di backtest_radars.py::simulate_radar()
                # e di L1 reale — SL = calculate_sl_suggerito_l1, TP = calculate_stop_
                # gain_dynamic, check una volta al giorno sul Close.
                entry_price = float(open_pos['entry_price'])
                ema20_series = analyzer._ema(close, 20).tail(10)
                ema20_today = float(ema20_series.iloc[-1])

                sl_data = analyzer.calculate_sl_suggerito_l1(entry_price, current_price, ema20_today)
                sl = sl_data.get('sl_suggerito')
                sg_data = analyzer.calculate_stop_gain_dynamic(entry_price, current_price, ema20_series, analyzer.p)
                tp_hit = bool(sg_data.get('trigger'))
                sl_hit = sl is not None and current_price <= sl

                if sl_hit or tp_hit:
                    gross_pct = round((current_price / entry_price - 1) * 100, 3)
                    db.close_shadow_position(open_pos['id'], today, current_price,
                                              'TP' if tp_hit else 'SL', gross_pct)
                    closed += 1
                    add_log(f"    🔁 SHADOW RADAR-{radar_type.upper()} EXIT {ticker} | "
                            f"{'TP' if tp_hit else 'SL'} | {gross_pct:+.2f}%")
            else:
                if radar_type == 'approach':
                    signal = analyzer.compute_approach_signal(close, high, low, **params)
                    fired = bool(signal.get('approaching'))
                else:
                    signal = analyzer.compute_pullback_bounce_signal(close, high, low, **params)
                    fired = bool(signal.get('bouncing'))

                if fired:
                    db.open_shadow_position(model_name, ticker, isin, famiglia, today, current_price)
                    opened += 1
                    new_entries.append({
                        'ticker': ticker, 'isin': isin,
                        'nome': result.get('nome', ticker),
                        'famiglia': famiglia, 'price': current_price,
                        'score': signal.get('score'),
                    })
                    add_log(f"    🔁 SHADOW RADAR-{radar_type.upper()} ENTRY {ticker} @ "
                            f"{current_price:.2f} (score={signal.get('score')})")
        except Exception as e:
            add_log(f"    ⚠️  Shadow Radar-{radar_type} errore {ticker}: {type(e).__name__}: {e}")
            continue

    if opened or closed:
        add_log(f"  Shadow Monitor Radar-{radar_type} ({model_name}): {checked} controllati, "
                f"{opened} nuovi ingressi, {closed} uscite")

    return new_entries


def run_shadow_monitor_radar_approach(db, results, add_log=print):
    return _run('approach', db, results, add_log)


def run_shadow_monitor_radar_bounce(db, results, add_log=print):
    return _run('bounce', db, results, add_log)
