"""
directa_exit.py — Modello di uscita FEDELE all'esecuzione reale su Directa.

## Perche' esiste (item 15 della roadmap post-lockdown, deciso 2026-09-03)

Tutti i backtest (`backtest_l0_v2.py`, `backtest_l1.py`, gli sweep) e tutti gli
Shadow Monitor usano finora un modello di uscita "pulito":

    esce al primo tra  Close <= SL_trailing  oppure  Close >= TP_fisso,
    con fill esatto a quel prezzo.

Ma su Directa (conto cash, niente OCO) non funziona cosi'. C'e' **un solo ordine
di vendita attivo alla volta** — di default lo Stop. Avvicinandosi al TP,
`order_pricing.compute_order_prices()` **stringe lo Stop verso il prezzo corrente**
(entro il 3% dal TP -> prezzo*0.985; entro 1.5% -> prezzo*0.99; buffer piu' largo
per strumenti volatili) e lo **ratchetta** (non scende mai piu', finche' la
posizione resta aperta). L'uscita reale avviene quando il prezzo tocca lo **Stop
effettivo** = `max(SL_trailing_ufficiale, ratchet_di_avvicinamento_al_TP)`,
ricalcolato ogni giorno. Il TP puro non e' quasi mai un fill pulito: e' solo
l'ancora che tira su lo Stop.

Effetto **bidirezionale**, non un semplice "haircut" dell'1%:
  - vincitore che corre OLTRE il TP  -> il modello Directa cattura DI PIU'
    (lo Stop trailing lo segue su, nessun tetto rigido al target)
  - vincitore che tocca il TP e poi ritraccia -> cattura ~1% IN MENO
Netto ambiguo -> va misurato. Prior: il candidato "ratchet piu' aggressivo"
del 2026-08-19 perdeva -7% in-sample -> aspettarsi che il modello fedele faccia
sembrare i candidati PEGGIORI, non migliori. E' il punto: se l'esecuzione reale
e' peggiore, vogliamo saperlo.

## Scelta di modellazione

"Cavalca lo Stop stretto" (realistico, ~1% di giveback, tiene l'upside sui
runner) — NON "assumi uno switch manuale perfetto a un Limite esattamente al TP".
Coerente con la filosofia "nessun automatismo" del resto del sistema (l'utente
tocca SL/TP a mano su Directa, il codice non vende mai da solo).

## Rilevamento sul Close, non intraday

Come ogni backtest esistente e come il monitor reale: si valuta **una volta al
giorno sul Close**, non su High/Low. Questo isola il cambio di modello di uscita
come unica variabile rispetto al modello pulito.

## Broker con OCO (Webank ecc.)

Se `broker` supporta Stop+Limite in parallelo (`order_pricing.OCO_CAPABLE_BROKERS`)
il TP esegue da solo come Limite pulito -> in quel caso il modello coincide con
quello "pulito" (primo tra SL e TP, fill esatto). Oggi tutte le nuove posizioni e
tutti gli Shadow Monitor sono Directa, ma il ramo e' gestito per correttezza.
"""
from datetime import datetime, date
from typing import Optional, Dict

import pandas as pd

from order_pricing import compute_order_prices, OCO_CAPABLE_BROKERS


def _l0_sl_tp(analyzer, entry_price: float, current_price: float):
    sl = analyzer.calculate_sl_suggerito_l0(entry_price, current_price).get('sl_suggerito')
    tp = analyzer.calculate_tp_suggerito_l0(entry_price, current_price).get('tp_suggerito')
    return sl, tp


def _l1_sl_tp(analyzer, entry_price: float, current_price: float,
              ema20_today: Optional[float], ema20_series: Optional[pd.Series]):
    sl = analyzer.calculate_sl_suggerito_l1(entry_price, current_price, ema20_today).get('sl_suggerito')
    sg = analyzer.calculate_stop_gain_dynamic(entry_price, current_price, ema20_series, analyzer.p)
    if sg.get('trigger'):
        tp = current_price  # target dinamico gia' raggiunto -> l'ancora e' il prezzo di oggi
    else:
        tp = entry_price * (1 + sg.get('target_pct', 0.0))
    return sl, tp


