---
name: etf-evening-check-routine-2026-09-04
description: "Scheduled cloud routine \"ETF Monitor - Check Serale\" (trig_016y9YG3XnixyZdng9vb2Yrk) created 2026-09-04 — daily weekday check, notifies only when actionable."
metadata: 
  node_type: memory
  type: project
  originSessionId: bfa51328-4875-4391-a8a1-5a8b8ed7311a
  modified: 2026-09-04T19:20:28.412Z
---

User asked (2026-09-04) to stop being sent Directa screenshots for every buy/hold/sell
question — "you have all the values, you should tell me what to watch, not the other way
round." Set up a scheduled routine instead of manual check-ins.

**Routine**: `trig_016y9YG3XnixyZdng9vb2Yrk` — https://claude.ai/code/routines/trig_016y9YG3XnixyZdng9vb2Yrk
- Cron `30 17 * * 1-5` (19:30 CEST / 17:30 UTC weekdays, after the 17:00 CEST monitor run).
  **DST note**: fixed UTC cron → after DST ends (late Oct) this becomes 18:30 local, not
  19:30. Revisit then if the earlier time matters.
- Cloud CCR session, **no SSH/VPS access** (cloud sandbox can't reach the local
  `~/.ssh/id_ed25519_vps` key) — reads the **public HTTPS** endpoints instead, verified
  reachable with no auth: `https://etf.andreapavan.tech/data/dashboard_data.json`,
  `/api/portfolio-sl`, `/api/bounce-radar`.
- Checks (from that day's snapshot only, no cross-run state/diffing needed): new L1/L0
  entries · any of the real portfolio positions with price at/through `sl_inserted` or
  `sl_suggested` meaningfully above `sl_inserted` · ETHE.SW thresholds (see below) · bounce
  radar entries with `days_since_min<=1`.
- **Notifies only if actionable** (`PushNotification`, status proactive) — silent otherwise,
  by design (not a "nothing changed today" ping). A data-fetch failure still notifies
  (silent failure would be worse than a false alarm).
- To change thresholds/timing/days: `RemoteTrigger action:"update"` with the trigger id above.

**ETHE.SW manual position** (referenced in the routine prompt, not in the system portfolio):
50x CoinShares Ethereum Staking ETP (GB00BLD4ZM24), bought 2026-09-04 on Directa/**Xetra**
in **EUR** at €66.09 (~9% of the ~37k portfolio — user proceeded after being told this is
aggressive sizing after a +30% run, RSI hot, no technical entry signal exists for crypto
per the Part B finding). System only tracks this ISIN via `ETHE.SW` (SIX Swiss, **CHF**) —
confirmed on Directa's own search 2026-09-04 that **no Swiss listing exists there**, only
Amsterdam (CETH) and Xetra (X.CETH, the one held) — see
[[etf-isin-ticker-fixes-2026-09-04]]. %/RSI transfer reasonably (CHF↔EUR near parity),
absolute prices don't — not added to `etf_portfolio_entries` for that reason (would compute
wrong SL/TP). User manages the stop manually on Directa: **Trigger €59.50 / Limite €58.90**
(-10% from carico) advised 2026-09-04, **confirmed placed by user 2026-09-04**.
Routine flags: RSI back ≤52, price (CHF) ≤57, or dist_ema20 ≤-1% (trend-break, one-day only,
telegraphed as "reverify tomorrow" not confirmed).
