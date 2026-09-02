---
name: etf-session-2026-08-25-rsi-gate-pac-fixes-radar
description: "RSI-gate tighten candidate for smart_6_macd + Shadow Monitor, two real PAC bugs found+fixed, dashboard reorder, L2 Readiness DB-persistence bug fix, new Radar Anticipato + Radar Rimbalzo EMA20 features"
metadata: 
  node_type: memory
  type: project
  originSessionId: 08f5fb05-04e4-497b-884f-5c0ccaa5bd9e
  modified: 2026-08-25T14:38:14.824Z
---

## CANDIDATE_TIGHTEN_RSI_20260825 — L1 entry refinement, Shadow-tracked

User noticed [[etf_l1_smart6_macd_candidate]]-style entries (LGQM.DE, mercati_emergenti)
firing already extended from EMA20 (dist 4.71%, near the 5% family cap) with RSI over the
range (66.1 vs max 58) — the "smart_6_macd" boost (live since 2026-08-24, see
[[etf_family_viability_survey_2026_08_24]]) accepts 6/7 when the only missing condition is
`rsi_ok` as long as MACD confirms, which structurally tends to fire on already-extended
moves (that's what an overbought RSI means).

**Two candidate fixes discussed and backtested**:
1. **"tighten"**: when the only missing condition is `rsi_ok`, additionally require
   `dist_ema20 <= 3.0%` (a tighter cap than the family's normal 4-5% `ema_dist_max`) before
   accepting the entry — otherwise skip that day.
2. **"wait_pullback"**: same trigger, but instead of a hard skip, explicitly wait (up to N
   days) for price to pull back near EMA20, freezing eligibility instead of re-checking all
   6 other conditions daily.

**Result: numerically IDENTICAL at every threshold tested** (1.5%/2.0%/2.5%/3.0%, wait
windows 5/10/15/20gg) — because "tighten" already re-scans daily when not holding, which in
practice reproduces the same wait behavior on this dataset (the other 6 conditions rarely
flip during the wait). Chose **"tighten" for simplicity** — no reason to build the more
complex frozen-eligibility state machine for an identical result.

⚠️ **Real bug found and fixed in the backtest script itself before trusting results**: the
first version applied `CORE_ENTRY_ZONE` overrides (`adx_delta=-4`, `mm200_absolute=7.0`) on
top of `entry['baseline_p']` — but since `CANDIDATE_MODEL_B_20260807` was promoted straight
into `config/etf_families.yaml` on 2026-08-24, that baseline **already contains** those same
adjustments. Re-applying `adx_delta=-4` on an already-lowered ADX threshold (18) silently
produced an effective threshold of 14 (double discount) — this alone inflated the baseline
mode's trade count to N=44 IN / N=33 OUT instead of the true, previously-certified N=31/N=18.
Fixed by dropping the redundant overrides entirely and using the live production `p` as-is
(`min_buy_count=7` + the internal `use_smart_6_7_macd` boost, no manual overrides) — verified
the corrected baseline mode reproduces the certified CANDIDATE_MODEL_B numbers **exactly**
(IN N=31 PF=1.45 WR=54.8%, OUT N=18 PF=1.62 WR=55.6%) before trusting the tighten/wait
numbers built on top of it.
**Lesson for any future candidate backtest on families whose baseline already includes a
promoted bundle: check whether your "delta overrides" are being applied on top of a baseline
that already contains them.**

**Final certified numbers, cluster `core` (5 families), Golden Dataset batch 2026-08-07,
same IN/OUT split as CANDIDATE_MODEL_B**:

| | baseline (produzione) | tighten cap=3.0% |
|---|---|---|
| IN | N=31 PF=1.45 WR=54.8% avg=0.98% MaxDD=32.5% | N=24 PF=2.21 WR=62.5% avg=2.04% MaxDD=14.9% |
| OUT | N=18 PF=1.62 WR=55.6% avg=1.53% MaxDD=19.1% | N=14 PF=1.69 WR=57.1% avg=1.64% MaxDD=19.1% |

Tighten cap=3.0% beats baseline on **every single metric, both IN and OUT** — cleaner than
2.0%/2.5% (which underperform baseline OOS despite looking better IN, classic overfitting
signature) and 1.5% (fewer trades, similar OOS to 2.0%). Still N<30 in both windows — NOT
promoted to production, same discipline as every other candidate this month.

**Shadow Monitor built and wired same day**: `shadow_monitor_tighten_rsi.py`,
`model_name='candidate_tighten_rsi_20260825'`, STEP 8g in `monitor.py::run()`, non-blocking
try/except. Reuses production `suggest_level()` entirely (no duplicated entry logic) — only
adds the extra `dist_ema20<=3.0%` gate in the specific "only rsi_ok missing" sub-case; every
other entry (native 7/7, or 6/7 missing something else) is identical to what real L1 already
does. Email variant `'TIGHTEN_RSI'` added to `alerts.py::_SHADOW_VARIANTS` (purple, #8E44AD).

**Extraction query at next checkpoint** (same pattern as other candidates):
```sql
SELECT ticker, entry_date, exit_date, exit_reason, gross_pct_gain, status
FROM etf_shadow_positions WHERE model_name = 'candidate_tighten_rsi_20260825'
ORDER BY entry_date;
```

## Two real bugs found+fixed in the PAC comparison page (`/pac`)

1. **`get_exited_portfolio_entries()` silently missed a real L0 loss**: the query filters
   `status='exited'`, but the BRES/LBRE.DE position (LU1834983550, the same whipsaw ETF from
   [[etf_session_2026_08_20_l2_radar_and_breadth_idea]]/`CANDIDATE_MODEL_L0_SL_20260820`) had
   `status='closed'` in the DB — a leftover value from a manual SQL edit during that
   promotion, never written by the normal `exit_portfolio_entry()` code path (which always
   writes `'exited'`). Result: the L0 sleeve card showed only Silver's +17.15% (1 position)
   instead of the true blended +1.23% (2 positions, including BRES's real −2.35% net loss).
   **Fixed by normalizing the DB row** (`UPDATE ... SET status='exited' WHERE id=16`) rather
   than widening the query — `'closed'` was never a real production status. **If any other
   position ever shows an unexpected status value, check for the same class of leftover from
   a manual SQL edit** (this project has done a few of these promotions via direct SQL, e.g.
   the "PROMOTED" admin-closes documented in [[etf_post_lockdown_todo_20260906]]).
2. **`templates/pac.html` winner banner ignored the sample-size gate**: `app.py::get_pac()`
   already computes `signal` (up/down/neutral) requiring BOTH spread≥3pp AND all sleeves
   n_positions≥3 — but the frontend's separate "🏆 In vantaggio" banner only checked
   spread≥3pp, so it could declare a winner while every arrow showed ➡️ neutral (visible
   contradiction, user caught it live: banner said "L1 +3.78pp" while all arrows were
   neutral because n=1/1/2). Fixed by mirroring the same `n_positions>=3` check in the JS.

Both deployed via `./deploy.sh` (commit `ceaadbb`, 2026-08-25).

## New feature: Radar Anticipato (dashboard)

User's idea, refined through discussion: instead of a hard boolean day-over-day check
(noisy with few observations), use **linear regression (slope + R²) over a lookback window**
(default 7 days) on `dist_ema20`, MACD histogram, and ADX for ETFs still below their EMA20
(not yet L1/L2 by alignment) — flags "approaching" only when all three trends are positive
AND each fit's R² clears a minimum threshold (default 0.3), to avoid mistaking noise for a
real convergence.

- `ETFTechnicalAnalyzer.compute_approach_signal()` (`technical_analysis.py`) — new
  `_slope_r2()` helper (linear regression + R², building on the existing `_slope()`).
- `GET /api/approach-radar` (`app.py`) — scans L2/L3 candidates from cached
  `dashboard_data.json`, fetches OHLC history live per candidate from
  `db.get_ohlc_by_isin()`, computes the signal on-demand (nothing stored/precomputed, always
  fresh on page load). Query params `days`/`min_r2` optional.
- New collapsible dashboard section (same UI pattern as ⭐ Preferiti — `renderApproachRadarSection()`/`toggleApproachRadarSection()`/`loadApproachRadar()` in `dashboard.html`).
- Purely informational — does not touch `suggest_level()`, L0-L3 classification, or any
  real decision. Empty results are expected and common (strict by design); with the default
  threshold relaxed to R²≥0.1 as a one-off test, only one weak case appeared
  (LFOD.DE/LU1834985845, score 40) — confirms the filter is working as intended, not silently
  broken.

## Dashboard reorder + "always open, progressively sorted" UI preference (later same day)

User's standing preference for these list-like dashboard sections, worth applying by default
to any future one: **open by default** (not collapsed behind a click) and **sorted by
buy_count descending** (most conditions met first) — except L3 (Universe), which is large and
low-signal enough that it should be the one section collapsed by default, accordion-style.
Order requested: L0 → L1 → **Portfolio** (moved up here, was previously below L2/L3) → L2 →
L3 (collapsed) → Preferiti (open, sorted) → Radar Anticipato (open, sorted) → param ref.

Implementation reused the existing collapse infra already used by Preferiti/Radar
(`portfolioSectionOpen`/`favoritesSectionOpen`/`approachRadarOpen` flags default flipped to
`true`) plus a new `level3Open` flag (default `false`) for L3's accordion — L0/L1/L2 never had
a collapse toggle and still don't, only L3 got one. Deployed.

## Real bug found+fixed: "L2 Readiness" tab (Portfolio section) was empty since inception

Different mechanism from [[etf_session_2026_08_25_rsi_gate_pac_fixes_radar]]'s Radar
Anticipato above — this is the older "L2 Readiness" tab inside the Portfolio section
(PRIORITÀ 3, STEP 15 in `monitor.py`, weighted 6-component score 0-100 with EMA-3 smoothing +
hysteresis enter@70/exit@60). User asked why it was always empty; checked prod DB directly —
`etf_l2_watchlist` had **0 rows, ever**, not just currently-empty.

**Cause**: `database.py::update_l2_watchlist_state()` (the write function) was fully coded but
**never called from anywhere** — `monitor.py::_apply_l2_smoothing()` computed the score and
persisted it only to a local JSON file (`data/l2_score_state.json`), never to the DB table
that `/api/l2-watchlist` (and the dashboard tab) actually reads. Computed-but-never-persisted,
same class of bug as the "computed but never sent to frontend" ones from
[[etf_session_2026_08_10_l2_fix_favorites_ui_overhaul]].

**Fix**: wired `self.db.update_l2_watchlist_state(...)` into the STEP 15 block, gated on
`isin` being non-empty (table PK is `isin`, NOT NULL). Also had to refactor
`_apply_l2_smoothing()` to track a real persistent `in_watchlist` boolean in
`self.l2_score_state[isin]` — the old version only derived one-shot enter/exit *transition*
events from `smoothed_prev` vs the threshold, with no actual membership memory, which isn't
enough to know what boolean to write to the DB each day (and technically allowed a false
re-"ENTRA" log if smoothed dipped into the 60-70 dead zone and raw crossed 70 again). New
logic: enters when `!was_in_watchlist && smoothed>=70`, exits when `was_in_watchlist &&
smoothed<60`, otherwise holds — true hysteresis with memory.

Deployed & verified on prod: table went from 0 rows forever to 226/236 populated after one
full monitor cycle; 0 currently `in_watchlist=true` (all today's scores <70) — expected given
current market conditions, not a sign the fix is broken.

## New feature: "Radar Rimbalzo — Test EMA20" (3rd radar, complementary to Radar Anticipato)

User's idea: catch ETFs **already above** EMA20 that pull back toward it but reverse — bounce
— **before piercing it**, i.e. a successful support retest during an ongoing uptrend pullback.
Deliberately the mirror-opposite population of Radar Anticipato (which only looks at ETFs
still *below* EMA20, approaching for the first time).

**Why it's not redundant**: today's dashboard has a real blind spot here — if price dips below
EMA20 even a single day, L1's persistence counter (condition 2) resets and the ETF drops to
L2 with zero visible trace that it was "almost L1 yesterday, dipped, now recovering." This
radar surfaces exactly that case.

- `ETFTechnicalAnalyzer.compute_pullback_bounce_signal()` (`technical_analysis.py`): finds a
  local minimum ("V" shape) in `dist_ema20` over a lookback window (default 10gg) — distance
  must stay ≥0% throughout (never truly pierced, else it's a different pattern: re-entry after
  a real break), the segment before the minimum must slope down, the segment after must slope
  up with R²≥min_r2 (same noise filter as `compute_approach_signal`'s), and the minimum can't
  sit at either edge of the window (needs ≥2 points on both sides for a real V, not a
  monotonic trend in one direction).
- `GET /api/bounce-radar` (`app.py`) — exact structural mirror of `/api/approach-radar`:
  candidates pulled from cached `dashboard_data.json` levels 1/2/3 (L0 excluded, different
  context), fast pre-filter on today's `dist_ema20>=0` before paying for the OHLC
  fetch+regression per candidate.
- New collapsible dashboard section "🔁 Radar Rimbalzo — Test EMA20", open by default, sorted
  desc by `buy_count` — same convention as Preferiti/Radar Anticipato above.
- Deployed & verified live: 19 ETF flagged on the very first run (e.g. TELE.PA score 96.7,
  EMID.L 91.1, both plausible pullback-in-uptrend cases).

## Backtest of both radars as real entry triggers vs L1 + 2 new Shadow Monitors

User asked whether the two radars above made sense to test as actual entry triggers (not
just informational) and how to compare against L1/L0. Built `backtest_radars.py` (new,
committed) — reuses `backtest_l1.py`'s Golden Dataset walk-forward exactly (same
FrozenDataFetcher, same TARGET_FAMILIES universe, same IN 2023-08-05→2025-08-05/OUT
2025-08-05→2026-08-05 split, same cost model 5+5€/26% tax) but the entry trigger is
`compute_approach_signal()`/`compute_pullback_bounce_signal()` instead of `suggest_level()`;
exit reuses the same real `calculate_sl_suggerito_l1`/`calculate_stop_gain_dynamic`. L1
reference = production `suggest_level()` with no overrides, simulated in the SAME run for a
true apples-to-apples comparison (not old certified numbers from a different batch/universe).
L0 not re-simulated (different mechanism, mean-reversion not trend-following) — only cited
as context from the already-certified CANDIDATE_MODEL_L0_20260808 numbers.

⚠️ **Found the SAME known corrupted-data ticker again** (`3LAM.MI`, already flagged in
[[etf_family_viability_survey_2026_08_24]] — a fake +19,147% trade there) — this time it
produced a fake +11,960% single trade in the "bounce" radar's IN-sample results, inflating
PF from a real ~1.34 to a fake 5.88 and MaxDD to a nonsensical 649% (the raw cumulative-%
MaxDD metric from `optimize_hyperparameters.py::extra_metrics()` also doesn't scale sanely
past a few hundred trades — not comparable to the ~30-150-trade candidates it was designed
for; ignore MaxDD in any radar-vs-L1 comparison, it's not a real risk figure here).

**Certified numbers (10k€/trade, `3LAM.MI` excluded, 229/231 tickers, both radars use
production-default `lookback`/`min_r2` — 7d/0.3 approach, 10d/0.3 bounce)**:

| | L1 reale (produzione) | Radar Anticipato | Radar Rimbalzo |
|---|---|---|---|
| IN  | N=37 WR=59.5% PF=1.90 | N=932 WR=43.1% PF=1.54 | N=1085 WR=52.5% PF=1.38 |
| OUT | N=17 WR=52.9% PF=1.45 | N=381 WR=49.1% PF=**1.93** | N=435 WR=54.9% PF=**1.56** |

Both radars **improve PF out-of-sample** (opposite of the overfitting signature seen
elsewhere in this project) and have near-zero overlap with real L1 entries on the same
ticker within ±10 days (approach 0.0%, bounce 1.2% — see `compute_overlap()` in the script)
— genuinely different opportunities, not noise around the same gate. Trade volume ~25-30x
L1's, but WR/PF per trade both lower than L1's — "more quantity, lower quality per trade"
rather than a replacement for L1.

**Shadow Monitor built and deployed same day** (`shadow_monitor_radars.py`, new module,
STEP 8h/8i in `monitor.py::run()`): `model_name` = `candidate_radar_approach_20260825` /
`candidate_radar_bounce_20260825`. Candidate universe mirrors the live `/api/approach-radar`
(levels 2/3) and `/api/bounce-radar` (levels 1/2/3) endpoints exactly. Exit reuses the same
real L1 SL/TP functions (no duplicated logic). Two new email variants in
`alerts.py::_SHADOW_VARIANTS` (`RADAR_APPROACH` teal #16A085, `RADAR_BOUNCE` orange #CA6F1E).
Smoke-tested on 15 real tickers before deploy (0 errors, entries matched expectations), test
positions cleaned from DB before the real deploy. First live cycle (2026-08-25, post-deploy):
**4 approach entries** (UTI.MI, EPRE.PA, IPRP.AS, IPRE.DE), **19 bounce entries** (TELE.PA,
EMID.L, GRE.PA, LGQM.DE, CN1.PA, WEXU.DE, ECR3.DE, LYY7.DE, COMH.MI, PHAU.L, SXR2.DE,
WSML.L, IWQU.L, COPM.MI, IWDE.L, SGLD.MI, IGLN.L, PHPT.MI, EXS1.DE), 0 errors, 236/236 ETF
analyzed OK.

**Extraction query at next checkpoint** (same pattern as every other candidate):
```sql
SELECT ticker, entry_date, exit_date, exit_reason, gross_pct_gain, status
FROM etf_shadow_positions WHERE model_name IN
  ('candidate_radar_approach_20260825', 'candidate_radar_bounce_20260825')
ORDER BY model_name, entry_date;
```

## ⚠️ Real bug found — and my first fix attempt made it WORSE, reverted (same session)

While checking Shadow Monitor health, found a genuine pre-existing data-quality bug
unrelated to anything above: **two different real funds share the same Yahoo ticker
`UST.PA` in `etf_monitoraggio.xlsx`** — `LU1829221024` (Amundi Core Nasdaq-100 Swap UCITS
ETF **Acc**, unhedged — confirmed via Yahoo `/v1/finance/search?q=` and the chart endpoint's
`longName`, this IS the correct owner of `UST.PA`) and `LU1954152853` (the **EUR Hedged**
share class of the same fund, wrongly also tagged `UST.PA`). Both were getting IDENTICAL
price/OHLCV/technical-analysis output (verified: both showed price 102.32, same EMA/RSI/ADX)
despite being genuinely different NAVs (hedged vs unhedged).

**First fix attempt (WRONG, reverted same session)**: Yahoo ISIN search for `LU1954152853`
resolved to `LU1954152853.SG` (Stuttgart, shortName "Lyxor Nasdaq-100 UCITS ETF - EU" — a
legacy Lyxor-branded listing surviving in Yahoo's index after the Amundi/Lyxor merger) with
a plausible, genuinely different EUR price (~20.50 vs UST.PA's ~102) confirmed via direct
`query1.finance.yahoo.com/v8/finance/chart/` curl calls. Applied this ticker to the Excel
(`docker exec` + openpyxl, live via bind mount) — **but never tested the actual fetch path
the app uses**. `yfinance.Ticker('LU1954152853.SG').history()` returns **empty**
("possibly delisted; no price data found") even though the raw Yahoo chart API and
`.info` metadata both resolve fine — a real yfinance-vs-raw-API discrepancy, not a typo.
Also tried `.F`/`.DE` suffixes, both 404 on yfinance. Because `get_etf_history()`'s
DB-fallback path (`monitor.py`) silently returns the last cached row when a fresh fetch
fails, the dashboard kept showing the SAME stale duplicated price with **no error surfaced**
— worse than the original bug (frozen forever + silent, vs at least visibly-updating-but-
duplicated before). **Reverted** `LU1954152853`'s ticker back to `UST.PA` (status quo ante)
rather than leave broken/frozen data. Committed both the wrong fix and the revert to git
(commits `224a349` then `25f04e7`) for a clean trail.

**Still an open, unresolved issue** — do NOT re-apply `LU1954152853.SG` without first
verifying `yfinance.Ticker(...).history()` actually returns rows (not just checking the raw
Yahoo REST API, which behaves differently). Finding the real correct ticker likely needs the
fund provider's own factsheet/KID (Amundi's site) rather than an automated ISIN search — not
done this session, low priority (L3, buy_count low, no real position affected).

## Operational lesson (repeated twice this session)

`docker restart` / `docker compose up -d --force-recreate` on `etf_monitor_system-app-1`
kills any `docker exec -d` background process running inside the container (e.g. a
long-running scratch backtest) — same warning already in CLAUDE.md re: production
(`/root/etf_monitor_system` bind mount), confirmed again here for `./deploy.sh`'s container
recreate step specifically. **Always check for an in-flight background computation before
restarting/redeploying the container** — wait for it to finish first if one is running,
rather than losing 15-20 minutes of compute.
