---
name: adr_architecture_decisions
description: Architecture Decision Records — Traccia decisioni architetturali e scenari alternativi
metadata: 
  node_type: memory
  type: project
  date: 2026-07-22
  originSessionId: 2f9d89cf-c8ec-4cb5-8314-7d617accdaa5
  modified: 2026-07-22T20:51:01.388Z
---

# Architecture Decision Records (ADR) — ETF Monitor System

Documento di tracciamento delle decisioni architetturali passate, presenti e future.
Serve a evitare di ripetere scelte sbagliate e a documentare i checkpoint per riconsiderare il percorso.

---

## ADR-001: Scelta tra Buy Count Elastico (v2.0) vs 7 Condizioni Rigide (v4.0)

**Data Decisione**: 2026-07-22
**Status**: ⚠️ **UNDER REVIEW** (implementazione v4.0 live, ma rischi identificati)
**Stakeholder**: Andrea Pavan (user)

### Contesto
Sistema ETF Monitor con 240 asset di categorie diverse (equity, bond, crypto, commodity, leva, monetario).
Necessità di definire architettura di ingresso L1: elastica vs rigida.

### Decisione Presa
**V4.0 — 7 Condizioni TUTTE Obbligatorie**
- Allineamento, Persistenza, RSI, Distanza EMA20, ADX, MACD, Spazio Residuo
- Doppio percorso L0 (fast/slow) + regime filter
- Anti-flickering L2 (isteresi 70/60 + EMA3)
- State machine con persistenza

### Conseguenze (Pro/Contro)

**PRO**:
- ✅ Rigoroso: richiede tutte le 7, non elastico
- ✅ Quantitativo: ATR-normalized, Z-score, parametri specifici famiglia
- ✅ Sofisticato: future-proof, scalabile

**CONTRO**:
- ❌ 25-30 parametri per famiglia (350 gradi di libertà vs 110 giorni dati = OVERFITTING)
- ❌ Zero walk-forward validation (nessun backtest storico)
- ❌ Latenza L0 lento (primo rimbalzo già finito prima entry)
- ❌ Complexity: difficile debug se fallisce
- ❌ State machine a rischio DB (corruzione = incoerenza permanente)

### Rischi Identificati
- 🔴 65% probabilità di performance mediocre live (35-45% L1 profittevoli)
- 🔴 Difficile fixare se va male (black box quantitativo)

### Checkpoint di Riconsiderazione
```
⏰ 2026-08-01: Valutare risultati first month live
   IF performance < 50% profittevoli
   THEN: Riconsiderare Hybrid v3.2
   
⏰ 2026-09-01: Valutare backtest walk-forward (se fatto)
   IF overfitting confermato > 20%
   THEN: Ridurre parametri per famiglia da 25 → 12
   
⏰ 2026-10-01: Congelamento decision (min 3 mesi live)
   Mantenere v4.0 oppure rollback/pivot a alternativa
```

### Alternativa Considerata: Hybrid v3.2
**Non implementata adesso, ma documentata come backup**

Mantiene:
- ✅ 7 condizioni rigide (L1 rigoroso)
- ✅ Anti-flickering L2 (isteresi + EMA3)
- ✅ ATR normalization L0

Riduce complessità:
- ⬅️ L0: percorso singolo semplice (4 condizioni base)
- ⬅️ Parametri per famiglia: 25 → 12-15
- ⬅️ Eliminare readiness score come pre-screening (info only)

Aggiunge validazione:
- ✅ Backtest 2 settimane (2026-01 → 2026-07)
- ✅ Chop zone test (2022-2023)
- ✅ Paper trading 1 settimana

**Timeline**: 3-4 settimane (vs 5-6 per v4.0 full)
**Rischio**: 40% probabilità di performance OK live (55-60% L1 profittevoli)

---

## ADR-002: Sincronizzazione Documentale (Una Fonte di Verità)

**Data Decisione**: 2026-07-22 (PIANIFICATA, NON IMPLEMENTATA)
**Status**: 📋 **PLANNED FOR Q3 2026**
**Stakeholder**: Andrea Pavan, Claude

### Contesto
Tre fonti documentali disallineate:
1. CLAUDE.md (hardcoded parametri)
2. dashboard.html (hardcoded parametri + tabelle)
3. PDF generato (parziale, auto-gen)

Ogni modifica richiede updates manuali in 2-3 posti → errori frequenti.

### Decisione Presa
**YAML Come Fonte Unica di Verità**

```
config/etf_families_extended.yaml (MASTER)
  ↓ (read)
  ├─→ /api/parameters → JSON live
  ├─→ dashboard.html (AJAX per dati dinamici)
  ├─→ pdf_generator.py (auto-generato ogni monitor)
  └─→ CLAUDE.md (solo concetti, link a dashboard/PDF)
```

