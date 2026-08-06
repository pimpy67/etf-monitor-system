---
name: project_capital_allocation
description: Capital requirements and ROA for L1+L0 strategies at different scales
metadata: 
  node_type: memory
  type: project
  originSessionId: e67eaca6-74dc-4036-81a9-5dc2cb642f2d
  modified: 2026-08-06T14:25:19.203Z
---

# 💰 Capital Allocation Guide — L1+L0 Strategies

**Baseline:** 3-year backtest validation (80 L1 trades @ 60% WR, 24 L0 trades @ 37.5% WR)

---

## Quick Reference Table

| Capitale | L1 Posizioni | L0 Posizioni | P&L Annuale | ROA | Note |
|:---:|:---:|:---:|:---:|:---:|---------|
| **€10k** | 1 × €10k | — | €239 | 2.4% | Troppo piccolo, solo L1 raro |
| **€20k** | 2 × €10k | — | €955 | 4.8% | 1-2 L1 concurrent, niente L0 |
| **€30k** | 3 × €10k | — | €1.433 | 4.8% | 3 L1 mixed, migliore rapporto L1-only |
| **€40k** | 3 × €10k | 1 × €10k | €3.176 | 7.9% | 3 L1 + 1 L0, buon mix |
| **€50k** ✅ | 3 × €10k | 2 × €10k | €4.567 | 9.1% | **RECOMMENDED — optimal parallelization** |
| **€70k** | 4 × €10k | 3 × €10k | €6.500+ | 9.3% | Aggressive, surplus per fluttuazioni |

---

## Scenario Dettagliato: €50k (RACCOMANDATO)

### Allocazione Iniziale
```
Portafoglio €50.000 (€1 = 1 EUR)
│
├─ L1 Strategy: €30.000
│  ├─ Posizione #1: €10.000 (entry day 1)
│  ├─ Posizione #2: €10.000 (entry day 10)
│  └─ Posizione #3: €10.000 (entry day 20)
│
├─ L0 Strategy: €20.000
│  ├─ Posizione #1: €10.000 (deep buy day 2)
│  └─ Posizione #2: €10.000 (deep buy day 15)
│
└─ Liquidità Residua: €0 (tutto deployato, costante riciclo)
```

### Holding & Rotazione
- **L1 duration:** 29 giorni in media
  - Entry giorno 1 → Exit giorno 30
  - Capital ricicla ogni 29gg
  - ~27 trades/anno su €30k = ~1 new entry ogni 13 giorni

- **L0 duration:** 41 giorni in media
  - Entry giorno 2 → Exit giorno 43
  - Capital ricicla ogni 41gg
  - ~8 trades/anno su €20k = ~1 new entry ogni 6-7 settimane

### P&L Atteso
```
L1 Rendimento:
  27 trades/anno × €10.000 per trade
  × 60% WR
  × (5.17% avg winner − 4.29% avg loser)
  − Costs (€5 buy + €5 sell)
  − Tasse (26% flat)
  = €2.392/anno netto

L0 Rendimento:
  8 trades/anno × €10.000 per trade
  × 37.5% WR
  × (+14.36% avg winner − 2.00% avg loser)
  − Costs (€5 buy + €5 sell)
  − Tasse (26% flat)
  = €2.175/anno netto

TOTALE: €4.567/anno su €50.000 = 9.1% ROA
```

---

## Scenario Piccolo: €20k (MINIMO VIABILE)

```
Portafoglio €20.000
│
├─ L1 Strategy: €20.000
│  ├─ Posizione #1: €10.000 (entry day 1)
│  └─ Posizione #2: €10.000 (entry day 15)
│
└─ L0 Strategy: €0 (skip, budget insufficiente)
```

**P&L Atteso:** €955/anno = 4.8% ROA

**Limite:** Solo L1, niente L0. Poco diversificato.

---

## Scenario Aggressivo: €70k+ (SURPLUS)

```
Portafoglio €70.000
│
├─ L1 Strategy: €40.000
│  ├─ Posizione #1: €10.000
│  ├─ Posizione #2: €10.000
│  ├─ Posizione #3: €10.000
│  └─ Posizione #4: €10.000
│
├─ L0 Strategy: €30.000
│  ├─ Posizione #1: €10.000
│  ├─ Posizione #2: €10.000
│  └─ Posizione #3: €10.000
│
└─ Liquidità Cuscinetto: €0 (optionale, 10% = €7.000)
```

**P&L Atteso:** €6.500+/anno = 9.3% ROA

**Vantaggio:** Più posizioni concurrent = meno "downtime" tra trades.

---

## Scaling Strategy (Se Inizi Piccolo)

### Anno 1: €20.000 → €30.000
```
Start: €20.000
Target: L1 only (2 posizioni concurrent)
P&L: €955 (year 1)
→ Reinvesti il 50% dei profitti (€477)
End of Year 1: €20.477 → round up to €25.000 (aggiunta manuale)
```

### Anno 2: €30.000 → €45.000
```
Start: €30.000 (3 L1 concurrent)
Add L0: €1 posizione quando disponibile
P&L: €1.433 (year 2)
→ Reinvesti il 100% (€1.433)
End of Year 2: €31.433 → €40.000 (aggiunta + reinvestimento)
```

### Anno 3: €50.000 (TARGET RAGGIUNTO)
```
Start: €40.000
Full L1 + L0 mix: 3 L1 + 2 L0
P&L: €3.500-€4.000 (year 3)
→ Compounding year-over-year
Projected Anno 4: €54.000+
```

---

## Considerazioni Pratiche

### Commissioni Directa
- **Acquisto:** €5 flat (indipendente dalla size)
- **Vendita:** €5 flat
- **Impatto relativo:**
  - Su €10k = 0.1% (minimo)
  - Su €5k = 0.2% (leggero)
  - Su €1k = 1% (oneroso)

### Tassazione 26%
- Solo sulle **plusvalenze** (non si compensa con minusvalenze in questo modello semplificato)
- Nel backtest: già scontata al netto

### Drawdown Massimo Tollerato
- **L1 alone:** ~5-7% (stop loss iniziale a 5%)
- **L0 alone:** ~2-5% (rare mean-reversion crash)
- **Combined (€50k):** ~€2.000-€2.500 max drawdown contemporaneo
  - 3 L1 × €500 = €1.500
  - 2 L0 × €200 = €400
  - Total: ~€2.000 max (4% del portfolio)

---

## Decisione: Quanto Allocare?

**Raccomandazione:** Inizia con quello che puoi, ma punta a **€50.000** in 2-3 anni.

| Situazione | Scelta |
|-----------|--------|
| Ho €10-15k | Inizia con L1 only, aspetta 2 anni per L0 |
| Ho €20-30k | L1 full mix, skip L0 per ora |
| Ho €40-50k | **Deploy entrambi** — configurazione ottimale |
| Ho €70k+ | Deploy aggressivo + cuscinetto di liquidità |

---

**Last Updated:** 2026-08-06  
**Next Review:** After 30-day validation window (2026-09-06)

