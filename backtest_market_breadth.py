"""
backtest_market_breadth.py — Test "terza via" Market Breadth / Super-Bull Market
(proposta utente 2026-08-20, vedi CLAUDE.md "Stato Attuale & Roadmap L1" per il contesto
degli altri candidati gia' certificati con lo stesso schema IS/OOS).

IDEA: quando la % di ETF nell'universo con EMA20>SMA50 (breadth) supera una soglia alta,
il sistema entra in regime "SUPER_BULL" — in quella finestra si allenta il gate L1 da
7/7 a 6/7+MACD-obbligatorio (stesso identico smart_6_macd gia' backtestato il 2026-08-05,
MAI reso condizionale a un regime esterno prima d'ora) e/o si aumenta la size per trade.
Fuori da SUPER_BULL, tutto resta 7/7 nativo — zero modifiche al comportamento attuale.

Motore di simulazione: RIUSA backtest_l1.py::load_universe/apply_costs_and_tax e
optimize_hyperparameters.py::precompute_ticker/extra_metrics — nessuna logica di
indicatori duplicata. L'unica parte nuova e' simulate_breadth_gated() (variante di
backtest_l1.py::simulate() con soglia di ingresso condizionale al regime del giorno,
che backtest_l1.py::simulate() non supporta nativamente) e il calcolo della breadth
stessa (cross-sezionale sull'intero universo, mai fatto prima in questo repo).

Universo:
  - BREADTH (regime macro): TUTTE le 13 famiglie tradabili (stesso universo di
    backtest_l1.py, ~230 ticker) — un segnale di mercato deve guardare tutto il mercato.
  - INGRESSI (dove si applica il gate allentato): solo cluster 'core' (5 famiglie:
    equity_sviluppati, oro_metalli_preziosi, mercati_emergenti, settoriali_growth,
    metalli_industriali) — stesso cluster di CANDIDATE_MODEL_B_20260807, l'unico dove
    smart_6_macd produce volume reale (difensivo/speculativo: ~0 trade, vedi CLAUDE.md).

Isteresi: soglia doppia (enter 80% / exit 65%), niente sfarfallio giorno-per-giorno al
bordo — una volta in SUPER_BULL serve scendere sotto la soglia di uscita per tornare
NORMAL. Un solo config testato in questo primo giro (non una grid search) — vedi
NOTE finali per i limiti.

Uso (dentro il container):
  python3 backtest_market_breadth.py
"""
import sys
sys.path.insert(0, '/app')

import json
import time
from datetime import datetime
from contextlib import redirect_stdout
import io

import pandas as pd

from technical_analysis import ETFTechnicalAnalyzer
from database import PriceDatabase
from backtest_l1 import load_universe, apply_costs_and_tax, DEFAULT_FROZEN_BATCH
from optimize_hyperparameters import precompute_ticker, extra_metrics

CORE_FAMILIES = {'equity_sviluppati', 'oro_metalli_preziosi', 'mercati_emergenti',
                  'settoriali_growth', 'metalli_industriali'}

TRAIN_START = datetime(2023, 8, 5).date()
TRAIN_END = datetime(2025, 8, 5).date()
TEST_END = datetime(2026, 8, 5).date()

ENTER_THRESHOLD = 0.80
EXIT_THRESHOLD = 0.65

NORMAL_SIZE = 10000.0
SUPERBULL_SIZE = 15000.0


def load_all_data(freeze_batch, min_rows=220):
    """Carica TUTTO l'universo tradabile (13 famiglie) con indicatori precalcolati —
    serve sia per la breadth (tutte) sia per gli ingressi (solo sottoinsieme 'core')."""
    db = PriceDatabase()
    universe = load_universe()
    items = []
    skipped = []
    for u in universe:
        ticker, famiglia = u['ticker'], u['famiglia']
        hist = db.get_frozen_ohlcv(ticker, freeze_batch)
        if hist.empty or len(hist) < min_rows:
            skipped.append(ticker)
            continue
        has_ohlc = all(c in hist.columns for c in ['Open', 'High', 'Low'])
        close_full = hist['Close'].astype(float)
        high_full = hist['High'].astype(float) if has_ohlc else None
        low_full = hist['Low'].astype(float) if has_ohlc else None

        analyzer_tmp = ETFTechnicalAnalyzer(famiglia=famiglia)
        precomputed = precompute_ticker(analyzer_tmp, close_full, high_full, low_full)

        items.append({
            'ticker': ticker, 'famiglia': famiglia,
            'close_full': close_full, 'high_full': high_full, 'low_full': low_full,
            'hist_index': hist.index, 'precomputed': precomputed,
            'baseline_p': dict(analyzer_tmp.p),
        })
    print(f"Caricati {len(items)}/{len(universe)} ticker ({len(skipped)} scartati per storico insufficiente)")
    return items


