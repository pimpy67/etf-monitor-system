---
name: etf-directa-faithful-exit-model-todo
description: "QUEUED for after the 2026-09-06 checkpoint — rebuild the shadow-monitor + backtest exit model to match real Directa execution (one active sell order, Stop ratchets near TP) instead of the current clean 'SL-or-TP-first-touched, exact fill' model."
metadata: 
  node_type: memory
  type: project
  originSessionId: 09a37320-8783-4b11-9516-618e20ac9073
  modified: 2026-09-03T07:56:24.418Z
---

User asked (2026-09-03) to make the shadow monitors / backtests model **real Directa
execution** as faithfully as possible, since that's where trades actually happen.

## The gap

Current model (all shadow monitors + `backtest_l0_v2.py` + every sweep): exit at the
first of `calculate_sl_suggerito_l0` (trailing SL) or `calculate_tp_suggerito_l0`
(fixed family %), **exact fill at that price**.

Real Directa (cash account, no OCO): **one sell order active at a time**. Default = the
Stop. Approaching TP, `order_pricing.compute_order_prices()` ratchets the Stop toward
current price (within 3% of TP → `price×0.985`; within 1.5% → `price×0.99`; wider buffer
1.5/2.0% for families with `sl_initial_pct >= 0.07`; never below the official trailing SL).
Real exit = when price touches the **effective Stop** = `max(SL_trailing, TP_proximity_ratchet)`,
recomputed daily. The pure TP is almost never a clean fill — it's the anchor that pulls
the Stop up near it.

Not just a ~1% haircut — bidirectional:
- winner running **past** TP → Directa model captures **more** (trails past, no 18% cap)
- winner that touches TP then reverses → captures **~1% less**

Net effect ambiguous → must be measured. Prior: 2026-08-19 rejected candidate ("lean
harder on a ratcheting stop") lost −7% in-sample — so expect the faithful model to make
candidates look **worse, not better**. That's the point: if real execution is worse, we
want to know.

## The plan (agreed 2026-09-03)

1. **Shared helper** `simulate_directa_exit(entry, price_series_since_entry, famiglia, ...)`
   — replays daily `max(SL_trailing, TP_proximity_ratchet)` using the REAL functions
   (`calculate_sl_suggerito_l0`/`_l1` + `compute_order_prices`). One implementation.
2. Wire it into `backtest_l0_v2.py` AND all live shadow monitors:
   - L0: `shadow_monitor_l0.py`, `_l0_cooldown`, `_l0_metalli`, `_l0_oro`,
     `_l0_sl_tier1` (5%/6%), `_l0_regime_baseline`
   - L1: `shadow_monitor_tighten_rsi`, `_radars` (approach+bounce), `_breadth`,
     `_bond_trend`
3. **Re-certify** the baselines (CANDIDATE_MODEL_L0_20260808, CANDIDATE_MODEL_B, etc.)
   on the frozen Golden Dataset under the new model → new reference numbers.
4. Cutover all shadows same day. Note in CLAUDE.md that `etf_shadow_positions` splits
   into a "pre-faithful" and "post-faithful" era (the ~1 month of pre-2026-09 data was
   under the old model — all N<30, little lost).

Modeling choice: **"ride the tightened Stop" (realistic, ~1% giveback, keeps upside on
runners)**, NOT "assume a perfect manual switch to a Limit exactly at TP" — matches the
project's "no automation" philosophy.

## Timing

Queued for **after the 2026-09-06 checkpoint** (read the current shadow data first for a
clean old-model snapshot; no promotion is decided at that checkpoint anyway — all N<30).
Then this is the next project, **ahead of** the "wider / ATR-based L1 SL" analysis from
[[etf-l1-gate-widening-analysis-2026-09-01]] (which would otherwise run on the wrong
exit model).

See CLAUDE.md "Esecuzione ordini reali su Directa (2026-08-08)" and
[[etf_session_2026_08_19_directa_ratchet_and_terminology]] for the ratchet mechanism.
