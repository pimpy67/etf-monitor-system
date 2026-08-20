"""
backtest_advanced_pillars.py — Test dei 4 "pilastri quant avanzati" proposti dall'utente
(position sizing risk-parity, filtro macro-regime, ranking momentum, qualita' dati volume),
sullo stesso Golden Dataset/metodologia gia' usata per native_7/smart_6_macd/CANDIDATE_MODEL_L0.

Riusa (senza modificarli) backtest_l1.py, backtest_l0_v2.py e optimize_hyperparameters.py.
Dove serve una variante del walk-forward (veto macro-regime), si copia localmente il loop
minimo necessario invece di toccare i file esistenti.

Uso (dentro il container, working dir /app):
  python3 backtest_advanced_pillars.py --all
  python3 backtest_advanced_pillars.py --volume-only   # solo diagnostica volumi (veloce)
"""
import sys
sys.path.insert(0, '/app')

import argparse
import json
from datetime import datetime

import pandas as pd

from technical_analysis import ETFTechnicalAnalyzer
from database import PriceDatabase
from backtest_l1 import (load_universe as load_universe_l1, TARGET_FAMILIES, make_analyzer,
                          simulate as simulate_l1, apply_costs_and_tax as costs_l1,
                          FrozenDataFetcher, DEFAULT_FROZEN_BATCH)
from backtest_l0_v2 import (load_universe as load_universe_l0, get_l0_whitelist,
                             simulate_l0, apply_costs_and_tax as costs_l0)
from optimize_hyperparameters import (load_cluster_data, make_analyzer_for_combo, run_combo,
                                       TRAIN_START, TRAIN_END, TEST_END, extra_metrics,
                                       precompute_ticker)

IS_START, IS_END, OOS_END = TRAIN_START, TRAIN_END, TEST_END  # 2023-08-05 / 2025-08-05 / 2026-08-05
CANDIDATE_B_OVERRIDES = {'mm200_absolute': 7.0, 'adx_delta': -4, 'target_max_pct': 0.15}
BENCHMARK_CANDIDATES = ['ACWI.PA', 'IWDA.AS', 'IWDA.L']


def split_is_oos(trades):
    is_t = [t for t in trades if IS_START.isoformat() <= t['entry_date'] < IS_END.isoformat()]
    oos_t = [t for t in trades if IS_END.isoformat() <= t['entry_date'] < OOS_END.isoformat()]
    return is_t, oos_t


# ─────────────────────────────────────────────────────────────────────────
# Base trade sets (riusati da piu' esperimenti)
# ─────────────────────────────────────────────────────────────────────────

def build_native7_trades(_cache=[]):
    """native_7 su tutte le 13 famiglie target, storico intero IS+OOS. Usa lo stesso
    precompute (ema10/ema20/sma50/sma200/rsi/adx/macd/atr) gia' validato in
    optimize_hyperparameters.py invece di farlo ricalcolare da suggest_level() ogni giorno —
    stesso identico risultato (indicatori causali), solo piu' veloce su 236 ticker."""
    if _cache:
        return _cache[0]
    fetcher = FrozenDataFetcher(DEFAULT_FROZEN_BATCH)
    universe = load_universe_l1()
    out = []
    for item in universe:
        ticker, famiglia = item['ticker'], item['famiglia']
        hist = fetcher.get_historical_data(ticker, days=1200)
        if hist.empty or len(hist) < 220:
            continue
        has_ohlc = all(c in hist.columns for c in ['Open', 'High', 'Low'])
        close_full = hist['Close'].astype(float)
        high_full = hist['High'].astype(float) if has_ohlc else None
        low_full = hist['Low'].astype(float) if has_ohlc else None
        test_dates = [d for d in hist.index if IS_START <= d.date() < OOS_END]
        if not test_dates:
            continue
        analyzer = make_analyzer(famiglia)
        precomputed_full = precompute_ticker(analyzer, close_full, high_full, low_full)
        precomputed_for_sim = {k: v for k, v in precomputed_full.items() if k != 'macd_ok'}
        trades = simulate_l1(analyzer, close_full, high_full, low_full, hist.index, test_dates,
                              precomputed_full=precomputed_for_sim)
        if trades:
            for t in trades:
                t['ticker'], t['famiglia'] = ticker, famiglia
                t['_close_full'] = close_full
                t['_ema20_full'] = precomputed_full['ema20']
                t['_hist_index'] = hist.index
            out.extend(trades)
    _cache.append(out)
    return out


