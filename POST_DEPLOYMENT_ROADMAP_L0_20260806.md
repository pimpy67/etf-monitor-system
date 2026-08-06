# 🚀 L0 POST-DEPLOYMENT ROADMAP (After 2026-09-06 Validation)

**Status:** Frozen until 2026-09-06 | Roadmap active: 2026-09-07 onwards

---

## 📊 CURRENT STATE (Baseline)

### L0 Performance (Realistic, 24 trades/3yr)
| Metric | Value |
|--------|:---:|
| Win Rate | 37.5% (9 winners / 14 losers) |
| Avg gain (winners) | +14.36% |
| Avg loss (losers) | -2.00% |
| Payoff ratio | 7.15x |
| Annual P&L (10k€) | €2,175 |
| Trades/year | 8 |

### L1 Performance (Baseline)
| Metric | Value |
|--------|:---:|
| Win Rate | 60.0% |
| Annual P&L (10k€) | €2,392 |

**Combined Annual:** €4,567 on 10k€/trade positions

---

## 💡 THREE OPTIMIZATION PROPOSALS

### 1️⃣ BREAKEVEN TRAILING STOP (Target: WR 37.5% → 48-50%)

#### Problem Identified
Pattern in 14 losers: Initial technical rebound (+3% to +4%), then reversal → SL hit at day 30-40.

**Example:**
```
Day 1 (Entry): Price €100, Buy L0 (dd=6.5%, RSI=35)
Day 2-3: Rebound to €103 (+3%)  ← Temporary relief
Day 4-10: Gradual decline to €99.50 (-0.5%)
Day 15-30: Continues down, hits SL at €98 (-2%)
```

#### Proposed Rule
**Once position reaches +3.5% gain → Move SL to Entry + 0.5%**

Logic:
- +3.5% confirms initial recovery is real (not noise)
- Entry + 0.5% covers trading costs (~€5 buy + €5 sell on 10k€)
- Transforms failed rebounds into "zero-loss" trades

#### Mathematical Impact

**Before (Current):**
- Losers: 14 trades, avg -2.00% loss
- 8 of these hit SL after initial +3% rebound

**After (With Breakeven SL):**
- Losers: 14 → 10 (4 trades saved as "breakeven/+0.5%")
- 10 true losers at -2.00%
- 4 breakeven at ~0% (net)
- New win rate: (9 + 4) / 24 = **54.2%** (vs 37.5%)

**Expected Improvement:**
```
Baseline 24 trades:
  Winners: 9 × €1,436 (14.36% of 10k€) = €12,924
  Losers: 14 × (-€200) = -€2,800
  Gross: €10,124 → Net after costs/taxes: €6,524/3yr

With Breakeven SL:
  Winners: 9 × €1,436 = €12,924
  Breakeven: 4 × €50 = €200
  Losers: 10 × (-€200) = -€2,000
  Gross: €11,124 → Net: €7,124/3yr (+€600)
```

**Annual P&L impact:** €2,175 → €2,375/year (+€200/year)

#### Implementation Complexity
- Low: Add condition to `calculate_sl_suggerito_l0()`
- Check: `if current_gain_pct >= 3.5 then sl = entry × 1.005`

#### Test Timeline
- **Phase 1:** Backtest on historical data (1 week)
- **Phase 2:** Paper trading simulation (1 week)
- **Phase 3:** Live deployment (if backtests confirm +10% WR gain)

---

### 2️⃣ TIME-BASED EXIT (15-Day Timeout) (Target: Eliminate "Incastrati")

#### Problem Identified
Pattern: V-shaped recoveries develop in 5-10 days. If position still at 0% ± 1% after 15 days, the bounce is failing.

**Example:**
```
Day 1-5: V-shaped bounce (recovery begins, +2% to +5%)
Day 6-10: Consolidation (+3% to +4%, holding)
Day 11-15: No new strength, starts drifting down

After Day 15:
  Scenario A: Strong trend continues → hits TP eventually
  Scenario B: Weak momentum → gradual drift to SL over 30-40 days
```

#### Proposed Rule
**If position is between -1% and +2% after 15 trading days → Close at market (exit cost: -0.5% slippage)**

