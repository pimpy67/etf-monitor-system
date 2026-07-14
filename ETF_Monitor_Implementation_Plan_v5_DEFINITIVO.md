# ETF Monitor — Piano di Implementazione v5.0 DEFINITIVO
# Tutte le scelte confermate il 16/07/2026
# Due portafogli: L1 (breve termine) + L0 (medio/lungo termine)

> **Come usare questo file con Claude in VS Code**
> ```bash
> claude
> /load ETF_Monitor_Implementation_Plan_v5_DEFINITIVO.md
> ```
> Prima di produrre codice, Claude leggerà il contesto e ti farà
> le domande tecniche preliminari (sezione 0).
> Tutte le scelte strategiche sono già state prese dal proprietario
> del sistema — NON proporre alternative, implementa esattamente
> quello che è scritto qui.

---

## 0. Domande preliminari — Claude deve chiedere PRIMA di scrivere codice

1. **Stack**: Python / Excel / JavaScript / altro?
2. **File principale**: qual è l'entry point? (es. `main.py`, `monitor.py`)
3. **Dati prezzi**: da dove arrivano EMA20, SMA50, RSI, ADX, EMA10?
4. **Storico disponibile**: quanti giorni per ogni ETF?
5. **Struttura posizioni**: c'è già un oggetto/tabella con prezzo carico,
   data apertura, livello ingresso? Mostrami la struttura attuale.
6. **Trailing stop attuale**: dove vive la logica? (nome file, funzione)
7. **Flag portafoglio**: dove nel codice viene gestito il flag "+ Port."?
   Come funziona adesso?
8. **Email**: come viene inviata adesso? (SMTP, servizio esterno, altro?)
9. **Aggiornamento prezzi**: come avviene alle 18:30? (API, scraping, manuale?)

**NON scrivere codice finché non hai tutte le 9 risposte.**

---

## 1. Architettura generale — due portafogli distinti

```
PORTAFOGLIO L1 — Breve Termine
  Alimentato da: flag "+ Port." su ETF in livello L1
  Obiettivo:     catturare rally brevi con stop gain dinamico
  Holding:       giorni / settimane
  Uscita:        Stop Gain + Stop Loss ibrido + regole F/B/C

PORTAFOGLIO L0 — Medio/Lungo Termine
  Alimentato da: flag "+ Port." su ETF in livello L0
  Obiettivo:     cavalcare recuperi da correzione per mesi
  Holding:       settimane / mesi
  Uscita:        Trailing stop progressivo + regole F/β/α/ε

REGOLA DI INSTRADAMENTO (da implementare nel flag "+ Port."):
  Al momento del click sul flag:
    if etf.livello == "L1" → inserisci in Portafoglio L1
    if etf.livello == "L0" → inserisci in Portafoglio L0
    if etf.livello == "L2" o "L3" → chiedi conferma (non dovrebbe accadere)

NOTA: uno stesso ETF può avere una posizione in L1 e una in L0
      contemporaneamente se è stato acquistato in momenti diversi.
      Le due posizioni sono completamente indipendenti.
```

### 1.1 Struttura posizione aggiornata

```python
position = {
    # Campi esistenti — NON modificare
    "isin":           "LU1681038672",
    "ticker":         "RS2K",
    "nome":           "Amundi IS Russell 2000 UCITS ETF EUR",
    "famiglia":       "equity_sviluppati",
    "entry_price":    373.35,
    "entry_date":     "2026-05-26",
    "quote":          9,

    # Campi nuovi da aggiungere
    "portafoglio":    "L1",        # "L1" o "L0" — determinato dal flag
    "entry_layer":    "L1",        # livello tecnico al momento dell'acquisto
    "entry_quality":  2,           # quality score 0-4 (solo L1)
    "entry_confidence": 0.50,      # 0.50 / 0.75 / 1.00 (solo L1)
    "capital_pct":    0.50,        # % capitale allocato (solo L1)
    "trailing_stop":  381.00,      # aggiornato ogni giorno (entrambi)
    "stop_gain_target": 402.25,    # solo L1, None per L0
    "sl_suggerito":   381.00,      # calcolato ogni giorno — mostrato nel monitor
    "sg_suggerito":   402.25,      # solo L1 — mostrato nel monitor
    "days_in_trade":  51,          # aggiornato ogni giorno
    "add_history":    [],          # aggiunte progressive capital (solo L1)

    # Solo L0
    "days_no_recovery": 0,         # contatore per timeout 45 giorni
    "stallo_counter":   0,         # contatore per alert stallo 20 giorni
}
```