def build_candidate_b_trades(veto_regime=None, _cluster_items_cache=[]):
    """smart_6_macd / CANDIDATE_MODEL_B, cluster 'core' soltanto.
    veto_regime: se fornito, dict {date_iso: bool} — blocca i NUOVI ingressi nei giorni
    in cui il benchmark macro non e' in BULL (le uscite non sono mai toccate).

    Senza veto_regime, chiama run_combo() di optimize_hyperparameters.py VERBATIM (non una
    riscrittura) per garanzia di identita' con i numeri gia' certificati di CANDIDATE_MODEL_B.
    Con veto_regime, serve un macd_skip_mask combinato che run_combo() non espone — qui si
    replica lo stesso identico corpo di run_combo() con un solo termine aggiunto nella mask."""
    if not _cluster_items_cache:
        by_cluster = load_cluster_data(DEFAULT_FROZEN_BATCH, cluster_name='core')
        _cluster_items_cache.append(by_cluster.get('core', []))
    cluster_items = _cluster_items_cache[0]

    if veto_regime is None:
        results = run_combo(cluster_items, CANDIDATE_B_OVERRIDES, IS_START, OOS_END)
        out = []
        by_ticker = {e['ticker']: e for e in cluster_items}
        for r in results:
            entry = by_ticker[r['ticker']]
            for t in r['variants']['combo']['trades']:
                t['ticker'], t['famiglia'] = r['ticker'], r['famiglia']
                t['_close_full'] = entry['close_full']
                t['_ema20_full'] = entry['precomputed']['ema20']
                t['_hist_index'] = entry['hist_index']
                out.append(t)
        return out

    out = []
    for entry in cluster_items:
        analyzer = make_analyzer_for_combo(entry, CANDIDATE_B_OVERRIDES, min_buy_count=6)
        test_dates = [d for d in entry['hist_index'] if IS_START <= d.date() < OOS_END]
        if not test_dates:
            continue
        precomputed_series = {k: v for k, v in entry['precomputed'].items() if k != 'macd_ok'}
        macd_ok_mask = entry['precomputed']['macd_ok']
        regime_mask = pd.Series(
            [veto_regime.get(d.date().isoformat(), True) for d in entry['hist_index']],
            index=entry['hist_index'])
        combined_mask = macd_ok_mask & regime_mask
        trades = simulate_l1(analyzer, entry['close_full'], entry['high_full'], entry['low_full'],
                              entry['hist_index'], test_dates, require_macd=True,
                              precomputed_full=precomputed_series, macd_skip_mask=combined_mask)
        for t in trades:
            t['ticker'], t['famiglia'] = entry['ticker'], entry['famiglia']
            t['_close_full'] = entry['close_full']
            t['_ema20_full'] = entry['precomputed']['ema20']
            t['_hist_index'] = entry['hist_index']
        out.extend(trades)
    return out