def compute_breadth_timeline(items):
    """% di ETF (sull'intero universo tradabile) con EMA20>SMA50 per ogni data —
    cross-sezionale, mai fatto prima in questo repo (tutti gli sweep precedenti erano
    per-ticker walk-forward, non aggregati sul mercato)."""
    frames = []
    for it in items:
        ema20 = it['precomputed']['ema20']
        sma50 = it['precomputed']['sma50']
        s = (ema20 > sma50).rename(it['ticker'])
        frames.append(s)
    wide = pd.concat(frames, axis=1)
    breadth = wide.mean(axis=1, skipna=True)
    n_available = wide.notna().sum(axis=1)
    return breadth, n_available


def apply_hysteresis(breadth: pd.Series, enter_th: float, exit_th: float) -> pd.Series:
    """Isteresi a doppia soglia: SUPER_BULL una volta innescato resta tale finche' la
    breadth non scende sotto exit_th — evita di flippare regime giorno per giorno vicino
    al bordo (stesso principio di days_above_ema, applicato qui al mercato intero)."""
    state = []
    current = 'NORMAL'
    for val in breadth:
        if pd.isna(val):
            state.append(current)
            continue
        if current == 'NORMAL' and val >= enter_th:
            current = 'SUPER_BULL'
        elif current == 'SUPER_BULL' and val < exit_th:
            current = 'NORMAL'
        state.append(current)
    return pd.Series(state, index=breadth.index)


