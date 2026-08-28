"""
radar_compute.py — calcolo condiviso dei due radar informativi
(Radar Anticipato + Radar Rimbalzo EMA20).

Nato dall'incidente 2026-08-28: gli endpoint /api/approach-radar e
/api/bounce-radar scansionavano ~200 ETF (una query DB + regressione lineare
ciascuno) a OGNI richiesta, e la dashboard li chiama a ogni apertura pagina +
ogni 60s di auto-refresh. Su un server a 1 vCPU / 1 thread le scansioni si
accavallavano e bloccavano l'intera app.

Soluzione: il calcolo pesante gira UNA volta per ciclo del monitor
(`refresh_radar_files`) e viene salvato in `data/radar_*.json`. Gli endpoint
leggono il file (istantaneo). Se il file manca o e' troppo vecchio, l'endpoint
lo ricalcola una volta e lo riscrive — cosi' funziona anche prima del primo
ciclo monitor, senza mai piu' fare il lavoro pesante a ogni richiesta.
"""
import json
import os
import time

from technical_analysis import ETFTechnicalAnalyzer

# Stessi default degli endpoint live storici (app.py) e del backtest.
DEFAULTS = {
    'approach': {'lookback': 7,  'min_r2': 0.3, 'levels': ('2', '3')},
    'bounce':   {'lookback': 10, 'min_r2': 0.3, 'levels': ('1', '2', '3')},
}
_FILES = {
    'approach': 'data/radar_approach.json',
    'bounce':   'data/radar_bounce.json',
}
# Un file piu' vecchio di questo viene ricalcolato al primo hit (il monitor
# normalmente lo rinfresca a ogni ciclo, ~2 volte al giorno).
_FILE_MAX_AGE_SEC = 8 * 3600


def _assign_quality_rank(results):
    """
    Ranking dei segnali Radar per qualita' tecnica (idea utente 2026-08-27):
    evidenzia i 3 migliori per quality_score (ADX + RVOL) con 'quality_rank'
    1/2/3. Non cambia l'ordine di visualizzazione. Muta i dict in-place.
    """
    ranked = sorted((r for r in results if r.get('quality_score') is not None),
                    key=lambda r: -r['quality_score'])
    for i, r in enumerate(ranked[:3]):
        r['quality_rank'] = i + 1


def compute_radar(radar_type, data, db, lookback=None, min_r2=None):
    """
    Calcolo pesante (scansione + regressione su ~200 ETF). `data` = contenuto di
    dashboard_data.json, `db` = PriceDatabase. Ritorna il dict pronto per jsonify.
    """
    cfg = DEFAULTS[radar_type]
    lookback = cfg['lookback'] if lookback is None else lookback
    min_r2 = cfg['min_r2'] if min_r2 is None else min_r2

    # I livelli sono chiavi stringa quando il dict arriva da dashboard_data.json,
    # chiavi int quando arriva in-memory dal monitor — accetta entrambe.
    levels_dict = (data or {}).get('levels', {}) or {}
    candidates = []
    for level_key in cfg['levels']:
        candidates.extend(levels_dict.get(level_key) or levels_dict.get(int(level_key)) or [])

    results = []
    for etf in candidates:
        isin = etf.get('isin')
        ticker = etf.get('ticker')
        identifier = isin or ticker
        if not identifier:
            continue

        # dist_ema20 gia' nello snapshot odierno: scarta subito chi e' dalla
        # parte sbagliata dell'EMA20 senza fare query/regressione inutili.
        dist_today = etf.get('dist_ema20')
        if dist_today is not None:
            if radar_type == 'approach' and dist_today >= 0:
                continue
            if radar_type == 'bounce' and dist_today < 0:
                continue

        hist = db.get_ohlc_by_isin(identifier, days=max(60, lookback + 30))
        if hist.empty or len(hist) < 25:
            continue

        close = hist['Close'].astype(float)
        has_ohlc = hist['High'].notna().any() and hist['Low'].notna().any()
        high = hist['High'].astype(float) if has_ohlc else None
        low = hist['Low'].astype(float) if has_ohlc else None
        volume = hist['Volume'].astype(float) if hist['Volume'].notna().any() else None

        analyzer = ETFTechnicalAnalyzer(famiglia=etf.get('etf_type', 'equity_sviluppati'))
        if radar_type == 'approach':
            signal = analyzer.compute_approach_signal(close, high, low, volume=volume,
                                                      lookback=lookback, min_r2=min_r2)
            if not signal.get('approaching'):
                continue
        else:
            signal = analyzer.compute_pullback_bounce_signal(close, high, low, volume=volume,
                                                             lookback=lookback, min_r2=min_r2)
            if not signal.get('bouncing'):
                continue

        results.append({
            'isin': isin, 'ticker': ticker, 'nome': etf.get('nome'),
            'famiglia': etf.get('etf_type'), 'categoria': etf.get('categoria'),
            'price': etf.get('price'), 'buy_count': etf.get('buy_count'),
            'regime': etf.get('regime'),
            **signal,
        })

    _assign_quality_rank(results)
    if radar_type == 'approach':
        results.sort(key=lambda r: (-r['score'], r['dist_ema20_pct']))
    else:
        results.sort(key=lambda r: (-r['score'], r['days_since_min']))

    return {'lookback_days': lookback, 'min_r2': min_r2,
            'n_scanned': len(candidates), 'results': results,
            'computed_at': time.time()}


def _read_file(radar_type):
    try:
        with open(_FILES[radar_type], 'r') as f:
            return json.load(f)
    except Exception:
        return None


def _write_file(radar_type, payload):
    try:
        os.makedirs('data', exist_ok=True)
        tmp = _FILES[radar_type] + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(payload, f)
        os.replace(tmp, _FILES[radar_type])
    except Exception:
        pass


def get_radar(radar_type, data, db, lookback=None, min_r2=None):
    """
    Usato dagli endpoint. Con parametri di default: serve il file precalcolato
    (lo ricalcola solo se manca o e' vecchio). Con parametri non standard:
    calcola live (caso raro, la dashboard usa sempre i default).
    """
    cfg = DEFAULTS[radar_type]
    is_default = ((lookback is None or lookback == cfg['lookback']) and
                  (min_r2 is None or abs(min_r2 - cfg['min_r2']) < 1e-9))

    if is_default:
        cached = _read_file(radar_type)
        if cached and (time.time() - cached.get('computed_at', 0)) < _FILE_MAX_AGE_SEC:
            return cached
        payload = compute_radar(radar_type, data, db)
        _write_file(radar_type, payload)
        return payload

    return compute_radar(radar_type, data, db, lookback=lookback, min_r2=min_r2)


def refresh_radar_files(data, db, add_log=print):
    """Chiamato dal monitor a fine ciclo: ricalcola e salva entrambi i file."""
    for radar_type in ('approach', 'bounce'):
        try:
            payload = compute_radar(radar_type, data, db)
            _write_file(radar_type, payload)
            add_log(f"  Radar {radar_type}: {len(payload['results'])} segnali "
                    f"({payload['n_scanned']} scansionati) -> {_FILES[radar_type]}")
        except Exception as e:
            add_log(f"  ⚠️  Radar {radar_type} refresh fallito: {type(e).__name__}: {e}")
