---
name: etf-pending-tasks-2026-08-05
description: Explicit TODO list left open when the user paused the 2026-08-05/06 etf_monitor_system session — check this first when the thread resumes.
metadata:
  node_type: memory
  type: project
  originSessionId: 6c15300f-1a71-4a05-b9d0-981a69b89d95
  modified: 2026-08-06T02:28:35.579Z
---

The user explicitly asked to save everything still pending before stepping away ("memorizza tutto quello che resta da fare"). This is the checklist for resuming — see [[etf-l1-smart6-macd-candidate]] and [[etf-l0-rebuild-and-portfolio-bugs]] for the full context behind each item.

**In flight right now**: the feature-extraction backtest (3 variants + `entry_features` capture, `backtest_l1.py`) was launched ~02:12 UTC 2026-08-06, fully detached (nohup+disown on the VPS, survives disconnect). At last check (~02:19 UTC, 13/236 tickers) the pace suggested a longer run than the previous similar one — budget **up to ~2 hours**, not the ~75-90 min first estimated. Check status: `ssh root@76.13.37.133 "docker top etf_monitor_system-app-1 | grep backtest_l1; tail -100 /root/etf_monitor_system/backtest_feature_extraction_output.log"`.

**User's explicit instruction for when it finishes** (given right before pausing): send the summary email only (via `AlertSystem._send_email`, same pattern used all day) — do NOT do the full write-up immediately. The rest (analyze the "FASE 2 — FEATURE EXTRACTION TP vs SL" table in the log, decide if any indicator shows a clean discriminating threshold, write conclusions into `etf_monitor_system/CLAUDE.md`, commit+push, report in chat) is explicitly deferred to a later session — "poi tutto il resto lo facciamo più avanti con calma."

**Backlog beyond the immediate backtest** (not started, no urgency signaled):
1. Test excluding `bond_governativi` + `bond_corp_hy_em` from the momentum/MACD-based L1 gate properly (a real backtest variant, not just the retroactive per-family split already computed on `smart_6_macd`'s trade list — see [[etf-l1-smart6-macd-candidate]] for the preliminary numbers, 54.4%→56.7% win rate, small sample caveat).
2. If `smart_6_macd` (or a bond-excluded refinement of it) is eventually approved for production, it needs to be implemented for real in `technical_analysis.py::suggest_level()` — today's work only added it to the `backtest_l1.py` harness, the live engine still uses plain `min_buy_count=7`.
3. `alerts.py` full content/design review — repeatedly deferred all day ("le vediamo dopo, saranno da rivedere in toto"), only functional bugs were fixed (stale data, duplicate send), not the actual template/content.
4. The dashboard-level L0 tracking's `ε` (30-day timeout) rule is documented but was never implemented — not urgent, just a known gap.
5. `check_l1_entry_tiered()`/`check_l1_entry_accelerated()` ("Fase 3 tiered system") remains unwired — an alternative to `smart_6_macd` that was discussed but not pursued today since the simpler MACD-mandatory variant already tested well.

**Already fully done and deployed as of pausing** (do not re-do): the entire L0 rebuild, the 3 real portfolio bugs (column desync, dashboard status filter, stale email data), the duplicate-email removal, and the `smart_6_macd`/segmentation backtests described above — all committed+pushed on `main` (`etf_monitor_system`, commits `626072c` through `3bdb52e`) and live via `deploy.sh`. Four real portfolio positions were reactivated the same day (3 L1 + 1 L0) after being found wrongly auto-closed by a since-fixed bug — see [[etf-l0-rebuild-and-portfolio-bugs]] for which ones and why.
