"""
shadow_monitor_tighten_rsi.py — Shadow Monitor per CANDIDATE_TIGHTEN_RSI_20260825.

Origine (2026-08-25): l'utente ha notato che i segnali L1 sulle famiglie 'core'
(smart_6_macd) a volte entrano gia' troppo distanti dalla EMA20, con rischio di
ritracciamento — specificamente nel sotto-caso in cui l'unica condizione nativa
mancante e' rsi_ok (RSI troppo alto): il sistema accetta comunque l'ingresso via
il boost "6/7 + MACD obbligatorio" gia' in produzione (CANDIDATE_MODEL_B_20260807,
promosso 2026-08-24), ma proprio in quel sotto-caso l'RSI alto e' spesso
accompagnato da una distanza dalla EMA20 gia' estesa.

Candidato testato (backtest_rsi_gate_variants.py, scratch, Golden Dataset batch
2026-08-07, stesso split IN/OUT di CANDIDATE_MODEL_B): quando l'unica condizione
mancante e' rsi_ok, richiedere in aggiunta dist_ema20 <= 3.0% (invece del
ema_dist_max normale di famiglia, 4-5%) prima di accettare l'ingresso — altrimenti
skip (il candidato NON entra quel giorno, anche se la produzione lo farebbe).
Per ogni altro caso (7/7 nativo, o 6/7 con condizione mancante diversa da RSI) il
candidato e' IDENTICO alla produzione. Confrontata anche un'alternativa "aspetta
il pullback" (wait_pullback): risultati numericamente identici su ogni soglia
testata (il rescan giornaliero di 'tighten' produce di fatto la stessa attesa),
quindi si traccia solo la versione piu' semplice.

Risultati backtest (10.000€/trade, costi Directa 5+5€, tasse 26%):
  baseline (produzione)      IN N=31 PF=1.45 WR=54.8% | OUT N=18 PF=1.62 WR=55.6%
  tighten cap=3.0% (questo)  IN N=24 PF=2.21 WR=62.5% | OUT N=14 PF=1.69 WR=57.1%
Migliora OGNI metrica sia in-sample che out-of-sample rispetto alla baseline —
ma N ancora sotto la soglia di 30 usata in questo progetto per la fiducia, quindi
NON promosso in produzione: Shadow Monitor prima, stessa disciplina di ogni altro
candidato (vedi CLAUDE.md).

Stesso pattern non invasivo degli altri Shadow Monitor: logga solo su
etf_shadow_positions, non tocca mai config/etf_families.yaml ne' alcuna decisione
reale. Uscita via le stesse funzioni reali di L1 (calculate_sl_suggerito_l1 /
calculate_stop_gain_dynamic con i parametri l1_stop_gain_dynamic gia' nativi di
famiglia — nessun override separato, a differenza del candidato Bond-Trend che
usa un target diverso).

Chiamato da monitor.py::run() come STEP 8g, avvolto in try/except — un errore qui
non deve mai bloccare il ciclo di monitoraggio reale.
"""
from datetime import date

from technical_analysis import ETFTechnicalAnalyzer

MODEL_NAME = 'candidate_tighten_rsi_20260825'

CORE_FAMILIES = {'equity_sviluppati', 'mercati_emergenti', 'settoriali_growth',
                  'oro_metalli_preziosi', 'metalli_industriali'}

CONDITION_KEYS = ['allineamento_ok', 'persistenza_ok', 'rsi_ok', 'distance_ok',
                  'adx_ok', 'macd_ok', 'space_residuo_ok']

TIGHTEN_DIST_CAP = 3.0  # % — cap piu' stretto sul solo sotto-caso "manca solo RSI"


def _is_rsi_only_entry(conditions: dict) -> bool:
    missing = [k for k in CONDITION_KEYS if not conditions.get(k, True)]
    return len(missing) == 1 and missing[0] == 'rsi_ok'


def run_shadow_monitor_tighten_rsi(db, results: list, add_log=print):
    """results: la stessa lista gia' calcolata da monitor.py::run() nel ciclo
    principale (analyze_etf() per ogni ETF) — riusata per evitare un secondo fetch."""
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
            analyzer = ETFTechnicalAnalyzer(famiglia=famiglia)

            if open_pos:
                entry_price = float(open_pos['entry_price'])
                days_needed = 40
                hist = db.get_ohlc_by_isin(isin, days=days_needed)
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
                    add_log(f"    🟣 SHADOW TIGHTEN-RSI EXIT {ticker} | {'TP' if tp_hit else 'SL'} | "
                            f"{gross_pct:+.2f}%")
            else:
                if a.get('suggested_level') != 1:
                    continue
                conditions = a.get('conditions', {}) or {}
                dist_ema20 = conditions.get('dist_ema20')

                if _is_rsi_only_entry(conditions):
                    # sotto-caso specifico: applica il cap piu' stretto della candidata
                    if dist_ema20 is None or not (0 <= dist_ema20 <= TIGHTEN_DIST_CAP):
                        continue  # produzione entrerebbe, il candidato no
                # altri casi (7/7 nativo, o 6/7 con missing != RSI): identico alla produzione

                db.open_shadow_position(MODEL_NAME, ticker, isin, famiglia,
                                         today, current_price)
                opened += 1
                new_entries.append({
                    'ticker': ticker, 'isin': isin,
                    'nome': result.get('nome', ticker),
                    'famiglia': famiglia, 'price': current_price,
                })
                add_log(f"    🟣 SHADOW TIGHTEN-RSI ENTRY {ticker} @ {current_price:.4f} "
                        f"(dist_ema20={dist_ema20})")
        except Exception as e:
            add_log(f"    ⚠️  Shadow tighten-RSI monitor errore {ticker}: {type(e).__name__}: {e}")
            continue

    if opened or closed:
        add_log(f"  Shadow Monitor Tighten-RSI ({MODEL_NAME}): {checked} controllati, "
                f"{opened} nuovi ingressi, {closed} uscite")

    return new_entries