---

## 2. SISTEMA L1 — Portafoglio Breve Termine

### 2.1 Condizioni di ingresso — Opzione 3 (Gate + Quality + Size)

```python
def check_l1_entry_tiered(price, ema20, sma50, rsi, adx,
                           macd_hist, dist_ema20_pct, family_params):
    """
    SCELTA CONFERMATA: Opzione 3
    Gate obbligatorio 2/2 + Quality flessibile 2/4 + Size dinamica
    """

    # ── GATE STRUTTURALE (obbligatorio 2/2) ─────────────────────────────
    gate_a  = price > ema20          # prezzo sopra EMA20
    gate_x  = ema20 > sma50          # regime Bull (EMA20 sopra SMA50)
    gate_ok = gate_a and gate_x

    if not gate_ok:
        return {
            "should_enter": False,
            "confidence":   0.0,
            "gate_ok":      False,
            "quality_score": 0,
            "reason": "Gate KO — prezzo < EMA20 o EMA20 < SMA50",
        }

    # ── QUALITY SCORE (flessibile min 2/4) ──────────────────────────────
    rsi_low  = family_params.get("rsi_in_low",  45)
    rsi_high = family_params.get("rsi_in_high", 70)
    adx_min  = family_params.get("adx_min",     18)

    q_r = rsi_low <= rsi <= rsi_high          # RSI in range famiglia
    q_d = adx >= (adx_min * 0.80)            # ADX con tolleranza -20%
    q_m = macd_hist > 0                       # MACD positivo
    q_p = 0.0 <= dist_ema20_pct <= 2.0       # vicino alla media (non sui picchi)

    quality_score  = int(q_r) + int(q_d) + int(q_m) + int(q_p)
    quality_detail = {"Q_R_rsi": q_r, "Q_D_adx": q_d,
                      "Q_M_macd": q_m, "Q_P_dist": q_p}

    if quality_score < 2:
        return {
            "should_enter":   False,
            "confidence":     0.0,
            "gate_ok":        True,
            "quality_score":  quality_score,
            "quality_detail": quality_detail,
            "reason": f"Quality {quality_score}/4 — minimo 2 richiesto",
        }

    # ── SIZE DA CONFIDENZA ───────────────────────────────────────────────
    confidence = {2: 0.50, 3: 0.75, 4: 1.00}[min(quality_score, 4)]

    return {
        "should_enter":   True,
        "confidence":     confidence,
        "gate_ok":        True,
        "quality_score":  quality_score,
        "quality_detail": quality_detail,
        "reason": f"Ingresso L1 — quality {quality_score}/4 — size {int(confidence*100)}%",
    }
```

### 2.2 Accumulo progressivo se il segnale migliora

```python
def check_position_add(position, current_quality):
    """
    Se la quality migliora dopo entrata parziale → aggiungi capitale.
    Es: entrato a 50% (quality 2), migliora a 3 → aggiungi 25%.
    """
    entry_confidence   = position.get("entry_confidence", 1.0)
    current_confidence = {2: 0.50, 3: 0.75, 4: 1.00}.get(current_quality, 0)

    if current_confidence <= entry_confidence:
        return {"add": False, "reason": "Segnale non migliorato"}

    add_pct = current_confidence - entry_confidence
    return {
        "add":           True,
        "add_pct":       add_pct,
        "new_total_pct": entry_confidence + add_pct,
        "reason": f"Quality {entry_confidence:.0%} → {current_confidence:.0%} — aggiungi {add_pct:.0%}",
    }
```

### 2.3 Stop Loss ibrido L1

```
SCELTA CONFERMATA: Stop Loss ibrido C

Profitto < 2%  → SL largo  = EMA20 − buffer_famiglia
                 (lascia respirare, non uscire sui ritracciamenti normali)

Profitto ≥ 2%  → SL stretto = EMA20 − 1%
                 (proteggi il gain accumulato)

Calcolato ogni giorno per tutti gli ETF in Portafoglio L1.
Mostrato come "SL Suggerito" nel monitor (come adesso).
Inviato nell'email delle 19:00.

Buffer per famiglia (usato quando profitto < 2%):
  equity_sviluppati:   2.0%
  mercati_emergenti:   2.5%
  settoriali_growth:   3.0%
  settoriali_difensivi:1.5%
  bond_governativi:    1.0%
  bond_corp_hy_em:     1.5%
  oro_metalli_preziosi:2.5%
  commodities:         3.0%
  metalli_industriali: 2.5%
  real_estate_reit:    2.0%
  crypto_digital:      5.0%
  leva_single_stock:   4.0%
  private_equity:      1.5%
```

