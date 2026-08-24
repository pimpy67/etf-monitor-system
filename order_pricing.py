"""
order_pricing.py — Traduce SL/TP suggeriti (i valori teorici calcolati da
technical_analysis.py) in ordini piazzabili sul broker reale.

Nessun broker retail comune ha un ordine "Take Profit" nativo sulle azioni/ETF:
uno Stop di vendita accetta solo un trigger "Prezzo Stop ≤ X" (verso il basso)
— per catturare un target al rialzo serve un normale ordine LIMITE (nessun
trigger, un solo prezzo). Lo Stop stesso è sempre una coppia Prezzo Stop +
Prezzo Limite (il secondo con un margine sotto il primo, per garantire il fill
anche in caso di gap).

IMPORTANTE — il vincolo su Stop+Limite IN PARALLELO è per BROKER, non
universale (verificato in produzione 2026-08-08 su due broker diversi
dell'utente, vedi CLAUDE.md sezione "Esecuzione ordini reali su Directa"):
- **Directa** (conto cash): NON è possibile tenere attivi Stop e Limite in
  parallelo sulle stesse quote — un secondo ordine di vendita per l'intera
  posizione viene rifiutato ("quantità superiore alla disponibilità in
  portafoglio o titolo non vendibile allo scoperto"), perché lo Stop già
  impegna tutte le quote. `prezzo_limite_tp` è quindi un TARGET DI
  RIFERIMENTO da tenere d'occhio: quando il prezzo si avvicina, l'azione
  reale è cancellare lo Stop e piazzare il Limite (o vendere) in quel
  momento — da qui l'euristica di stringimento sotto.
- **Webank** (e altri broker con OCO nativo): supporta Stop Loss e Take
  Profit contemporaneamente attivi — `prezzo_stop`/`prezzo_limite_stop` e
  `prezzo_limite_tp` si piazzano entrambi da subito come ordini separati,
  nessuna euristica di stringimento necessaria (il TP eseguirà da solo).

A differenza delle formule in technical_analysis.py (tutte backtestate,
determinano QUANDO uscire), le costanti/l'euristica qui sotto riguardano solo
COME si formula l'ordine su un broker senza OCO — non cambiano mai il segnale
di uscita.
"""
from typing import Optional, Dict

# Broker noti che supportano Stop Loss e Take Profit attivi in parallelo
# (verosimilmente OCO) — tutti gli altri (incl. valori sconosciuti/vuoti)
# sono trattati come Directa: un solo ordine di vendita alla volta.
OCO_CAPABLE_BROKERS = {'Webank'}

# Margine tra Prezzo Stop e Prezzo Limite di un ordine Stop — dà spazio
# all'esecuzione anche se il prezzo scende oltre il trigger in un solo scatto.
STOP_LIMIT_GAP_PCT = 0.01  # 1%

# Margine allargato per strumenti ad alta volatilità (stesso criterio wide-tier
# usato sotto per il buffer di avvicinamento al TP — ATR14 o, in fallback,
# sl_initial_pct di famiglia). Motivato da un caso reale (2026-08-24): su PHAG
# (Argento, ATR14 ~2,87%) l'1% standard tra Trigger e Limite (~0,53€ su 53€)
# lascia meno margine reale di quanto sembri, perché l'escursione giornaliera
# tipica dello strumento è già dello stesso ordine di grandezza del gap stesso
# — un salto veloce può bucare l'intera forbice senza eseguire l'ordine. Su un
# ETF calmo come MEU (equity Europa) lo stesso 1% è ampiamente sufficiente
# perché il movimento tipico è molto più piccolo del gap.
STOP_LIMIT_GAP_PCT_WIDE = 0.02  # 2%

# Zona di avvicinamento al TP (solo broker senza OCO): sotto queste soglie si
# stringe lo Stop verso il prezzo corrente invece di lasciarlo al valore
# "ufficiale" (pensato per il medio periodo, non per blindare un target
# specifico che si sta per toccare).
TP_PROXIMITY_TIGHT_PCT = 0.03        # <3% dal TP → fase "allerta"
TP_PROXIMITY_VERY_TIGHT_PCT = 0.015  # <1.5% dal TP → fase "critica"

# Buffer standard (asset a volatilità giornaliera contenuta, es. equity/bond ETF)
TP_PROXIMITY_CRITICA_BUFFER = 0.99    # fase critica → Stop a prezzo_attuale * 0.99
TP_PROXIMITY_ALLERTA_BUFFER = 0.985   # fase allerta → Stop a prezzo_attuale * 0.985

# Buffer allargato per asset ad alta volatilità intraday (commodities/ETC, leva,
# crypto — sl_initial_pct >= WIDE_TIER_SL_INITIAL_PCT nel YAML di famiglia):
# stringere all'1% un asset come l'Argento rischia di far eseguire l'ordine su
# un micro-spike negativo intraday un attimo prima che tocchi il TP vero.
WIDE_TIER_SL_INITIAL_PCT = 0.07
TP_PROXIMITY_CRITICA_BUFFER_WIDE = 0.985  # fase critica, asset volatili → 1.5%
TP_PROXIMITY_ALLERTA_BUFFER_WIDE = 0.98   # fase allerta, asset volatili → 2.0%

# Soglia ATR14 normalizzato (% del prezzo) sopra la quale un singolo STRUMENTO
# (non famiglia) è trattato come ad alta volatilità — bypassa sl_initial_pct
# quando disponibile. Motivato da un caso reale (2026-08-22): PHAG/WisdomTree
# Physical Silver è in famiglia oro_metalli_preziosi (sl_initial_pct=5%, sotto
# la soglia sopra) ma ha ATR14 misurato 2,87% — la famiglia raggruppa Oro e
# Argento sotto un unico sl_initial_pct, ma l'Argento è storicamente molto più
# volatile e un buffer stretto (1%) rischiava di far scattare lo Stop su un
# normale movimento intraday. L'ATR è per-strumento, quindi cattura questo
# caso senza dover spostare l'intera famiglia (che include anche l'Oro, molto
# meno volatile) su un profilo di rischio diverso.
WIDE_TIER_ATR_PCT = 2.0


