---
name: etf-session-2026-08-20-l2-radar-and-breadth-idea
description: "2026-08-20: confirmed the two 2026-08-19 background backtests finished with no improvement found; shipped an L2 'radar' email section; discussed but did not start a Market Breadth (Super-Bull) idea"
metadata: 
  node_type: memory
  type: project
  originSessionId: c23e4e15-4c77-4fcf-a9c0-f0d2dc00b62b
  modified: 2026-08-20T08:53:40.472Z
---

## 1. The two 2026-08-19 background VPS backtests are DONE — no improvement found

Checked on 2026-08-20 morning: no backtest processes running, both jobs finished
overnight, both confirm the existing certified candidates rather than beating them.

- **L0 relaxed-conditions sweep** (`backtest_l0_relaxed_slow_extended.json` /
  `_fast_extended.json`, 12 combos each, ~2.5h/side): SLOW grid confirms
  `CANDIDATE_MODEL_L0_20260808` (`regime_min_days_below_sma200=5,
  dd_min_duration_days=4`) as the best point — OOS PF 4.84, nothing in the wider grid
  beats it. FAST grid: no useful signal, same conclusion as before (FAST isn't the
  lever). See [[etf_l0_project_2026_08_07]].
- **4 pilastri quant avanzati** (`backtest_advanced_pillars_result.json`): risk-parity
  sizing scales capital not just P&L (not a fair like-for-like comparison as computed);
  macro-regime veto (ACWI.PA benchmark) hurts `smart_6_macd` OOS (PF 1.45→1.07) and is
  neutral on `candidate_l0`; momentum ranking has only N=8 usable dates (inconclusive);
  volume/RVOL coverage confirmed 75.4% good, Milano/Swiss weaker than Parigi (already
  known). See [[etf_session_2026_08_07_golden_dataset_and_sweep]].

Both are backtest-only, zero production impact, consistent with the existing lockdown
until 2026-09-06.

## 2. Shipped: "Radar L2" email section (2026-08-20)

User wants a "third way" beyond L0/L1 explored — first concrete ask: enrich the evening
email with a radar over the WHOLE L2 universe (not just the curated "Preferiti"
watchlist), showing which of the 7 L1 conditions is still missing per ETF instead of
just a bare count.

- `monitor.py::_build_l2_radar(results)` — new method, reads `analysis['conditions']`
  dict (already computed by `suggest_level()`, unused elsewhere) and translates false
  keys into Italian labels (Allineamento/Persistenza/RSI/Distanza EMA20/ADX/MACD/Spazio
  Residuo). Handles the "7/7 but blocked by fondamenta" case separately (parses
  `level_reason` text for "non BULL" / "< SMA50" since `reason_codes` isn't in the
  wrapper dict returned by `analyze_etf()` — only `level_reason` string survives).
  Sorted by buy_count desc, capped at 20.
- `alerts.py::send_portfolio_report()` — new optional `l2_radar` param, renders a
  "📡 RADAR L2" HTML section in the same daily email (same passive-digest philosophy as
  Preferiti — no extra email traffic). Placed after the Preferiti section.
- Wired in `monitor.py` STEP 5 (same daily-report block as `favorites_digest`), wrapped
  in try/except non-blocking, same pattern as every other optional step.
- Validated logic against real live data before deploying: dry-run against the 10 real
  L2 ETFs in `dashboard_data.json` — output looked correct (e.g. `CEC.PA 5/7, manca:
  Allineamento, MACD`). Notably 7/10 L2 ETFs today are missing MACD specifically —
  consistent with the "73% of 6/7 trades miss MACD" finding from 2026-08-05
  ([[etf_l1_smart6_macd_candidate]]), a nice independent cross-check.
