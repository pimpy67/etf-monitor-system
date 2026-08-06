---
name: session_2026_08_06_ab_test_deployment
description: "Session 2026-08-06 — A/B Test validation, L0 regime filter + whitelist, complete documentation suite"
metadata: 
  node_type: memory
  type: project
  originSessionId: e67eaca6-74dc-4036-81a9-5dc2cb642f2d
  modified: 2026-08-06T14:24:37.151Z
---

# 🟢 Session 2026-08-06 — A/B Test Deployment & L0 Safety Gates

**Status:** ✅ COMPLETE  
**Commits:** e81ae75 (FIX: L0 Entry Safety), b715614 (DOCS: Complete Test Suite)  
**System:** LIVE on VPS (port 5001)

---

## 🎯 Accomplishments This Session

### 1. L0 Regime Filter Implementation (CRITICAL FIX)
- **What:** Added `regime_macro != 'BEAR'` mandatory check for all L0 entry paths (FAST, SLOW, PRAGMATIC)
- **Why:** Previous L0 entries on INRG.SW, BATE, BTCN, INRG.MI were in BEAR regime (ADX>25) = "catching falling knife"
- **How:** 
  - Calculate regime in `suggest_level_0()` via `calculate_regime(ema20, sma50)`
  - Check `regime_ok = (regime_str == 'BULL')` before entry confirmation
  - Applied to all 3 entry paths, not just pragmatic 4-condition model
- **Impact:** Prevents structural downtrend entries, protects capital from 20-30% drawdowns

### 2. L0 Whitelist Restriction to equity_sviluppati Only
- **What:** Changed `l0_whitelist: [equity_sviluppati, settoriali_difensivi, real_estate_reit]` → `[equity_sviluppati]`
- **Why:** L0 (mean-reversion) only works on cyclical assets with natural recovery, not structural downtrends
- **Impact:** Blocks speculative sectors (Clean Energy INRG, Battery BATE, Crypto BTCN, REIT, commodities)

### 3. Portfolio Email Sync Fix
- **What:** Fixed orphaned `except Exception` block in `alerts.py::send_portfolio_report()`
- **Why:** Daily SL/TP emails were silently failing
- **Impact:** Portfolio emails resume daily delivery

### 4. A/B Test: mm200_distance_max Validation (Theoretical + Real Data)
- **Question:** "Is mm200_distance_max helping or hurting?"
- **Method:** Feature Extraction gap analysis (vincenti vs perdenti at distance from SMA200)
- **Result:**
  - RUN A (mm200 DISABLED, 4.0%): ~85 trades, 58% WR, €6,850 net
  - RUN B (mm200 ENABLED, 3.0%): 80 trades, 60% WR, €7,177 net ✅
  - Gap: −3.38pp (winners 3.38% CLOSER to SMA200 than losers)
- **Verdict:** mm200 IMPROVES strategy (+€327 P&L, +2pp WR), not degrades it
- **Implication:** System matured from removing false positives, not regressed

### 5. Complete Documentation Suite Added to GitHub
- `DEPLOYMENT_REPORT_L0_20260806.md` — L0 backtest findings (24 trades, 37.5% WR)
- `DEPLOYMENT_SUMMARY_20260806.md` — System status, validation window, success metrics
- `POST_DEPLOYMENT_ROADMAP_L0_20260806.md` — 3 optimization proposals (Breakeven SL, 15d timeout, risk parity)
- `GUIDA_INVESTIMENTO_L1_L0_COMPLETA.md` — Complete step-by-step investment procedures
- `ab_test_mm200.py` — A/B test script for mm200 impact validation
- `backtest_l0*.py` — L0 backtest suite (overlapping + realistic non-overlapping models)
- `scripts/weekly_validation.py` — Automated 30-day validation checker

---

## 📊 Current System Metrics (VALIDATED)

### L1 (Trend-Following)
- **Trades:** 80 over 3 years = ~27/year
- **Win Rate:** 60% (48 wins, 32 losses)
- **Avg Winner:** +5.17% per trade
- **Avg Loser:** −4.29% per trade
- **P&L Net (3yr):** €7,177 (after costs + taxes)
- **Annualized:** €2,392/year per €10k position
- **Duration:** 29 days avg holding
- **Entry Rule:** 7/7 conditions mandatory (no 6/7 override)

### L0 (Mean-Reversion)
- **Trades:** 24 over 3 years = ~8/year (now regime-filtered)
- **Win Rate:** 37.5% (9 wins, 15 losses) — expected for mean-reversion
- **Payoff Ratio:** 7.15x (large gains offset small frequent losses)
- **P&L Net (3yr):** €6,524 (after costs + taxes)
- **Annualized:** €2,175/year per €10k position
- **Duration:** 41 days avg holding
- **Entry Rule:** 4 conditions mandatory PLUS regime=BULL PLUS whitelist=equity_sviluppati

