"""
backtest_market_breadth_sweep.py — Sensitivity analysis sulle soglie di isteresi
della breadth (backtest_market_breadth.py, 2026-08-20), richiesta esplicitamente
prima di dare qualunque fiducia al risultato del primo giro (config unica 80%/65%,
N=7/10 — troppo piccolo e mai testato per robustezza sui bordi).

OTTIMIZZAZIONE (necessaria per rendere una griglia di soglie fattibile su 1 vCPU):
il costo dominante di backtest_market_breadth.py e' suggest_level() chiamato ogni
giorno per ogni ticker — ma quella chiamata NON dipende dalla soglia di breadth
(la breadth decide solo QUALE ramo di ingresso e' permesso quel giorno, non cosa
suggest_level() risponde). Quindi: si calcolano UNA VOLTA SOLA, per ogni ticker/
giorno, due flag booleani indipendenti dalla soglia (native_7_ok, six_macd_ok) —
poi ogni combinazione della griglia si limita a rileggere questi flag e a
ri-applicare l'isteresi con soglie diverse, senza mai richiamare suggest_level().
Nessuna differenza di logica rispetto a backtest_market_breadth.py: stesso motore,
stessa definizione di ingresso, solo il costo ricorrente rimosso dal loop.

Uso (dentro il container):
  python3 backtest_market_breadth_sweep.py
"""
import sys
sys.path.insert(0, '/app')

import json
import time
from contextlib import redirect_stdout
import io

from backtest_l1 import apply_costs_and_tax, DEFAULT_FROZEN_BATCH
from optimize_hyperparameters import extra_metrics
from backtest_market_breadth import (
    load_all_data, compute_breadth_timeline, apply_hysteresis,
    CORE_FAMILIES, TRAIN_START, TRAIN_END, TEST_END, NORMAL_SIZE,
)
from technical_analysis import ETFTechnicalAnalyzer

# Griglia: exit sempre almeno 10pp sotto enter (isteresi minima significativa,
# altrimenti soglie troppo vicine flippano quasi ad ogni giorno — stesso principio
# giu' documentato nello script principale).
ENTER_CANDIDATES = [0.70, 0.75, 0.80, 0.85]
EXIT_CANDIDATES = [0.55, 0.60, 0.65, 0.70]
MIN_GAP = 0.10


def precompute_entry_flags(analyzer, close_full, high_full, low_full, hist_index, all_dates, precomputed_full):
    """UNA volta per ticker, su TUTTO il range (IS+OOS insieme): per ogni giorno,
    native_7_ok (suggested_level==1) e six_macd_ok (buy_count==6 + macd_ok +
    fondamenta, indipendente dalla breadth — quella si applica dopo in fase di
    simulazione). Nessuna threshold-dipendenza qui: e' il costo che si paga una
    volta sola e si riusa per ogni combinazione della griglia."""
    flags = {}
    quiet = io.StringIO()
    with redirect_stdout(quiet):
        for d in all_dates:
            pos = hist_index.get_loc(d)
            close_slice = close_full.iloc[:pos + 1]
            high_slice = high_full.iloc[:pos + 1] if high_full is not None else None
            low_slice = low_full.iloc[:pos + 1] if low_full is not None else None
            close_today = float(close_slice.iloc[-1])

            precomputed_today = {k: v.iloc[:pos + 1] for k, v in precomputed_full.items()
                                  if k not in ('macd_histogram', 'macd_ok')}
            precomputed_today['macd'] = {'histogram': precomputed_full['macd_histogram'].iloc[:pos + 1]}
            result = analyzer.suggest_level(close_slice, current_level=3,
                                             high=high_slice, low=low_slice,
                                             precomputed=precomputed_today)
            native_7_ok = result.get('suggested_level') == 1
            c = result.get('conditions', {})
            bc = result.get('buy_count', 0)
            sma50_v = c.get('sma50_current')
            fondamenta_ok = (not c.get('kill_switch', False)) and c.get('regime_ok', False) \
                and (sma50_v is not None and close_today >= sma50_v)
            six_macd_ok = bool(bc == 6 and c.get('macd_ok') and fondamenta_ok)

            flags[d.strftime('%Y-%m-%d')] = (native_7_ok, six_macd_ok)
    return flags


def simulate_from_flags(analyzer, close_full, ema20_full, hist_index, test_dates, flags, regime_by_date):
    """Ri-simulazione VELOCE: nessuna chiamata a suggest_level(), solo lookup dei
    flag pre-calcolati + regime del giorno. Uscita identica allo script principale
    (SL/TP giornalieri su Close via calculate_sl_suggerito_l1/calculate_stop_gain_dynamic).
    ema20_full e' la serie EMA20 precalcolata una volta sola sull'intera storia
    (indicatore causale — tagliarla da qui da' lo stesso valore che ricalcolarla da
    zero su una finestra troncata, stesso principio gia' documentato altrove)."""
    holding = False
    entry_price = entry_date = entry_mode = None
    trades = []

    for d in test_dates:
        pos = hist_index.get_loc(d)
        close_today = float(close_full.iloc[pos])
        ds = d.strftime('%Y-%m-%d')

        if not holding:
            native_7_ok, six_macd_ok = flags.get(ds, (False, False))
            mode = None
            if native_7_ok:
                mode = 'native_7'
            elif six_macd_ok and regime_by_date.get(ds, 'NORMAL') == 'SUPER_BULL':
                mode = 'breadth_6_macd'
            if mode:
                holding = True
                entry_price = close_today
                entry_date = d.date().isoformat()
                entry_mode = mode
            continue
        else:
            ema20_today = float(ema20_full.iloc[pos])
            sl_data = analyzer.calculate_sl_suggerito_l1(entry_price, close_today, ema20_today)
            sl = sl_data.get('sl_suggerito')

            ema20_series = ema20_full.iloc[:pos + 1].tail(10)
            sg_data = analyzer.calculate_stop_gain_dynamic(entry_price, close_today, ema20_series, analyzer.p)
            tp_trigger = bool(sg_data.get('trigger'))

            sl_hit = sl is not None and close_today <= sl

            if sl_hit or tp_trigger:
                exit_reason = 'SL' if sl_hit else 'TP'
                gross_pct = round((close_today / entry_price - 1) * 100, 3)
                trades.append({
                    'entry_date': entry_date, 'entry_price': entry_price,
                    'exit_date': d.date().isoformat(), 'exit_price': close_today,
                    'status': 'closed', 'gross_pct_gain': gross_pct,
                    'exit_reason': exit_reason, 'entry_mode': entry_mode,
                })
                holding = False
                entry_price = entry_date = entry_mode = None

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


