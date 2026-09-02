---
name: project-l1-ohlc-followup
description: RESOLVED — the ETF DB OHLC fix (commit 6059559) was confirmed clean via multiple full 3-year backtests on 2026-08-05.
metadata: 
  node_type: memory
  type: project
  originSessionId: 6c15300f-1a71-4a05-b9d0-981a69b89d95
  modified: 2026-08-06T02:09:12.770Z
---

**Resolved 2026-08-05.** On 2026-08-04 a bug was found where `monitor.py`/`database.py` discarded Open/High/Low/Volume for ISIN-tagged ETFs from the second monitor run of a day onward, which would silently force `space_residuo_ok` (L1 condition 7) to always fail. Fixed same day in commit `6059559` (`get_ohlc_by_isin()` + `save_ohlcv_bulk()`).

The follow-up this memory asked for — re-verify on a clean trading day that the fix actually holds — is done: multiple full 3-year backtests run 2026-08-05 (236 ETF, 13 families) show consistent, stable results (`native_7` = exactly 3 trades across both the 12-month and 3-year windows, no data-quality anomalies), confirming the OHLC pipeline is healthy. No further action needed on this specific item.

See `etf_monitor_system/CLAUDE.md` → "Stato Attuale & Roadmap L1" for the current, living state of L1 threshold decisions (superseded this same-day memory's original purpose).
