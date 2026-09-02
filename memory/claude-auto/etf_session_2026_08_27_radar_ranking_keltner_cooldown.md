---
name: etf-session-2026-08-27-radar-ranking-keltner-cooldown
description: "2026-08-27 session — Radar RVOL/ADX quality ranking shipped, Keltner/ATR filter on L0-oro backtested and rejected, L0 re-entry cooldown candidate backtested and Shadow-tracked, Radar favorites star added"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3318254f-a574-4958-aee9-2fddf39954f3
  modified: 2026-08-27T15:14:54.103Z
---

Session triggered by external-consulting suggestions the user relayed and asked to
evaluate/implement. Three pistas, three different outcomes — useful pattern: not every
consulting idea should be treated the same way.

## 1. Radar quality ranking (RVOL + ADX) — SHIPPED to production same day

Added `_rvol()` (volume today / 20-day avg) and `_quality_score()` (ADX+RVOL composite,
0-100, capped at ADX=40/RVOL=2.5x) to `technical_analysis.py`, wired into
`compute_approach_signal`/`compute_pullback_bounce_signal`. `app.py::_assign_quality_rank()`
marks the top 3 per-day with `quality_rank`. Dashboard shows RVOL + Qualità columns and
🥇🥈🥉 badges on both Radar tables.

**Deliberate choice**: did NOT change the tables' default sort order (stays buy_count desc,
an already-established UI preference) — the ranking is an additional highlight, not a
resort. Not backtested as a predictor — pure display priority for when many signals fire
the same day with limited real cash (~€37k on Directa, the origin of the ask).

## 2. Keltner/ATR filter on L0-oro — BACKTESTED AND REJECTED

Origin: 5 shadow positions on `candidate_l0_oro_20260824` all red (-0.8% to -3.0%),
consultant suggested requiring price to also touch a Keltner lower band (EMA20-mult*ATR14)
instead of RSI-oversold alone.

Scratch backtest (`backtest_l0_oro_keltner.py`, deleted after use), 4/5 oro tickers with
sufficient history, whitelist+blacklist bypassed same as `shadow_monitor_l0_oro.py`, split
IN 2023-08-05→2025-08-05 / OOS 2025-08-05→2026-08-05:

| Variant | IN N/WR/PF | OOS N/WR/PF |
|---|---|---|
| Baseline | 12/50%/2.64 | 0/—/— |
| Keltner x1.5 | 2/50%/2.93 | 0/—/— |
| Keltner x2.0 | 2/100%/inf | 0/—/— |
| Keltner x2.5, x3.0 | 0/—/— | 0/—/— |

**Rejected, two reasons**: (1) the filter shrinks an already-rare signal (12→2→0 trades) —
makes the rarity problem worse, not better; (2) impossible to validate OOS at all, filtered
or not — zero closed trades in the entire OOS year for every variant including baseline
(same finding as [[etf_family_viability_survey_2026_08_24]]'s oro OOS=0). Also worth
remembering: baseline's 50% WR is still profitable (PF 2.64) thanks to asymmetric payoff
(avg TP~+17%, avg SL~-4.7%) — the 5 live red shadow positions are ordinary variance for N
this small, not evidence the entry is broken. No code changed.

## 3. L0 re-entry cooldown — BACKTESTED, Shadow-tracked as CANDIDATE_L0_COOLDOWN_20260827

Full detail in [[etf_post_lockdown_todo_20260906]] section 13 (the canonical checklist —
check there first for the SQL extraction query and exact params). Summary: found
`suggest_level_0()` is level-triggered (signal stays 'True' for many days straight), so a
SL stop taken mid-signal produces an immediate re-entry next trading day, no memory of the
stop (real case: LBRE.DE, SL 08-14, re-entry 08-15 — in that instance it *helped*, lower
cost basis right before a real recovery to +7.19%, but the mechanism has zero protection
against the opposite whipsaw).

Two variants tested on equity_sviluppati (105 tickers, Golden Dataset batch 2026-08-07):
- `reclaim` (block until price > stopped trade's entry): REJECTED, classic overfitting
  signature (IN improves PF 4.23→5.18, OOS collapses PF 2.02→1.42).
- `cooldown 10 trading days` (block re-entry on same ticker for N days post-SL, nothing
  else changed): beats baseline on every OOS metric, no overfitting signature — OOS N=12
  PF=2.41 WR=50.0% vs baseline OOS N=11 PF=2.02 WR=45.5%. First re-entry-gate candidate in
  this project that's clean IN+OOS.

Shipped as Shadow Monitor same day (`shadow_monitor_l0_cooldown.py`, STEP 8j,
`model_name='candidate_l0_cooldown_20260827'`, new `database.py::get_last_shadow_sl_exit()`
helper). Verified live: full manual monitor cycle completed with 0 errors in STEP 8j.
N<30 — not promoted, same discipline as every other candidate this month.

## 4. Radar tables — favorites (⭐) star added, same as everywhere else

User asked to be able to add ETFs found in the Radar Anticipato/Rimbalzo tables to
Preferiti, same star toggle already used on the L0-L3 tables. Added the same `favBtn`
markup (reusing `favoriteIsins`/`toggleFavorite()`) to both
`renderApproachRadarTable`/`renderBounceRadarTable` rows. Since these tables are rendered
outside `renderDashboard()` (populated by their own async loaders hitting
`/api/approach-radar`/`/api/bounce-radar`), toggling a favorite needed a way to refresh
their star icons without re-fetching (a full Radar refetch recomputes regressions for
every candidate ETF — slow, causes flicker just to flip one icon). Fix: store the
last-fetched rows in module-level `lastApproachRadarRows`/`lastBounceRadarRows`, and added
`refreshRadarFavoriteButtons()` (re-renders both tables in place from the cached rows) —
called from `toggleFavorite()`/`removeFavorite()` alongside the existing `renderDashboard()`
call. Deployed, container restarted clean.

## Meta-lesson from this session

Three consulting ideas, evaluated the same way (backtest on Golden Dataset, IN/OOS split,
N≥30 discipline), got three different outcomes: one shipped as a low-risk UI feature (no
backtest needed — it's display, not a trading rule), one rejected with data, one
Shadow-tracked as a genuine candidate. The discipline itself — never implement a trading
idea straight from intuition without the IN/OOS check — is what's producing the
differentiation; treat future external suggestions the same way rather than by how
plausible they sound going in (the reclaim idea sounded more obviously correct than plain
cooldown, and it's the one that failed OOS).
