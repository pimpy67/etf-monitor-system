---
name: etf-session-2026-08-19-directa-ratchet-and-terminology
description: "Shipped the TP-proximity Stop ratchet + volatility-tiered buffer for Directa order pricing (L1+L0), renamed dashboard/email labels to Directa's exact field names, and backtested-then-rejected a continuous+ratchet L0 SL formula candidate."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7cc407d7-643a-4918-ac5f-d6c3d670b1c9
  modified: 2026-08-19T13:13:56.896Z
---

## Shipped and deployed (commit `2f015e2`, 2026-08-19)

**Feature**: `order_pricing.py::compute_order_prices()` — the tactical Stop tightening near
TP (used only for Directa-style brokers without OCO, i.e. `broker != 'Webank'`) now has:
1. **Ratchet**: never suggests a tactical Stop lower than the max already suggested for that
   position. New DB column `etf_portfolio_entries.tp_proximity_stop_max`, written only by
   `monitor.py`'s daily L1/L0 update steps, read by `alerts.py` (email) and `app.py`
   (`/api/portfolio`) as `previous_tightened_stop`.
2. **Volatility-tiered buffer**: families with `sl_initial_pct >= 0.07` (commodities, leva,
   crypto — i.e. `WIDE_TIER_SL_INITIAL_PCT` in `order_pricing.py`) get a wider tightening
   buffer (1.5%/2.0% instead of 1.0%/1.5%) so a volatile asset like Silver/PHAG doesn't get
   stopped by a normal intraday spike right before actually touching TP. Derived from the
   per-family YAML `sl_initial_pct`, not a hardcoded asset-class flag — matches the project's
   existing convention of driving behavior from `etf_families.yaml`.

Applies to **both L1 and L0** portfolio positions (`monitor.py::_update_portfolio_l1_suggerito`
and `_update_portfolio_l0_suggerito`), both now pass `broker`, `sl_initial_pct` (via
`ETFTechnicalAnalyzer(famiglia=...).p.get('sl_initial_pct')`), and the persisted
`tp_proximity_stop_max` into `compute_order_prices()`.