```python
def calculate_sl_suggerito_l1(position, ema20, family_params):
    """
    Calcola SL Suggerito per posizioni L1.
    Mostrato nel monitor come valore aggiornato quotidianamente.
    """
    entry_price  = position["entry_price"]
    current_price = position["prezzo_attuale"]
    profit_pct   = (current_price - entry_price) / entry_price

    buffer = family_params.get("sl_buffer_wide", 0.020)  # default 2%

    if profit_pct < 0.02:
        # Profitto < 2% → SL largo
        sl = ema20 * (1 - buffer)
    else:
        # Profitto ≥ 2% → SL stretto
        sl = ema20 * 0.99

    return round(sl, 4)
```

### 2.4 Stop Gain dinamico L1

```
SCELTA CONFERMATA: Target variabile per famiglia, dal prezzo di carico

Target per famiglia:
  equity_sviluppati:    +4%     floor: +2.0%
  mercati_emergenti:    +5%     floor: +2.5%
  settoriali_growth:    +7%     floor: +3.5%
  settoriali_difensivi: +3%     floor: +1.5%
  bond_governativi:     +2%     floor: +1.0%
  bond_corp_hy_em:      +3%     floor: +1.5%
  oro_metalli_preziosi: +5%     floor: +2.5%
  commodities:          +6%     floor: +3.0%
  metalli_industriali:  +5%     floor: +2.5%
  real_estate_reit:     +4%     floor: +2.0%
  crypto_digital:       +12%    floor: +6.0%
  leva_single_stock:    +15%    floor: +7.5%
  private_equity:       +3%     floor: +1.5%

Trigger alternativo (indipendente dal target %):
  RSI a 5 periodi scende sotto 65 con profitto > 1% → esci comunque

Floor: il target non scende mai sotto il floor (non esci per meno)
Pendenza: il target si abbassa se EMA20 perde pendenza (momentum in calo)
Calcolato ogni giorno per tutti gli ETF in Portafoglio L1.
Mostrato come "SG Suggerito" nel monitor (nuovo campo — come SL Suggerito).
Inviato nell'email delle 19:00.
```

```python
def calculate_sg_suggerito_l1(position, ema20_series, rsi_5, family_params):
    """
    Calcola SG Suggerito per posizioni L1.
    Mostrato nel monitor come valore aggiornato quotidianamente.
    """
    entry_price   = position["entry_price"]
    current_price = position["prezzo_attuale"]
    days_held     = position["days_in_trade"]

    target_max = family_params.get("sg_target_pct",  0.05)
    target_min = family_params.get("sg_floor_pct",   0.025)
    decay      = family_params.get("sg_decay_day",   0.002)
    slope_win  = family_params.get("sg_slope_window",5)
    slope_mult = family_params.get("sg_slope_mult",  0.8)
    rsi_exit   = family_params.get("sg_rsi_exit",    65)

    # Decadimento temporale
    time_decay = days_held * decay

    # Pendenza EMA20
    if len(ema20_series) >= slope_win:
        recent    = ema20_series[-slope_win:]
        slope_pct = (recent[-1] - recent[0]) / recent[0] / slope_win
    else:
        slope_pct = 0.0

    # Target dinamico
    target_pct   = max(min(target_max - time_decay + slope_pct * slope_mult,
                           target_max), target_min)
    target_price = entry_price * (1 + target_pct)

    # Trigger uscita
    profit_pct   = (current_price - entry_price) / entry_price
    should_exit  = False
    trigger      = None

    if current_price >= target_price:
        should_exit = True
        trigger     = "target_raggiunto"

    if rsi_5 < rsi_exit and profit_pct > 0.01:
        should_exit = True
        trigger     = "rsi_momentum_esaurito"

    return {
        "sg_suggerito": round(target_price, 4),
        "target_pct":   round(target_pct * 100, 2),
        "should_exit":  should_exit,
        "trigger":      trigger,
    }
```

### 2.5 Regole di uscita L1 — ordine di priorità