### Conseguenze
**PRO**:
- ✅ Modifica YAML → tutto sincronizzato automaticamente
- ✅ Dashboard sempre aggiornato (live)
- ✅ PDF generato ogni ciclo (no stale)
- ✅ Nessun hardcoding di numeri in HTML/Markdown
- ✅ Git history coerente (commit unico)

**CONTRO**:
- ❌ Richiede 5 ore di lavoro (Fasi 1-7)
- ❌ Testare end-to-end (API + PDF + browser)
- ❌ Possibili breaking changes durante transizione

### Implementation Plan
- **Fase 1-2** (1.5h): Estendere YAML + API endpoint
- **Fase 3-4** (1.75h): Dashboard AJAX + PDF auto
- **Fase 5-7** (1.5h): Cleanup CLAUDE.md + test + deploy

**Timeline**: 1 settimana (quando decidi di prioritizzarlo)
**Go/No-Go**: Dopo congelamento v4.0 (agosto inizio)

### Rollback Plan
Se qualcosa va storto:
```
git revert <commit-yaml-extend>
Torna a hardcoded dashboard.html (precedente versione)
Nessun dato perso (YAML è backward-compatible)
```

---

## ADR-003: Validazione di Robustezza (Backtest + Paper Trading)

**Data Decisione**: 2026-07-22 (RICHIESTA, NON ESEGUITA)
**Status**: 🔴 **CRITICAL — MUST DO BEFORE LIVE**
**Stakeholder**: Andrea Pavan

### Contesto
v4.0 implementato senza validazione storica.
Parametri probabilmente curve-fitted ai dati 2026-01 → 2026-07.
Rischio di overfitting elevato (DoF/Data = 3.18, dovrebbe essere < 0.1).

### Decisione Presa (NECESSARIA)
**Eseguire 3 fasi di validazione**

#### Fase 1: Backtest Walk-Forward (2 settimane)
```
Dati: 2020-01-01 → 2026-07-22
Suddivisione: 5 periodi × 1 anno

Per ogni periodo:
  Train: primo anno
  Test: secondo anno
  Metrica: % L1 profittevoli entro 5gg, Sharpe ratio, Max DD
  
Target: 55-65% profittevoli, Sharpe > 0.8
Alert: Se < 50% profittevoli → review parametri
Alert: Se > 70% profittevoli → possibile overfitting
```

#### Fase 2: Chop Zone Test (1 settimana)
```
Periodo: 2022-06 → 2023-12 (mercati laterali)

Contare per asset:
  - Quanti L1 falsi (loss entro 5gg): target < 8%
  - Quanti L2 flickering (oscillazioni > 10): target < 5 per asset
  - Quanti L0 scattati: target < 2 per asset
```

#### Fase 3: Live Paper Trading (1 mese)
```
Simulazione senza denaro reale
Misurare:
  - Slippage vs EMA20 entry: target < 0.7%
  - Latenza esecuzione: target < 5 min
  - Incoerenze stato: target = 0
```

### Conseguenze
**PRO**:
- ✅ Identifica overfitting prima di $ reali
- ✅ Valida state machine (incoerenze rivelate)
- ✅ Calibra aspettative (% profittevoli realistico)
- ✅ Permette rollback/pivot se necessario

**CONTRO**:
- ❌ Richiede 3-4 settimane lavoro
- ❌ Potrebbe rivelare che v4.0 non funziona (richiede rework)

### Go/No-Go
```
✅ GO live se:
   - Walk-forward: 55-65% profittevoli
   - Chop zone: < 8% L1 falsi
   - Paper trading: zero incoerenze stato

❌ NO GO live se:
   - Walk-forward: < 50% profittevoli
   - Chop zone: > 15% L1 falsi
   - Paper trading: > 2 incoerenze stato
   
→ Pivot a Hybrid v3.2 oppure v2.0 + miglioramenti
```

### Timeline Critico
```
2026-07-22: Decidi
  ├─ Opzione A: Backtest ADESSO (fine luglio)
  │  └─ Live inizio agosto se GO
  │
  └─ Opzione B: Skip backtest, live subito
     └─ 65% rischio di mediocre/disastro
```

**Raccomandazione**: Opzione A (2-3 settimane extra vs rischio elevato)

---

## ADR-004: Stop Loss Iniziale e Trailing Dinamico

**Data Decisione**: 2026-07-09
**Status**: ✅ **IMPLEMENTATO** (v4.0)
**Stakeholder**: Andrea Pavan

### Contesto
Protezione del capitale da drawdown durante L1.
Due livelli: stop loss iniziale (fisso) + trailing (dinamico).