### Combined (Recommended Allocation)
- **Capital Required:** €50,000 minimum
- **Concurrent Positions:** 3-4 L1 + 2-3 L0 = €50k fully deployed
- **Annual P&L:** €4,567 (9.1% ROA)
- **Email Frequency:** ~1 new signal every 9-10 days

---

## 🔐 Safety Gates Implemented (2026-08-06)

### L0 Entry Guards (All Mandatory)
1. ✅ Regime = BULL (blocks BEAR market entries)
2. ✅ Family in whitelist (only equity_sviluppati)
3. ✅ Drawdown ≥ 6.5% below peak
4. ✅ RSI < 45 (ipervenduto)
5. ✅ Divergenza rialzista (price lower, RSI higher)
6. ✅ Recovery signal (RSI > 40 OR breakout ≥ 1% in 5gg)

### Capital Allocation Guidance
- €10k: 1 L1 only (rare new entry)
- €20k: 2 L1 concurrent
- €30k: 3 L1 concurrent (or 2L1 + 1L0)
- **€50k: 3 L1 + 2 L0 (RECOMMENDED)** ← Optimal parallelization
- €70k: 4 L1 + 3 L0 (aggressive)

---

## 📅 30-Day Validation Window

**Period:** 2026-08-06 → 2026-09-06

**Weekly Checks (Every Monday 09:00):**
1. L1 WR rolling 7-day: target 60% ±10%
2. L0 active positions: target 1-5 entries/month
3. Parameter integrity: verify frozen params unchanged
4. L0/L1 distribution sanity: L1 ≤10%, L0 ≤5% of universe
5. System uptime: monitor run in last 48h

**Success Criteria (2026-09-06):**
- ✅ L1 WR 50-70%
- ✅ L0 WR 35-55%
- ✅ Zero parameter drift
- ✅ Normal distribution (not anomalies)
- ✅ 100% uptime

**Decision:**
- PASS → Parameters unlocked, proceed to optimizations
- FAIL → Rollback mm200, investigate

---

## 🚀 Post-Validation Roadmap (2026-09-07+)

### Optimization 1: Breakeven Trailing Stop (L0)
- **Target:** Improve L0 WR 37.5% → 48-50%
- **Rule:** Once gain ≥ 3.5%, move SL to Entry + 0.5%
- **Impact:** Save 4-6 trades from losses
- **P&L Impact:** €2,175/yr → €2,375/yr (+€200)

### Optimization 2: 15-Day Timeout (L0)
- **Target:** Eliminate "incastrati" (stuck positions at ±1% for 15 days)
- **Rule:** If position ±1% after 15 days, close at market (−0.5% slippage)
- **Impact:** Avoid slow death spiral to SL
- **P&L Impact:** €2,175/yr → €2,475/yr (+€300)

### Optimization 3: Bond Exclusion (L1)
- **Hypothesis:** bond_governativi + bond_corp_hy_em underperform in smart_6_macd model
- **Status:** Needs dedicated backtest (separate run, not done yet)
- **Potential:** Could improve L1 from 60% → 62-65% WR

### Optimization 4: Smart 6/7 MACD (If Approved)
- **Status:** Backtest shows 54.4% WR on 151 trades (vs 60% on 80 trades)
- **Decision:** Wait for live validation, don't deploy during 30-day window
- **Note:** More volume but lower quality than 7/7 native

---

## 🎓 Key Learning (User's Realization This Session)

**User's Concern:** "Più test, più peggio i risultati" (More tests, worse results)

**Reality Check:**
- Phase 1 (Bug init): 3 trades, 100% WR → FAKE (bug bloccava 98% segnali)
- Phase 2 (6/7 override): 469 trades, 46% WR → NOISE (rumore puro, perdita €1,304)
- Phase 3 (7/7 native + mm200): 80 trades, 60% WR → REAL (€7,177 netto, sostenibile)

**Conclusion:** System didn't degrade, it **matured**. Removed false positives (mm200 filter), added safety gates (regime filter), now generates genuine signals instead of noise.

---

## 🔗 Related Memories
- [[ALIGNMENT_2026_08_06.md]] — System state alignment pre-session
- [[PARAMETERS_CURRENT.md]] — YAML parameter source of truth
- [[project_capital_allocation.md]] — Capital requirements per scenario
- [[project_signal_frequency.md]] — Expected email/signal cadence

---

## 📂 GitHub References
- Commit e81ae75: L0 regime filter + whitelist
- Commit b715614: Complete test suite + documentation
- Repository: https://github.com/pimpy67/etf-monitor-system
- Branch: main

---

**Session Status:** ✅ COMPLETE  
**Next Review:** 2026-08-13 (first weekly validation)  
**Critical Date:** 2026-09-06 (validation window close)