```
SCELTA CONFERMATA:

Priorità 1 — F Kill Switch:
  Calo giornaliero ≤ -3% → uscita immediata totale
  Vale per TUTTI gli ETF in L1, senza eccezioni

Priorità 2 — Stop Loss ibrido (sostituisce regola A):
  Prezzo ≤ SL Suggerito (calcolato con formula ibrida sezione 2.3)
  → uscita totale

Priorità 3 — B Trailing (EMA10 < EMA20):
  La media veloce scende sotto quella lenta → trend invertito
  → uscita totale

Priorità 4 — C Stanchezza:
  RSI era ≥ 70, scende sotto 70 → rally esaurito
  → uscita totale (solo equity/commodity, non bond)

Priorità 5 — Stop Gain dinamico:
  Prezzo ≥ SG Suggerito O RSI(5) < 65 con profitto > 1%
  → uscita totale — prendi il guadagno

Priorità 6 — E ADX Debole (opzionale):
  ADX < 18 AND prezzo < EMA20
  → uscita (solo equity/commodity)

ELIMINATA — D Regola 90%/10% XEON:
  Non applicabile con Banco BPM (costo fiscale + operativo)
  Non ha senso per L1 breve termine con Stop Gain attivo
```

```python
def check_exit_l1(position, market_data, family_params):
    """
    Unico punto di controllo uscite per Portafoglio L1.
    Rispetta l'ordine di priorità confermato.
    """
    price      = market_data["close"]
    daily_chg  = market_data["daily_change_pct"]
    ema10      = market_data["ema10"]
    ema20      = market_data["ema20"]
    rsi        = market_data["rsi_14"]
    rsi_5      = market_data["rsi_5"]
    adx        = market_data["adx"]
    rsi_prev   = market_data.get("rsi_14_prev", rsi)

    famiglia   = position["famiglia"]
    entry      = position["entry_price"]
    profit_pct = (price - entry) / entry

    # P1 — Kill Switch
    if daily_chg <= -0.03:
        return {"exit": True, "reason": "F_kill_switch", "priority": 1}

    # P2 — Stop Loss ibrido
    sl = calculate_sl_suggerito_l1(position, ema20, family_params)
    if price <= sl:
        return {"exit": True, "reason": "SL_ibrido", "priority": 2,
                "sl_level": sl}

    # P3 — Trailing EMA10 < EMA20
    if ema10 < ema20:
        return {"exit": True, "reason": "B_trailing_ema10", "priority": 3}

    # P4 — Stanchezza RSI (non bond)
    bond_families = ["bond_governativi","bond_corp_hy_em","inflation_linked",
                     "monetario_liquidita"]
    if famiglia not in bond_families:
        if rsi_prev >= 70 and rsi < 70:
            return {"exit": True, "reason": "C_stanchezza_rsi", "priority": 4}

    # P5 — Stop Gain dinamico
    sg = calculate_sg_suggerito_l1(position, market_data["ema20_series"],
                                    rsi_5, family_params)
    if sg["should_exit"]:
        return {"exit": True, "reason": f"SG_{sg['trigger']}", "priority": 5,
                "sg_level": sg["sg_suggerito"], "profit_pct": profit_pct}

    # P6 — ADX debole (opzionale, solo equity/commodity)
    equity_commodity = ["equity_sviluppati","mercati_emergenti",
                        "settoriali_growth","settoriali_difensivi",
                        "commodities","metalli_industriali"]
    if famiglia in equity_commodity:
        if adx < 18 and price < ema20:
            return {"exit": True, "reason": "E_adx_debole", "priority": 6}

    return {"exit": False, "reason": None}
```

---

## 3. SISTEMA L0 — Portafoglio Medio/Lungo Termine

### 3.1 Condizioni di ingresso L0 — parametri pragmatici

```
SCELTA CONFERMATA: parametri pragmatici
Struttura a 4 condizioni invariata — cambiano solo le soglie
Primi 30 giorni: solo alert-only (non apre posizioni automaticamente)

Parametri pragmatici per famiglia:
  Famiglia              DD min   RSI max  EMA fast  Giorni high  Recovery min
  equity_sviluppati     6.5%     45       EMA10     3            1.5%
  mercati_emergenti     8.5%     42       EMA10     3            2.0%
  settoriali_growth     10.0%    42       EMA8      2            2.5%
  settoriali_difensivi  5.0%     48       EMA10     3            1.0%
  bond_governativi      4.0%     42       EMA15     5            0.8%
  bond_corp_hy_em       5.5%     44       EMA10     3            1.2%
  oro_metalli_preziosi  8.0%     42       EMA10     3            2.0%
  commodities           10.0%    40       EMA10     3            2.5%
  metalli_industriali   8.0%     42       EMA10     3            2.0%
  real_estate_reit      7.0%     44       EMA12     3            1.5%
  inflation_linked      4.0%     42       EMA15     5            0.8%
  crypto_digital        25.0%    38       EMA8      2            5.0%
  leva_single_stock     DISABILITATO (troppo rischioso su L0)
  private_equity        7.0%     42       EMA10     3            1.5%
  monetario_liquidita   DISABILITATO (non ha logica L0)
```