**Verified live post-deploy**: triggered a real monitor run same day. Amundi MSCI Europe (L1,
Directa) was ~2.5% from its TP and the ratchet correctly activated (floor saved, no visible
🔶 today since the official trailing SL was already higher). WisdomTree Physical Silver (L0,
Directa) was ~15% from TP — mechanism correctly inactive, nothing to protect yet. The two
Webank positions correctly skip the whole mechanism (`parallel_ok=True`, Webank has native
OCO so doesn't need it).

**Terminology (explicit user request, 2026-08-19)**: use Directa's own field names verbatim,
no invented synonyms. Column/label changes across `alerts.py` + `dashboard.html`:
"Prezzo Limite (Stop)" → **"Prezzo Limite"**, "Prezzo Limite (TP)" → **"Target TP"** (it's not
a field on the Stop order, it's a separate future Limit order's reference target — inventing
"Prezzo Limite (TP)" implied it was the same kind of field, which it isn't). Email-only at
first, then extended to dashboard on explicit follow-up request: "Prezzo Stop" → **"Prezzo
Stop (Trigger)"** in both surfaces. See [[etf_directa_trigger_vs_limit_confusion]] for the
related (but distinct) issue of the user typing the wrong one of these into personal-SL
fields — that memory's field-name references were updated to match this rename.

**Bug fixed as a side effect** (`dashboard.html::loadAllPortfolioSLData()`): was overwriting
the correctly-tightened "Prezzo Stop (Trigger)" span (set by `renderPortfolio()` from
`/api/portfolio`'s `prezzo_stop`) with the raw untightened `sl_suggested` from
`/api/portfolio-sl` right after page load — would have silently hidden the new ratchet
feature in the dashboard (email was unaffected, separate code path). Removed the overwrite.

**Known bug found but NOT fixed** (out of scope, flagged only): `dashboard.html` line ~1404
calls `updatePortfolioP_L(isin, pos.entry_price)` inside `loadAllPortfolioSLData()`'s
`positions.forEach` — that function **does not exist anywhere in the file** (likely dead code
from before a refactor to `updatePLCalc()`, which takes no args and reads a single detail-panel's
DOM, not a per-row model). Throws, caught by the outer try/catch, which **kills the rest of the
forEach loop** — only the first position in the list gets its `sl-pers-`/`shares-` input
auto-fill from `/api/portfolio-sl`; all positions after it silently don't. Not touched.

## Evaluated and REJECTED: continuous+ratchet L0 SL formula (2026-08-19)

Triggered by the user noticing WisdomTree Physical Silver (L0 entry 45.39€) peaked at 51.87€
on 2026-08-12 (+14.27%, just under the 15% tier boundary) then pulled back to 49.45€ (+8.9%)
by 08-19 without the SL (`calculate_sl_suggerito_l0`, 3-tier: <5%→entry×0.98, 5-15%→entry×1.01
pareggio, >15%→entry×(1+profit-0.08)) ever rising above pareggio — the formula is tier-based on
*today's* profit, not peak-tracking, so a near-miss of a tier boundary gets zero incremental
protection.

Built a candidate (continuous formula merging tiers 2+3: `entry×(1+max(0.01, profit-0.08))`
for profit≥5%, eliminating the 15% cliff, **plus a ratchet** — never let the suggested SL drop
below the max ever suggested for that position, same principle as the shipped Directa-order
ratchet but applied to the actual exit formula this time) and backtested it against the frozen
Golden Dataset (batch `2026-08-07`) using a new script mirroring `backtest_l0_v2.py`'s real
entry logic (`suggest_level_0()`, unchanged) with only the SL swapped — script was scratch-only,
copied into the container via `docker cp`, run there, then deleted; nothing left in `/app` or
git.

**Result — real trade-off, not a clean win, 107 ETF (`equity_sviluppati`, the only L0-whitelisted
family), same IN/OUT split as `CANDIDATE_MODEL_L0_20260808`:**

| | Trade | Win rate | Profit Factor | P&L netto (10k€/trade) |
|---|:---:|:---:|:---:|:---:|
| Baseline IN (146 trades) | 84 SL / 62 TP | 42.5% | 3.18 | 53.602€ |
| Candidate IN (146 trades) | 94 SL / 52 TP | 47.9% | 3.56 | **49.801€ (-3.801€, -7%)** |
| Baseline OUT (26 closed) | 21 SL / 5 TP | 19.2% | 1.05 | 309€ |
| Candidate OUT (29 closed) | 24 SL / 5 TP | 20.7% | 1.12 | **713€ (+405€)** |

Win rate and PF improve, but total € is what matters and it's *worse* on the larger, more
reliable in-sample set: the faster-rising ratcheted SL stops out trades early that would have
consolidated mid-run and gone on to hit the full fixed TP — exactly the trades that make L0
profitable in the first place. The OOS improvement is real but on too small a sample (26-29
trades) to outweigh the in-sample cost.

## Portfolio UI overhaul (same session, after the above)

- Row view (`renderPortfolioTable`): replaced the underused "Target TP Personale" slot with
  **"Prezzo Stop Personale (Trigger)"** (new DB column `stop_trigger_inserted`) — now the row
  shows the exact Trigger+Limite pair the user actually entered on Directa, plus a working
  P&L display (was calling a nonexistent `updatePortfolioP_L` — fixed, new `updatePortfolioRowPL`).
- Detail modal (`slManagementPanel`): now wired to the ratchet too (`/api/portfolio-sl` applies
  `compute_order_prices()` same as `/api/portfolio`) — "SL Suggerito" shows the tightened value
  with 🔶, matching the row view exactly. Added a "Prezzo di Carico" box (JS already referenced
  `entryPriceDisplay` but the HTML element never existed — pure oversight, now fixed).
- Both "Prezzo Limite Personale" fields (row + detail modal) write to the **same** DB column
  (`stop_loss_inserted`) via the same endpoint — confirmed to the user they're genuinely linked,
  not two independent trackers.
- Inputs now accept both `,` and `.` as decimal separator (`parseLocaleFloat()` helper) — the
  two number-type inputs in the detail modal were silently rejecting comma in most browsers.
  Save actions on both surfaces now show a visible ✅/❌ result (row view had none before).
- **Shadow Monitor email activated** (2026-08-19, explicit user request): `alerts.py::
  send_shadow_entries()` existed since 2026-08-07 but was never called ("no email" was a
  deliberate choice then). Generalized it with a `variant='L1'|'L0'` param and wired it into
  `monitor.py` STEP 8/8b — fires only on new shadow entries (not exits), only when
  `send_daily_report=True` (skips the 09:00 silent run). CLAUDE.md's several "nessuna email"
  notes for both shadow candidates updated to match.

## Dashboard clickability sweep + "Allineamento" explanation bug (same session)

- **Real display bug found and fixed**: the ETF detail modal's "Allineamento" condition
  row (`dashboard.html`, `interpret()`/`detail()` for `allineamento_ok`) only ever checked
  `price>EMA20` and `EMA20>SMA50` — it never learned about the `dist_sma200_ok` /
  `mm200_distance_max` sub-check added to condition 1 on 2026-08-06 (see CLAUDE.md
  "L1 — Come Si Entra"). Result: an ETF failing ONLY on SMA200-distance (e.g. ENRG.PA at
  +12.99% vs a 3.0% cap for `equity_sviluppati`) showed a ❌ badge next to a positive-sounding
  explanation text that never mentioned SMA200 at all — actively misleading, not just
  incomplete. Fixed end-to-end: `technical_analysis.py` now includes `dist_sma200_ok`,
  `dist_sma200_pct`, `mm200_distance_max` in the `conditions` dict; `app.py`'s
  `/api/etf-detail` passes them through in `values`/`thresholds`; dashboard.html's
  `interpret()` now gives the real reason when alignment fails only on SMA200 distance.
  Verified live on both ENRG.PA (fails) and WATC.SW (fails at +4.7%/3.0%) — the ❌ verdict
  itself was always correct, only the explanation was wrong. Don't re-investigate this as a
  bug if seen again — it's fixed.
- **Clickability sweep across all tabs** (user asked after noticing Favorites wasn't
  clickable): main L0/L1/L2/L3 tables and Portfolio L1/L0 sub-tabs were already fine.
  Two more spots had the exact same bug — a `cursor:pointer` style promising a click that
  did nothing (no `onclick` at all): the **L2 Readiness tab** (inside the Portfolio section,
  `/api/l2-watchlist` rows) and **Favorites** (fixed earlier same session). Both now call
  `openETFDetail(ticker, isin)` on row click, matching the established pattern.
- **Found, NOT fixed — still open, needs a user decision**: a second, separate "🛡️ Stop Loss
  Portafoglio L1" panel (`renderPortfolioSL()`, populated into `<div id="slPanel">`) sits
  below the L1/L0/L2 tabs in the Portfolio section and duplicates info already shown in the
  richer `renderPortfolioTable()` rows above it — looks like dead/superseded UI from before
  the current portfolio table design. There are also **two elements with `id="slPanel"`** in
  the HTML (one static/empty at the top of `#mainContent`, presumably inert since
  `#mainContent` gets fully replaced on render; one real, inside `renderPortfolioSection()`)
  — a duplicate-ID smell worth cleaning up regardless of what happens to the panel. Asked the
  user whether to make it clickable or remove it as redundant — no answer yet as of this
  memory's writing.

## Doc correction: L0 Shadow Monitor was already live (CLAUDE.md was stale)

While investigating "what would the shadow tests show today," found `etf_monitor_system/CLAUDE.md`
still said "L0 non ha ancora un candidato abbastanza maturo da meritare uno Shadow Monitor" — false.
`shadow_monitor_l0.py` (STEP 8b in `monitor.py::run()`) has existed and run daily since 2026-08-08,
tracking `candidate_model_l0_20260808` on `equity_sviluppati`. It only logs a summary line when
something opens/closes that day, so 12 days of mostly-silent operation made it look inactive — it
wasn't. Fixed the CLAUDE.md note (same location, ~line 1805) with the real status as of 2026-08-19:
5 shadow positions (1 closed SL -2.42%, 4 open: ENRG.PA, INCI.MI, WATC.SW, LBRE.DE-reentry). Same
day, the L1 shadow (`candidate_model_b_20260807`) had 0 entries in the same 12 days — both gates
(native 7/7 and the looser candidate) found nothing on the core families, not a native-gate-specific
drought.

**Decision: keep the production tiered formula unchanged.** The Silver case (1.52% from TP at
its peak) was already inside the zone the shipped tactical Directa-order ratchet above would
have covered had it existed yet — no need to touch the backtested exit formula for it. Don't
re-propose this exact continuous-formula idea without new data; if revisited, the user
suggested a more surgical variant (ratchet only above ~10-12% profit) as an unexplored
alternative, not this flat merge of tiers 2+3.
