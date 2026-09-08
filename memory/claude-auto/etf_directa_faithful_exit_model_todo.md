---
name: etf-directa-faithful-exit-model-todo
description: "QUEUED for after the 2026-09-06 checkpoint — rebuild the shadow-monitor + backtest exit model to match real Directa execution (one active sell order, Stop ratchets near TP) instead of the current clean 'SL-or-TP-first-touched, exact fill' model."
metadata: 
  node_type: memory
  type: project
  originSessionId: 09a37320-8783-4b11-9516-618e20ac9073
  modified: 2026-09-07T19:30:03.145Z
---

User asked (2026-09-03) to make the shadow monitors / backtests model **real Directa
execution** as faithfully as possible, since that's where trades actually happen.

## PROGRESS (2026-09-07 — started right after the 06/09 checkpoint)

- ✅ **Step 1 DONE**: `directa_exit.py` (new module, in repo working tree, NOT committed).
  - `directa_stop_today(analyzer, entry_price, current_price, level, *, ema20_today,
    ema20_series, prev_tp_stop_max, sl_initial_pct, atr_pct, broker)` — single-day
    primitive for the shadow monitors. Effective stop = `compute_order_prices(...)['prezzo_stop']`
    = max(official SL, TP-proximity ratchet). Close-based hit detection. Handles OCO
    brokers (clean TP fill). exit_reason ∈ {STOP_LOSS, STOP_TRAIL_PROFIT, STOP_TP_RATCHET, TP_OCO}.
  - `simulate_directa_exit(analyzer, close_full, hist_index, entry_pos, level, *, high_full,
    low_full, ...)` — walk-forward version for backtests, recomputes per-instrument ATR14
    each day like the real monitor.
- ✅ **Step 2 DONE**: `backtest_l0_v2.py` wired — new flags `--exit-model clean|directa|both`,
  `--split-date YYYY-MM-DD` (IN/OUT), `--candidate-l0` (applies regime_min_days=5 override),
  `--limit N` (smoke). `aggregate()` rewritten: `_summary()` returns PF + win-rate +
  exit-reason breakdown; reports TUTTO / IN / OUT per exit_model.
  - Smoke test (8 tickers, `both`, container `/app`): wiring works. `directa` produces
    MORE trades than `clean` (LBRE.DE 3→6, GRE.PA 5→6) — the ratcheting stop exits on
    pullbacks then re-enters. Consistent with the "expect worse not better" prior.
  - py_compile OK on container. `docker cp`'d to `/app` for testing only — NOT part of any
    running process (directa_exit.py imported only by backtest_l0_v2.py so far).