def simulate_breadth_gated(analyzer, close_full, high_full, low_full, hist_index, test_dates,
                            precomputed_full, regime_by_date):
    """Variante di backtest_l1.py::simulate() — stessa logica di uscita (SL/TP giornalieri
    su Close, nessuna regola B/C/E/F), ma ingresso condizionale al regime del giorno:
      - buy_count>=7 + fondamenta (via suggested_level==1, analyzer.p['min_buy_count']=7
        SEMPRE — non viene mai abbassato): ingresso 'native_7', qualunque regime.
      - buy_count==6 + macd_ok + fondamenta, SOLO SE oggi e' SUPER_BULL: ingresso
        'breadth_6_macd'. Fuori da SUPER_BULL questo ramo e' semplicemente non valutato.
    Un solo suggest_level() per giorno (letto per entrambi i rami, come backtest_l1.py fa
    per require_macd) — nessuna doppia simulazione, nessun doppio conteggio."""
    holding = False
    entry_price = None
    entry_date = None
    entry_mode = None
    trades = []

    quiet = io.StringIO()
    with redirect_stdout(quiet):
        for d in test_dates:
            pos = hist_index.get_loc(d)
            close_slice = close_full.iloc[:pos + 1]
            high_slice = high_full.iloc[:pos + 1] if high_full is not None else None
            low_slice = low_full.iloc[:pos + 1] if low_full is not None else None
            close_today = float(close_slice.iloc[-1])

            if not holding:
                precomputed_today = {k: v.iloc[:pos + 1] for k, v in precomputed_full.items()
                                      if k not in ('macd_histogram', 'macd_ok')}
                precomputed_today['macd'] = {'histogram': precomputed_full['macd_histogram'].iloc[:pos + 1]}
                result = analyzer.suggest_level(close_slice, current_level=3,
                                                 high=high_slice, low=low_slice,
                                                 precomputed=precomputed_today)
                mode = None
                if result.get('suggested_level') == 1:
                    mode = 'native_7'
                else:
                    regime_today = regime_by_date.get(d.strftime('%Y-%m-%d'), 'NORMAL')
                    if regime_today == 'SUPER_BULL':
                        c = result.get('conditions', {})
                        bc = result.get('buy_count', 0)
                        sma50_v = c.get('sma50_current')
                        fondamenta_ok = (not c.get('kill_switch', False)) and c.get('regime_ok', False) \
                            and (sma50_v is not None and close_today >= sma50_v)
                        if bc == 6 and c.get('macd_ok') and fondamenta_ok:
                            mode = 'breadth_6_macd'

                if mode:
                    holding = True
                    entry_price = close_today
                    entry_date = d.date().isoformat()
                    entry_mode = mode
                continue
            else:
                ema20_series = analyzer._ema(close_slice, 20).tail(10)
                ema20_today = float(ema20_series.iloc[-1])

                sl_data = analyzer.calculate_sl_suggerito_l1(entry_price, close_today, ema20_today)
                sl = sl_data.get('sl_suggerito')

                sg_data = analyzer.calculate_stop_gain_dynamic(entry_price, close_today, ema20_series, analyzer.p)
                tp = entry_price * (1 + sg_data.get('target_pct', 0.0))

                sl_hit = sl is not None and close_today <= sl
                tp_hit = bool(sg_data.get('trigger'))

                if sl_hit or tp_hit:
                    exit_price = close_today
                    exit_reason = 'SL' if sl_hit else 'TP'
                    gross_pct = round((exit_price / entry_price - 1) * 100, 3)
                    trades.append({
                        'entry_date': entry_date, 'entry_price': entry_price,
                        'exit_date': d.date().isoformat(), 'exit_price': exit_price,
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


def run_window(core_items, regime_by_date, start_date, end_date):
    """Esegue simulate_breadth_gated() su tutti i ticker 'core' nel range dato."""
    results = []
    for entry in core_items:
        analyzer = ETFTechnicalAnalyzer(famiglia=entry['famiglia'])
        analyzer.p = dict(entry['baseline_p'])  # min_buy_count resta 7 (nativo) SEMPRE
        test_dates = [d for d in entry['hist_index'] if start_date <= d.date() < end_date]
        if not test_dates:
            continue
        trades = simulate_breadth_gated(analyzer, entry['close_full'], entry['high_full'],
                                         entry['low_full'], entry['hist_index'], test_dates,
                                         entry['precomputed'], regime_by_date)
        results.append({'ticker': entry['ticker'], 'famiglia': entry['famiglia'], 'trades': trades})
    return results


def aggregate_trades(all_trades, position_size_fn):
    """Come backtest_l1.py::aggregate(), ma la size puo' dipendere dal trade
    (position_size_fn(trade) -> float) invece di essere fissa — serve per la Fase 1
    (sizing dinamico per regime)."""
    priced = []
    for t in all_trades:
        size = position_size_fn(t)
        priced.append(apply_costs_and_tax(dict(t), size))

    closed = [t for t in priced if t['status'] == 'closed']
    net_gains = [t['net_pct_gain'] for t in closed]
    net_eur = [t['net_gain_eur'] for t in closed]

    agg = {
        'n_trades_total': len(priced),
        'n_trades_closed': len(closed),
        'n_trades_open': len(priced) - len(closed),
        'win_rate_pct': round(100 * sum(1 for g in net_gains if g > 0) / len(net_gains), 1) if net_gains else None,
        'avg_net_pct_gain': round(sum(net_gains) / len(net_gains), 2) if net_gains else None,
        'total_net_eur': round(sum(net_eur), 2) if net_eur else 0,
        'trades': priced,
    }
    agg.update(extra_metrics(agg))
    return agg


def main():
    print("=" * 78)
    print("BACKTEST MARKET BREADTH — terza via Super-Bull (2026-08-20)")
    print(f"Isteresi: enter>={ENTER_THRESHOLD:.0%} / exit<{EXIT_THRESHOLD:.0%}  |  "
          f"Gate allentato: 6/7+MACD (smart_6_macd) SOLO durante SUPER_BULL, cluster core")
    print(f"Split IS/OOS: {TRAIN_START}→{TRAIN_END} / {TRAIN_END}→{TEST_END}")
    print("=" * 78)

    t0 = time.time()
    items = load_all_data(DEFAULT_FROZEN_BATCH)
    core_items = [it for it in items if it['famiglia'] in CORE_FAMILIES]
    print(f"Cluster 'core' (dove si testa il gate allentato): {len(core_items)} ticker\n")

    print("Calcolo breadth cross-sezionale (EMA20>SMA50 su tutto l'universo)...")
    breadth, n_available = compute_breadth_timeline(items)
    regime_series = apply_hysteresis(breadth, ENTER_THRESHOLD, EXIT_THRESHOLD)
    regime_by_date = {d.strftime('%Y-%m-%d'): r for d, r in zip(regime_series.index, regime_series.values)}

    # Statistiche descrittive della breadth per le due finestre (sanity check: il
    # regime non deve essere degenere, sempre acceso o sempre spento)
    def window_stats(start, end):
        mask = [(d.date() >= start and d.date() < end) for d in breadth.index]
        b = breadth[mask]
        r = regime_series[mask]
        superbull_days = int((r == 'SUPER_BULL').sum())
        return {
            'n_days': int(len(b)),
            'superbull_days': superbull_days,
            'superbull_pct': round(100 * superbull_days / len(b), 1) if len(b) else 0,
            'breadth_mean': round(float(b.mean()), 3) if len(b) else None,
            'breadth_max': round(float(b.max()), 3) if len(b) else None,
        }

    is_stats = window_stats(TRAIN_START, TRAIN_END)
    oos_stats = window_stats(TRAIN_END, TEST_END)
    print(f"IN-SAMPLE  breadth: {is_stats}")
    print(f"OUT-SAMPLE breadth: {oos_stats}\n")

    print(f"Caricamento+breadth completati in {time.time()-t0:.0f}s — avvio simulazione ingressi...\n")

    report = {'is_stats': is_stats, 'oos_stats': oos_stats, 'windows': {}}

    for label, start, end in [('in_sample', TRAIN_START, TRAIN_END), ('out_of_sample', TRAIN_END, TEST_END)]:
        t1 = time.time()
        results = run_window(core_items, regime_by_date, start, end)
        all_trades = [t for r in results for t in r['trades']]
        native_trades = [t for t in all_trades if t['entry_mode'] == 'native_7']
        breadth_trades = [t for t in all_trades if t['entry_mode'] == 'breadth_6_macd']

        # FASE 2 — effetto del gate allentato, size fissa 10k per isolare la sola variabile "gate"
        flat = lambda t: NORMAL_SIZE
        agg_native_only = aggregate_trades(native_trades, flat)
        agg_combined = aggregate_trades(all_trades, flat)

        # FASE 1 — effetto del sizing dinamico, sullo STESSO set di trade (combined),
        # per isolare la sola variabile "size" tenendo il gate fisso
        def dynamic_size(t):
            r = regime_by_date.get(t['entry_date'], 'NORMAL')
            return SUPERBULL_SIZE if r == 'SUPER_BULL' else NORMAL_SIZE
        agg_combined_dynamic_size = aggregate_trades(all_trades, dynamic_size)

        print(f"--- {label} ({time.time()-t1:.0f}s) ---")
        print(f"  native_7 soltanto      : N={agg_native_only['n_trades_closed']:3d}  "
              f"WR={agg_native_only['win_rate_pct']}%  PF={agg_native_only.get('profit_factor')}  "
              f"P&L={agg_native_only['total_net_eur']}EUR")
        print(f"  + breadth_6_macd (gate): N={agg_combined['n_trades_closed']:3d}  "
              f"WR={agg_combined['win_rate_pct']}%  PF={agg_combined.get('profit_factor')}  "
              f"P&L={agg_combined['total_net_eur']}EUR  ({len(breadth_trades)} trade extra dal gate)")
        print(f"  + sizing dinamico (15k) : N={agg_combined_dynamic_size['n_trades_closed']:3d}  "
              f"WR={agg_combined_dynamic_size['win_rate_pct']}%  "
              f"P&L={agg_combined_dynamic_size['total_net_eur']}EUR "
              f"(vs {agg_combined['total_net_eur']}EUR a size fissa 10k)\n")

        for a in (agg_native_only, agg_combined, agg_combined_dynamic_size):
            a.pop('trades', None)  # tolto dal riepilogo stampato, resta nel JSON sotto

        report['windows'][label] = {
            'native_7_only': agg_native_only,
            'combined_with_breadth_gate': agg_combined,
            'combined_dynamic_sizing': agg_combined_dynamic_size,
            'breadth_extra_trades': breadth_trades,
        }

    with open('data/backtest_market_breadth_result.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nCompletato in {time.time()-t0:.0f}s totali. Risultato: data/backtest_market_breadth_result.json")


if __name__ == '__main__':
    main()