```python
def check_l0_entry(ticker, close_series, rsi_14, ema_fast_series,
                   famiglia, family_params, alert_only=True):
    """
    SCELTA CONFERMATA: parametri pragmatici + alert_only=True per i primi 30gg

    4 condizioni tutte obbligatorie:
    ① Drawdown sufficiente dai massimi 63 giorni
    ② RSI scarico (non in panico, solo riposato)
    ③ Inversione confermata (EMA fast + chiusura sopra max 3 giorni)
    ④ Recupero minimo dai minimi 10 giorni
    """
    cfg = family_params.get("l0_entry", {})

    if not cfg.get("enabled", True):
        return {"l0_signal": False, "reason": "disabled_for_family"}

    close_today = close_series[-1]

    # ① Drawdown
    high_63d     = max(close_series[-63:]) if len(close_series) >= 63 else max(close_series)
    dd_from_high = (high_63d - close_today) / high_63d
    dd_threshold = cfg.get("dd_threshold", 0.065)
    cond1        = dd_from_high >= dd_threshold

    # ② RSI scarico
    rsi_max = cfg.get("rsi_max", 45)
    cond2   = rsi_14 < rsi_max

    # ③ Inversione (EMA fast + chiusura sopra max N giorni)
    ema_fast   = ema_fast_series[-1] if ema_fast_series else None
    cond3a     = (close_today > ema_fast) if ema_fast else False
    lookback   = cfg.get("lookback_high_days", 3)
    prev_high  = max(close_series[-(lookback+1):-1]) if len(close_series) > lookback else close_today
    cond3b     = close_today > prev_high
    cond3      = cond3a and cond3b

    # ④ Recupero minimo dai minimi 10 giorni
    low_10d      = min(close_series[-10:]) if len(close_series) >= 10 else close_today
    recovery_pct = (close_today - low_10d) / low_10d
    recovery_min = cfg.get("recovery_min_pct", 0.015)
    cond4        = recovery_pct >= recovery_min

    l0_signal = cond1 and cond2 and cond3 and cond4

    return {
        "l0_signal":    l0_signal,
        "alert_only":   alert_only,  # True → mostra in email, non apre posizione
        "ticker":       ticker,
        "famiglia":     famiglia,
        "dd_from_high": round(dd_from_high * 100, 2),
        "rsi_current":  round(rsi_14, 1),
        "recovery_pct": round(recovery_pct * 100, 2),
        "conditions":   {
            "①_drawdown":  cond1,
            "②_rsi":       cond2,
            "③a_ema_fast": cond3a,
            "③b_high_Ngg": cond3b,
            "④_recovery":  cond4,
        },
        "reason": "tutte_ok" if l0_signal else "condizioni_mancanti",
    }
```

### 3.2 Stop Loss — trailing progressivo L0

```
SCELTA CONFERMATA: trailing progressivo che protegge il capitale

Profitto < 5%   → SL = prezzo_carico × 0.98   (non perdere il capitale)
Profitto 5-15%  → SL = prezzo_carico × 1.01   (almeno in pareggio)
Profitto > 15%  → SL = prezzo_carico × (1 + profitto - 0.08)
                  (proteggi circa metà del gain accumulato)

Calcolato ogni giorno per tutti gli ETF in Portafoglio L0.
Mostrato come "SL Suggerito" nel portafoglio L0 nel monitor.
Inviato nell'email delle 19:00.
```

```python
def calculate_sl_suggerito_l0(position):
    """
    Calcola SL Suggerito per posizioni L0 — trailing progressivo.
    Garantisce che non si perde mai il capitale dopo +5%.
    """
    entry_price   = position["entry_price"]
    current_price = position["prezzo_attuale"]
    profit_pct    = (current_price - entry_price) / entry_price

    if profit_pct < 0.05:
        # Sotto +5% → proteggi il capitale (SL sotto carico del 2%)
        sl = entry_price * 0.98
    elif profit_pct < 0.15:
        # Tra +5% e +15% → almeno in pareggio
        sl = entry_price * 1.01
    else:
        # Sopra +15% → proteggi metà gain
        sl = entry_price * (1 + profit_pct - 0.08)

    return round(sl, 4)
```