def simulate_l0_with_veto(analyzer, close_full, high_full, low_full, hist_index, test_dates,
                           veto_regime, precomputed=None):
    """Copia locale di backtest_l0_v2.py::simulate_l0() con un solo skip aggiuntivo per i
    nuovi ingressi nei giorni non-BULL sul benchmark macro. Nessun'altra modifica alla logica.

    precomputed (opzionale): dict con rsi/ema20/sma50 gia' calcolati sull'intera serie (stesso
    pattern di optimize_l0.py::precompute_ticker) — evita di far ricalcolare tutto da zero a
    suggest_level_0() a ogni giorno del walk-forward (era il collo di bottiglia dominante)."""
    holding = False
    entry_price = None
    entry_date = None
    entry_mode = None
    trades = []

    for d in test_dates:
        pos = hist_index.get_loc(d)
        close_slice = close_full.iloc[:pos + 1]
        high_slice = high_full.iloc[:pos + 1] if high_full is not None else None
        low_slice = low_full.iloc[:pos + 1] if low_full is not None else None
        close_today = float(close_slice.iloc[-1])

        if not holding:
            if not veto_regime.get(d.date().isoformat(), True):
                continue
            precomputed_slice = ({k: v.iloc[:pos + 1] for k, v in precomputed.items()}
                                  if precomputed is not None else None)
            result = analyzer.suggest_level_0(close_slice, high_slice, low_slice, current_level=3,
                                               precomputed=precomputed_slice)
            if result.get('l0_entry'):
                holding = True
                entry_price = close_today
                entry_date = d.date().isoformat()
                entry_mode = result.get('l0_regime_mode')
        else:
            sl_data = analyzer.calculate_sl_suggerito_l0(entry_price, close_today)
            sl = sl_data.get('sl_suggerito')
            tp_data = analyzer.calculate_tp_suggerito_l0(entry_price, close_today)
            tp_hit = bool(tp_data.get('trigger'))
            sl_hit = sl is not None and close_today <= sl

            if sl_hit or tp_hit:
                exit_reason = 'SL' if sl_hit else 'TP'
                gross_pct = round((close_today / entry_price - 1) * 100, 3)
                trades.append({
                    'entry_date': entry_date, 'entry_price': entry_price,
                    'exit_date': d.date().isoformat(), 'exit_price': close_today,
                    'status': 'closed', 'gross_pct_gain': gross_pct,
                    'exit_reason': exit_reason, 'entry_mode': entry_mode,
                })
                holding = False
                entry_price = None
                entry_date = None
                entry_mode = None

    if holding:
        last_price = float(close_full.iloc[-1])
        gross_pct = round((last_price / entry_price - 1) * 100, 3)
        trades.append({
            'entry_date': entry_date, 'entry_price': entry_price,
            'exit_date': None, 'exit_price': last_price,
            'status': 'open', 'gross_pct_gain': gross_pct,
            'exit_reason': None, 'entry_mode': entry_mode,
        })
    return trades


def _load_l0_histories(_cache=[]):
    """Carica una sola volta lo storico OHLC + precompute (rsi/ema20/sma50, stesso pattern
    di optimize_l0.py::precompute_ticker) per l'universo whitelisted L0 — riusato sia dalla
    baseline sia dalla variante con veto macro, per non rifare I/O DB ne' ricalcolo due volte."""
    if not _cache:
        db = PriceDatabase()
        universe = load_universe_l0()
        loaded = []
        for item in universe:
            ticker, famiglia = item['ticker'], item['famiglia']
            hist = db.get_frozen_ohlcv(ticker, DEFAULT_FROZEN_BATCH)
            if hist.empty or len(hist) < 220:
                continue
            has_ohlc = all(c in hist.columns for c in ['Open', 'High', 'Low'])
            close_full = hist['Close'].astype(float)
            high_full = hist['High'].astype(float) if has_ohlc else None
            low_full = hist['Low'].astype(float) if has_ohlc else None
            test_dates = [d for d in hist.index if IS_START <= d.date() < OOS_END]
            if not test_dates:
                continue
            analyzer_tmp = ETFTechnicalAnalyzer(famiglia=famiglia)
            precomputed = {
                'rsi': analyzer_tmp._rsi(close_full),
                'ema20': analyzer_tmp._ema(close_full, analyzer_tmp.ema20_period),
                'sma50': analyzer_tmp._sma(close_full, 50),
            }
            loaded.append({'ticker': ticker, 'famiglia': famiglia, 'close_full': close_full,
                            'high_full': high_full, 'low_full': low_full,
                            'hist_index': hist.index, 'test_dates': test_dates,
                            'precomputed': precomputed})
        _cache.append(loaded)
        print(f"  [L0] Caricati+precomputati: {len(loaded)} ticker su {len(universe)} nella whitelist")
    return _cache[0]


