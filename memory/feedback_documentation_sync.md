---
name: documentation_always_sync
description: CLAUDE.md parametri sezione deve SEMPRE essere sincronizzata con codice YAML
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 0bf295aa-d8b6-4dc1-8b36-d92fda9540e6
---

**Regola assoluta**: Ogni volta che cambio parametri nel codice (YAML, technical_analysis.py, monitor.py), devo SEMPRE aggiornare CONTEMPORANEAMENTE la sezione "PARAMETRI DI RIFERIMENTO" nel CLAUDE.md.

**Why**: La documentazione è la "fonte di verità" leggibile per il team. Se diverge dal codice, crea confusione e bug di incoerenza.

**How to apply**: 
1. Fatto un cambio parametro? Vado nel CLAUDE.md e aggiorno la tabella corrispondente
2. Prima di committare, verifico che la documentazione rispecchi esattamente i valori nel YAML/codice
3. Se aggiungo un nuovo parametro nel YAML, devo documentarlo nel CLAUDE.md NELLO STESSO COMMIT

**Current state**: Le "Profili parametri per asset type (ETF)" al CLAUDE.md usano i vecchi nomi (equity_developed) mentre il YAML usa nomi famiglia (equity_sviluppati). Inoltre i valori sono outdated (vecchio min_buy_count=6, adx_entry=18). Devo creare una sezione "Profili parametri FAMIGLIE ETF" che mappa esattamente i valori dal config/etf_families.yaml e la mantengo sempre sincronizzata.

**Data ultima modifica**: 2026-07-02 19:16
