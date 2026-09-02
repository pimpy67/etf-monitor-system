---
name: etf-session-2026-08-19-20-backtests-and-bres-order
description: "Pending items from 2026-08-19/20 session — two background VPS backtests to check, plus a real BRES/LBRE.DE buy order placed that needs portfolio follow-up"
metadata: 
  node_type: memory
  type: project
  originSessionId: d338d306-ad71-4254-af98-19d88ac021b7
  modified: 2026-08-19T22:29:44.155Z
---

CHECK THIS FIRST on 2026-08-20 (or whenever this session resumes) — two open threads from the 2026-08-19 evening session, both explicitly requested to be followed up.

## 1. Two backtest forks running in background on the VPS

Launched to test ideas discussed in the session (comparison of the ETF system's L0/L1 gates against reference quant systems and against "relaxed" variants):

- **Fork "Test L0 con condizioni ridotte/allentate"** (agent name/id `aba12e49e390936de`) — testing whether loosening L0's SLOW/FAST entry parameters beyond the certified `CANDIDATE_MODEL_L0` (`regime_min_days_below_sma200=5, dd_min_duration_days=4`) adds trade volume without breaking Profit Factor. Best point found so far mid-run: `(2,4)` — +8.5% volume IN, +6.5% OOS, quality nearly unchanged (OOS PF 4.79 vs baseline 4.84). Only 3-4/12 combinations covered per side (SLOW path, FAST path) when last checked — job intentionally left running in background on VPS to finish the full grid (`data/backtest_l0_relaxed_p3.json`, `data/backtest_l0_relaxed_p4.json` on the VPS).
- **Fork "Test 4 pilastri quant avanzati"** (agent name/id `a3ab165a8ad4d9f68`) — testing 4 ideas pasted by the user from an external source: (1) ATR/risk-parity position sizing, (2) macro-regime veto on new entries (benchmark `ACWI.PA`/`IWDA`), (3) relative-momentum ranking when multiple L1 signals fire same day, (4) Volume/RVOL data-quality check. Point 4 (volume quality) already done: 75.4% of 235 ETFs have good (>90%) volume coverage in the frozen dataset, but Milano (35/51) and Swiss (2/6) exchanges are notably worse than Parigi (80/97) — RVOL filter viable only on a subset, not the whole universe. Points 1-3 were still in progress (`data/backtest_advanced_pillars_result.json` on VPS) when the session paused.

**Both forks needed repeated manual intervention** during the session — they kept re-launching redundant/duplicate backtest processes despite explicit instructions not to (wasted VPS CPU on a single-vCPU machine, required killing stale processes multiple times via SSH). If resuming this thread, watch for the same pattern and check `ps aux` on the VPS directly (`ssh -i ~/.ssh/id_ed25519_vps root@76.13.37.133`) rather than trusting the fork's self-report of "still working."

**Neither result is production-ready** — this is pure backtest/analysis work, explicitly done *without* waiting for the parameter lockdown (ends 2026-09-06) since backtesting has zero production impact, unlike deploying config changes.

## 2. Real order placed — BRES/LBRE.DE, needs portfolio follow-up once filled

User placed a real Limit buy order on Directa during this session: **71 shares of BRES (ISIN `LU1834983550`, = "Amundi STOXX Europe 600 Basic Res. UCITS ETF Acc") at €141,20 limit, day validity, submitted while market closed ("Immesso")** — not yet confirmed filled as of session end.

- This is the same ETF the ETF monitor's dashboard flags as `LBRE.DE` (Xetra listing, used for the system's price feed/SL-TP calc) — Directa trades the Milan (MTA) listing under ticker `BRES`, same ISIN, slightly different price (Milano ~2.7% above Xetra when checked).
- Triggered by a legitimate live L0 signal (`level_reason: "L0 Deep Recovery: -9.06% dal picco"`, confirmed via `dashboard_data.json`, family `equity_sviluppati`, regime BULL).
- **How to apply**: when this session resumes, ask the user whether the order filled. If yes: (a) get the actual fill price (may differ slightly from €141,20 if better), (b) help add it as an **L0** portfolio entry in the dashboard (ISIN `LU1834983550`, broker Directa), (c) recompute SL/TP off the real fill price — reference values computed at €141,20: SL ≈ €138,38 (entry×0.98), TP ≈ €163,79 (entry×1.16, family `l0_take_profit_pct=16%`). If not filled, the day order likely expired — check if the user wants to re-place it.

See [[etf_l0_project_2026_08_07]] and [[etf_session_2026_08_07_golden_dataset_and_sweep]] for the backtest methodology/baselines these two forks are extending.
