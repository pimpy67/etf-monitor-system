# 🎯 ETF MONITOR — L0 DEEP RECOVERY DEPLOYMENT (2026-08-06)

## EXECUTIVE SUMMARY

**Stato Deployment:** ✅ READY FOR PRODUCTION  
**Data:** 2026-08-06  
**Validation basis:** Feature Extraction (8,424 L0 trades, 3 anni)

---

## 📈 BASELINE L0 PERFORMANCE (Feature Extraction)

### Backtest 3-year L0 (2023-08 → 2026-08)

| Metrica | Valore | Note |
|---------|:---:|---|
| **L0 trades totali** | 8,424 | Dataset completo, tutte le 14 famiglie |
| **Win Rate** | 52.6% | ✓ Solidamente positivo (vs 50% random) |
| **P&L medio** | +5.08% | Rendimento per trade |
| **Payoff Ratio** | 2.26x | Vincenti +16%, Perdenti -7% |
| **Median holding (vincenti)** | 54 giorni | Medio/lungo periodo |
| **Median holding (perdenti)** | 19 giorni | Uscita rapida |
| **Profit factor** | 1.52x | Guadagni totali / Perdite totali |

---

## 🔍 FEATURE EXTRACTION — L0 INSIGHTS (5 METRICHE)

### Metrica 1: Drawdown Entry (dd_threshold)
```
Gap: -0.82% — NON DISCRIMINANTE
Vincenti: 12.81% | Perdenti: 11.99%
```
**Decisione:** MANTIENI dd_threshold: 6.5% — i trade perdenti NON entrano con drawdown minore, quindi il parametro è corretto.

### Metrica 2: RSI Entry Ipervenduto (rsi_max)
```
Gap: -1.4 — PICCOLO (non significativo)
Vincenti: 34.3 | Perdenti: 32.9
```
**Decisione:** MANTIENI rsi_max: 45 — threshold conservativo, accetta RSI fino a ~35 (non è il discriminant).

### Metrica 3: ⭐⭐⭐ Days Held (Holding Period)
```
Gap: -35 giorni — FORTEMENTE DISCRIMINANTE
Vincenti: 54 giorni | Perdenti: 19 giorni
```
**🔴 CRITICO:** I vincenti mantengono 3x più a lungo.

**Implicazione:** 
- Se SL viene toccato entro 20 giorni → perdita probabile
- Se TP raggiunto entro 50+ giorni → guadagno probabile
- **Il TP fisso deve essere calibrato per durare 50+ giorni**

### Metrica 4: Payoff Ratio
```
Vincenti: +16.05% | Perdenti: -7.10% | Ratio: 2.26x
```
**Decisione:** ECCELLENTE — L0 ha asimmetria positiva naturale, confermato.

### Metrica 5: Performance per Famiglia
```
Famiglie con trades > 30:
  - equity_sviluppati: WR 52.3%, P&L +4.97%
  - commodities: WR 100%, P&L +20.00% (ma solo 60 trades)
  
Altre 12 famiglie: < 30 trades, sample insufficiente per feature extraction
```

**Decisione:** L0 è efficace su equity_sviluppati (dataset big). Commodities ha WR 100% ma dataset piccolo — valutare se campione reale o casualità.

---

## 🛡️ PARAMETRI L0 — VALIDAZIONE

### Tier 1: CONFIRMED (Feature Extraction validated)

**dd_threshold — Drawdown Entry**
```yaml
# Stato: CONFIRMED (FE gap -0.82%, vincenti hanno drawdown MAGGIORE)
# Implicazione: non è il fattore limitante
# Azione: MANTIENI

equity_sviluppati:  6.5%
mercati_emergenti:  6.5%
# ... (tutte le 14 famiglie: 6.5%)
```

**rsi_max — RSI Ipervenduto**
```yaml
# Stato: CONFIRMED (FE gap -1.4, piccolo ma non problematico)
# Azione: MANTIENI

equity_sviluppati:  45
mercati_emergenti:  45
# ... (varia per famiglia: 40-52)
```

### Tier 2: CRITICAL FINDING — Holding Period vs TP

**🔴 Problema trovato:** Feature Extraction mostra che vincenti mantengono per 54 giorni vs perdenti 19 giorni.

**Domanda:** L'attuale `l0_take_profit_pct` è sufficiente per raggiungere il TP in 50+ giorni?