- ✅ **Step 3 — L0 native run DONE 2026-09-07** (ran ~3.5h under 80% CPU steal, detached).
  `backtest_l0_v2.py --start 2023-08-05 --exit-model both --split-date 2025-08-05` on 103
  equity_sviluppati tickers, native L0 entries (regime_min_days=10), frozen batch 2026-08-07.
  Output was `/app/data/directa_L0_baseline_1531.txt` (on the container, not committed).

  **clean vs directa — the delta (10k€/trade):**

  | | clean | directa | Δ |
  |---|---|---|---|
  | N TUTTO | 348 | 378 | +30 (ratchet exits sooner → re-enters; dur 90→77gg) |
  | WR TUTTO | 56.0% | **59.0%** | +3pp (tightened stop locks small wins) |
  | PF TUTTO | 2.77 | **2.46** | −0.31 (ratchet caps the runners) |
  | avg_net/trade | 4.5% | **3.48%** | −1.0pp (the "~1% giveback", slightly worse) |
  | P&L netto TUTTO | 156.7k€ | **131.6k€** | **−16%** |
  | P&L netto IN | 126.6k€ | 104.9k€ | −17% |
  | P&L netto OUT | 30.1k€ | 26.7k€ | −11% |
  | WR IN / OUT | 54.7 / 64.6% | 57.8 / 65.5% | +3 / +1pp |
  | PF IN / OUT | 2.65 / 4.58 | 2.37 / 3.70 | −0.28 / −0.88 |

  **Exit reasons under directa**: `STOP_TP_RATCHET` 223 (59%) + `STOP_LOSS` 155 (41%).
  **Zero clean TP fills, zero STOP_TRAIL_PROFIT / TP_OCO** — every win is the tightened
  stop near TP getting hit, every loss is the official SL. The L0 SL tier2/3
  (breakeven/half-gain) never fire before the TP-proximity ratchet, which sits much higher
  (~+11-13% vs tier2's +1%). Model behaves sensibly.

  **CONCLUSION**: the Directa-faithful model makes L0 look **~15% worse on P&L, ~0.3 lower
  PF, ~1pp lower avg return** — but **higher win rate** and still solidly profitable
  (PF 2.4-3.7, WR 58-66%). Exactly the "expect worse not better" prior. The L0 edge
  survives realistic execution; it's just smaller. **When re-certifying any L0 candidate
  under this model, shave ~15% off the old clean P&L and ~0.3 off PF as the rough
  translation.** (4 tickers skipped for insufficient frozen history: WLSC.PA, USTH.MI,
  VWCE.MI, WATC.PA — recent ticker changes, expected.)

- ✅ **Step 3 remainder — L1 backtest WIRED + smoke-VALIDATED 2026-09-07** (`backtest_l1.py`,
  not committed): new `--exit-model clean|directa` + `--limit N`; `simulate()` gets
  `exit_model` kwarg (last arg, default 'clean' → every existing caller unaffected:
  optimize_hyperparameters, backtest_l1_fast, backtest_adx_slope, backtest_market_breadth
  all call it positionally). In the directa branch `exit_reason` stays `'SL'/'TP'` (keeps
  aggregate + FASE 2 diagnostics working, mapped by sign of P&L) and the real reason goes in
  a new `exit_detail` key. `aggregate()` now also returns `profit_factor` +
  `exit_detail_counts`.
  - **Smoke test (12 tickers, `--compare-min-buy 6`, clean vs directa, 10k€/trade)** —
    absolute P&L meaningless (tiny non-representative sample, all negative), only the DELTA
    matters:

    | variant | metric | clean → directa |
    |---|---|---|
    | smart_6_macd | N / WR / PF / P&L | 13→15 / 30.8→40.0% / 0.78→0.70 / −857→−1267€ |
    | native_7 | N / WR / PF / P&L | 7→8 / 28.6→25.0% / 0.93→0.68 / −162→−804€ |
    | override_6 | N / WR / PF / P&L | 27→28 / 37.0→42.9% / 0.78→0.72 / −1566→−1939€ |

    exit_detail under directa: dominated by `STOP_LOSS` + `STOP_TP_RATCHET`, one
    `STOP_TRAIL_PROFIT` seen (override_6). `exit_reason` SL/TP mapping verified consistent
    with WR.
  - **DELTA DIRECTION = same as L0**: directa → slightly more trades (+1/+2, ratchet exits
    then re-enters), **lower PF** (−0.06 to −0.25, ratchet caps winners), **worse P&L**,
    win rate similar-or-better. Wiring confirmed working end-to-end on L1.
  - Still TODO (deferred while CPU steal ~80%, see [[etf-502-cpu-steal-incident-2026-09-07]]):
    full L1 re-cert on the real universe, `backtest_radars.py` wiring, `--candidate-l0` L0
    variant (low priority — L0 delta already characterised).
- ⬜ **Step 4 NOT STARTED** (design decided 2026-09-07, not written): wire the faithful
  exit into the ~13 live shadow monitors + `backtest_l1.py`/`backtest_radars.py`, re-certify,
  same-day cutover. Only after Step 3 remainder + explicit user sign-off.

  **KEY DESIGN DECISION — no schema migration needed**: `etf_shadow_positions` has NO column
  to persist the ratchet floor (`tp_proximity_stop_max`) between daily runs. Rather than add
  one, each shadow monitor's "if open_pos" branch should **recompute statelessly** each day:
  fetch OHLC from ~40d before entry_date to today, find `entry_pos`, call
  `simulate_directa_exit(analyzer, close_full, hist_index, entry_pos, level=...)` (it replays
  the ratchet from entry internally). If it returns `status='closed'` with `exit_date == today`
  → close the shadow position with that price/reason; else leave open. Cost: 1 OHLC fetch +
  short replay per open shadow position per run (L0 ~5-15, radar_bounce ~43 — all cheap).
  Reuses the already-tested `simulate_directa_exit`, zero new DB state.
  - `exit_reason` column is `VARCHAR(10)` → the L0 backtest's long codes
    (`STOP_TP_RATCHET`) won't fit. For the shadows, map to `'SL'`/`'TP'` (keeps
    `get_shadow_digest_stats` / `get_last_shadow_sl_exit` / cooldown gate working) and
    optionally stash the detail elsewhere. Decide at cutover.
  - `get_last_shadow_sl_exit` (cooldown gate) keys on `exit_reason='SL'` — so the map above
    must send every losing/stop-loss exit to `'SL'`.
  - L0 monitors → `level='L0'`; L1 monitors (tighten_rsi, radars, breadth, bond_trend,
    momentum, adx_slope) → `level='L1'`.

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