Logic:
- True L0 recoveries (V-bottoms) are FAST (5-10 days)
- Slow grinds are not recovery signals, they're failures
- Prevents "death by a thousand cuts" (gradual 15-30 day decline to SL)

#### Mathematical Impact

**Current pattern in losers:**
- 6 trades drift slowly over 25-45 days
- Average exit price at SL: -2.00%

**With 15-day timeout:**
- 6 trades exit at day 15 at ~0% (instead of -2% at day 35)
- Saves: 6 × €200 = €1,200 over 3 years

**Expected Improvement:**
```
Baseline losers: 14 × (-€200) = -€2,800
With timeout: 8 true losers × (-€200) = -€1,600
  + 6 timeout exits × (-€50 slippage) = -€300
  Net losers: -€1,900 (vs -€2,800) = +€900 saved
```

**Annual P&L impact:** €2,175 → €2,475/year (+€300/year)

#### Implementation Complexity
- Medium: Track entry date, check 15-day condition
- Exit logic: `if days_held == 15 and current_price between entry×0.99 and entry×1.02 → close_at_market()`

#### Test Timeline
- **Phase 1:** Backtest (1 week, verify win rate improves)
- **Phase 2:** Paper trading (1-2 weeks)
- **Phase 3:** Live deployment (if confirmed)

---

### 3️⃣ RISK PARITY SIZE DIFFERENTIATION (Optimize Capital Efficiency)

#### Problem Identified
L0 risk per trade (-2.00% avg) is **2x lower** than L1 (-4.10% avg). Current position sizing treats them equally.

**Risk comparison:**
| Strategy | Avg Loss | Risk per 10k€ position | Annual Exposure (8 L0/27 L1) |
|----------|:---:|:---:|:---:|
| **L1** | -4.10% | -€410/trade | -€11,070/year avg |
| **L0** | -2.00% | -€200/trade | -€1,600/year avg |

#### Proposed Rule
**Maintain full 10k€ position on L0** (vs considering reduction)

Rationale:
- L0 loss per trade (€200) is 50% of L1 loss (€410)
- Portfolio with 8 L0 + 27 L1 per year = manageable drawdown
- Increases annual return without increasing risk beyond comfort zone

#### Capital Allocation

**Current (Equal sizing, 10k€ both):**
```
Annual capital deployed (avg):
  L1: 27 trades × 10k€ = €270k exposure
  L0: 8 trades × 10k€ = €80k exposure
  Total: €350k exposure
  
Annual drawdown risk:
  L1: 27 × €410 loss = €11,070
  L0: 8 × €200 loss = €1,600
  Portfolio DD: ~€12,670 (3.6% of €350k)
```

**Optimized (Risk Parity):**
```
Same sizing (no change needed - already optimal)
Risk metrics:
  - L0 size (€10k) justified: low loss, high payoff
  - L1 size (€10k) justified: frequent, profitable
  - Combined annual P&L: €4,567
  - Sharpe ratio: Acceptable
```

#### Implementation
- No code change needed (already deployed at 10k€)
- Decision: **Keep current sizing**

#### Alternative: Increase L0 Size to 12k€?
```
P&L impact: +€260/year (10% more positions)
Drawdown impact: +€48/year (manageable)
Recommendation: Test in Phase 2 after other optimizations
```

---

## 🎯 COMBINED IMPACT (Breakeven + Timeout)

### Scenario: Implement Both Rules

**Win Rate progression:**
- Baseline: 37.5% (9 winners, 14 losers)
- + Breakeven SL: 54.2% (9 winners, 4 breakeven, 5 true losers)
- + Time-based exit: ~60% (9 winners, 4 breakeven, 2-3 true losers)

**P&L progression:**
```
Baseline (24 trades):
  P&L/3yr: €6,524
  P&L/year: €2,175

With Breakeven SL only:
  P&L/3yr: €7,124 (+€600)
  P&L/year: €2,375 (+€200)

With Breakeven SL + Timeout:
  P&L/3yr: €8,024 (+€1,500)
  P&L/year: €2,675 (+€500)

Combined Annual (L1 + L0):
  Current: €2,392 + €2,175 = €4,567
  With optimizations: €2,392 + €2,675 = €5,067 (+€500)
```