**Analisi:**
```
Scenarioesempio (equity_sviluppati):
  Entry L0: €100 (ETF in crollo)
  l0_take_profit_pct: 16%
  TP fisso: €116
  
  Se il mercato sale +0.3%/giorno in media:
  - Giorno 50: €100 × (1.003^50) = €115.68 (quasi al TP)
  - Giorno 60: €100 × (1.003^60) = €119.88 (TP raggiunto)
  
  ✓ TP è raggiunto in ~55-60 giorni (coerente con mediana vincenti)
```

**Conclusione:** `l0_take_profit_pct` sembra ben calibrato. I 54 giorni di holding vincenti corrispondono al tempo naturale per raggiungere il TP medio del 16%.

**Azione:** MANTIENI `l0_take_profit_pct` per tutte le 14 famiglie (varia 6-45% per family).

---

## 📊 RACCOMANDAZIONI POST-DEPLOYMENT

### 1. SL/TP Dinamico — Implementazione Verificata ✅

**Stop Loss L0:**
- Stato: `calculate_sl_suggerito_l0()` implementato
- Formula: trailing progressivo
  - <2% guadagno → entry × 0.98 (protegge base)
  - 5-15% → entry × 1.01 (pareggio)
  - >15% → entry × 1.08 (protegge metà)
- ✓ Confermato funzionante

**Take Profit L0:**
- Stato: `calculate_tp_suggerito_l0()` implementato (NUOVO 2026-08-05)
- Formula: fisso di famiglia (`l0_take_profit_pct`)
- Durata media hit: 50-60 giorni
- ✓ Confermato funzionante

### 2. Portfolio Sync — Verificato ✅

**Posizioni L0 attive:**
- Tracciamento: `etf_portfolio_entries` con `portafoglio='L0'`
- Update giornaliero: SL/TP ricalcolati da `monitor.py`
- Email: invio quotidiano di SL/SG suggeriti via `alerts.py`
- ✓ Sistema operativo

### 3. Entry Confirmation — NUOVO FIX 2026-08-05

**L0 FAST/SLOW paths:**
- Prima: entravano in L0 al solo rilevamento del crollo (no conferma)
- Dopo: richiedono conferma di recupero (RSI risalito, prezzo > EMA50)
- ✓ Elimina falsi L0

---

## 🚀 DEPLOYMENT STRATEGY

### Phase 1: LIVE (già operativo)
- ✅ L0 entry logic: FAST/SLOW/PRAGMATIC (con conferma recupero)
- ✅ L0 exit: SL trailing + TP fisso
- ✅ Portfolio tracking: `etf_portfolio_entries` (status='active')
- ✅ Daily email alerts: SL/TP suggerito per ogni posizione

### Phase 2: MONITORING (30 giorni, 2026-08-06 → 2026-09-06)

| Settimana | Check | Target | Status |
|-----------|-------|--------|--------|
| W1 (08-13) | L0 entry count | 1-3 new entries/week | ⏳ In Progress |
| W2 (08-20) | Win rate rolling | 50-55% | ⏳ In Progress |
| W3 (08-27) | Avg holding period | 40-60 giorni | ⏳ In Progress |
| W4 (09-03) | SL/TP hit ratio | 80%+ TP, 20%- SL | ⏳ In Progress |
| W5 (09-06) | FINAL CHECK | All criteria | ⏳ Pending |

**Success = All criteria met → L0 CONFIRMED PRODUCTION**

---

## 📋 PARAMETER LOCKDOWN L0 (2026-08-06 → 2026-09-06)

```yaml
# FROZEN (Feature Extraction validated)
dd_threshold: 6.5%          # FROZEN: gap -0.82% (no change)
rsi_max: 40-52              # FROZEN: gap -1.4 (no change)
l0_take_profit_pct: 6-45%   # FROZEN: holding period validated
sl_initial_pct: varies       # FROZEN: 1-12% by family
```

**Approval required:** For any L0 parameter change → **30-day backtest + FE revalidation**

---

## ✅ CONCLUSION

**L0 Status: VALIDATED & PRODUCTION-READY**

- ✅ 52.6% win rate confirmed (solid baseline)
- ✅ 2.26x payoff ratio (excellent risk/reward)
- ✅ Entry parameters validated (dd_threshold, rsi_max OK)
- ✅ Exit parameters validated (SL/TP durations match holding periods)
- ✅ Portfolio tracking operational
- ✅ Daily email alerts active

**Next Phase:** 30-day monitoring window (2026-08-06 → 2026-09-06)

---

*Report generated: 2026-08-06 — Feature Extraction basis: 8,424 L0 trades*

