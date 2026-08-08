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

# Zona di avvicinamento al TP (solo broker senza OCO): sotto queste soglie si
# stringe lo Stop verso il prezzo corrente invece di lasciarlo al valore
# "ufficiale" (pensato per il medio periodo, non per blindare un target
# specifico che si sta per toccare).
TP_PROXIMITY_TIGHT_PCT = 0.03        # <3% dal TP → Stop a prezzo_attuale * 0.985
TP_PROXIMITY_VERY_TIGHT_PCT = 0.015  # <1.5% dal TP → Stop a prezzo_attuale * 0.99


def compute_order_prices(current_price: Optional[float], sl_suggerito: Optional[float],
                          tp_suggerito: Optional[float], broker: str = 'Directa') -> Dict:
    """
    Ritorna i prezzi da inserire sul broker:
      - prezzo_stop / prezzo_limite_stop: la coppia per l'ordine Stop (SL)
      - prezzo_limite_tp: il prezzo per il semplice ordine Limite (TP)
      - tightened: True se lo Stop è stato stretto per l'avvicinamento al TP
        (solo broker senza OCO — sempre False se parallel_ok)
      - parallel_ok: True se Stop e Limite possono restare attivi insieme su
        questo broker (piazzabili entrambi da subito)
    """
    parallel_ok = (broker or 'Directa') in OCO_CAPABLE_BROKERS
    result = {
        'prezzo_stop': None, 'prezzo_limite_stop': None,
        'prezzo_limite_tp': None, 'tightened': False, 'parallel_ok': parallel_ok,
    }
    if not current_price:
        return result

    stop = float(sl_suggerito) if sl_suggerito else None

    if not parallel_ok and sl_suggerito and tp_suggerito and tp_suggerito > current_price:
        dist_to_tp_pct = (tp_suggerito - current_price) / current_price
        tightened_candidate = None
        if dist_to_tp_pct < TP_PROXIMITY_VERY_TIGHT_PCT:
            tightened_candidate = current_price * 0.99
        elif dist_to_tp_pct < TP_PROXIMITY_TIGHT_PCT:
            tightened_candidate = current_price * 0.985

        if tightened_candidate is not None and tightened_candidate > stop:
            stop = tightened_candidate
            result['tightened'] = True

    if stop:
        result['prezzo_stop'] = round(stop, 4)
        result['prezzo_limite_stop'] = round(stop * (1 - STOP_LIMIT_GAP_PCT), 4)
    if tp_suggerito:
        result['prezzo_limite_tp'] = round(float(tp_suggerito), 4)

    return result