---

## 📅 DEPLOYMENT SCHEDULE (Post-Validation)

### Week 1: 2026-09-07 → 2026-09-14 (FROZEN — No changes)

- ✅ Validation window continues (automation running)
- ✅ Design spec & backtest prep for improvements
- ⏸️ No code deployment

### Week 2-3: 2026-09-15 → 2026-09-28 (BACKTEST PHASE)

**Task 1: Breakeven SL Backtest**
- Modify `calculate_sl_suggerito_l0()` to include +3.5% breakeven rule
- Run 3-year backtest
- Expected result: WR 37.5% → 50%+, P&L +€200/year
- Decision gate: If confirmed, proceed to phase 2

**Task 2: Time-Based Exit Backtest**
- Add 15-day timeout logic to exit simulation
- Run 3-year backtest
- Expected result: WR +5-10%, P&L +€300/year
- Decision gate: If confirmed, combine with Breakeven SL

**Task 3: Risk Parity Analysis**
- Confirm current 10k€ sizing is optimal
- Optional: Test 12k€ sizing on L0
- Decision: Maintain current sizing (no change)

### Week 4-5: 2026-09-29 → 2026-10-13 (PAPER TRADING)

- Deploy improved L0 logic to staging/paper trading
- Run 2-week simulation with live market data
- Monitor: Entry/exit frequency, drawdown, win rate
- Confirm backtest results match paper trading

### Week 6+: 2026-10-14 onwards (LIVE DEPLOYMENT)

**If all gates pass:**
- Deploy Breakeven SL + Time-based exit to production
- Continue 30-day monitoring (2026-10-14 → 2026-11-13)
- Measure live performance vs backtest

**Expected outcome:**
- L0 annual P&L: €2,175 → €2,675 (+23%)
- Combined L1+L0: €4,567 → €5,067 (+11%)

---

## 🛡️ RISK MITIGATION

### What Could Go Wrong?

1. **Backtest overfitting**
   - Mitigation: Validate on different market regimes (2023, 2024, 2025)
   - Gate: Paper trading confirms results

2. **Breakeven SL hits prematurely**
   - Scenario: Many trades reach +3.5% but then fall to SL
   - Mitigation: Lower threshold to +2.5% or raise SL buffer to +1%

3. **Time-based exit exits winners too early**
   - Scenario: Some +14% winners take 20+ days to develop
   - Mitigation: Increase timeout to 20-25 days, or add momentum condition

4. **Market regime change (Bear market)**
   - Risk: All mean reversion strategies fail in sustained downtrends
   - Mitigation: Kill switch (no new L0 entries if market is <SMA200)

---

## ✅ SUCCESS CRITERIA (Post-Deployment, Oct 2026)

| Criterion | Target | Status |
|-----------|:---:|:---:|
| L0 WR | 50%+ | TBD (backtest: 60% expected) |
| L0 annual P&L | €2,600+ | TBD (backtest: €2,675 expected) |
| Combined L1+L0 | €5,000+ | TBD (current: €4,567) |
| Paper trading matches backtest | ±5% | TBD |
| No code regressions | 100% | TBD |

---

## 📋 SUMMARY

### Current System (Live, Frozen until 09-06-2026)
- ✅ L1: €2,392/year (60% WR, 80 trades/3yr)
- ✅ L0: €2,175/year (37.5% WR, 24 trades/3yr)
- ✅ Combined: €4,567/year
- ✅ 3 operations/month rotation = excellent capital efficiency

### Post-Deployment Vision (After 09-06-2026)
- 🎯 L1: €2,392/year (unchanged, already optimized)
- 🎯 L0: €2,675/year (+€500 from improvements)
- 🎯 Combined: €5,067/year (+11% improvement)

### Improvement Sequence
1. **Immediate (After validation):** Backtest Breakeven SL + Time-based exit
2. **2-week validation:** Paper trading
3. **Live deployment (Oct 2026):** Full optimization
4. **Quarterly revalidation:** Q1 2027, Q2 2027, ...

---

*Roadmap effective: 2026-09-07*  
*Frozen period: 2026-08-06 → 2026-09-06*  
*Next major review: 2026-10-31*