### 3.3 Stop Gain L0

```
SCELTA CONFERMATA: NESSUNO STOP GAIN SU L0
La posizione rimane aperta finché non scatta una regola di uscita.
Obiettivo: cavalcare il trend per mesi senza uscire prematuramente.
```

### 3.4 Regole di uscita L0 — ordine di priorità

```
SCELTA CONFERMATA:

Priorità 1 — F Kill Switch:
  Calo giornaliero ≤ -3% → uscita immediata totale

Priorità 2 — β Bear Trap:
  RSI scende sotto 25 dopo l'ingresso → uscita immediata
  (stavamo comprando su un minimo falso)

Priorità 3 — α Stop Assoluto:
  Prezzo scende sotto il minimo degli ultimi 30 giorni → uscita
  (il trend ribassista continua, non era vera inversione)

Priorità 4 — Trailing Stop (SL Suggerito):
  Prezzo ≤ SL Suggerito calcolato con formula progressiva → uscita

Priorità 5 — ε Timeout:
  45 giorni senza che il prezzo superi EMA20 → uscita automatica
  (il capitale sta dormendo senza motivo)

Promozione γ (NON è uscita — solo aggiornamento livello):
  Prezzo > EMA20 → livello sale da L0 a L2 nel monitor
  MA la posizione rimane in Portafoglio L0 con trailing stop
  La strategia NON cambia

NOTA: nessuna Regola D (XEON) su L0 — non applicabile con Banco BPM
```

```python
def check_exit_l0(position, market_data):
    """
    Unico punto di controllo uscite per Portafoglio L0.
    """
    price      = market_data["close"]
    daily_chg  = market_data["daily_change_pct"]
    rsi        = market_data["rsi_14"]
    days_no_rec= position.get("days_no_recovery", 0)
    ema20      = market_data["ema20"]

    # Minimo 30 giorni
    close_series  = market_data.get("close_series", [])
    min_30d = min(close_series[-30:]) if len(close_series) >= 30 else price * 0.85

    # P1 — Kill Switch
    if daily_chg <= -0.03:
        return {"exit": True, "reason": "F_kill_switch", "priority": 1}

    # P2 — Bear Trap
    if rsi < 25:
        return {"exit": True, "reason": "β_bear_trap", "priority": 2}

    # P3 — Stop Assoluto
    if price < min_30d:
        return {"exit": True, "reason": "α_stop_assoluto", "priority": 3}

    # P4 — Trailing Stop
    sl = calculate_sl_suggerito_l0(position)
    if price <= sl:
        return {"exit": True, "reason": "trailing_stop", "priority": 4,
                "sl_level": sl}

    # P5 — Timeout 45 giorni
    if price < ema20:
        days_no_rec += 1
    else:
        days_no_rec = 0  # reset se supera EMA20

    if days_no_rec >= 45:
        return {"exit": True, "reason": "ε_timeout_45gg", "priority": 5}

    # Aggiorna contatori
    stallo = position.get("stallo_counter", 0)
    profit_pct = (price - position["entry_price"]) / position["entry_price"]
    if -0.01 <= profit_pct <= 0.02:
        stallo += 1
    else:
        stallo = 0

    return {
        "exit":              False,
        "reason":            None,
        "days_no_recovery":  days_no_rec,
        "stallo_counter":    stallo,
        "alert_stallo":      stallo >= 20,  # alert nell'email dopo 20 giorni
    }
```

### 3.5 Promozione L0 → L2 → L1 (solo informativa)

```python
def update_livello_l0(position, price, ema20, sma50,
                      buy_count, family_params):
    """
    Aggiorna il livello tecnico mostrato nel monitor.
    NON cambia portafoglio, NON cambia strategia di uscita.
    La posizione rimane sempre in Portafoglio L0.
    """
    if price > ema20 and ema20 > sma50 and buy_count >= 6:
        livello_display = "L1"   # tecnicamente L1 ma posizione resta in P_L0
    elif price > ema20:
        livello_display = "L2"   # in recupero
    else:
        livello_display = "L0"   # ancora in fase di recupero

    return livello_display  # solo per display, non cambia logica
```

---

## 4. EMAIL GIORNALIERA — struttura confermata