def build_candidate_l0_trades(veto_regime=None):
    """CANDIDATE_MODEL_L0: solo equity_sviluppati (whitelist), regime_min_days_below_sma200=5.
    veto_regime=None equivale a nessun veto (dict vuoto: .get(date, True) e' sempre True) —
    stessa funzione simulate_l0_with_veto usata per baseline e variante, per garanzia di
    identita' di comportamento a parte il veto stesso."""
    veto = veto_regime if veto_regime is not None else {}
    out = []
    for e in _load_l0_histories():
        analyzer = ETFTechnicalAnalyzer(famiglia=e['famiglia'])
        analyzer.p = dict(analyzer.p)
        analyzer.p['l0_regime'] = dict(analyzer.p.get('l0_regime', {}))
        analyzer.p['l0_regime']['regime_min_days_below_sma200'] = 5  # CANDIDATE_MODEL_L0

        trades = simulate_l0_with_veto(analyzer, e['close_full'], e['high_full'], e['low_full'],
                                        e['hist_index'], e['test_dates'], veto,
                                        precomputed=e['precomputed'])
        for t in trades:
            t['ticker'], t['famiglia'] = e['ticker'], e['famiglia']
        out.extend(trades)
    return out


# ─────────────────────────────────────────────────────────────────────────
# Esperimento 1 — Position sizing risk-parity
# ─────────────────────────────────────────────────────────────────────────

def sl_initial_l1(analyzer, trade):
    ema20_full = trade['_ema20_full']
    hist_index = trade['_hist_index']
    entry_ts = pd.Timestamp(trade['entry_date'])
    try:
        pos = hist_index.get_loc(entry_ts)
    except KeyError:
        return None
    ema20_at_entry = float(ema20_full.iloc[pos]) if pd.notna(ema20_full.iloc[pos]) else None
    if ema20_at_entry is None:
        return None
    sl = analyzer.calculate_sl_suggerito_l1(trade['entry_price'], trade['entry_price'], ema20_at_entry)
    return sl.get('sl_suggerito')


