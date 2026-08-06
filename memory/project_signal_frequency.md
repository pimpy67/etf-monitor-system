---
name: project_signal_frequency
description: Expected email frequency and signal cadence for L1+L0 strategies
metadata: 
  node_type: memory
  type: project
  originSessionId: e67eaca6-74dc-4036-81a9-5dc2cb642f2d
  modified: 2026-08-06T14:26:53.753Z
---

# 📧 Signal Frequency & Email Cadence

**Baseline:** 3-year backtest validation (€50k portfolio, 3-4 L1 concurrent + 2-3 L0 concurrent)

---

## 📊 Quick Reference

| Metrica | Valore | Frequenza |
|---------|:---:|---------|
| **L1 Nuovi Ingressi** | 27/anno | ~1 ogni 13 giorni |
| **L0 Nuovi Ingressi** | 8/anno | ~1 ogni 6-7 settimane |
| **Segnali Totali** | 35/anno | ~1 ogni 9-10 giorni |
| **Email al Giorno** | ~1 | Recap portafoglio + alert |
| **Email con Nuovo Segnale** | 0.5/settimana | Martedì o mercoledì |
| **Email di Uscita (SL/TP)** | 0.5/settimana | Giovedì o venerdì |

---

## 📅 Settimana Tipo (€50k Portfolio)

### Scenario: RIALZO (Market BULL)

```
LUNEDÌ
  17:00 CEST: Email portafoglio recap
  "📊 Portafoglio oggi: SWDA.L +1.2%, AMEU.PA +0.8%, IWDA.L flat
   SL aggiornati: SWDA.L SL €9.600 / TP €10.800
   Nessun nuovo segnale"
  → Tempo azione: 2 minuti (leggi + ignora)

MERCOLEDÌ
  17:00 CEST: Email NUOVO SEGNALE L1
  "🟢 NUOVO INGRESSO L1 — XLU.L (Utilities)
   Prezzo: €105.50 | SL: €100.23 | TP: €113.94
   Azione: Compra su Directa a €105.50 (basta ordine a mercato)"
  → Tempo azione: 5 minuti (esegui ordine)
  
  17:30 CEST: Email portfolio update con nuova posizione
  "📊 Portafoglio aggiornato (4 posizioni L1 aperte)..."

GIOVEDÌ
  17:00 CEST: Email USCITA TP
  "✅ USCITA L1 — SWDA.L raggiunge Take Profit
   Entry: €82.50 | Exit: €89.10 (TP) | Gain: +8.0%
   Azione: Vendi su Directa a €89+ (ordine a mercato)"
  → Tempo azione: 5 minuti (esegui ordine)

VENERDÌ
  17:00 CEST: Email Recap settimanale
  "📊 Settimana completata:
   +1 ingresso L1, +1 uscita TP, −0 uscite SL
   P&L settimana: +€820 lordo, +€620 netto
   Portafoglio: 3 L1 + 2 L0 aperte"
  → Tempo azione: 2 minuti (leggi)

FINE SETTIMANA
  Niente — mercati chiusi
```

### Scenario: LATERALE/RIBASSO (Market BEAR)

```
LUNEDÌ
  17:00 CEST: Email portafoglio recap
  "📊 Portafoglio: 2 L1 aperte (no new signal), 1 L0 in attesa recovery
   Nessun nuovo segnale L1 (regime BEAR)"
  → Tempo azione: 2 minuti

MERCOLEDÌ
  17:00 CEST: Email NUOVO SEGNALE L0 (Deep Recovery)
  "🟠 NUOVO INGRESSO L0 — INRG.SW (Clean Energy Recovery)
   Drawdown: 8.2% | RSI: 38 | Divergenza: confermata
   Entry: €42.30 | SL: €41.50 | TP: €49.10
   Azione: Compra su Directa a €42.30"
  → Tempo azione: 5 minuti

MARTEDÌ (alternato)
  17:00 CEST: Email USCITA SL
  "❌ USCITA L1 — AMEU.PA Stop Loss
   Entry: €243.80 | Exit: €231.61 (SL) | Loss: −4.99%
   Reason: Prezzo < EMA20 per 3 giorni
   Azione: Accetta uscita (già impostata su Directa)"
  → Tempo azione: 1 minuto (notifica)

FINE SETTIMANA
  Niente — mercati chiusi
```

---

## 📈 Distribuzione Frequenza (Variabilità Reale)

**Non è regolare!** Dipende molto dal regime di mercato.

### Settimane Active (Regime BULL STRONG)
```
L1 nuovi ingressi: 1-2
L0 nuovi ingressi: 0-1
Email nuove operazioni: 2-3
Email di uscita (SL/TP): 1-2
→ Total nuove email: 3-5 per settimana
→ Totale azioni: 3-5 ordini da eseguire manualmente
```

### Settimane Lente (Regime BEAR o LATERALE)
```
L1 nuovi ingressi: 0
L0 nuovi ingressi: 0-1
Email nuove operazioni: 0-1
Email di uscita (SL/TP): 0-1 (posizioni lasciate aperte)
→ Total nuove email: 0-1 per settimana
→ Totale azioni: Solo recap portafoglio (passivo)
```

### Media su 52 Settimane/Anno
```
27 L1 trade/anno → 27 ingressi + 27 uscite = 54 ordini
8 L0 trade/anno → 8 ingressi + 8 uscite = 16 ordini
Total ordini: 70/anno ÷ 52 settimane = 1.35 ordini/settimana
→ Circa 1 nuovo segnale ogni 7-9 giorni
```

---

