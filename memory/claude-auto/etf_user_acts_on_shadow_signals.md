---
name: etf-user-acts-on-shadow-signals
description: "The user sometimes buys real positions off SHADOW-monitor signals, not only production L0/L1 signals — so shadow-entry emails are NOT purely informational for this user. First seen 2026-09-03 (TELE.PA)."
metadata: 
  node_type: memory
  type: user
  originSessionId: 09a37320-8783-4b11-9516-618e20ac9073
  modified: 2026-09-03T12:36:49.837Z
---

2026-09-03: the user bought **TELE.PA** (LU1834988609, Amundi STOXX Europe 600 Telecom,
entry €52.74) on Directa and added it to the real portfolio as an L0 position — acting on
the **`candidate_model_l0_20260808` Shadow Monitor** entry from that morning's email
(`regime_min_days=5`, more permissive than production's `10`). Production L0 did NOT flag
it (`etf_l0_tracking` was empty). The shadow email's own disclaimer says "non è un acquisto
reale, nessuna azione richiesta" — the user acted anyway.

**Implications:**
- Shadow-entry emails (`alerts.py::send_shadow_entries`, all the `_SHADOW_VARIANTS`) are
  NOT purely informational for this user. When one fires, don't assume it will be ignored.
- The user may open real positions on candidates that have NOT cleared N≥30 validation.
- When a shadow entry is on a weak/low-conviction candidate (e.g. a family the surveys
  flagged, or a candidate with a poor forward record so far), say so plainly in the same
  breath as giving the SL/TP — the user is entitled to the full picture before acting, but
  it's their call. Don't lecture; one factual line.
- SL/TP for such a position: compute with the REAL production functions for that
  `portfolio_type` (`calculate_sl_suggerito_l0`/`_l1` + `order_pricing.compute_order_prices`,
  broker='Directa'), same as any real position. Note if the stored DB value is stale (it
  self-corrects on the next monitor run).

Related standing rules: [[etf_no_auto_exit_real_positions]] (the system still never
auto-closes these), [[etf_l0_project_2026_08_07]] (production L0 = equity_sviluppati only,
regime gate relaxed 2026-09-03).
