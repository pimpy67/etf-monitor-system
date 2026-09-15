---
name: session-2026-09-15-summary
description: Sessione del 15/09/2026 — 3 fix critici L0/L1 + migrazione High Watermark
metadata:
  type: project
---

# Sessione 2026-09-15 — Fix Critici & Migrazione High Watermark

## 🚀 Tre Deploy Effettuati

### 1️⃣ Fix Bug Query L0/L1 (fd7657f)
**Problema**: Query leggeva `stop_loss_suggested` (inesistente) → NULL → SL poteva scendere
**Fix**: Legge `sl_suggerito` (corretta) → trailing stop proteggente funziona
**Impatto**: SL non scendono mai (max vs previous_sl)

### 2️⃣ Migrazione High Watermark SL (f429341) ⭐
**Cambio**: Entry-based → High Watermark (prezzo max raggiunto)

Vecchia: SL = entry × (formula) — ignora drawdown dal picco
Nuova: SL = max × (formula) — vede il vero drawdown, lock-in progressivo

**Implementazione**:
- `technical_analysis.py`: `calculate_sl_suggerito_l0()` accetta `max_price`
- `database.py`: aggiunto `get_max_price_since(isin, start_date)`
- `monitor.py`: passa il max_price dal DB

### 3️⃣ Gate Regime L0: BULL+LATERALE only (a9e39c1) ⭐
**Problema**: Gate BEAR (03/09) genera falsi rimbalzi (Water: entrato-uscito-rientrato stesso giorno)

**Backtest**: BULL+LAT only batte BEAR:
- WR +5pp IN (44.1% → 49.1%)
- P&L +€14.5k IN (-€13.375 → +€1.176)
- WR +6pp OUT (51.6% → 57.6%)
- P&L +€3.4k OUT (+€3.844 → +€7.280)
- PF +15% (3.38 → 3.89)

**Decisione**: Gate BEAR rimosso (decisione 03/09 era sbagliata)

---

## 🎯 TO-DO Obsoleti (IGNORARE)

I TO-DO iniziali di oggi (SL 51.69→50.63, ecc.) usano formula vecchia.
Nuovi TO-DO arrivano dall'email 19:30 CEST con valori High Watermark corretti.

---

## ⏰ Prossimo Monitor: 17:30 CEST

Con:
✅ High Watermark SL
✅ Gate BULL+LATERALE only
✅ Trailing stop proteggente

Email 19:30 CEST con nuovi TO-DO.