## 📧 Email Types & Cadenza

| Email Type | Frequenza | Urgenza | Azione Richiesta |
|-----------|:---:|:---:|---------|
| **Recap Portafoglio** | Quotidiana (17:00 CEST) | 🟢 Bassa | Leggi SL/TP (no ordine) |
| **Nuovo Ingresso L1** | ~1 ogni 13 giorni | 🔴 ALTA | Compra entro 1h |
| **Nuovo Ingresso L0** | ~1 ogni 6-7 settimane | 🔴 ALTA | Compra entro 1h |
| **Uscita TP Raggiunto** | ~1 ogni 2 settimane (L1+L0 mix) | 🟡 Media | Vendi entro 1h |
| **Uscita SL Colpito** | ~0.5 ogni settimana | 🟡 Media | Accetta (già ordine a mercato?) |
| **Kill Switch (-3% giorno)** | Raro (~3x/anno) | 🔴 CRITICA | Check immediato |
| **Alert Regime Change** | Raro (~2x/anno) | 🟡 Media | Info sola (sistema auto-adatta) |

---

## ⏱️ Tempo Operativo Richiesto

### Giorno Normale (con Email)
```
17:00 CEST: Arriva email recap + possibile alert
├─ Leggi email: 2 minuti
├─ Se nuovo segnale: esegui ordine Directa: 5 minuti
├─ Se uscita SL/TP: check posizione, accetta: 3 minuti
└─ Total: 2-10 minuti a seconda degli alert

→ MEDIA: ~5 minuti per giorno lavorativo
```

### Settimana Completa
```
Lunedì-Venerdì: 5 email (recap quotidiano)
→ 5 × 2 minuti = 10 minuti

Margine per nuovi segnali (est. 1x/settimana)
→ +5 minuti per ordine

Margine per uscite SL/TP (est. 1x/settimana)
→ +3 minuti per check

TOTALE SETTIMANALE: ~20 minuti
TOTALE ANNUALE: ~17 ore (0.4% tempo)
```

---

## 🎯 Se Vuoi Più/Meno Segnali

### Se ricevi TROPPI segnali (stress)
```
Opzione 1: Riduci da €50k a €30k portfolio
  → Scende a 1 segnale ogni 14-15 giorni (meno stress)
  → P&L: €2.300/anno (invece di €4.567)

Opzione 2: Disabilita L0 temporaneamente
  → Solo L1: 1 segnale ogni 13 giorni (stabile)
  → P&L: €2.392/anno (perde il L0 income)

Opzione 3: Aumenta Stop Loss duration (più lassa)
  → Accetta più consolidamenti, meno noise exits
  → Richiede codice change, non consigliato durante validation
```

### Se ricevi TROPPO POCHI segnali (bored)
```
Opzione 1: Scala a €70k portfolio
  → Segnale ogni 7-8 giorni (più attivo)
  → P&L: €6.500+/anno (più capitale, stessa ROA)

Opzione 2: Abilita smart_6_macd override
  → Volume da 27 → 45 trade/anno per L1 (quasi doppio)
  → WR cala da 60% → 54% (trade quality soffrono)
  → Richiede backtest + live validation

Opzione 3: Non suggerito → Non ridurre soglie critiche
  → Rischio curve-fitting su rumore
```

---

## 🔔 Critical Alerts (Non Segnali Normali)

Questi arrivano **fuori agenda** se verificati:

| Alert | Trigger | Azione | Frequenza |
|-------|---------|--------|-----------|
| Kill Switch | Daily change ≤ −3% | CHECK PORTFOLIO — non vendere automatico | ~3x/anno |
| SL Auto-Hit | Overnight gap | Posizione chiusa (check P&L netto) | ~2x/anno |
| Regime Change | BULL → BEAR | INFO sola — sistema auto-adatta L0 | ~2x/anno |
| Email Failure | No recap for 2 days | CHECK VPS logs | <1x/anno |

---

## 📊 Example: Anno di Operazioni (Scenario Reale)

```
ANNO 2026 (27 L1 + 8 L0 = 35 trade totali)

Gennaio: 2 L1 + 0 L0 = 2 segnali (lento BEAR)
Febbraio: 2 L1 + 1 L0 = 3 segnali
Marzo: 3 L1 + 1 L0 = 4 segnali (forte BULL)
Aprile: 2 L1 + 0 L0 = 2 segnali (consolidamento)
Maggio: 3 L1 + 2 L0 = 5 segnali (BULL riparte)
Giugno: 3 L1 + 1 L0 = 4 segnali
Luglio: 3 L1 + 1 L0 = 4 segnali
Agosto: 1 L1 + 1 L0 = 2 segnali (calo estivo)
Settembre: 2 L1 + 0 L0 = 2 segnali
Ottobre: 1 L1 + 1 L0 = 2 segnali
Novembre: 0 L1 + 0 L0 = 0 segnali (BEAR)
Dicembre: 0 L1 + 0 L0 = 0 segnali (BEAR)

TOTAL: 27 L1 + 8 L0 = 35 segnali
Media: 2.9 segnali/mese = 0.7 segnali/settimana
Email totali: ~35 × 2 (ingresso + uscita) = 70 email + 260 recap = 330 email/anno
Email/giorno: 330 ÷ 260 giorni = 1.3 email/giorno lavorativo ✅
```

---

**Last Updated:** 2026-08-06  
**Context:** €50k portfolio, 3-4 L1 concurrent + 2-3 L0 concurrent  
**Validation Window:** 2026-08-06 → 2026-09-06 (collect live data)