```
ORARIO:
  18:30 → aggiornamento prezzi e calcolo SL/SG suggeriti
  19:00 → invio email

STRUTTURA EMAIL (unico messaggio):

════════════════════════════════════════════════════
📊 ETF Monitor | Portafoglio Giornaliero | GG/MM/AAAA
════════════════════════════════════════════════════

── PORTAFOGLIO L1 — Breve Termine ──────────────────

  ETF              | Carico  | Attuale | Perf%  | Gg | SL Sug.  | SG Sug.  | Note
  Russell 2000     | 373.35  | 392.10  | +5.01% | 51 | 388.18 ↑ | 402.25   | SG vicino
  EPAB Eurozone    | 40.39   | 42.80   | +6.0%  | 50 | 42.37 ↑  | 43.32    | —
  DJ Industrial    | 457.90  | 470.00  | +2.64% | 29 | 461.56   | 480.86   | —
  Canada           | 261.93  | 268.00  | +2.32% | 55 | 263.46   | 273.83   | —
  MSCI Europe      | 243.80  | 246.00  | +0.90% | 21 | 240.12   | 255.12   | —
  Water            | 70.00   | 71.00   | +1.43% | 21 | 68.60    | 72.52    | —
  USHYC Bond HY    | 10.55   | 10.47   | -0.72% | 21 | 10.31    | —        | ⚠ PERDITA

  Totale L1: +2.90% | +502€ lordi | +371€ netti stimati

  🟢 NUOVI SEGNALI L1 (valuta acquisto):
     GENY Millennials  | Quality 3/4 | Size 75% | Gate ✓
     WLD MSCI World II | Quality 2/4 | Size 50% | Gate ✓

  📊 Regime mercato: BULL 68/100

── PORTAFOGLIO L0 — Medio/Lungo Termine ─────────────

  (vuoto — nessuna posizione aperta al momento)

  🔵 CANDIDATI L0 (alert — valuta manualmente):
     nessun segnale oggi

════════════════════════════════════════════════════
```

```
COLONNE EMAIL L1:
  ETF        → nome breve + ticker
  Carico     → prezzo medio di carico
  Attuale    → ultimo prezzo (18:30)
  Perf%      → (attuale - carico) / carico
  Gg         → giorni in portafoglio
  SL Sug.    → stop loss suggerito (formula ibrida — aggiornato)
  SG Sug.    → stop gain suggerito (formula dinamica — aggiornato)
  Note       → alert: SG vicino / SL vicino / PERDITA / STALLO

COLONNE EMAIL L0:
  ETF        → nome breve + ticker
  Carico     → prezzo medio di carico
  Attuale    → ultimo prezzo
  Perf%      → performance dalla data acquisto
  Gg         → giorni in portafoglio
  Livello    → livello tecnico attuale (L0/L2/L1) — solo informativo
  SL Sug.    → trailing stop progressivo aggiornato
  Note       → alert: STALLO 20gg / TIMEOUT vicino / BEAR TRAP
```

---

## 5. Piano di implementazione per step

```
STEP 1 — Aggiorna struttura posizione (30 min)
  Aggiungi campi: portafoglio, entry_layer, entry_quality,
  entry_confidence, capital_pct, stop_gain_target,
  sl_suggerito, sg_suggerito, days_no_recovery, stallo_counter
  Per posizioni esistenti: portafoglio="L1", confidence=1.0

STEP 2 — Aggiorna logica flag "+ Port." (45 min)
  Al click del flag: leggi etf.livello attuale
  → L1: inserisce in Portafoglio L1
  → L0: inserisce in Portafoglio L0
  → altro: chiedi conferma

STEP 3 — Implementa check_l1_entry_tiered (60 min)
  Opzione 3: Gate 2/2 + Quality 2/4 + Size dinamica
  Testa i 6 scenari della sezione 2.1
  NON toccare Opzione 1 e 2 esistenti — lavorano in parallelo

STEP 4 — Implementa calculate_sl_suggerito_l1 (30 min)
  Formula ibrida: largo < 2% profitto, stretto ≥ 2%
  Aggiunge colonna "SL Suggerito" già presente nel monitor
  Aggiorna la formula di calcolo — non il campo visivo

STEP 5 — Implementa calculate_sg_suggerito_l1 (45 min)
  Target per famiglia + pendenza EMA20 + RSI(5) trigger
  Aggiunge NUOVA colonna "SG Suggerito" nel monitor
  Visivamente uguale a "SL Suggerito" (stesso stile)

STEP 6 — Implementa check_exit_l1 (45 min)
  Ordine priorità: F → SL → B → C → SG → E
  Rimuove Regola D (XEON)
  Testa tutti i trigger con posizioni simulate

STEP 7 — Implementa check_l0_entry con parametri pragmatici (60 min)
  alert_only=True per i primi 30 giorni
  Testa su ETF storici con correzioni del 5-10% nel 2024-2025

STEP 8 — Implementa calculate_sl_suggerito_l0 (20 min)
  Trailing progressivo: < 5% / 5-15% / > 15%
  Aggiunge "SL Suggerito" anche nel Portafoglio L0

STEP 9 — Implementa check_exit_l0 (45 min)
  Ordine: F → β → α → trailing → ε timeout 45gg
  Gestisce contatori days_no_recovery e stallo_counter

STEP 10 — Aggiorna email 19:00 (60 min)
  Struttura: sezione L1 poi sezione L0
  Aggiunge SG Suggerito nella sezione L1
  Aggiunge candidati L0 (alert-only)
  Aggiunge alert stallo 20 giorni per L0
  Aggiornamento prezzi: 18:30

PRIORITÀ ASSOLUTA: Step 4 e 5 (SL + SG Suggerito nel monitor e email)
perché le posizioni L1 sono già aperte e ne hai bisogno subito.
```