def experiment_1_position_sizing(native7_trades, candb_trades, candl0_trades):
    print("\n" + "=" * 78)
    print("ESPERIMENTO 1 — Position sizing risk-parity (budget rischio 1%/2% su 100.000EUR)")
    print("=" * 78)

    results = {}
    for label, trades, is_l0 in [('native_7', native7_trades, False),
                                  ('smart_6_macd', candb_trades, False),
                                  ('CANDIDATE_MODEL_L0', candl0_trades, True)]:
        closed = [t for t in trades if t['status'] == 'closed']
        rows = []
        skipped_no_sl = 0
        for t in closed:
            if is_l0:
                sl_data_dummy = None  # calcolato sotto senza analyzer per famiglia (whitelist unica)
                analyzer = ETFTechnicalAnalyzer(famiglia='equity_sviluppati')
                sl = analyzer.calculate_sl_suggerito_l0(t['entry_price'], t['entry_price']).get('sl_suggerito')
            else:
                analyzer = make_analyzer(t['famiglia'])
                sl = sl_initial_l1(analyzer, t)
            if sl is None or sl >= t['entry_price']:
                skipped_no_sl += 1
                continue
            risk_pct = (t['entry_price'] - sl) / t['entry_price']
            rows.append({**t, 'risk_pct': risk_pct})

        for budget_pct, budget_eur, flat_size in [(0.01, 1000, 10000), (0.02, 2000, 10000)]:
            flat_total, risk_total = 0.0, 0.0
            flat_capital, risk_capital = 0.0, 0.0
            for r in rows:
                size_flat = flat_size
                size_risk = min(budget_eur / r['risk_pct'], flat_size * 3)  # cap 3x per evitare size assurde su rischio minuscolo
                t_flat = costs_l0(dict(r), size_flat) if is_l0 else costs_l1(dict(r), size_flat)
                t_risk = costs_l0(dict(r), size_risk) if is_l0 else costs_l1(dict(r), size_risk)
                flat_total += t_flat['net_gain_eur']
                risk_total += t_risk['net_gain_eur']
                flat_capital += size_flat
                risk_capital += size_risk
            print(f"\n[{label}] budget rischio {budget_pct:.0%} ({budget_eur}EUR) — "
                  f"{len(rows)} trade con SL noto (skip {skipped_no_sl} senza SL calcolabile)")
            print(f"  Flat {flat_size}EUR/trade:    P&L netto totale {flat_total:+.2f}EUR "
                  f"| capitale impegnato cumulato {flat_capital:.0f}EUR")
            print(f"  Risk-parity ({budget_pct:.0%}): P&L netto totale {risk_total:+.2f}EUR "
                  f"| capitale impegnato cumulato {risk_capital:.0f}EUR "
                  f"| size media {risk_capital/len(rows) if rows else 0:.0f}EUR")
            results.setdefault(label, {})[f'{budget_pct:.0%}'] = {
                'n_trades': len(rows), 'flat_net_eur': round(flat_total, 2),
                'risk_parity_net_eur': round(risk_total, 2),
                'flat_capital_eur': round(flat_capital, 2), 'risk_capital_eur': round(risk_capital, 2),
            }
    return results


# ─────────────────────────────────────────────────────────────────────────
# Esperimento 2 — Filtro Macro-Regime come veto sui nuovi ingressi
# ─────────────────────────────────────────────────────────────────────────

def build_benchmark_regime():
    db = PriceDatabase()
    best = None
    for tk in BENCHMARK_CANDIDATES:
        hist = db.get_frozen_ohlcv(tk, DEFAULT_FROZEN_BATCH)
        if not hist.empty and len(hist) >= 220 and (best is None or len(hist) > len(best[1])):
            best = (tk, hist)
    if best is None:
        raise RuntimeError("Nessun benchmark disponibile tra " + str(BENCHMARK_CANDIDATES))
    ticker, hist = best
    close = hist['Close'].astype(float)
    analyzer = ETFTechnicalAnalyzer(famiglia='equity_sviluppati')  # solo per _ema/_sma/calculate_regime, generici
    ema20 = analyzer._ema(close, 20)
    sma50 = analyzer._sma(close, 50)
    regime_by_date = {}
    for i in range(len(close)):
        e = float(ema20.iloc[i]) if pd.notna(ema20.iloc[i]) else None
        s = float(sma50.iloc[i]) if pd.notna(sma50.iloc[i]) else None
        regime_by_date[close.index[i].date().isoformat()] = (analyzer.calculate_regime(e, s) == 'BULL')
    n_bull = sum(regime_by_date.values())
    print(f"Benchmark macro scelto: {ticker} ({len(hist)}gg storico, {n_bull}/{len(regime_by_date)} "
          f"giorni BULL = {100*n_bull/len(regime_by_date):.1f}%)")
    return ticker, regime_by_date


