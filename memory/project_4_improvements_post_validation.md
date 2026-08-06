---
name: project_4_improvements_post_validation
description: 4 high-impact quantitative refinements for system v5.0 (deploy after 2026-09-06 validation)
metadata: 
  node_type: memory
  type: project
  originSessionId: e67eaca6-74dc-4036-81a9-5dc2cb642f2d
  modified: 2026-08-06T14:26:04.506Z
---

# 🚀 4 Areas of Improvement — Post-Validation Roadmap (2026-09-07+)

**Freeze Window:** 2026-08-06 → 2026-09-06 (30 giorni — NO CODE CHANGES)  
**Rationale:** Disciplina del trading sistematico = frozen parameters during out-of-sample validation ≠ curve-fitting continuo  
**Target:** Implement whichever 2-3 of these 4 show strongest backtest validation by 2026-10-15

---

## 🎯 Area 1: Position Sizing Basato su Volatilità (ATR Sizing)

**Problema Attuale:**
- Alloca sempre €10.000 per posizione L1, indipendentemente dalla volatilità dell'ETF
- Un ETF volatile (es. mercati emergenti: ATR ~3%) rischia €300 netto sui stop loss
- Un ETF stabile (es. MSCI World: ATR ~1.5%) rischia €150 netto sui stop loss
- **Asimmetria di rischio:** Il portafoglio è vulnerabile ai picchi di volatilità su asset specifici

**Soluzione Proposta:**
```yaml
# Pseudocodice
entry_sl_pct = 5%  # SL iniziale standard
atr_normalized = current_atr / current_price
target_risk_per_trade = €300  # Risk budget fisso per trade

position_size = target_risk_per_trade / (entry_sl_pct × current_price)
  # IF atr_normalized HIGH (es. 3%) → smaller size (es. €7.000)
  # IF atr_normalized LOW (es. 1%) → larger size (es. €12.000)
```

**Implementazione:**
1. Calcola ATR14 per ogni ETF in `technical_analysis.py`
2. In `monitor.py::suggest_l1_entry()`, calcola `position_size = risk_budget / (sl_pct × price)`
3. Salva in `etf_portfolio_entries.suggested_size` per email SL/TP

**Vantaggio Atteso:**
- ✅ Risk per trade **equalizzato** su tutti gli ETF
- ✅ Riduce picchi di perdita sui singoli asset volatili
- ✅ Migliora Sharpe ratio (~0.8 → 0.95 stimato)
- ✅ Nessun impatto su Win Rate (entry/exit logic unchanged)

**Backtest Priority:** HIGH  
**Expected P&L Impact:** +€200-400/anno (migliore risk-adjusted returns)

---

## ⏱️ Area 2: Time-Based Exit per Inerzia (20-Day Timeout)

**Problema Attuale:**
- Una posizione rimane aperta finché non tocca SL o TP (media 29 gg per L1)
- Se il trend perde forza dopo 15-20 giorni di borsa aperta, la posizione rimane "incastrata" (flat, −1% to +1%)
- Capital non viene riciclato velocemente sui nuovi segnali L1 freschi
- **Costo opportunità:** Posizione stagnante blocca liquidità per 10-15 giorni extra

**Soluzione Proposta:**
```
SE giorni_aperti >= 15 
   AND prezzo BETWEEN (entry × 0.99, entry × 1.01)  # ±1%
ALLORA: chiudi a mercato (exit price ≈ prezzo attuale)
```

**Implementazione:**
1. Aggiungi `days_open` tracking in `etf_portfolio_entries.entry_date`
2. In `monitor.py::check_l1_exit()`, aggiungi regola time-based
3. Exit con slippage cost (~€20 per −0.5%)

**Vantaggio Atteso:**
- ✅ Libera liquidità ~2 settimane prima
- ✅ Elimina "dead money" immobilizzato
- ✅ Migliora turnover capitale (27 → 30 trade/anno)
- ✅ Riduce esposizione a consolidamenti laterali

**Backtest Priority:** MEDIUM  
**Expected P&L Impact:** +€250-350/anno (migliore capital efficiency)

---

## 💎 Area 3: Breakeven Trailing Stop Chirurgico su L0

**Problema Attuale:**
- L0 entra su drawdown ≥6.5%, ATR ipervenduto, divergenza rialzista
- Nei primi 3-5 giorni: rimbalzo naturale +3-4%
- Poi: graduale erosione (−0.5% al giorno) che tocca il SL a giorno 30-40
- **Risultato:** 14 trade perdenti su 24 totali (58%) → tanti finiscono per inertia al SL

**Soluzione Proposta:**
```
SE posizione_l0_aperta >= 3_giorni 
   AND guadagno >= 3.5%
ALLORA: sposta SL a (entry_price + 0.5%)
  # 0.5% copre le commissioni (€5 buy + €5 sell = ~€1 su €10k = 0.1% × 2 = 0.2%)
```

**Implementazione:**
1. In `calculate_sl_suggerito_l0()`, aggiungi condizione breakeven
2. Se `current_gain_pct >= 3.5` e `days_held >= 3`: `sl = entry × 1.005`
3. Email giornaliera aggiornata con nuovo SL protettivo

