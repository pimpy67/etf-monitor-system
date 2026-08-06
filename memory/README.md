# 📚 Memory Archive — ETF Monitor System

Questo è l'archivio di memoria del progetto ETF Monitor. Contiene tutte le note di sessione, decisioni tecniche, roadmap e procedure operative.

## 🗂️ Struttura

### 📍 **Punto di Partenza**
- **[MEMORY.md](MEMORY.md)** ← INIZIA QUI per indice completo

### 📋 **Session Logs (Dal più recente)**
- `SESSION_2026_08_06_AB_TEST_DEPLOYMENT.md` — A/B Test, L0 regime filter, stato sistema
- `SESSION_2026_07_22_FINAL_CHECKPOINT.md` — Checkpoint agosto, decisioni prese
- `session_2026_07_22_L0_L1_fixes.md` — Fix critico: L0 regime + L1 7-condition
- `session_2026_06_29_final.md`, `session_2026_07_06_l1_filtering_fix.md` — Archive

### 💰 **Operational Reference (Leggi Se Devi Decidere)**
- **`project_capital_allocation.md`** — Quanto capitale? €10k-€70k scenario
- **`project_signal_frequency.md`** — Quanti segnali al giorno? Email cadence
- **`project_4_improvements_post_validation.md`** — Le 4 migliorie post-Sept 6
- `directa_etf_procedure.md` — Come comprare/vendere manualmente
- `project_equity_bond_correlation_strategy.md` — Bond analysis

### 🏗️ **System State (Technical Reference)**
- `ALIGNMENT_2026_08_06.md` — Stato sistema allineato con GitHub
- `PARAMETERS_CURRENT.md` — Parametri YAML attuali (14 famiglie, 7/7 entry)
- `CURRENT_STATUS.md` — L1 count, monitor timing, work in progress
- `BUGS_FIXED.md` — Storico bug e fix (da seguire per non replicarli)

### 🔒 **Rules & Governance (Non Modificare)**
- `RULE_PDF_SYNC_PERMANENT.md` — Sincronizzazione automatica PDF (binding permanente)
- `DEPLOYMENT_CHECKLIST.md` — Checklist pre-deploy
- `DOCUMENTATION_SYNC_SOLUTION.md` — Come sincronizzare docs con codice

### 📦 **Archive (Obsoleto 2026-08-05)**
- `STEP3_v4_0_COMPLETE.md`, `V4_0_DEPLOYMENT_LIVE.md`, `V5_DEFINITIVO_COMPLETE.md` — Versioni vecchie
- `ADR_ARCHITECTURE_DECISIONS.md`, `ALIGNMENT_MATRIX.md` — Decisioni superseded

---

## 🎯 Come Usare Questo Archivio

### Se Lavori da Un Altro PC
1. Clona il repo: `git clone https://github.com/pimpy67/etf-monitor-system.git`
2. Entra in `memory/`
3. Leggi `MEMORY.md` (indice)
4. Naviga ai file che ti servono

### Se Hai Una Domanda Specifica

| Domanda | Leggi |
|---------|-------|
| "Quanto capitale mi serve?" | `project_capital_allocation.md` |
| "Quanti segnali riceverò?" | `project_signal_frequency.md` |
| "Quali sono le prossime migliorie?" | `project_4_improvements_post_validation.md` |
| "Quali bug sono stati corretti?" | `BUGS_FIXED.md` |
| "Qual è lo stato attuale del sistema?" | `ALIGNMENT_2026_08_06.md` |
| "Come comporò/vendo manualmente?" | `directa_etf_procedure.md` |
| "Quali sono i parametri attuali?" | `PARAMETERS_CURRENT.md` |

### Se Lavori Contemporaneamente da Due PC
- **PC Casa:** `git pull` prima di iniziare (sincronizza memory/)
- **PC VPS:** Modifica il codice, committa
- **PC Casa:** `git pull` per leggere gli aggiornamenti

---

## 📅 Timeline Critica

| Data | Evento | Leggi |
|------|--------|-------|
| **2026-08-06** | Deploy L0 regime filter + A/B test | `SESSION_2026_08_06_AB_TEST_DEPLOYMENT.md` |
| **2026-08-06 → 2026-09-06** | 30-day validation window (FROZEN params) | `ALIGNMENT_2026_08_06.md` |
| **2026-09-06** | Fine validazione — success/fail decision | Vedi MEMORY.md per success criteria |
| **2026-09-07+** | Implementa 4 migliorie (IF validation pass) | `project_4_improvements_post_validation.md` |

---

## ✨ File Creato Oggi (2026-08-06)

```
memory/
├─ SESSION_2026_08_06_AB_TEST_DEPLOYMENT.md ⭐
├─ project_4_improvements_post_validation.md ⭐
├─ project_capital_allocation.md ⭐
├─ project_signal_frequency.md ⭐
└─ MEMORY.md (indice aggiornato)
```

Questi sono i file della sessione di oggi. Leggili per capire lo stato attuale del sistema.

---

## 🔗 Link Utili

- **GitHub:** https://github.com/pimpy67/etf-monitor-system
- **Dashboard:** https://etf.andreapavan.tech
- **VPS:** 76.13.37.133 (ssh root@...)

---

**Ultimo aggiornamento:** 2026-08-06 14:30 CEST  
**Validation Window:** 2026-08-06 → 2026-09-06 (30 giorni, parametri FROZEN)  
**Prossima azione critica:** 2026-09-06 (revisione validazione)