def compute_order_prices(current_price: Optional[float], sl_suggerito: Optional[float],
                          tp_suggerito: Optional[float], broker: str = 'Directa',
                          previous_tightened_stop: Optional[float] = None,
                          sl_initial_pct: Optional[float] = None,
                          atr_pct: Optional[float] = None) -> Dict:
    """
    Ritorna i prezzi da inserire sul broker:
      - prezzo_stop / prezzo_limite_stop: la coppia per l'ordine Stop (SL)
      - prezzo_limite_tp: il prezzo per il semplice ordine Limite (TP)
      - tightened: True se lo Stop mostrato è quello tattico di avvicinamento al
        TP (calcolato oggi o ereditato dal ratchet), non il valore "ufficiale"
        (solo broker senza OCO — sempre False se parallel_ok)
      - parallel_ok: True se Stop e Limite possono restare attivi insieme su
        questo broker (piazzabili entrambi da subito)
      - tp_proximity_stop_max: il nuovo massimo storico dello Stop tattico da
        persistere (ratchet) — None se il meccanismo non si applica (parallel_ok,
        niente TP, o mai stato in prossimità). Il chiamante lo salva nel DB e lo
        ripassa come `previous_tightened_stop` al giro successivo.

    previous_tightened_stop: il valore persistito dal giro precedente — il nuovo
      Stop tattico non scende mai sotto questo (ratchet: una volta stretto per
      l'avvicinamento al TP, non si allarga più, anche se il prezzo si allontana
      di nuovo dal target prima di toccarlo).
    sl_initial_pct: sl_initial_pct della famiglia (da etf_families.yaml) — sceglie
      il buffer standard o quello allargato per asset volatili. Usato solo come
      fallback quando atr_pct non è disponibile. None → standard.
    atr_pct: ATR14 normalizzato dello STRUMENTO specifico, in % del prezzo (non
      della famiglia) — se presente ha priorità su sl_initial_pct per scegliere
      il buffer, perché misura la volatilità reale di quel singolo ETF/ETC
      invece del proxy di famiglia (che può raggruppare strumenti a volatilità
      molto diversa, es. Oro e Argento nella stessa famiglia). None → fallback
      su sl_initial_pct.
    """
    parallel_ok = (broker or 'Directa') in OCO_CAPABLE_BROKERS
    result = {
        'prezzo_stop': None, 'prezzo_limite_stop': None,
        'prezzo_limite_tp': None, 'tightened': False, 'parallel_ok': parallel_ok,
        'tp_proximity_stop_max': None,
    }
    if not current_price:
        return result

    stop = float(sl_suggerito) if sl_suggerito else None

    # Classificazione volatilità dello strumento — usata sia per il buffer di
    # avvicinamento al TP sia per il gap Trigger/Limite (vedi STOP_LIMIT_GAP_PCT_WIDE).
    if atr_pct is not None:
        is_wide_tier = atr_pct >= WIDE_TIER_ATR_PCT
    else:
        is_wide_tier = sl_initial_pct is not None and sl_initial_pct >= WIDE_TIER_SL_INITIAL_PCT

    if not parallel_ok and stop and tp_suggerito:
        # Nota: nessun requisito tp_suggerito > current_price — se il prezzo ha
        # già raggiunto o superato il TP, dist_to_tp_pct sotto è <= 0, quindi
        # rientra comunque nella fascia "critica" e stringe al massimo. Questo è
        # voluto: il sistema non chiude mai la posizione da solo (vedi
        # monitor.py::_update_portfolio_l0_suggerito/_update_portfolio_l1_suggerito),
        # quindi lo Stop deve continuare a proteggere il target finché l'utente
        # non conferma manualmente l'uscita reale su Directa.
        buffer_critica = TP_PROXIMITY_CRITICA_BUFFER_WIDE if is_wide_tier else TP_PROXIMITY_CRITICA_BUFFER
        buffer_allerta = TP_PROXIMITY_ALLERTA_BUFFER_WIDE if is_wide_tier else TP_PROXIMITY_ALLERTA_BUFFER

        dist_to_tp_pct = (tp_suggerito - current_price) / current_price
        tightened_candidate = None
        if dist_to_tp_pct < TP_PROXIMITY_VERY_TIGHT_PCT:
            tightened_candidate = current_price * buffer_critica
        elif dist_to_tp_pct < TP_PROXIMITY_TIGHT_PCT:
            tightened_candidate = current_price * buffer_allerta

        # RATCHET: lo Stop tattico è il massimo tra il candidato di oggi e quello
        # già suggerito nei giorni precedenti — non torna mai indietro finché la
        # posizione resta aperta e il TP non è stato toccato.
        candidates = [c for c in (tightened_candidate, previous_tightened_stop) if c is not None]
        if candidates:
            floor = max(candidates)
            result['tp_proximity_stop_max'] = round(floor, 4)
            if floor > stop:
                stop = floor
                result['tightened'] = True

    if stop:
        gap_pct = STOP_LIMIT_GAP_PCT_WIDE if is_wide_tier else STOP_LIMIT_GAP_PCT
        result['prezzo_stop'] = round(stop, 4)
        result['prezzo_limite_stop'] = round(stop * (1 - gap_pct), 4)
    if tp_suggerito:
        result['prezzo_limite_tp'] = round(float(tp_suggerito), 4)

    return result
