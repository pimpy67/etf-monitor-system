---
name: session_2026_07_21_step3_debug
description: "Session 2026-07-21 — STEP 3 v4.0 bugfixing, L1/L0 diagnostics"
metadata: 
  node_type: memory
  type: project
  originSessionId: 91bdf91d-b745-47f5-90dd-2aae520ff327
  modified: 2026-07-21T20:48:51.272Z
---

# ETF Monitor System — Session 2026-07-21 — STEP 3 v4.0 Debugging

## Discovery: OLD CODE Blocking L1

### The Problem
After deploying PRIORITÀ 2 (L1 7ª condition), L1 remained at 0 ETF despite 5/6 conditions passing.

### Root Cause
**Two layers of OLD CODE (NOT in STEP 3 v4.0 spec) were blocking L1:**

1. **Gerarchia 2+2** (lines 1715-1827 of technical_analysis.py)
   - `check_l1_entry_accelerated()` — gate A∧M + velocity 2+/4
   - Was using ACCELERATED entry logic instead of standard 6-condition L1
   - Only DIAGNOSTIC (logging) — doesn't affect main flow
   - **Action**: Left in place (harmless, just informational)

2. **EMA20 Slope Filter** (lines 1305-1323, previously)
   - Required EMA20 to grow >= 0.2% in 10 days
   - **NOT in STEP 3 v4.0 spec**
   - Was BLOCKING ALL L1 entries before 7ª condition was even evaluated
   - **Action**: REMOVED entirely

### The Proper Flow (STEP 3 v4.0)
```
IF 6 conditions ALL true:
  IF squeeze_valido AND breakout_confirmed:
    → L1 ENTRY (bypass min_reward_pct)
  ELSE IF (distance_to_resistance >= min_reward_pct) OR (space_atr >= min_reward_pct):
    → L1 ENTRY
  ELSE:
    → L2 (insufficient reward space)
ELSE (< 6 conditions):
  → L2/L3 depending on partial conditions
```

## Fixes Applied

### Fix 1: suggest_level_0() Signature (20:24-20:30)
**Error**: `NameError: name 'high' is not defined`
- suggest_level_0() was using high/low without receiving them as parameters
- **Fix**: Added `high` and `low` params to signature
- **Result**: L0 logic now runs without crash

### Fix 2: EMA20 Slope Filter Removed (20:45-20:48)
**Error**: All ETF blocked at 5/6 conditions (didn't reach 7ª check)
- EMA20 slope >= 0.2% requirement was OLD CODE
- Removed ~19 lines of old logic
- Simplified structure: if not 7ª_ok → L2, else → L1
- **Result**: Now 7ª condition can actually be evaluated

### Fix 3: Debug Output Added (20:48)
- Added per-condition debugging for 5/6 case
- Prints which of {ALIGN, PERSIST, RSI, DIST, ADX, MACD} fails
- Will identify why only 5/6 pass

## Current State (2026-07-21 20:48)

| Metric | Value | Status |
|--------|-------|--------|
| L0 ETF | 52 | ↑ (was 5) — Percorsi lento working |
| L1 ETF | 0 | ⚠️ Awaiting debug output |
| L2 ETF | 106 | Watchlist |
| L3 ETF | 82 | Monitoring |
| Monitor | Running | Deploy 20:48, awaiting completion |

### Monitor Progress
- Started: 20:48:08
- Expected completion: 20:53-20:58
- Debug output will show which condition fails

## Next Steps

### Immediate (When monitor completes)
1. Check debug output: which condition at 5/6?
2. If MACD: may need to relax `macd_rising` condition
3. If PERSIST: may need to lower `days_above_ema` or `ema20_slope`
4. If other: adjust family params in YAML

### This Session
- If L1 > 0 after fix: Proceed to PRIORITÀ 1 FASE 2
- If L1 == 0 after fix: Iterate on condition parameters

### Future
- PRIORITÀ 1 FASE 2: State persistence (l0_confirmation_mode across cycles)
- PRIORITÀ 3: L2 Readiness Score with anti-flickering

## Files Modified
1. `technical_analysis.py` — 3 commits
   - suggest_level_0() signature fix
   - Removed EMA20 slope filter
   - Added debug output for condition failures

2. Config verified (no changes needed):
   - `config/etf_families.yaml` — l0_regime + l1_space_residuo params OK

---

## Key Takeaway
**The specification STEP 3 v4.0 is clean and simple: 6 conditions + 7ª override.** 
The old codebase had additional filters (EMA20 slope, gerarchia 2+2) that were NOT in the spec and were breaking the implementation. Cleaning this up is crucial for correctness.
