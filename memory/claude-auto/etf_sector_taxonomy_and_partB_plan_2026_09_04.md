---
name: etf-sector-taxonomy-and-partb-plan-2026-09-04
description: "Part A SHIPPED — ETF taxonomy (Asset Class/Geografia/Settore) + \"Momentum Settori\" dashboard view (now with clickable rows + Settore/Geografia/Categoria filter bar). Part B CLOSED same day — every mechanism tested (deep-recovery extension, sector rotation incl. LEV, dynamic PAC split) failed validation. No new active mechanism; Momentum Settori stays a read-only tool."
metadata: 
  node_type: memory
  type: project
  originSessionId: bfa51328-4875-4391-a8a1-5a8b8ed7311a
  modified: 2026-09-04T14:03:22.961Z
---

Two-part project the user asked for on 2026-09-04, after using per-ETF detail charts to
make buy/hold/sell calls and asking "can the system analyse sector by sector, like AI".

## Part A — SHIPPED 2026-09-04 (commit `32c6b19`, deployed)

**Goal:** clean multi-dimensional taxonomy for all 236 ETFs → a "momentum per settore"
ranking view. Motivated by the `Categoria` column being a mess (51 values mixing geography
/ asset class / sector / style in ONE field — e.g. `CHIP.MI` semiconductors tagged "Stati
Uniti"; only 2 AI ETFs findable when there are ~9).

- **`etf_taxonomy.py`** (new) — `classify(nome, categoria) -> {asset_class, geografia, settore}`
  from ~40 name-keyword rules. 236 ETFs, 0 low-confidence. User reviewed the full CSV and
  said "confermo" (no corrections). CLI `--write` adds/updates 3 Excel columns.
  **Does NOT touch `detect_family()` or the `Categoria` column** → L0/L1 engine unchanged
  (respects the lockdown). The 3 columns are an editable OVERRIDE: monitor uses them if
  filled, falls back to `classify()` if empty.
- **Excel** — 3 new columns `Asset Class` / `Geografia` / `Settore` (cols P/Q/R, appended,
  nothing reads by index so safe). `smart_restore.py` preserves them (only touches col 1).
- **`monitor.py`** — `build_taxonomy_rollup(dashboard)`: aggregates ETFs (from
  `dashboard['levels']`) by Settore and Geografia → per bucket: n, %L1+L2, median %1M/1W/1G,
  median RSI/ADX, breadth (% above EMA20), `momentum_score` = mean of percentile-ranks on
  [med_1m, med_1w, breadth_ema20], 0-100, only for buckets n>=2. Saved to
  `dashboard_data.json['taxonomy_momentum']`. `analyze_etf` / `_empty_result` / `etf_data`
  now carry `asset_class`/`geografia`/`settore`. `update_excel` self-heals the 3 columns.
  Bucket `—` (bonds) relabelled `Bond & Monetario`.
- **`dashboard.html`** — collapsible "📊 Momentum Settori" section: sortable table,
  Settori/Geografie toggle, 🥇🥈🥉 on top-3 by score. Data-driven from `allData` (no fetch).

23 sector buckets, ~45 true sector/thematic ETFs cleanly bucketed. First live snapshot
(pre-final-monitor): Commodity Broad top score, Giappone top geo, AI & Robotics near bottom.

**Debatable calls the user accepted as-is:** GENY/ELCR → Technology; IUSB (timber) →
Materiali; the 7-8 `3x` leveraged ETPs → settore "Leva Titolo Singolo", geo Globale.

## Part B — QUEUED (not started)

**Goal:** family by family, scan the frozen Golden Dataset (2022→2026) for every episode
where an ETF rose **>10%** trough→peak, then feature-extract the indicator fingerprint at
the START (earliest catchable entry) vs the TOP vs a non-episode baseline → derive
family-specific entry/exit rules that would have caught those big-growth runs.
Method = the same "feature extraction" already used on the 80 native-7/7 trades. Swing
detector (ZigZag) + no-look-ahead entry study + IN/OOS split + Shadow Monitor for anything
that clears the bar (N≥30, explicit decision — never auto-promote).

**This IS the momentum/parabola mechanism half-decided 2026-09-03** — see
[[etf_l1_gate_widening_analysis_2026_09_01]] and [[etf_post_lockdown_todo_20260906]] item
18b. Different objective from L1 (which = "strong safe trend"): catching +10% runs needs
momentum/breakout logic that DROPS the RSI cap and dist-EMA20 cap.

**Reality checks:** bond/defensive families ~0 episodes; only equity_sviluppati,
settoriali_growth, oro, metalli_industriali, mercati_emergenti, crypto have enough sample.
Watch for regime artifacts (bull-window mirages — burned repeatedly).

### LEV — leveraged single-stock mechanism, FOLDED INTO Part B (user decision 2026-09-04)

The 7-8 `3x` daily ETPs (3LNV/3SNV NVIDIA, 3LTS Tesla, 3LAP Apple, 3LAM Amazon, 3LFB Meta,
3LMS Microsoft, 3ITL FTSE MIB). Family `leva_single_stock`, L1 disabled (`min_buy_count:
8`) + L0 blacklisted — 12/12 losing trades over 3yr, structural volatility decay from daily
reset. User wants a **dedicated tested mechanism**, and chose to fold it into Part B (same
method: momentum-burst capture + hard % stop + TIME STOP — LEV would be the first mechanism
in the whole system with a hold-days cap).

LEV specifics to carry into the Part B study, treating `leva_single_stock` as one family:
- **Signals on the UNDERLYING stock** (NVDA/TSLA/… — clean long Yahoo history), P&L on the ETP.
- **Synthetic 3x** for pre-ETP history: simulate 3x-daily-reset from underlying returns
  minus ~0.35%/yr cost drag; validate against real ETP in the overlap window.
- Extra 3x-specific entry gate: **realized-vol ceiling** (only ride the 3x when the
  underlying trends smoothly — high vol = high decay). And RSI(underlying) < ~75 at entry
  (opposite of L1 — don't buy the 3x after a parabola).
- Hard % stop (−8/−15%, not EMA-trailing) + time stop ~10-15 trading days + momentum-break exit.
- The **−3x short (3SNV)** almost certainly loses long-term (equity drift) → likely drop or hedge-only.
- Bar: OOS PF ≥ ~1.5, stable IN→OOS. If it only works in the 2023-24 AI bull → REJECT and
  document "don't" (we'll have tested it, which is what the user asked).
- `min_buy_count: 8` stays until/unless promoted via Shadow + N≥30.

## Sequencing
Part A done. Part B next — but per the 2026-09-03 decision it sits behind item 15
(Directa-faithful exit model) and item 17 (L1 exit analysis) in
[[etf_post_lockdown_todo_20260906]]; the momentum/LEV work is item 18b, lowest priority.
(Superseded same day — user pulled Part B forward and ran it to completion; see verdict below.)

## PART B — FINAL VERDICT (same day, 2026-09-04) — CLOSED, nothing promoted

User's framing that triggered the full run: "if crypto/gold/AI is running now and we have
no way to catch it, something's wrong with only L1+L0." Tested every angle honestly with
the project's standard discipline (frozen data where possible, IN/OOS or walk-forward
splits, reject on overfitting signature, no pooled-family shortcuts):

**Phase 1-2 (episode study, 6 families kept: equity_sviluppati, mercati_emergenti,
settoriali_growth, metalli_industriali, oro_metalli_preziosi, crypto_digital_assets):**
>10% runs are **oversold-bounce shaped** (entry RSI ~34-46 vs ~50 baseline, price near/below
EMA20, elevated realized vol), not breakouts. 79-93% catchable ~2 days after the trough with
12-17% of the run still left — genuinely tradeable in principle. Crypto showed **zero**
indicator discrimination at entry (RSI gap ≈0) — not timeable at all.

**Phase 3 / Track 1 (extend L0-style deep-recovery to the other 3-4 families, first pass
64 combos, then a proper 96-128 combo re-test with drawdown-from-peak + bullish divergence
added to the entry — the conditions the first pass had omitted):**
- First pass: REJECTED outright — OOS PF 0.24-0.48 across the board, classic overfit
  (mercati_emergenti: +2,045€ IN → -7,422€ OOS on the "best" combo).
- Wide re-test: **equity_sviluppati survives** (IN pf 4.67 → OOS pf 2.7, WR 76%) — but
  that's exactly what production L0 already does (only whitelisted family). EM/growth/
  metalli **still fail OOS** (pf 0.46-0.72) even with divergence+drawdown added. Verdict:
  deep-recovery genuinely only works on equity_sviluppati; extending it is dead. Positive
  side-effect: this *validates* L0's existing design (dd+divergence aren't optional).

**Track 2 (sector rotation, the "ride the leader" mechanism) — the one that looked
promising, then didn't:**
- US sector SPDRs (2003-2026, live Yahoo): K=1 (single best sector), 12-month momentum,
  monthly rebalance → spectacular: +1871% vs SPY +670%, and **beat SPY through GFC (-9% vs
  -55%) and the 2022 bear (+59% vs -19%)**. Looked like a real mechanism #3.
- **European validation (iShares STOXX 600 sector family, Xetra, 2008-2026) killed it**:
  loses to buy&hold by 145-193pp over 14 years, and in the 2022 bear it did *worse* than
  the benchmark (opposite of the US result — no clean crisis-winner rotation happened in
  European sectors that year). **Walk-forward rolling windows are the decisive number**:
  beats buy&hold on both return+drawdown only 9-22% of rolling 3-5yr windows. The US
  result was a fluke of US-specific sector dispersion (energy 2022), doesn't generalize.
- LEV (leveraged single-stock, folded into this track per user's 2026-09-04 request):
  never reached — moot once the base rotation mechanism failed validation; the frozen
  ETP price data for `leva_single_stock` is separately confirmed corrupted (2.2M% "gains",
  scale errors) so any future attempt must use underlying-stock + synthetic-3x, not the
  ETP series directly.

**Bonus test same day — dynamic PAC contribution split** (tilt VWCE/GAGG monthly
contribution ±15% around 75/25 based on equity breadth from Momentum Settori, tiers
>70%→65/35, 40-70%→75/25, <40%→85/15): backtested 2022-02→2026-08 on frozen breadth +
live VWCE.MI/GAGG.MI. **Loses to a flat 75/25 on both return and drawdown** (+34.1%/-13.6%
tilt vs +34.8%/-13.8% fixed) — statistically indistinguishable from noise, and any equity
tilt at all (87/13, 100% VWCE) beats both because 2022-26 was equity-dominated. Rejected.

**Bottom line — nothing from Part B gets promoted, no Shadow Monitor built.** The gap the
user identified (no mechanism for "asset class is leading, ride it") is real but
**unfillable with a validated systematic approach** on the evidence gathered. Confirms
Decision 3 from 2026-09-03 as final, not provisional: PAC = VWCE + GAGG fixed 75/25 +
cash reserve; active = L1 (strong trend) + L0 (deep dip, equity_sviluppati only) — the
extremes only. **Momentum Settori stays a discretionary reading aid** (don't-chase-the-top
filter, L0-hunting-ground-at-the-bottom filter, regime read) — never an automated signal
and never a contribution-split formula. Don't re-open this without genuinely new data or
a different, currently-unconsidered mechanism — every reasonable angle on "catch the
leader" has now been tested and lost.