---

## 6. Checklist finale prima del go-live

```
SISTEMA L1:
[ ] Flag instrada correttamente in Portafoglio L1 se ETF è in L1
[ ] check_l1_entry_tiered funziona con Gate + Quality + Size
[ ] SL Suggerito aggiornato quotidianamente con formula ibrida
[ ] SG Suggerito nuovo campo visibile nel monitor come SL Suggerito
[ ] check_exit_l1 rispetta ordine priorità F→SL→B→C→SG→E
[ ] Regola D (XEON) rimossa da L1
[ ] Email 19:00 contiene SL Sug. + SG Sug. + nuovi segnali L1

SISTEMA L0:
[ ] Flag instrada in Portafoglio L0 se ETF è in L0
[ ] check_l0_entry usa parametri pragmatici
[ ] Primi 30gg: solo alert-only nell'email, non apre posizioni
[ ] SL Suggerito trailing progressivo calcolato per L0
[ ] check_exit_l0 gestisce F/β/α/trailing/ε(45gg)
[ ] Alert stallo 20 giorni attivo nell'email L0
[ ] Promozione L0→L2→L1 aggiorna solo il livello display, non il portafoglio

EMAIL:
[ ] Aggiornamento prezzi alle 18:30
[ ] Email unica alle 19:00 — prima L1 poi L0
[ ] Totale portafoglio L1 (€ lordi e netti stimati)
[ ] Candidati L0 come alert nella sezione L0

COMPATIBILITÀ:
[ ] Posizioni esistenti migrate con portafoglio="L1", confidence=1.0
[ ] Score APRDXM ancora calcolato e mostrato (backward compat.)
[ ] Nessun campo esistente rinominato o eliminato
[ ] Backup prima di ogni modifica
```

---

## 7. Riepilogo decisioni — tutto confermato il 16/07/2026

| # | Argomento | Scelta confermata |
|---|-----------|-------------------|
| L1-1 | Ingresso | Opzione 3: Gate 2/2 + Quality 2/4 + Size 50/75/100% |
| L1-2 | Stop Loss | Ibrido C: largo < 2% profitto, stretto ≥ 2% |
| L1-3 | Stop Gain | Variabile per famiglia dal prezzo carico |
| L1-4 | Regole uscita | F+B+C attive, A→SL ibrido, E opzionale, D eliminata |
| L1-5 | Email | 19:00 unica con SL+SG suggerito + nuovi segnali L1 |
| L1-6 | Portafogli | Flag instrada su livello ETF al momento del click |
| L1-7 | Kill Switch | Solo KS1 (-3% giorno), tutto il resto manuale |
| L0-1 | Ingresso | Parametri pragmatici, alert-only primi 30gg |
| L0-2 | Trailing | Progressivo: < 5% / 5-15% / > 15% profitto |
| L0-3 | Stop Gain | NESSUNO — solo trailing stop, lascia correre il trend |
| L0-4 | Regole uscita | F+β+α+trailing+ε(45gg) |
| L0-5 | Email | Stessa email L1 delle 19:00 — sezione L0 dopo L1 |
| L0-6 | Promozione | Posizione resta sempre in P_L0 indipendentemente dal livello |

---

*Versione: 5.0 DEFINITIVO — 16 Luglio 2026*
*Sistema: ETF Monitor — ETFplus Borsa Italiana — Banco BPM*
*Tutte le scelte sono state confermate interattivamente dal proprietario*
*Compatibile con specifica ufficiale v2.0 (1 luglio 2026)*