def metrics_block(trades, label):
    is_t, oos_t = split_is_oos(trades)

    def agg(ts):
        closed = [t for t in ts if t['status'] == 'closed']
        if not closed:
            return {'n': 0}
        net = [costs_l1(dict(t), 10000)['net_pct_gain'] if 'entry_buy_count' in t or '_close_full' in t
               else costs_l0(dict(t), 10000)['net_pct_gain'] for t in closed]
        wins = [g for g in net if g > 0]
        losses = [g for g in net if g <= 0]
        pf = round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else None
        wr = round(100 * len(wins) / len(net), 1) if net else None
        return {'n': len(closed), 'win_rate_pct': wr, 'profit_factor': pf,
                'avg_net_pct': round(sum(net) / len(net), 2) if net else None}

    is_m, oos_m = agg(is_t), agg(oos_t)
    print(f"[{label}] IS:  N={is_m.get('n')} WR={is_m.get('win_rate_pct')}% "
          f"PF={is_m.get('profit_factor')} avg%={is_m.get('avg_net_pct')}")
    print(f"[{label}] OOS: N={oos_m.get('n')} WR={oos_m.get('win_rate_pct')}% "
          f"PF={oos_m.get('profit_factor')} avg%={oos_m.get('avg_net_pct')}")
    return {'IS': is_m, 'OOS': oos_m}


def experiment_2_macro_veto(candb_trades_base, candl0_trades_base):
    print("\n" + "=" * 78)
    print("ESPERIMENTO 2 — Filtro Macro-Regime come veto sui nuovi ingressi")
    print("=" * 78)
    benchmark_ticker, regime_by_date = build_benchmark_regime()

    print("\n--- smart_6_macd (CANDIDATE_MODEL_B) — SENZA veto (baseline) ---")
    base_b = metrics_block(candb_trades_base, 'senza veto')
    print("\n--- smart_6_macd (CANDIDATE_MODEL_B) — CON veto macro ---")
    candb_veto = build_candidate_b_trades(veto_regime=regime_by_date)
    veto_b = metrics_block(candb_veto, 'con veto')

    print("\n--- CANDIDATE_MODEL_L0 — SENZA veto (baseline) ---")
    base_l0 = metrics_block(candl0_trades_base, 'senza veto')
    print("\n--- CANDIDATE_MODEL_L0 — CON veto macro ---")
    candl0_veto = build_candidate_l0_trades(veto_regime=regime_by_date)
    veto_l0 = metrics_block(candl0_veto, 'con veto')

    return {
        'benchmark_ticker': benchmark_ticker,
        'smart_6_macd': {'senza_veto': base_b, 'con_veto': veto_b},
        'candidate_l0': {'senza_veto': base_l0, 'con_veto': veto_l0},
    }


# ─────────────────────────────────────────────────────────────────────────
# Esperimento 3 — Ranking per Momentum Relativo
# ─────────────────────────────────────────────────────────────────────────

def experiment_3_momentum_ranking(candb_trades):
    print("\n" + "=" * 78)
    print("ESPERIMENTO 3 — Ranking per Momentum Relativo (solo cluster 'core', smart_6_macd)")
    print("=" * 78)

    by_date = {}
    for t in candb_trades:
        by_date.setdefault(t['entry_date'], []).append(t)
    multi_dates = {d: ts for d, ts in by_date.items() if len(ts) > 1}
    print(f"Date totali con >=1 ingresso: {len(by_date)}  |  Date con >1 ingresso simultaneo: {len(multi_dates)}")

    if len(multi_dates) < 5:
        print("Campione insufficiente (<5 date con segnali multipli) per un test di ranking "
              "significativo — risultato onesto: con un gate cosi' selettivo, le occasioni di "
              "scegliere tra piu' candidati nello stesso giorno sono troppo rare per validare "
              "un ranking su questo storico. Non forzo una conclusione statistica.")
        return {'n_multi_signal_dates': len(multi_dates), 'conclusive': False}

    picked_top_net, picked_random_avg_net, all_net = [], [], []
    for d, ts in multi_dates.items():
        scored = []
        for t in ts:
            close_full, hist_index = t['_close_full'], t['_hist_index']
            entry_ts = pd.Timestamp(t['entry_date'])
            try:
                pos = hist_index.get_loc(entry_ts)
            except KeyError:
                continue
            if pos < 60:
                continue
            mom60 = (close_full.iloc[pos] - close_full.iloc[pos - 60]) / close_full.iloc[pos - 60]
            net = costs_l1(dict(t), 10000)['net_pct_gain']
            scored.append((mom60, net))
            all_net.append(net)
        if not scored:
            continue
        scored.sort(key=lambda x: -x[0])
        picked_top_net.append(scored[0][1])
        picked_random_avg_net.append(sum(n for _, n in scored) / len(scored))

    if not picked_top_net:
        print("Nessuna data utilizzabile (storico <60gg per calcolare il momentum su tutti i candidati).")
        return {'n_multi_signal_dates': len(multi_dates), 'conclusive': False}

    avg_top = sum(picked_top_net) / len(picked_top_net)
    avg_random = sum(picked_random_avg_net) / len(picked_random_avg_net)
    print(f"Su {len(picked_top_net)} date con segnali multipli e storico sufficiente:")
    print(f"  Rendimento medio netto SCEGLIENDO il migliore per momentum a 60gg: {avg_top:+.2f}%")
    print(f"  Rendimento medio netto di TUTTI i candidati di quelle date (baseline): {avg_random:+.2f}%")
    print(f"  Differenza: {avg_top - avg_random:+.2f} punti percentuali")
    return {
        'n_multi_signal_dates': len(multi_dates), 'n_usable_dates': len(picked_top_net),
        'avg_net_pct_top_momentum': round(avg_top, 2), 'avg_net_pct_all_candidates': round(avg_random, 2),
        'conclusive': True,
    }