def directa_stop_today(analyzer, entry_price: float, current_price: float,
                       level: str = 'L0', *,
                       ema20_today: Optional[float] = None,
                       ema20_series: Optional[pd.Series] = None,
                       prev_tp_stop_max: Optional[float] = None,
                       sl_initial_pct: Optional[float] = None,
                       atr_pct: Optional[float] = None,
                       broker: str = 'Directa') -> Dict:
    """Un solo giorno: lo Stop effettivo che sarebbe attivo su Directa oggi, e se il
    Close di oggi lo tocca.

    Primitiva incrementale — gli Shadow Monitor la chiamano ogni giorno passando il
    `tp_proximity_stop_max` persistito nel giro precedente come `prev_tp_stop_max`.

    Ritorna dict:
      sl_suggerito / tp_suggerito : valori "ufficiali" della formula
      effective_stop              : lo Stop realmente attivo = max(sl, ratchet)
      tp_proximity_stop_max       : il nuovo floor del ratchet da persistere
      tightened                   : True se lo Stop mostrato e' quello tattico
      hit                         : True se Close <= effective_stop  (uscita reale)
      exit_reason                 : STOP_LOSS | STOP_TRAIL_PROFIT | STOP_TP_RATCHET |
                                    TP_OCO | None
    """
    if sl_initial_pct is None:
        sl_initial_pct = analyzer.p.get('sl_initial_pct')

    if level == 'L1':
        sl, tp = _l1_sl_tp(analyzer, entry_price, current_price, ema20_today, ema20_series)
    else:
        sl, tp = _l0_sl_tp(analyzer, entry_price, current_price)

    op = compute_order_prices(
        current_price, sl, tp, broker,
        previous_tightened_stop=prev_tp_stop_max,
        sl_initial_pct=sl_initial_pct,
        atr_pct=atr_pct,
    )
    effective_stop = op.get('prezzo_stop')
    parallel_ok = op.get('parallel_ok', False)

    hit = False
    reason = None

    if parallel_ok:
        # Broker OCO: Stop e Limite in parallelo -> il TP esegue da solo, fill pulito.
        sl_hit = effective_stop is not None and current_price <= effective_stop
        tp_hit = tp is not None and current_price >= tp
        if tp_hit and not sl_hit:
            hit, reason = True, 'TP_OCO'
        elif sl_hit:
            hit = True
            reason = 'STOP_LOSS' if effective_stop < entry_price else 'STOP_TRAIL_PROFIT'
    else:
        # Directa: un solo ordine, lo Stop effettivo (con ratchet di avvicinamento al TP).
        if effective_stop is not None and current_price <= effective_stop:
            hit = True
            if op.get('tightened'):
                reason = 'STOP_TP_RATCHET'       # stop stretto per il TP, prezzo ritracciato dentro
            elif effective_stop >= entry_price:
                reason = 'STOP_TRAIL_PROFIT'     # trailing/pareggio sopra il carico -> uscita in gain
            else:
                reason = 'STOP_LOSS'             # stop sotto il carico -> perdita

    return {
        'sl_suggerito': sl,
        'tp_suggerito': tp,
        'effective_stop': effective_stop,
        'prezzo_limite_stop': op.get('prezzo_limite_stop'),
        'tp_proximity_stop_max': op.get('tp_proximity_stop_max'),
        'tightened': op.get('tightened', False),
        'parallel_ok': parallel_ok,
        'hit': hit,
        'exit_reason': reason,
    }


def simulate_directa_exit(analyzer, close_full: pd.Series, hist_index,
                          entry_pos: int, level: str = 'L0', *,
                          high_full: Optional[pd.Series] = None,
                          low_full: Optional[pd.Series] = None,
                          sl_initial_pct: Optional[float] = None,
                          atr_pct: Optional[float] = None,
                          broker: str = 'Directa') -> Dict:
    """Walk-forward dall'ingresso alla fine della serie, replicando lo Stop effettivo
    Directa giorno per giorno (Close-based). Per i backtest.

    Args:
      close_full  : serie Close INTERA del ticker (index = hist_index), non solo da
                    dopo l'ingresso — serve il warm-up per EMA20 (L1) / ATR.
      entry_pos   : posizione intera in hist_index del giorno di ingresso. Il prezzo
                    di carico e' close_full.iloc[entry_pos]; l'uscita si valuta dal
                    giorno DOPO.
      high_full/low_full : se forniti, l'ATR14 per-strumento viene ricalcolato ogni
                    giorno (come fa il monitor reale). Altrimenti si usa
                    sl_initial_pct di famiglia come proxy di volatilita'.

    Ritorna dict:
      exit_pos    : posizione in hist_index dell'uscita, o None se ancora aperta
      exit_date   : ISO date dell'uscita, o None
      exit_price  : Close del giorno di uscita (o ultimo Close se ancora aperta)
      exit_reason : vedi directa_stop_today, o None se ancora aperta
      status      : 'closed' | 'open'
      gross_pct_gain
      days_held   : giorni di calendario
      max_effective_stop : ultimo floor del ratchet (diagnostica)
    """
    entry_price = float(close_full.iloc[entry_pos])
    entry_date = hist_index[entry_pos].date()
    n = len(close_full)

    tp_stop_max = None
    last_diag = None

    for pos in range(entry_pos + 1, n):
        close_today = float(close_full.iloc[pos])

        ema20_today = None
        ema20_series = None
        if level == 'L1':
            ema20_series = analyzer._ema(close_full.iloc[:pos + 1], 20).tail(10)
            ema20_today = float(ema20_series.iloc[-1])

        day_atr_pct = atr_pct
        if day_atr_pct is None and high_full is not None and low_full is not None:
            atr_norm = analyzer._calculate_atr_normalized(
                high_full.iloc[:pos + 1], low_full.iloc[:pos + 1], close_full.iloc[:pos + 1])
            if atr_norm is not None:
                day_atr_pct = round(atr_norm * 100, 2)

        d = directa_stop_today(
            analyzer, entry_price, close_today, level,
            ema20_today=ema20_today, ema20_series=ema20_series,
            prev_tp_stop_max=tp_stop_max,
            sl_initial_pct=sl_initial_pct, atr_pct=day_atr_pct, broker=broker,
        )
        if d['tp_proximity_stop_max'] is not None:
            tp_stop_max = d['tp_proximity_stop_max']
        last_diag = d

        if d['hit']:
            exit_date = hist_index[pos].date()
            return {
                'exit_pos': pos,
                'exit_date': exit_date.isoformat(),
                'exit_price': close_today,
                'exit_reason': d['exit_reason'],
                'status': 'closed',
                'gross_pct_gain': round((close_today / entry_price - 1) * 100, 3),
                'days_held': (exit_date - entry_date).days,
                'max_effective_stop': tp_stop_max,
            }

    last_price = float(close_full.iloc[-1])
    return {
        'exit_pos': None,
        'exit_date': None,
        'exit_price': last_price,
        'exit_reason': None,
        'status': 'open',
        'gross_pct_gain': round((last_price / entry_price - 1) * 100, 3),
        'days_held': (hist_index[-1].date() - entry_date).days,
        'max_effective_stop': tp_stop_max,
    }