- Deployed via `./deploy.sh` same session (user explicitly approved "Deploy ora").
- There's a separate, pre-existing, NEVER-surfaced "L2 Readiness Score" system
  (`l2_calculate_readiness_score`, STEP 15 in monitor.py, 6-component score with
  anti-flickering hysteresis via `_apply_l2_smoothing`/`etf_l2_watchlist` table) — found
  while investigating this feature. It's computed and logged every day but never shown
  in email or dashboard (confirmed via grep — no references outside
  monitor.py/technical_analysis.py/database.py/test file). Deliberately NOT used for
  the radar (used the same `buy_count`/`conditions` gate that actually decides
  `suggested_level==2` instead, for consistency with CLAUDE.md's documented L2 rule).
  If ever revisited, this dormant score is worth investigating on its own merits before
  reusing or removing it.

## 3. Discussed, NOT started: Market Breadth / "Super-Bull Market" regime filter

User pasted a third external-analysis text (same pattern as the "4 pilastri" one from
2026-08-19) proposing a market-breadth-gated regime: when % of universe with
EMA20>SMA50 crosses ~75-80%, loosen the L1 gate (7/7→5/7) and/or increase position size
(10k→12.5-15k€) tactically, on the theory that a broad rally reduces false-signal risk
even for weaker individual setups.

**My assessment given to the user**: implementable, real technique (breadth-thrust
family of indicators), but split into two independently-testable levers rather than
bundled:
1. **Sizing-only** (low risk — doesn't touch the entry gate, just a bigger suggested
   position in the email/dashboard, consistent with "no automation").
2. **Gate-loosening** (higher risk — recommended testing "6/7 during high breadth" as
   the minimal delta first, not jumping straight to 5/7, since `smart_6_macd` itself
   isn't live yet).

Flagged concrete engineering gaps before it's backtestable:
- Needs hysteresis/persistence (dual threshold or N-day minimum) to avoid the breadth
  metric flapping daily near the 75-80% boundary — same principle as `days_above_ema`.
- Golden Dataset universe is today's 236 ETFs projected backward — historical breadth
  computed on it doesn't reflect the smaller universe that actually existed in earlier
  years (195→214→240→236 growth documented in CLAUDE.md).
- Needs a genuinely new backtest engine: a cross-sectional per-date aggregation across
  the whole universe, different from the per-ticker walk-forward engine already built in
  `backtest_l1.py`/`optimize_hyperparameters.py`.

**Not yet built.** Offered to write and launch a dedicated backtest (phase 1 sizing,
phase 2 gate, same IS/OOS discipline as CANDIDATE_MODEL_B) on the VPS, which is free
now — user has not yet confirmed whether to proceed. **Check this on resume.**

## 4. BRES/LBRE.DE order filled + a real shares-save bug found+fixed (2026-08-20)

The BRES limit order from 2026-08-19 filled at €140,58 (better than the €141,20 limit) —
71 shares, already correctly present in `etf_portfolio_entries` (id 16, L0, Directa) by
the time this was checked, apparently added by the user via dashboard already. Computed
and confirmed real SL/TP order values from `calculate_sl_suggerito_l0`/`calculate_tp_suggerito_l0`
(cross-checked against the monitor's own independent computation same morning — identical
numbers): SL trigger/limit 137,77€/136,39€, TP target 163,07€.

**Real bug found+fixed while helping enter these on Directa**: the ETF-detail-card
"Quote" field (`sharesInput` in dashboard.html, save button calls `saveStopLoss()` →
`POST /api/accept-sl-suggestion`) silently failed to persist — the frontend sent
`shares` in the request body but `app.py::accept_sl_suggestion()` only ever read
`sl_value`/`tp_value`/`trigger_value`, never `shares`, despite the `shares` column
already existing in `etf_portfolio_entries` and already being read correctly on load
(`/api/portfolio-sl`). Fixed by adding `shares` handling to the UPDATE in
`accept_sl_suggestion()`. Verified end-to-end with a real curl call using the user's
actual values (isin=LU1834983550, sl_value=136.3, shares=71) — confirmed written to DB.
Deployed.

Also updated the PHAG (WisdomTree Physical Silver, `JE00B1VS3333`) L0 position's Stop
order mid-session — up +14.46% at the time, price entered the TP-proximity tightening
zone (<1.5% from the €52,6573 target), walked the user through replacing their stale
Stop (trigger 45,85/exec 45,39, from the "pareggio" stage weeks ago) with the current
ratchet-tightened values (trigger 51,09/exec 50,58) already computed by that morning's
monitor run.

## 5. Shipped: dedicated "TP proximity" email alert (2026-08-20)

Triggered by the user asking, after the PHAG episode above, why this kind of update
has to wait for the evening digest instead of firing as soon as it's detected. Built and
deployed the same session:

- `monitor.py::_update_portfolio_l0_suggerito()` / `_update_portfolio_l1_suggerito()` now
  return a list of "new tightening events" (position just entered the TP-proximity zone,
  or the ratchet moved the stop further up since last run — detected by comparing
  `tp_proximity_stop_max` before/after with a 0.0001 epsilon, so an unchanged tightened
  state does NOT re-fire every run).
- `monitor.py::run()` STEP 7b collects both lists and calls the new
  `alerts.py::send_tp_proximity_alert(events)` immediately — **unconditional on
  `send_daily_report`**, so it fires on the silent 09:00 run too, not just the main
  evening run. This is the actual point of the feature (arrive before the *next*
  scheduled cycle, not truly real-time — the monitor only evaluates prices 1-2x/day, no
  intraday polling, so don't oversell this as instant).
- Dry-run tested against real PHAG numbers before deploying (mocked `_send_email` to
  print instead of send) — rendered correctly, no exceptions.
- Deployed via `./deploy.sh`. Not fully live-verified (PHAG's tightened value hadn't
  changed since that morning's run at deploy time, so the dedup logic correctly produced
  zero new events — confirms the dedup works, but means the send path itself is only
  syntax/dry-run tested, not confirmed against a real fired alert yet). **Worth
  double-checking the next time any L0/L1 position newly enters or advances the
  tightening zone that the email actually arrives.**

See [[etf_session_2026_08_19_20_backtests_and_bres_order]] for the prior day's context
(this note supersedes item 1 there — both forks confirmed done, no improvement).
