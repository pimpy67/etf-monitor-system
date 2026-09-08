"""
backtest_l1_exit.py — Analisi dell'USCITA L1 (item 17 della roadmap post-lockdown).

## Perche' esiste

L'analisi del 2026-09-01 ha concluso che il problema strutturale di L1 NON e' il gate
d'ingresso (allargarlo e' fragile o inerte) ma l'USCITA: nel 78-83% dei casi si esce per
stop loss. Lo Stop attuale (`calculate_sl_suggerito_l1`) e' EMA20-based e molto reattivo
(un solo Close sotto l'EMA20 = fuori).

L'uscita e' AGNOSTICA all'ingresso -> si testano le varianti di SL su un POOL AMPIO di
ingressi (ogni incrocio rialzista dell'EMA20, migliaia di eventi, nessun gate) per potenza
statistica su "quale SL", scollegata dal gate d'ingresso. Poi si applica la migliore.

⚠️ Gira col MODELLO DI USCITA DIRECTA-FEDELE (item 15, `simulate_directa_exit`) — testare
uno Stop piu' largo contro il vecchio modello "fill esatto al TP" darebbe la risposta
sbagliata (era il motivo per cui l'item 15 veniva prima).

## Pool di ingressi

Ogni giorno in cui il Close incrocia l'EMA20 dal basso (`close[t] > ema20[t]` e
`close[t-1] <= ema20[t-1]`), su tutte le famiglie tradabili, dal `--start`. Un solo
ingresso alla volta per ticker (niente sovrapposizioni): il successivo si valuta solo dopo
l'uscita del precedente.

## Varianti SL testate (vedi directa_exit.simulate_directa_exit sl_variant)

  baseline        SL ufficiale EMA20-based (calculate_sl_suggerito_l1) — riferimento
  ema20_wide_N%   SL = EMA20 * (1 - N/100), sempre (no stringimento a 0.99 in profitto)
  atr_k           SL = max(Close da ingresso) - k*ATR14  (chandelier, scala con la vol.)
  ema20_atr_k     SL = EMA20 - k*ATR14
  confirm2        SL ufficiale, ma esce solo dopo 2 Close consecutivi sotto lo stop
  weekly          SL ufficiale, ricalcolato 1 volta ogni 5 giorni di trading (meno rumore)

Uso (dentro il container):
  python3 backtest_l1_exit.py --start 2023-08-05 --split-date 2025-08-05
  python3 backtest_l1_exit.py --limit 20              # smoke test veloce
"""
import sys
sys.path.insert(0, '/app')

import argparse
import io
from contextlib import redirect_stdout
from datetime import datetime

import pandas as pd

from technical_analysis import ETFTechnicalAnalyzer
from database import PriceDatabase
from directa_exit import simulate_directa_exit
from backtest_l1 import (
    load_universe, FrozenDataFetcher, DEFAULT_FROZEN_BATCH,
    DIRECTA_FEE_BUY, DIRECTA_FEE_SELL, TAX_RATE,
)

DEFAULT_SPLIT = '2025-08-05'

VARIANTS = {
    'baseline':       None,
    'ema20_wide_3%':  {'mode': 'ema20_wide', 'buffer': 0.03},
    'ema20_wide_4%':  {'mode': 'ema20_wide', 'buffer': 0.04},
    'ema20_wide_5%':  {'mode': 'ema20_wide', 'buffer': 0.05},
    'ema20_wide_6%':  {'mode': 'ema20_wide', 'buffer': 0.06},
    'atr_2.0':        {'mode': 'atr', 'k': 2.0},
    'atr_2.5':        {'mode': 'atr', 'k': 2.5},
    'atr_3.0':        {'mode': 'atr', 'k': 3.0},
    'ema20_atr_1.0':  {'mode': 'ema20_atr', 'k': 1.0},
    'ema20_atr_1.5':  {'mode': 'ema20_atr', 'k': 1.5},
    'ema20_atr_2.0':  {'mode': 'ema20_atr', 'k': 2.0},
    'confirm2':       {'confirm_days': 2},
    'weekly':         {'recompute_days': 5},
}


def find_entries(close, ema20, test_dates_set):
    """Indici (posizionali) dei giorni in cui il Close incrocia l'EMA20 dal basso e
    la data e' nella finestra di test."""
    entries = []
    c = close.values
    e = ema20.values
    for i in range(1, len(c)):
        if pd.isna(e[i]) or pd.isna(e[i - 1]):
            continue
        if c[i - 1] <= e[i - 1] and c[i] > e[i] and close.index[i] in test_dates_set:
            entries.append(i)
    return entries


def net(trade_gross_pct, position_size, closed):
    gross_eur = position_size * (trade_gross_pct / 100.0)
    fees = DIRECTA_FEE_BUY + (DIRECTA_FEE_SELL if closed else 0)
    after = gross_eur - fees
    tax = TAX_RATE * after if after > 0 else 0.0
    return after - tax