def aggregate_flat(all_trades, size=NORMAL_SIZE):
    priced = [apply_costs_and_tax(dict(t), size) for t in all_trades]
    closed = [t for t in priced if t['status'] == 'closed']
    net_gains = [t['net_pct_gain'] for t in closed]
    net_eur = [t['net_gain_eur'] for t in closed]
    agg = {
        'n_trades_closed': len(closed),
        'win_rate_pct': round(100 * sum(1 for g in net_gains if g > 0) / len(net_gains), 1) if net_gains else None,
        'total_net_eur': round(sum(net_eur), 2) if net_eur else 0,
        'trades': priced,
    }
    agg.update(extra_metrics(agg))
    return agg


def main():
    t0 = time.time()
    print("=" * 78)
    print("SWEEP SOGLIE ISTERESI BREADTH — verifica robustezza del primo risultato")
    print("=" * 78)

    items = load_all_data(DEFAULT_FROZEN_BATCH)
    core_items = [it for it in items if it['famiglia'] in CORE_FAMILIES]
    print(f"Cluster 'core': {len(core_items)} ticker\n")

    print("Calcolo breadth cross-sezionale (una volta sola, indipendente dalle soglie)...")
    breadth, _ = compute_breadth_timeline(items)

    print("Precalcolo flag di ingresso per ticker (il costo pesante, pagato UNA volta)...")
    t1 = time.time()
    for entry in core_items:
        analyzer = ETFTechnicalAnalyzer(famiglia=entry['famiglia'])
        analyzer.p = dict(entry['baseline_p'])
        all_dates = [d for d in entry['hist_index'] if TRAIN_START <= d.date() < TEST_END]
        entry['test_dates'] = all_dates
        entry['analyzer'] = analyzer
        entry['flags'] = precompute_entry_flags(
            analyzer, entry['close_full'], entry['high_full'], entry['low_full'],
            entry['hist_index'], all_dates, entry['precomputed'])
    print(f"Flag precalcolati in {time.time()-t1:.0f}s\n")

    combos = [(e, x) for e in ENTER_CANDIDATES for x in EXIT_CANDIDATES if e - x >= MIN_GAP - 1e-9]
    print(f"Griglia: {len(combos)} combinazioni (enter/exit)\n")

    rows = []
    for enter_th, exit_th in combos:
        t2 = time.time()
        regime_series = apply_hysteresis(breadth, enter_th, exit_th)
        regime_by_date = {d.strftime('%Y-%m-%d'): r for d, r in zip(regime_series.index, regime_series.values)}

        row = {'enter': enter_th, 'exit': exit_th}
        for label, start, end in [('is', TRAIN_START, TRAIN_END), ('oos', TRAIN_END, TEST_END)]:
            all_trades = []
            for entry in core_items:
                window_dates = [d for d in entry['test_dates'] if start <= d.date() < end]
                if not window_dates:
                    continue
                trades = simulate_from_flags(entry['analyzer'], entry['close_full'],
                                              entry['precomputed']['ema20'], entry['hist_index'],
                                              window_dates, entry['flags'], regime_by_date)
                all_trades.extend(trades)
            agg = aggregate_flat(all_trades)
            row[f'{label}_n'] = agg['n_trades_closed']
            row[f'{label}_wr'] = agg['win_rate_pct']
            row[f'{label}_pf'] = agg.get('profit_factor')
            row[f'{label}_pnl'] = agg['total_net_eur']

        # % giorni SUPER_BULL per questa combinazione (contesto — quanto e' "raro" il regime)
        oos_mask = [(d.date() >= TRAIN_END and d.date() < TEST_END) for d in regime_series.index]
        oos_regime = regime_series[oos_mask]
        row['oos_superbull_pct'] = round(100 * (oos_regime == 'SUPER_BULL').sum() / len(oos_regime), 1) if len(oos_regime) else None

        rows.append(row)
        print(f"  enter={enter_th:.2f} exit={exit_th:.2f} ({time.time()-t2:.0f}s) | "
              f"IS: N={row['is_n']:3d} PF={row['is_pf']} WR={row['is_wr']}% P&L={row['is_pnl']}EUR | "
              f"OOS: N={row['oos_n']:3d} PF={row['oos_pf']} WR={row['oos_wr']}% P&L={row['oos_pnl']}EUR | "
              f"SUPER_BULL {row['oos_superbull_pct']}% gg OOS")

    with open('data/backtest_market_breadth_sweep_result.json', 'w', encoding='utf-8') as f:
        json.dump({'combos': rows}, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nCompletato in {time.time()-t0:.0f}s totali. Risultato: data/backtest_market_breadth_sweep_result.json")


if __name__ == '__main__':
    main()
