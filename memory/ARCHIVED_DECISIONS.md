---
name: archived_decisions
description: "Deprecated decisions, superseded approaches, and lessons learned"
metadata: 
  node_type: memory
  type: project
  originSessionId: c74b19e0-7264-4b9a-a514-edc7242ac1fd
---

## 🗂️ DECISIONI ARCHIVIATE & SUPERSEDUTE

### ❌ STRATO 3 Hardcoding (Superseduto 2026-07-06)
**Was**: `slope_fails = ema20_slope_value < 0.5` (hardcoded in line 842)
**Why**: Ignorava parametro famiglia
**Fixed**: Parametrizzato per leggere da `ema20_slope_min` YAML
**Lesson**: Sempre verificare che i parametri siano letti dalla config, non hardcoded

### ❌ Default ema20_slope_min 0.2% (Superseduto 2026-07-06)
**Was**: STRATO 2 usava default 0.2% (troppo blando)
**Why**: Permetteva trend piatti di entrare in L1
**Action**: Aumentato parametrizzato (0.5-1.0% per famiglia)
**Lesson**: I default vanno testati con dati reali; 0.2% era troppo permissivo

### ❌ Debug Log NameError (Risolto 2026-07-06)
**Was**: `print(f"[S3-CHECK] {ticker} | ...")`  — `ticker` non definito
**Error**: `NameError: name 'ticker' is not defined`
**Fixed**: Rimosso debug log non riuscito
**Lesson**: Verificare disponibilità variabili prima di usarle in print

### ❌ L1=14 Target (Rivisto 2026-07-06)
**Was**: Objective "ridurre L1 da 14 → 0-5"
**Reality**: 14 ETF hanno slope genuinamente >= 0.5%
**Why Failed**: Non erano falsi segnali; erano trend legittimi
**New Target**: 0-5 più realistico con soglie 1.0% (equity)
**Lesson**: Verificare se gli ingressi sono falsi vs. legittimi prima di filtrare

### ❌ Monitor Timing 17:00 CEST (Aggiornato 2026-07-06)
**Was**: 17:00 CEST (17:00 UTC) — troppo presto, prima che Yahoo Finance aggiorni
**Why**: Mercati chiudono 17:30 CET; Yahoo aggiorna dopo
**Fixed**: 18:30 CEST (16:30 UTC)
**Lesson**: Verificare timing delle fonti dati prima di schedulare

## 📚 FUTURE OPTIMIZATIONS (Non implementati)

- **Piede Dentro (90%/10%)**: Sell on RSI>78 (keep 10% + buy XEON)
- **ISIN Resolution**: Molti ticker ancora irrisolti su Yahoo
- **Backtest Framework**: Per validare strategie storicamente