### Decisione Presa
**Per famiglia**:
- `sl_initial_pct`: protezione iniziale (2.5% bond, 5% equity, 12% crypto)
- `trailing_base_pct`: distanza iniziale trailing (es. 8% equity)
- `trailing_sensitivity`: come si stringe col guadagno
- `trailing_min_pct`: floor minimo (non scendere sotto)

**Esempio equity_sviluppati** (entry €100):
```
Gain 0%   → SL = €95 (sl_initial_pct = 5%)
Gain +5%  → SL = €94.76 (8% di distanza da €107.5)
Gain +15% → SL = €110.92 (6% di distanza, trailing stringe)
Gain +25% → SL = €110.92 (floor minimo 94% attivo)
```

### Status Attuale
✅ Implementato in codice (technical_analysis.py)
✅ Parametri in config/etf_families.yaml
⚠️ Documentazione in CLAUDE.md vs dashboard.html disallineata

### Decisioni Future (Possibili)
- [ ] Parametrizzare ulteriormente per mercato (es. trailing_base_pct dinamico su volatilità)
- [ ] Aggiungere "hard stop" intraday (kill switch ATM livello percentuale)

---

## ADR-005: L0 Deep Recovery — Percorso Singolo vs Doppio

**Data Decisione**: 2026-07-22 (REVISIONE RICHIESTA)
**Status**: ⚠️ **UNDER REVIEW**
**Stakeholder**: Andrea Pavan, Claude

### Contesto
L0 ha due percorsi (fast/slow) per entrare:

**Lento**: Sotto SMA200 N giorni + drawdown sostenuto + reclaim EMA50
**Rapido**: Flash crash Z-score > 4 + reclaim EMA20

### Problema Identificato
- ❌ Latenza lento: primo 70% rimbalzo già finito quando entra
- ❌ Complessità: difficile debuggare quale percorso scatta
- ❌ Parametri non validati (flash_crash_zscore, giorni_SMA200, ecc)

### Opzioni

**Opzione A**: Mantieni doppio percorso (v4.0 completo)
- ✅ Sofisticato, cattura sia flash crash che bear market
- ❌ Complesso, rischioso se non validato

**Opzione B**: Semplifica a percorso singolo (Hybrid v3.2)
- ✅ Meno parametri, più debuggabile
- ❌ Perdi velocità su flash crash

### Recommendation
Implementa **Opzione B** fino a backtest walk-forward (agosto).
Se walk-forward OK, riconsiderare Opzione A in v4.1.

---

## Checklist per Sviluppi Futuri

### Prima di Aggiungere Nuove Condizioni L1/L0
- [ ] Backtest walk-forward sul periodo proposto (min 2 anni)
- [ ] Chop zone test (min 6 mesi laterali)
- [ ] Paper trading simulato (min 2 settimane)
- [ ] Documentare il razionale nel YAML (description + rationale)
- [ ] Aggiornare CLAUDE.md + dashboard.html + PDF

### Prima di Cambiare Parametri
- [ ] Backtest sensitivity analysis (come cambia il performance ±10%)
- [ ] Committare il change nel YAML (con messaggio chiaro)
- [ ] Aggiornare MEMORY.md con il checkpoint

### Prima di Considerare Rollback a v2.0
- [ ] Eseguire walk-forward su v2.0 (per confronto)
- [ ] Misurare trade-off (elastico vs rigoroso)
- [ ] Decidere consapevolmente vs "panic revert"

---

## Timeline Complessivo (Proposto)

```
22/07 (ADESSO):
  ✅ Decisione v4.0 live (con rischi noti)
  ✅ ADR documentato (possibilità future tracciabili)

01-15/08:
  Checkpoint 1: Risultati first 2 settimane live
  IF mediocre → pianifica Hybrid v3.2
  
01-31/08 (Opzionale):
  Backtest walk-forward (se decidi di farlo)
  Chop zone test
  
01-09/09:
  Paper trading simulato (1 mese)
  
01-10/09:
  Congelamento decision
  Mantenere v4.0 oppure pivot a alternativa
  
01-12/09:
  Implementare DOCUMENTATION_SYNC_SOLUTION
  (YAML → API → Dashboard → PDF)
```

---

## Come Usare Questo Documento

**Ogni settimana**:
1. Leggi i checkpoint rilevanti
2. Se performance live è mediocre → considera pivot
3. Se backtest rileva overfitting → riduci parametri

**Prima di nuove features**:
1. Leggi ADR relato
2. Aggiungi sezione nuova se è decisione importante
3. Documenta pro/contro/rischi

**Per comunicare con il team**:
1. Riferisci all'ADR specifico ("Vedi ADR-003 per validazione")
2. Evita di ripetere discussioni già fatte
3. Usa i checkpoint per decisioni go/no-go
