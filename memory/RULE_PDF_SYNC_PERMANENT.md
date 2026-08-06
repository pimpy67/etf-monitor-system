---
name: rule_pdf_sync_permanent
description: PDF parametri DEVE essere generato automaticamente dal YAML — sincronizzazione permanente binding
metadata: 
  node_type: memory
  type: feedback
  date: 2026-07-15
  status: IMPLEMENTATO
  originSessionId: ae0867eb-de7e-46f3-9b31-3785a4e8b296
---

# REGOLA PERMANENTE — Sincronizzazione Automatica PDF-YAML

## La Regola (BINDING PER SEMPRE)

**Ogni modifica ai parametri del sistema deve essere automaticamente riflessa nel PDF scaricabile.**

Il PDF **NON** deve mai:
- Essere scritto a mano
- Essere committato in git
- Essere gestito manualmente
- Divergere dal YAML

Il PDF **DEVE** sempre:
- Essere generato lato server da `pdf_generator.py`
- Leggere direttamente da `config/etf_families.yaml` (fonte di verità)
- Essere rigenerato ogni volta che il monitor gira
- Essere rigenerato all'avvio dell'app
- Essere 100% sincronizzato con il YAML in ogni momento

## Implementazione (2026-07-15)

### Componenti
1. **pdf_generator.py** — generatore PDF ReportLab (legge YAML, produce PDF vero)
2. **app.py** — genera PDF all'avvio + espone `/api/download-parameters-pdf`
3. **monitor.py** — rigeneraa PDF dopo ogni ciclo (STEP FINALE)
4. **dashboard.html** — bottone "📥 PDF" punta a `/api/download-parameters-pdf` (non html2pdf)
5. **CLAUDE.md** — Sezione "REGOLA DI SINCRONIZZAZIONE PERMANENTE" documenta il workflow

### Workflow Automatico

```
Modifica config/etf_families.yaml
  ↓
Prossimo monitor gira (17:00 o trigger manuale)
  ↓
monitor.py::run() STEP FINALE: generate_parameters_pdf()
  ↓
PDF rigenerato in data/ETF_Monitor_Parametri_Riferimento.pdf
  ↓
App riavvia oppure (se in background) endpoint legge il nuovo PDF
  ↓
Utente scarica: /api/download-parameters-pdf
  ↓
PDF fresco, sempre sincronizzato ✅
```

## Why (La Ragione)

**Problema**: Il PDF client-side (html2pdf) risultava bianco perché:
- Il contenuto dinamico non veniva caricato prima dell'export
- HTML2PDF non riusciva a renderizzare il contenuto caricato via fetch
- L'utente doveva scaricare un PDF non rappresentativo dello stato reale

**Soluzione**: Generare il PDF server-side direttamente dal YAML:
- ✅ Sempre affidabile
- ✅ Non dipendente da browser/JS
- ✅ Automatico e sincronizzato per definizione
- ✅ No responsabilità manuale

## How to Apply (Quando questa regola attiva)

### Ogni volta che modifichi parametri nel YAML
- ✅ Non fare nulla di speciale
- ✅ Il PDF sarà rigenerato al prossimo monitor
- ✅ Oppure all'avvio dell'app

### Se aggiungi un nuovo parametro al YAML
1. Aggiungi il parametro in `config/etf_families.yaml`
2. Aggiorna `technical_analysis.py` per usarlo
3. Se è interessante per il dashboard, aggiungi una riga in `pdf_generator.py` nella sezione table_data.append()
4. Nient'altro — il PDF sarà automaticamente incluso

### Se scopri un bug nel PDF
- Non modificare il PDF manualmente
- Modifica `pdf_generator.py` per fixare il bug
- Rigeneraa il PDF manualmente: `ssh root@76.13.37.133 "cd /root/etf_monitor_system && python3 -c 'from pdf_generator import generate_parameters_pdf; generate_parameters_pdf()'"`
- Oppure aspetta il prossimo monitor

## Eccezioni: ZERO

Non ci sono eccezioni a questa regola. Il PDF è SEMPRE derivato dal YAML. Punto.

## Link nel CLAUDE.md

**Sezione**: "REGOLA DI SINCRONIZZAZIONE PERMANENTE — PDF Parametri (2026-07-15)"
- Descrive il workflow completo
- Elenca i file interessati
- Spiega la procedura di modifica

## Memorie correlate

- [[CURRENT_STATUS.md]] — contiene info su deploy, monitor status
- [[PARAMETERS_CURRENT.md]] — parametri live
