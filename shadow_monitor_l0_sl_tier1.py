"""
shadow_monitor_l0_sl_tier1.py — Shadow Monitor per CANDIDATE_L0_SL_TIER1_20260828.

Origine: sweep del primo scaglione dello Stop L0 (`l0_sl_tier1_buffer_pct`, oggi
4% in produzione per equity_sviluppati) — optimize_l0_sl_structural.py, Golden
Dataset batch 2026-08-07, split IN 2023-08-05->2025-08-05 / OUT ->2026-08-05,
105 ticker equity_sviluppati:

  4% (produzione): IN N=103 WR=63.1% PF=4.39 +64.080EUR | OUT N=11 WR=45.5% PF=2.02 +3.179EUR
  5%             : IN N=92  WR=71.7% PF=5.29 +68.217EUR | OUT N=11 WR=54.5% PF=2.70 +4.729EUR
  6%             : IN N=89  WR=74.2% PF=5.05 +67.469EUR | OUT N=10 WR=60.0% PF=2.94 +4.961EUR

5% e 6% battono il 4% su WR/PF/P&L sia IN che OUT, in modo monotono — coerente
con lo stesso risultato di CANDIDATE_MODEL_L0_SL_20260820 (che aveva spostato il
tier1 da 2% a 4%). Le regole strutturali testate nello stesso sweep (ATR,
swing-low grezzo) sono risultate PEGGIO — l'unico segnale pulito e' "stop piu'
largo".

⚠️ N out-of-sample piccolo (10-11) — non conclusivo da solo. Shadow Monitor per
raccogliere dati forward reali. Promozione SOLO a N>=30 e decisione esplicita
dell'utente al checkpoint (stessa disciplina di ogni altro candidato).

Cosa cambia rispetto alla produzione: SOLO `l0_sl_tier1_buffer_pct` (scaglione
"protezione capitale", profit < 5%). Ingresso identico al nativo
(suggest_level_0, regime_min_days_below_sma200 di famiglia), TP identico
(l0_take_profit_pct YAML), tier2/tier3 dello Stop identici. Traccia DUE varianti
in parallelo: 5% e 6%.

Chiamato da monitor.py::run() (STEP 8k), avvolto in try/except — un errore qui
non blocca mai il ciclo reale. Log su etf_shadow_positions, differenziato da
model_name. Email sui nuovi ingressi via alerts.py::send_shadow_entries.
"""
from datetime import date

from technical_analysis import ETFTechnicalAnalyzer

# equity_sviluppati e' l'unica famiglia raggiungibile da L0 (whitelist gate in
# suggest_level_0()). "Azionari Tematici" ci cade dentro per il default_family
# YAML — quindi WATC.PA e simili sono inclusi.
L0_FAMILIES = {'equity_sviluppati'}

# model_name -> buffer del primo scaglione dello Stop
VARIANTS = {
    'candidate_l0_sl_tier1_5pct_20260828': 0.05,
    'candidate_l0_sl_tier1_6pct_20260828': 0.06,
}
# model_name -> variante email (alerts.py::_SHADOW_VARIANTS)
EMAIL_VARIANT = {
    'candidate_l0_sl_tier1_5pct_20260828': 'L0_SL_5PCT',
    'candidate_l0_sl_tier1_6pct_20260828': 'L0_SL_6PCT',
}


def _make_analyzer(famiglia: str, tier1_buffer: float) -> ETFTechnicalAnalyzer:
    """Copia locale di self.p con SOLO l'override del buffer tier1 — mai muta la
    baseline condivisa (stesso pattern sicuro di shadow_monitor_l0.py)."""
    analyzer = ETFTechnicalAnalyzer(famiglia=famiglia)
    analyzer.p = dict(analyzer.p)
    analyzer.p['l0_sl_tier1_buffer_pct'] = tier1_buffer
    return analyzer


def _run_variant(db, results, add_log, model_name, tier1_buffer):
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
            open_pos = db.get_open_shadow_position(model_name, ticker)
            analyzer = _make_analyzer(famiglia, tier1_buffer)

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
                    add_log(f"    🟣 SHADOW L0-SL{int(tier1_buffer*100)} EXIT {ticker} | "
                            f"{'TP' if tp_hit else 'SL'} | {gross_pct:+.2f}%")
            else:
                # Ingresso NATIVO — nessun override sui parametri d'ingresso.
                hist = db.get_ohlc_by_isin(isin, days=250)
                if hist.empty or len(hist) < 220:
                    continue
                close = hist['Close'].astype(float)
                high = hist['High'].astype(float) if 'High' in hist else close
                low = hist['Low'].astype(float) if 'Low' in hist else close
                result_l0 = analyzer.suggest_level_0(close, high, low, current_level=3)
                if result_l0.get('l0_entry'):
                    db.open_shadow_position(model_name, ticker, isin, famiglia,
                                             today, current_price)
                    opened += 1
                    new_entries.append({
                        'ticker': ticker, 'isin': isin,
                        'nome': result.get('nome', ticker),
                        'famiglia': famiglia, 'price': current_price,
                        'regime_mode': result_l0.get('l0_regime_mode'),
                    })
                    add_log(f"    🟣 SHADOW L0-SL{int(tier1_buffer*100)} ENTRY {ticker} @ "
                            f"{current_price:.2f} ({result_l0.get('l0_regime_mode', '?')})")
        except Exception as e:
            add_log(f"    ⚠️  Shadow L0-SL{int(tier1_buffer*100)} errore {ticker}: "
                    f"{type(e).__name__}: {e}")
            continue

    if opened or closed:
        add_log(f"  Shadow Monitor {model_name}: {checked} controllati, "
                f"{opened} nuovi ingressi, {closed} uscite")
    return new_entries


def run_shadow_monitor_l0_sl_tier1(db, results: list, add_log=print):
    """Ritorna {model_name: [new_entries]} per entrambe le varianti (5% e 6%)."""
    out = {}
    for model_name, buf in VARIANTS.items():
        out[model_name] = _run_variant(db, results, add_log, model_name, buf)
    return out