def check_shadow_exit_directa(db, analyzer, open_pos: dict, isin: str, level: str,
                              today, add_log=None, min_hist: int = 30) -> Optional[Dict]:
    """Per gli Shadow Monitor: ricalcola l'uscita col modello Directa-fedele (item 15),
    in modo STATELESS — nessuna colonna extra su etf_shadow_positions.

    Fetcha l'OHLC da ~45gg prima dell'ingresso a oggi, rigioca lo Stop effettivo Directa
    (max SL ufficiale / ratchet di avvicinamento al TP) giorno per giorno via
    simulate_directa_exit(), e se la posizione risulta chiusa chiude la riga in
    etf_shadow_positions con data / prezzo / % REALI dell'uscita. exit_reason viene
    mappato a 'SL'/'TP' (per segno di P&L) per non rompere get_shadow_digest_stats /
    get_last_shadow_sl_exit / il gate cooldown, che filtrano su quei due valori.

    Ritorna il dict di simulate_directa_exit (+ 'exit_reason_mapped') se ha chiuso,
    altrimenti None (la posizione resta aperta).

    `analyzer`: gia' costruito dal chiamante, con i suoi eventuali override di parametri.
    `level`: 'L0' o 'L1' — decide quali funzioni SL/TP reali usare.
    """
    entry_date = open_pos['entry_date']
    if isinstance(entry_date, str):
        entry_date = datetime.fromisoformat(entry_date).date()
    elif hasattr(entry_date, 'date') and not isinstance(entry_date, date):
        entry_date = entry_date.date()

    days = (today - entry_date).days + 45
    hist = db.get_ohlc_by_isin(isin, days=min(max(days, 60), 400))
    if hist is None or hist.empty or len(hist) < min_hist:
        return None

    close_full = hist['Close'].astype(float)
    has_ohlc = 'High' in hist.columns and 'Low' in hist.columns
    high_full = hist['High'].astype(float) if has_ohlc else None
    low_full = hist['Low'].astype(float) if has_ohlc else None

    idx_dates = list(hist.index.date) if hasattr(hist.index, 'date') else \
        [d.date() if hasattr(d, 'date') else d for d in hist.index]
    entry_pos = next((i for i, d in enumerate(idx_dates) if d >= entry_date), None)
    if entry_pos is None or entry_pos >= len(close_full) - 1:
        return None  # ingresso troppo recente o fuori dallo storico disponibile

    res = simulate_directa_exit(
        analyzer, close_full, hist.index, entry_pos, level,
        high_full=high_full, low_full=low_full,
        sl_initial_pct=analyzer.p.get('sl_initial_pct'),
    )
    if res['status'] != 'closed':
        return None

    mapped = 'SL' if res['gross_pct_gain'] <= 0 else 'TP'
    db.close_shadow_position(open_pos['id'], res['exit_date'], res['exit_price'],
                             mapped, res['gross_pct_gain'])
    res['exit_reason_mapped'] = mapped
    if add_log:
        add_log(f"    [directa-exit] {isin} {level} | {mapped} ({res['exit_reason']}) | "
                f"{res['gross_pct_gain']:+.2f}% | {res['exit_date']}")
    return res