def summarize(trades, position_size, label):
    closed = [t for t in trades if t['status'] == 'closed']
    if not closed:
        print(f"  {label}: 0 trade chiusi ({len(trades)} totali)")
        return None
    nets = [net(t['gross_pct_gain'], position_size, True) for t in closed]
    wins = sum(x for x in nets if x > 0)
    loss = -sum(x for x in nets if x < 0)
    wr = 100 * sum(1 for x in nets if x > 0) / len(nets)
    pf = (wins / loss) if loss > 0 else float('inf')
    durs = [t['days_held'] for t in closed]
    reasons = {}
    for t in closed:
        reasons[t['exit_reason']] = reasons.get(t['exit_reason'], 0) + 1
    print(f"  {label:16s} N={len(closed):4d} (aperti {len(trades) - len(closed):3d})  "
          f"WR={wr:4.1f}%  PF={pf:4.2f}  avg_net={sum(nets) / len(nets):+7.2f}EUR  "
          f"dur={sum(durs) / len(durs):5.1f}gg  P&L={sum(nets):+10.1f}EUR")
    print(f"       exit: {reasons}")
    return {'n': len(closed), 'wr': round(wr, 1), 'pf': round(pf, 2),
            'avg_net_eur': round(sum(nets) / len(nets), 2), 'pnl_eur': round(sum(nets), 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', default='2023-08-05')
    ap.add_argument('--split-date', default=DEFAULT_SPLIT)
    ap.add_argument('--frozen-batch', default=DEFAULT_FROZEN_BATCH)
    ap.add_argument('--position-size', type=float, default=10000)
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--variants', default=None,
                    help='sottoinsieme separato da virgola (default: tutte)')
    args = ap.parse_args()

    start = datetime.strptime(args.start, '%Y-%m-%d').date()
    split = datetime.strptime(args.split_date, '%Y-%m-%d').date()
    variants = ({k: VARIANTS[k] for k in args.variants.split(',')} if args.variants
                else VARIANTS)

    print(f"ANALISI USCITA L1 (item 17) — modello uscita Directa-fedele")
    print(f"Pool ingressi: incrocio rialzista EMA20, tutte le famiglie, dal {start}")
    print(f"Split IN/OUT: {split}  |  size {args.position_size:.0f}EUR/trade  |  batch {args.frozen_batch}")
    print(f"Varianti: {list(variants)}")
    print("=" * 92)

    universe = load_universe()
    if args.limit:
        universe = universe[:args.limit]
    fetcher = FrozenDataFetcher(args.frozen_batch)
    db = PriceDatabase()

    # trades[variant] = list
    trades = {k: [] for k in variants}
    n_entries_total = 0
    n_ok = 0

    for i, item in enumerate(universe, 1):
        ticker, famiglia = item['ticker'], item['famiglia']
        hist = fetcher.get_historical_data(ticker, days=1300)
        if hist.empty or len(hist) < 220:
            continue
        has_ohlc = all(c in hist.columns for c in ['Open', 'High', 'Low'])
        close_full = hist['Close'].astype(float)
        high_full = hist['High'].astype(float) if has_ohlc else None
        low_full = hist['Low'].astype(float) if has_ohlc else None

        analyzer = ETFTechnicalAnalyzer(famiglia=famiglia)
        ema20_full = analyzer._ema(close_full, 20)
        atr_abs_full = None
        if has_ohlc:
            atr_abs_full = analyzer._calculate_atr(high_full, low_full, close_full, 14)
        test_set = set(d for d in hist.index if d.date() >= start)
        entry_positions = find_entries(close_full, ema20_full, test_set)
        if not entry_positions:
            continue
        n_ok += 1
        n_entries_total += len(entry_positions)

        quiet = io.StringIO()
        with redirect_stdout(quiet):
            for vname, vcfg in variants.items():
                # un ingresso alla volta: salta i cross che cadono mentre si e' ancora dentro
                busy_until = -1
                for ep in entry_positions:
                    if ep <= busy_until:
                        continue
                    res = simulate_directa_exit(
                        analyzer, close_full, hist.index, ep, 'L1',
                        high_full=None, low_full=None,
                        sl_initial_pct=analyzer.p.get('sl_initial_pct'),
                        sl_variant=vcfg,
                        ema20_precomp=ema20_full, atr_abs_precomp=atr_abs_full,
                    )
                    entry_date = hist.index[ep].date()
                    trades[vname].append({
                        'ticker': ticker, 'famiglia': famiglia,
                        'entry_date': entry_date.isoformat(),
                        'in_sample': entry_date < split,
                        'status': res['status'],
                        'gross_pct_gain': res['gross_pct_gain'],
                        'exit_reason': res['exit_reason'],
                        'days_held': res['days_held'],
                    })
                    busy_until = res['exit_pos'] if res['exit_pos'] is not None else len(close_full)
        if i % 25 == 0:
            print(f"  ... {i}/{len(universe)} ticker  ({n_entries_total} ingressi finora)")

    print(f"\nTicker con ingressi: {n_ok}  |  ingressi/variante: ~{n_entries_total}")
    print("=" * 92)

    for scope in ('TUTTO', 'IN', 'OUT'):
        print(f"\n######## {scope} ########")
        for vname in variants:
            tl = trades[vname]
            if scope == 'IN':
                tl = [t for t in tl if t['in_sample']]
            elif scope == 'OUT':
                tl = [t for t in tl if not t['in_sample']]
            summarize(tl, args.position_size, vname)


if __name__ == '__main__':
    main()