# ─────────────────────────────────────────────────────────────────────────
# Esperimento 4 — Qualita' dati Volume (diagnostica, no filtro RVOL)
# ─────────────────────────────────────────────────────────────────────────

def experiment_4_volume_quality():
    print("\n" + "=" * 78)
    print("ESPERIMENTO 4 — Qualita' dati Volume nel Golden Dataset (diagnostica)")
    print("=" * 78)

    db = PriceDatabase()
    conn = db._get_connection()
    if not conn:
        print("Nessuna connessione DB.")
        return {}
    cur = conn.cursor()
    cur.execute("""
        SELECT ticker,
               COUNT(*) AS n_rows,
               COUNT(*) FILTER (WHERE volume IS NOT NULL AND volume > 0) AS n_volume_ok
        FROM etf_price_history_frozen
        WHERE freeze_batch = %s AND date >= %s AND date < %s
        GROUP BY ticker
    """, (DEFAULT_FROZEN_BATCH, IS_START.isoformat(), OOS_END.isoformat()))
    rows = cur.fetchall()
    conn.close()

    universe = {item['ticker']: item['famiglia'] for item in load_universe_l1()}
    # includi anche le famiglie escluse da TARGET_FAMILIES (es. monetario) per copertura piena
    import pandas as _pd
    full_df = _pd.read_excel('etf_monitoraggio.xlsx', sheet_name='ETF')
    for _, r in full_df.iterrows():
        tk = str(r.get('Ticker', '')).strip()
        if tk and tk.lower() != 'nan' and tk not in universe:
            universe[tk] = ETFTechnicalAnalyzer.detect_family(str(r.get('Categoria', '')))

    EXCHANGE_SUFFIX = {'.MI': 'Milano', '.PA': 'Parigi', '.DE': 'Xetra', '.AS': 'Amsterdam',
                        '.L': 'Londra', '.SW': 'Swiss'}

    buckets = {'>90%': 0, '50-90%': 0, '<50%': 0, '0% (vuoto/nullo)': 0}
    by_exchange = {}
    coverage_rows = []
    seen = set()
    for ticker, n_rows, n_ok in rows:
        seen.add(ticker)
        pct = (n_ok / n_rows * 100) if n_rows else 0
        coverage_rows.append((ticker, n_rows, n_ok, pct))
        if pct == 0:
            buckets['0% (vuoto/nullo)'] += 1
        elif pct < 50:
            buckets['<50%'] += 1
        elif pct < 90:
            buckets['50-90%'] += 1
        else:
            buckets['>90%'] += 1
        suffix = next((s for s in EXCHANGE_SUFFIX if ticker.endswith(s)), '(altro)')
        exch = EXCHANGE_SUFFIX.get(suffix, '(altro)')
        by_exchange.setdefault(exch, {'ok': 0, 'tot': 0})
        by_exchange[exch]['tot'] += 1
        if pct >= 90:
            by_exchange[exch]['ok'] += 1

    missing_from_frozen = [tk for tk in universe if tk not in seen]

    print(f"Ticker con dati nel batch congelato: {len(coverage_rows)} / {len(universe)} nell'universo Excel "
          f"({len(missing_from_frozen)} assenti dal batch)")
    print("\nDistribuzione copertura Volume (non-nullo, >0) su 2023-08-05..2026-08-05:")
    for b, n in buckets.items():
        print(f"  {b:20s}: {n:4d} ticker")

    print("\nCopertura >=90% per borsa (suffisso ticker):")
    for exch, d in sorted(by_exchange.items(), key=lambda kv: -kv[1]['tot']):
        pct = 100 * d['ok'] / d['tot'] if d['tot'] else 0
        print(f"  {exch:12s}: {d['ok']:3d}/{d['tot']:3d} ticker con copertura>=90% ({pct:.0f}%)")

    n_good = buckets['>90%']
    total = len(coverage_rows)
    verdict = ("RACCOMANDAZIONE: la copertura e' sufficiente per costruire un filtro RVOL "
               "affidabile sulla maggioranza dell'universo." if total and n_good / total >= 0.7 else
               "RACCOMANDAZIONE: copertura Volume INSUFFICIENTE su una quota rilevante dell'universo — "
               "sconsiglio di investire tempo in un filtro RVOL prima di risolvere la qualita' dati a monte "
               "(probabile causa: yfinance non riporta volumi affidabili per molte borse europee minori).")
    print(f"\n{verdict}")

    return {
        'n_ticker_in_universe': len(universe), 'n_ticker_with_frozen_data': len(coverage_rows),
        'n_missing_from_frozen': len(missing_from_frozen),
        'coverage_buckets': buckets, 'coverage_by_exchange': by_exchange,
        'pct_good_coverage': round(100 * n_good / total, 1) if total else 0,
    }


# ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--volume-only', action='store_true')
    parser.add_argument('--smoke', action='store_true', help='smoke test rapido su dati gia'' caricati')
    args = parser.parse_args()

    if args.volume_only:
        result = {'experiment_4_volume': experiment_4_volume_quality()}
        with open('data/backtest_advanced_pillars_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        return

    print("Costruzione trade set di base (native_7, smart_6_macd, CANDIDATE_MODEL_L0)...")
    native7_trades = build_native7_trades()
    print(f"  native_7: {len(native7_trades)} trade totali (IS+OOS)")
    candb_trades = build_candidate_b_trades()
    print(f"  smart_6_macd: {len(candb_trades)} trade totali (IS+OOS)")
    candl0_trades = build_candidate_l0_trades()
    print(f"  CANDIDATE_MODEL_L0: {len(candl0_trades)} trade totali (IS+OOS)")

    result = {}
    result['experiment_1_sizing'] = experiment_1_position_sizing(native7_trades, candb_trades, candl0_trades)
    result['experiment_2_macro_veto'] = experiment_2_macro_veto(candb_trades, candl0_trades)
    result['experiment_3_momentum'] = experiment_3_momentum_ranking(candb_trades)
    result['experiment_4_volume'] = experiment_4_volume_quality()

    def _clean(t):
        return {k: v for k, v in t.items() if not k.startswith('_')}
    result['_meta'] = {
        'native7_n': len(native7_trades), 'candb_n': len(candb_trades), 'candl0_n': len(candl0_trades),
        'generated_at': datetime.now().isoformat(),
    }

    with open('data/backtest_advanced_pillars_result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    print("\nSalvato in data/backtest_advanced_pillars_result.json")


if __name__ == '__main__':
    main()
