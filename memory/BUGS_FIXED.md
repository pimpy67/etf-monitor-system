---
name: bugs_fixed
description: "Bug history — problems found, root causes, solutions, lessons learned"
metadata: 
  node_type: memory
  type: project
  originSessionId: c74b19e0-7264-4b9a-a514-edc7242ac1fd
---

## 🐛 BUGS RISOLTI & LEZIONI

### 2026-07-06 — NameError in Debug Log
**Sintomo**: Monitor crash con `NameError: name 'ticker' is not defined`
**Linea**: technical_analysis.py:844 (debug print)
**Root Cause**: Usato `{ticker}` in f-string ma variabile non definita nel contesto STRATO 3
**Fix**: Rimosso debug log errato
**Commit**: `99ddfbe`
**Lezione**: ✅ Sempre verificare scope variabili prima di usarle in print

---

### 2026-07-06 — Docker Volume Sync Issue (Risolto 2026-07-03)
**Sintomo**: dashboard_data.json non aggiornato dal monitor
**Root Cause**: Volume anonimo in docker-compose.yml (`etf_data:/app/data`)
**Problema**: Dati scritti nel container ma non synced con host
**Fix**: Changed to bind mount `/root/etf_monitor_system/data:/app/data`
**Commit**: `1a9cc6a` (da storico)
**Lezione**: ✅ Bind mount per file critici (dashboard_data, Excel), volumes per DB persistenza

---

### 2026-07-06 — STRATO 3 Hardcoded Slope
**Sintomo**: STRATO 3 usava soglia 0.5% hardcoded per tutte le famiglie
**Root Cause**: `slope_fails = ema20_slope_value < 0.5` (linea 842)
**Problema**: Non leggeva ema20_slope_min dalla famiglia (come STRATO 2)
**Fix**: Parametrizzato: `slope_fails = ema20_slope_value < ema20_slope_threshold_s3`
**Commit**: `1a5a5e6`
**Lezione**: ✅ Se un parametro è configurable in YAML, NON hardcodarlo

---

### 2026-07-06 — Monitor Timing Too Early
**Sintomo**: Monitor a 17:00 CEST, ma Yahoo Finance ancora non aggiornato
**Root Cause**: Mercati chiudono 17:30 CET; Yahoo Finance aggiorna post-close
**Problema**: Prendeva dati di ieri (stale prices)
**Fix**: Spostato a 18:30 CEST (16:30 UTC)
**Commit**: Docker-compose.yml linea 14-15
**Lezione**: ✅ Verificare timing di aggiornamento delle fonti dati

---

### 2026-07-01 — Portfolio API Error
**Sintomo**: GET /api/portfolio-sl → 500 `'PriceDatabase' object has no attribute 'get_connection'`
**Root Cause**: Mancava implementazione del metodo get_connection() in database.py
**Fix**: Aggiunto metodo context manager
**Lezione**: ✅ Test tutti gli endpoint API dopo refactor

---

### 2026-06-29 — Min Buy Count Not Applied
**Sintomo**: Molti 4/5 entravano in L1 quando dovevano stare L2
**Root Cause**: min_buy_count parametrizzato ma non implementato nelle condizioni
**Fix**: Aggiunto controllo `if int(buy_count) < p['min_buy_count']: ...`
**Commit**: c92eed5
**Lezione**: ✅ Quando si parametrizza, verificare che sia usato ovunque

---

## 🎓 PATTERN COMUNI
1. **Hardcoding = Male** — Sempre leggere da config
2. **Testing = Critico** — Ogni cambio di parametro necessita test
3. **Timing = Silenzioso** — I timing bug sono i più subdoli
4. **Volume Mounts** — Essenziali per file modificati dal codice
