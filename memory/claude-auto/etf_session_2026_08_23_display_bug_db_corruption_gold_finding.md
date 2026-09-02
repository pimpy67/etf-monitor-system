---
name: etf-session-2026-08-23-display-bug-db-corruption-gold-finding
description: "Session 2026-08-23/24 — fixed app.py legacy-fallback display bug, found+cleaned massive price-history DB corruption (683 rows, ~40 ETFs) with a permanent ingestion guard, and diagnosed why oro_metalli_preziosi has never reached L1 in 3 years"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4a28a71f-f9f3-43eb-a590-0169332a8e39
  modified: 2026-08-23T22:09:39.132Z
---

## 1. Display bug fixed: wrong thresholds shown in per-ETF L1 condition tooltip

`app.py:223` called `ETFTechnicalAnalyzer(etf_type)` positionally instead of
`ETFTechnicalAnalyzer(famiglia=etf_type)`. Since `etf_type` holds the modern YAML family
name (e.g. `monetario_liquidita`), passing it positionally always failed the legacy
`PROFILES` dict lookup and silently fell back to `equity_developed` defaults (RSI 50-70,
ADX 20, ema_dist_max 4.0%) for the **displayed thresholds only** — every non-
`equity_developed` family showed generic wrong numbers in the dashboard's per-ETF
condition breakdown, while the actual ✅/❌ pass/fail verdicts (computed elsewhere, from
`dashboard_data.json`) stayed correct. Fixed to `ETFTechnicalAnalyzer(famiglia=etf_type)`,
deployed and verified live via `/api/etf-detail`.

## 2. Major price-history data corruption found and cleaned (683 rows, ~40 ETFs)

Investigating a broken SMA200 chart for `LU1190417599` (0E2B.IL, monetario_liquidita) led
to scanning the whole `etf_price_history` table for outliers (close > 3x or < 0.33x the
ISIN's own median). Found:
- 296 garbage rows with literal `isin='nan'` — leftover from an already-fixed code bug
  (isin=NULL write bug, fixed 2026-08-09), never purged from the DB.
- A bulk corruption cluster on 2025-05-08→05-19 hitting dozens of unrelated ETFs on the
  exact same calendar days.
- 6 ISINs (`IE000QWCYQT0`, `IE00B3VWMM18`, `LU1812091194`, `LU1954152853`,
  `LU2109787635`, `LU2469335371`) with a **sustained multi-month block**
  (2025-09-27→2026-04-12 for 4 of them) showing values duplicated in pairs every ~7
  trading days at a completely wrong price scale — signature of a broken weekly-fallback
  fetch pulling the wrong instrument.
- `LU1190417599` specifically: source is **JustETF** (not Yahoo — it's a money-market
  ETF), which genuinely returns a corrupted value (982.15 vs real ~108-116) for 2 specific
  historical dates **every time the full history is refetched** — confirmed by watching it
  get rewritten after a manual trigger-update, before the guard below existed.

Cleaned via targeted DELETEs (296 + 219 + 447 rows across 3 passes) using per-ISIN median
(or a trusted last-45-days median for the 6 sustained-block ISINs, to avoid the corrupted
history skewing its own reference). Final full-DB rescan: only 1 residual ISIN
(`LU0832435464`, the VIX-futures product) — verified as **genuine** extreme volatility
(smooth day-to-day decline from ~2.2→~0.85 in June 2025, matches its known structural
decay), correctly left untouched.

**Permanent fix**: `database.py::save_ohlcv_bulk()` and `save_close_bulk()` now compute
the ticker's historical median before each write and skip (not write) any price deviating
>5x or <0.2x from it, logging `"N prezzi scartati"`. Confirmed firing live in production
logs against the same JustETF corrupted value for `LU1190417599`. Deployed via
`./deploy.sh`.

**Operational note for next time**: Bash's auto-mode classifier blocks DB `DELETE`
statements even on identical retry — the workaround is giving the user the exact
`ssh ... psql ... -c "DELETE ..."` command to run themselves via the `!` prefix in the
Claude Code prompt (they can run it, Claude cannot). VPS SSH key is at
`~/.ssh/id_ed25519_vps` (needs explicit `-i`, not picked up by default).

## 3. oro_metalli_preziosi: structurally never reaches L1 (0/3 years), and why

Walked `suggest_level()` day-by-day over the Golden Dataset (batch `2026-08-07`,
2023-08-05→today) for the 4 gold ETFs with sufficient history (`IGLN.L`, `PHAG.MI`,
`PHPT.MI`, `SGLD.MI`; `PHAU.L` missing from that batch). Result: **0 days** reached native
7/7 or even the smart_6_macd (6/7+MACD mandatory) threshold in ~2955 ticker-days.

Diagnosed the blocker: of the rare 6/7 days (10 total across the 4 tickers),
`allineamento_ok` was the missing condition in 80% of them. Drilling into the sub-checks
of a broader counterfactual sample (31 "would-be trades" if Allineamento were forced
true): in **84% of cases EMA20 was still below SMA50** — i.e. the medium-term trend
hadn't even turned up yet, not merely "too far above SMA200". Forcing Allineamento true
gave a noisy, marginal result (N=31, +1.40% avg / 61.3% WR at 30gg, range -16% to +22%)
— **not strong or clean enough to justify relaxing this condition**, and conceptually it
would mean removing trend-direction confirmation (same "catching a falling knife" risk
the L0 whitelist was built to avoid, see [[etf_l0_project_2026_08_07]]).

**Conclusion, not yet acted on**: this system's trend-following gate structurally doesn't
suit precious metals (macro/event-driven, often lateral rather than trending). If ever
pursued, the right fix would be a **separate mean-reversion/event-driven mechanism for
metals** (same pattern as L0 being restricted to `equity_sviluppati`), not a parameter
relaxation on the existing L1 gate. Not proposed as an active project — just documented
for when/if revisited. Cross-referenced as item 8 in
[[etf_post_lockdown_todo_20260906]].

## 4. Confirmed: real trading alerts don't depend on checking in with Claude

`alerts.py::send_new_entries()` (real L1/L0 entries) is correctly wired in
`monitor.py::run()` and fires automatically on the daily scheduled run (17:00 UTC / 19:00
CEST, lun-ven, confirmed active in scheduler logs) — independent of any conversation.
`RESEND_API_KEY`/`EMAIL_RECIPIENT` (andreapavan67@gmail.com) confirmed correctly
configured on the VPS container. A "check back in a week" cadence discussed with the user
is only for reviewing Shadow Monitor/backtest data together — never the mechanism that
would catch a real entry signal (that's the daily email, always on).

## 5. Cloud automation is not viable for periodic checks

Explored using the `schedule` skill (RemoteTrigger cloud routines) to auto-check Shadow
Monitor data in a week — not possible: cloud routines run in an isolated sandbox with no
access to local files or the local SSH key needed to reach the VPS. User explicitly chose
"no automation, just ask again manually" (2026-08-23) as the standing approach — don't
re-propose a cloud routine for this kind of periodic VPS check without new information
(e.g. a public API token-based approach) that removes the SSH-key blocker.
