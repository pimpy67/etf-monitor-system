"""
shadow_monitor_bond_trend.py — Shadow Monitor per CANDIDATE_BOND_TREND_20260824.

Origine (2026-08-24): l'utente ha chiesto un terzo meccanismo per le 5 famiglie
difensive/bond bloccate lo stesso giorno da L1 (min_buy_count: 8 — vedi CLAUDE.md,
sezione "Survey completo 14 famiglie") dopo che il test L0 sulle stesse 8 famiglie
"morte" ha dato zero segnali anche li'. Diagnosticato (memory/etf_family_viability_
survey_2026_08_24.md) che il blocco strutturale di native_7 e' allineamento_ok
(EMA20>SMA50) e rsi_ok — filtri di momentum calibrati su equity, non su bond a bassa
volatilita'. `ETFTechnicalAnalyzer.suggest_bond_trend_entry()` (technical_analysis.py)
implementa un gate molto piu' semplice (solo trend+persistenza+distanza, niente
RSI/ADX/MACD/SMA50), backtestato sul Golden Dataset: IN N=191 WR=60.8% PF=1.71 | OUT
N=76 WR=45.2% PF=1.68 — il candidato piu' stabile del grid search fatto lo stesso giorno.

Stessa filosofia "no automazione" e stesso pattern non invasivo degli altri Shadow
Monitor (candidate_model_b, candidate_model_l0, candidate_l0_oro/metalli): logga solo
su etf_shadow_positions, non tocca mai `config/etf_families.yaml`'s min_buy_count ne'
alcuna decisione reale. Uscita via le stesse funzioni reali di L1
(calculate_sl_suggerito_l1/calculate_stop_gain_dynamic), parametri di target presi da
global_params.bond_trend_model nello YAML (target_max_pct=3%, non il 15% di equity —
il realistico upside di un bond e' molto piu' piccolo).

Chiamato da monitor.py::run() come STEP 8e, avvolto in try/except — un errore qui non
deve mai bloccare il ciclo di monitoraggio reale.
"""
from datetime import date

from technical_analysis import ETFTechnicalAnalyzer

MODEL_NAME = 'candidate_bond_trend_20260824'


def _get_params():
    analyzer = ETFTechnicalAnalyzer(famiglia='bond_governativi')
    gp = analyzer._FAMILIES_CONFIG.get('global_params', {})
    return gp.get('bond_trend_model', {
        'families': ['bond_governativi', 'bond_corp_hy_em', 'settoriali_difensivi',
                     'real_estate_reit', 'private_equity_buffer'],
        'persistence_days': 20, 'dist_max_pct': 0.5,
        'target_max_pct': 0.03, 'target_floor_pct': 0.02,
        'slope_window': 3, 'slope_sensitivity': 0.15,
    })


def run_shadow_monitor_bond_trend(db, results: list, add_log=print):
    """results: la stessa lista gia' calcolata da monitor.py::run() nel ciclo
    principale (analyze_etf() per ogni ETF) — riusata per evitare un secondo fetch."""
    params = _get_params()
    target_families = set(params['families'])
    candidates = [r for r in results if r.get('etf_type') in target_families]
    if not candidates:
        return []

    persistence_days = params['persistence_days']
    dist_max_pct = params['dist_max_pct']
    sg_params = {
        'target_max_pct': params['target_max_pct'],
        'target_floor_pct': params['target_floor_pct'],
        'slope_window': params['slope_window'],
        'slope_sensitivity': params['slope_sensitivity'],
    }

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

            # Serve solo il Close storico (nessun OHLC/RSI/ADX per questo meccanismo)
            days_needed = persistence_days + 40
            hist = db.get_ohlc_by_isin(isin, days=max(days_needed, 120))
            if hist.empty or len(hist) < persistence_days + 25:
                continue
            close = hist['Close'].astype(float)
            ema20_series = analyzer._ema(close, analyzer.ema20_period)

            if open_pos:
                entry_price = float(open_pos['entry_price'])
                ema20_today = float(ema20_series.iloc[-1])
                sl_data = analyzer.calculate_sl_suggerito_l1(entry_price, current_price, ema20_today)
                sl = sl_data.get('sl_suggerito')
                sl_hit = sl is not None and current_price <= sl

                tp_data = analyzer.calculate_stop_gain_dynamic(entry_price, current_price,
                                                                 ema20_series,
                                                                 {'l1_stop_gain_dynamic': sg_params})
                tp_hit = bool(tp_data.get('trigger'))

                if sl_hit or tp_hit:
                    gross_pct = round((current_price / entry_price - 1) * 100, 3)
                    db.close_shadow_position(open_pos['id'], today, current_price,
                                              'TP' if tp_hit else 'SL', gross_pct)
                    closed += 1
                    add_log(f"    🟡 SHADOW BOND-TREND EXIT {ticker} | {'TP' if tp_hit else 'SL'} | "
                            f"{gross_pct:+.2f}%")
            else:
                entry_check = analyzer.suggest_bond_trend_entry(close, ema20_series,
                                                                  persistence_days, dist_max_pct)
                if entry_check.get('entry_ok'):
                    db.open_shadow_position(MODEL_NAME, ticker, isin, famiglia,
                                             today, current_price)
                    opened += 1
                    new_entries.append({
                        'ticker': ticker, 'isin': isin,
                        'nome': result.get('nome', ticker),
                        'famiglia': famiglia, 'price': current_price,
                    })
                    add_log(f"    🟡 SHADOW BOND-TREND ENTRY {ticker} @ {current_price:.4f}")
        except Exception as e:
            add_log(f"    ⚠️  Shadow bond-trend monitor errore {ticker}: {type(e).__name__}: {e}")
            continue

    if opened or closed:
        add_log(f"  Shadow Monitor Bond-Trend ({MODEL_NAME}): {checked} controllati, "
                f"{opened} nuovi ingressi, {closed} uscite")

    return new_entries
