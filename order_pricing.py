"""
order_pricing.py — Traduce SL/TP suggeriti (i valori teorici calcolati da
technical_analysis.py) in ordini piazzabili su Directa.

Directa non ha un ordine "Take Profit": lo Stop di vendita accetta solo un
trigger "Prezzo Stop ≤ X" (verso il basso) — per catturare un target al
rialzo serve un normale ordine LIMITE (nessun trigger, un solo prezzo). Lo
Stop stesso è sempre una coppia Prezzo Stop + Prezzo Limite (il secondo con
un margine sotto il primo, per garantire l'esecuzione anche in caso di gap).
Vedi CLAUDE.md, sezione "Esecuzione ordini reali su Directa" (2026-08-08).

A differenza delle formule in technical_analysis.py (tutte backtestate,
determinano QUANDO uscire), le costanti qui sotto sono un'euristica di sola
esecuzione, decisa con l'utente il 2026-08-08 — non cambiano mai il segnale
di uscita, solo come viene formulato l'ordine e quanto si stringe lo Stop
quando il prezzo si avvicina al target.
"""
from typing import Optional, Dict

# Margine tra Prezzo Stop e Prezzo Limite di un ordine Stop — dà spazio
# all'esecuzione anche se il prezzo scende oltre il trigger in un solo scatto.
STOP_LIMIT_GAP_PCT = 0.01  # 1%

# Zona di avvicinamento al TP: sotto queste soglie si stringe lo Stop verso il
# prezzo corrente invece di lasciarlo al valore "ufficiale" (pensato per il
# medio periodo, non per blindare un target specifico che si sta per toccare).
TP_PROXIMITY_TIGHT_PCT = 0.03        # <3% dal TP → Stop a prezzo_attuale * 0.985
TP_PROXIMITY_VERY_TIGHT_PCT = 0.015  # <1.5% dal TP → Stop a prezzo_attuale * 0.99


def compute_order_prices(current_price: Optional[float], sl_suggerito: Optional[float],
                          tp_suggerito: Optional[float]) -> Dict:
    """
    Ritorna i prezzi da inserire su Directa:
      - prezzo_stop / prezzo_limite_stop: la coppia per l'ordine Stop (SL)
      - prezzo_limite_tp: il prezzo per il semplice ordine Limite (TP)
      - tightened: True se lo Stop è stato stretto per l'avvicinamento al TP
    """
    result = {
        'prezzo_stop': None, 'prezzo_limite_stop': None,
        'prezzo_limite_tp': None, 'tightened': False,
    }
    if not current_price:
        return result

    stop = float(sl_suggerito) if sl_suggerito else None

    if sl_suggerito and tp_suggerito and tp_suggerito > current_price:
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