**Vantaggio Atteso:**
- ✅ Win Rate L0: 37.5% → 45-50% (salva 4-6 trade dall'SL)
- ✅ Pareggia i trade "falsi rimbalzi" (non perde ma non guadagna)
- ✅ Mantiene il payoff ratio alto (ancora 7x+ sui veri vincitori)
- ✅ Riduce frustrazione operativa (meno "quasi-vincenti" convertiti a perdenti)

**Backtest Priority:** HIGHEST (impatto immediato su L0)  
**Expected P&L Impact:** L0 €2.175/anno → €2.400-2.500/anno (+€225-325)

---

## 🌍 Area 4: Filtro Macro Unificato su MSCI World

**Problema Attuale:**
- Regime filter verifica la SMA200 del **singolo ETF**
- Un ETF può essere in trend rialzista personale mentre il mercato globale è in bear
- Esempio: INRG (green energy) salisce mentre IWDA (world) è sotto SMA200
- **False positive:** Entra L1 su un'anomalia settoriale in regime macro bear

**Soluzione Proposta:**
```
# Aggiungi controllo ombrello MSCI World
IF regime_msci_world == BEAR:
   - Nega TUTTI i nuovi ingressi L1 (indipendentemente dal singolo ETF regime)
   - Permette solo L0 come hedge
   - Nega anche nuove L0 (già fatto dal regime filter attuale)
   
IF regime_msci_world == BULL:
   - Procedi con regime check standard (singolo ETF)
```

**Implementazione:**
1. Fetch daily MSCI World (ticker: `IWDA` o `ACWX`) via `data_fetcher.py`
2. Calcola SMA200 e regime su MSCI World separatamente
3. In `suggest_level()`, aggiungi gate: `if regime_macro_world == BEAR: block_l1_entry`

**Vantaggio Atteso:**
- ✅ Elimina anomalie settoriali entry nel bear market globale
- ✅ Riduce false L1 entries durante correzioni macro (~5-10% meno ingressi in bear)
- ✅ Mantiene l'edge durante BULL market (regime check singolo ETF ancora attivo)
- ✅ Syncronizza il portafoglio con il ciclo macroeconomico globale

**Backtest Priority:** MEDIUM  
**Expected P&L Impact:** +€100-200/anno (riduce worst-case drawdowns durante bear globali)

---

## 📊 Summary: Ranking by Impact

| # | Area | P&L Gain | WR Gain | Implementation | Priority | Go-Live |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Breakeven SL L0 | +€250 | +7-12pp | 🟢 Easy (one function) | **HIGHEST** | 2026-09-15 |
| 2 | ATR Sizing | +€300 | ±0 | 🟡 Medium (new logic) | **HIGH** | 2026-09-22 |
| 3 | Macro Filter MSCI | +€150 | −2-5% | 🟡 Medium (new fetch) | HIGH | 2026-10-06 |
| 4 | Time-Based Exit | +€300 | ±0 | 🟡 Medium (state tracking) | MEDIUM | 2026-10-13 |

---

## 🔒 Governance: Why Freeze Until Sept 6?

**The Discipline of Out-of-Sample Validation:**

```
Curve-Fitting Death Spiral:
  Day 1: "L1 WR is 60%, perfect!"
  Day 2: "One bad trade today, let me adjust RSI range..."
  Day 3: "Another loser, lower ADX threshold..."
  Day 4: "Change mm200_distance..."
  → By Week 2: You've "optimized" the parameters to fit the 1 week of live noise
  → Result: Backtest 80%, live 35% (system is overfit to noise)

Out-of-Sample Discipline:
  Freeze all parameters for 30 days (Aug 6 → Sept 6)
  Collect live market data
  Only THEN backtest the 4 improvements on the entire dataset
  → Proves the refinement works on unseen data, not just the live week
```

**Decision Rule (2026-09-06):**
1. If live validation PASSES (L1 WR 50-70%, all checks green):
   - ✅ Parameters are VALID
   - ✅ Proceed with backtest on all 4 areas
   - ✅ Deploy 2-3 highest-impact improvements by 2026-10-15

2. If live validation FAILS (L1 WR <50% or >70%):
   - 🔴 Parameter set is at risk
   - 🔴 Do NOT deploy improvements
   - 🔴 Investigate root cause, consider rollback

---

## 📅 Implementation Timeline (Post-Validation)

### Week 1 (Sept 7-14): Backtest Phase
- Run 3-year backtest on each of the 4 improvements independently
- Rank by P&L gain, WR improvement, Sharpe ratio
- Select top 2-3 for deployment

### Week 2-3 (Sept 15-28): Paper Trading
- Deploy improved logic to staging (non-live VPS)
- Simulate 2 weeks of live market data
- Confirm backtest results match simulation

### Week 4-5 (Sept 29 - Oct 13): Live Deployment
- Merge to main, deploy highest-impact improvement first
- Monitor for 1 week, rollback if needed
- Deploy next improvement

### Week 6+ (Oct 14+): Monitoring
- 30-day monitoring of new improvements
- Measure live P&L against backtest predictions
- Adjust parameters if needed (only minor tuning)

---

## 🎓 Key Principle

**Better 30 days of frozen perfection than 30 days of continuous tweaking.**

The system is already optimal (60% WR, 9.1% ROA). These 4 areas are "nice-to-have" optimizations, not fixes. By resisting the urge to tweak during validation, we preserve the integrity of the model and ensure any improvements are backed by real data, not just hindsight bias from last week's trades.

---

**Last Updated:** 2026-08-06  
**Freeze Window:** 2026-08-06 → 2026-09-06  
**Implementation Start:** 2026-09-07 (if validation passes)

