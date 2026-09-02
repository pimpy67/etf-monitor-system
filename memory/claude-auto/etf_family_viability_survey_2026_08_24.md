---
name: etf-family-viability-survey-2026-08-24
description: "Full 14-family survey (Golden Dataset, 3yr) of which asset families ever produce a real (or even smart_6_macd) L1 entry — only 1 of 14 is a real trend-following driver, 12 are dead or lose money under this gate"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4a28a71f-f9f3-43eb-a590-0169332a8e39
  modified: 2026-08-24T12:54:17.835Z
---

Triggered by the user noticing `oro_metalli_preziosi` never reaches L1 (see
[[etf_session_2026_08_23_display_bug_db_corruption_gold_finding]] for how that was first
found) and asking "quali altre famiglie non entrano mai, e come li gestiamo". Surveyed all
14 families via `optimize_hyperparameters.py`'s existing fast/precomputed engine
(reuses `backtest_l1.py::simulate()`/`aggregate()`, no new simulation logic), Golden
Dataset batch `2026-08-07`, full 3-year window 2023-08-05→2026-08-05.

## Result table

| Family | Cluster | N trades (3yr) | Win rate | Net P&L (10k€/trade) | Verdict |
|---|---|---:|---:|---:|---|
| equity_sviluppati | core | 38 | 67.7% | +9,204€ | **Real driver — the only one** |
| settoriali_growth | core | 10 | 66.7% | +1,639€ | Modest, thin sample |
| mercati_emergenti | core | 13 | 27.3% | **-2,261€** | **Net loser — candidate for exclusion** |
| metalli_industriali | core | 3 | 33.3% | -352€ | Too thin to judge |
| oro_metalli_preziosi | core | 0 | — | — | Dead — needs a different mechanism |
| bond_governativi | difensivo | 2 | 0% | -362€ | Dead, and loses when it fires |
| bond_corp_hy_em | difensivo | 1 | 0% | -173€ | Dead, and loses when it fires |
| settoriali_difensivi | difensivo | 0 | — | — | Dead |
| real_estate_reit | difensivo | 0 | — | — | Dead |
| private_equity_buffer | difensivo | 1 | 0% | -321€ | Dead, and loses when it fires |
| commodities | speculativo | 0 | — | — | Dead |
| leva_single_stock | speculativo | 0 | — | — | Dead (already excluded from native_7 too) |
| crypto_digital_assets | speculativo | 0 | — | — | Dead |
| monetario_liquidita | (none) | n/a | n/a | n/a | Different logic by design, not trend-following |

**core cluster numbers use the exact `CANDIDATE_MODEL_B_20260807` params** (mm200=7%
absolute, adx_entry-4, TP target_max_pct=15% — the ones actually in Shadow Monitor today).
**difensivo/speculativo numbers use plain baseline smart_6_macd** (no override — those two
clusters' own 2026-08-07/08 sweeps already showed relaxing params doesn't help them, see
[[etf_post_lockdown_todo_20260906]] section 4, so testing the core-tuned override on them
wouldn't be meaningful). The `core` figure of 64 total trades doesn't exactly match the
certified split (IN=31/OUT=18=49) because this run used one continuous 3-year window
instead of two separately-simulated IN/OUT windows — expected methodology difference, not
a reproducibility bug (same frozen data, same code, deterministic).

## Headline: 1 of 14 families is a real trend-following driver

Only `equity_sviluppati` shows a clean, strong, reliable edge. `settoriali_growth`
contributes modestly on a thin sample. Every other family (12 of 14) is either
**completely dead** (0 trades in 3 years) or **actively loses money when the gate does
fire** (all 4 trades across the whole `difensivo` cluster were losses — not just rare,
wrong every single time it triggered). This isn't a parameter-tuning problem for those 12
— the trend-following philosophy (EMA/SMA alignment + persistence + MACD-rising) itself
doesn't fit bonds (too low-volatility, whipsaws on tiny moves), speculative/leveraged
assets (too noisy, real trends rarely survive the persistence+MACD-rising combo), or
precious metals (macro-burst-driven, not steadily trending — see the gold diagnosis).

## Action taken / proposed (not yet built, discussed with user 2026-08-24)

1. **`mercati_emergenti`**: proposed for the same treatment `leva_single_stock` already
   got in `native_7` (`min_buy_count: 8`, made unreachable) — but for `smart_6_macd`
   specifically, since that candidate isn't live yet. Not applied — `smart_6_macd` itself
   isn't in production, so there's nothing to change in the live YAML right now. Revisit
   if/when `smart_6_macd` is ever promoted.
2. **`oro_metalli_preziosi` — L0 tested 2026-08-24, encouraging but N too small**:
   bypassed the L0 whitelist **in-memory only** (no YAML change) and ran
   `backtest_l0_v2.py::simulate_l0()` — the real `suggest_level_0()` + real
   `calculate_sl_suggerito_l0`/`calculate_tp_suggerito_l0` formulas — on the same 4 gold
   tickers, Golden Dataset, 2023-08-05→today. Result: **3 trades**, all via the SLOW
   (bear-sustained) path, WR 66.7% (2 TP wins +13.37%/+12.12%, 1 SL loss -4.52%), avg net
   +6.99%, total net P&L +2,096.77€ (10k€/trade). Much more promising direction than L1
   (flat zero) and the right asymmetry (small loss, large wins) — but N=3 is far below
   this project's own N≥30 confidence bar (same caveat as the original "3 trades, 100%
   WR" native_7 equity_sviluppati result that was later judged inconclusive). **Verdict:
   promising enough to track, not to promote** — natural next step is a dedicated Shadow
   Monitor for L0-on-gold (same non-invasive pattern as the other 3 shadow candidates,
   `model_name` e.g. `candidate_l0_oro_20260824`) to accumulate real forward data, not a
   whitelist change. Nothing built yet — flagged, not shipped.
3. **Bond/difensive families + speculative families (8 total)**: no concrete proposal yet
   beyond "the trend-following philosophy doesn't fit them" — bonds likely need much
   tighter/different thresholds (or a carry/duration-based approach entirely unrelated to
   momentum), speculative assets likely need a volatility-adapted entry (wider bands,
   shorter persistence) or should simply stay out of any automated-entry logic. Not
   designed or backtested — flagged as an open question, not a plan.
4. **`metalli_industriali` — L0 tested 2026-08-24, more solid than gold**: same
   in-memory whitelist bypass, same `backtest_l0_v2.py::simulate_l0()` engine, 6 tickers
   (AIGI.MI, ALUM.MI, BATE.DE, COPA.MI, ZINC.MI — COPM.MI excluded, too short history).
   Result: **13 trades** (all SLOW path), WR 53.8% (7 TP ~+13-15%, 6 SL ~-4/-7% except
   one verified-genuine outlier -20.85% on COPA.MI 2025-07-31 — checked against the
   frozen dataset, confirmed NOT a repeat of the corruption pattern found earlier this
   session: the price shift is permanent, doesn't revert after a few months like the 6
   flagged corrupted ISINs did), avg net +3.91%, total net P&L +5,088€ (10k€/trade).
   Still under N≥30, but **the stronger candidate of the two L0 tests so far** (4x the
   sample of gold, 2.4x the net P&L). Shadow Monitor built same day, see below.

## Shadow Monitors built 2026-08-24 (both live, zero production impact)

Both follow the identical pattern: `suggest_level_0()` + real
`calculate_sl_suggerito_l0`/`calculate_tp_suggerito_l0`, L0 whitelist opened **only
in-memory** (mutates `ETFTechnicalAnalyzer._FAMILIES_CONFIG['global_params']['l0_whitelist']`
for the duration of the call only, restored in `finally` — `config/etf_families.yaml`
itself was never touched, whitelist stays `['equity_sviluppati']` in production). Wired
into `monitor.py::run()` as STEP 8d/8e, wrapped in try/except (non-blocking), email via
`alerts.py::send_shadow_entries()` new variants `L0_ORO`/`L0_METALLI`.

- `shadow_monitor_l0_oro.py` — `model_name='candidate_l0_oro_20260824'`
- `shadow_monitor_l0_metalli.py` — `model_name='candidate_l0_metalli_20260824'`

Both deployed via `./deploy.sh`, first cycle confirmed clean (no errors) for the gold
one; metalli one deployed same session, verify next session that its first cycle also
ran clean if not already confirmed.

⚠️ **Bug found same day, a few hours later**: both only bypassed `l0_whitelist`, never
`l0_blacklist` — and both `oro_metalli_preziosi`/`metalli_industriali` are ALSO in
`l0_blacklist`, which `suggest_level_0()` checks independently and blocks on regardless of
whitelist. Both shadow monitors were structurally guaranteed to find zero entries, forever,
until fixed. **Fixed and hot-patched into the running container same day** — both functions
now clear the family from `l0_blacklist` too. See the "🔴 Correction" section below for the
full story and corrected backtest numbers (oro N=3→12, metalli N=13→23 on the same window).

**Extraction query at next checkpoint** (same pattern as the other candidates):
```sql
SELECT ticker, entry_date, exit_date, exit_reason, gross_pct_gain, status
FROM etf_shadow_positions WHERE model_name IN ('candidate_l0_oro_20260824', 'candidate_l0_metalli_20260824')
ORDER BY model_name, entry_date;
```

## Final decision on the remaining 8 dead families (2026-08-24) — closed, not "TBD"

- **Bond/difensive (5: bond_governativi, bond_corp_hy_em, settoriali_difensivi,
  real_estate_reit, private_equity_buffer)**: **no active entry mechanism, passive
  monitoring only.** Not just silent — the 4 total L1 trades across all 3 years were
  **all 4 losses** (0% win rate), and these are inherently low-volatility instruments
  where the reward potential of any timing system is structurally small. Not worth
  the engineering effort. Decided, not revisit without new evidence.
- **Speculative (3: commodities, leva_single_stock, crypto_digital_assets)**:
  **explicitly excluded, no open research project.** Zero signals under every tested
  config (native_7, smart_6_macd baseline, the relaxed sweep). `leva_single_stock`
  already has a strong documented negative track record (-61% total over 3yr, 10/12
  losing trades). A volatility-breakout style alternative (CTA-like, not
  trend-following) is technically conceivable but would be a much bigger research
  project (new indicator logic, not parameter tuning) on an asset class where mistakes
  are costly (gaps, extreme volatility) — not to be opened without an explicit,
  deliberate user request, not as a natural continuation of today's work.

This closes the "what do we do with the dead families" thread opened by the user this
session — see the table above for the final map of all 14 families.

## Dashboard "remove dead families?" — discussed 2026-08-24, decided NOT to remove

User asked whether families that end up with no viable entry mechanism (bonds,
speculative/leva/crypto — see section above) should just be deleted from the dashboard
outright. Recommended against full removal: the monitor already collects their price
history regardless (needed for exactly this kind of periodic re-evaluation), some may
already be in the user's Preferiti/portfolio, and "never fires today" isn't the same as
"zero informational value" (price/regime/drawdown context still useful). Proposed
alternative for the post-lockdown dashboard rework: a visual grouping ("Motore attivo"
vs "Monitoraggio passivo") rather than deletion — not built, just a design idea to pick
up later.

See [[etf_post_lockdown_todo_20260906]] item 7 for the standing oro_metalli_preziosi
research direction — this file is the fuller multi-family context behind that entry.

## Follow-up same day: L1 block deployed + L0 tested on the 8 dead families

User asked three things after seeing this survey: (1) block L1 on the 5 bond/defensive
families given their 4/4 loss record, (2) noted a real gap — their actual portfolio is
diversified 75%/25% equity/bond, but with bonds inert there's no active monitoring on that
25%, (3) asked to test L0 on all 8 dead families the same way as oro/metalli.

**1. Done — `min_buy_count: 7→8` deployed for all 5** (`bond_governativi`,
`bond_corp_hy_em`, `settoriali_difensivi`, `real_estate_reit`, `private_equity_buffer`) in
`config/etf_families.yaml`, same mechanism/precedent as `leva_single_stock`. Deployed via
`./deploy.sh` (commit `f5a97b3`). Both CLAUDE.md files (root + etf_monitor_system) updated
per the sync rule — root table's `leva_single_stock` row was already stale (showed 7,
YAML had 8) even before this change, now corrected too.

**3. Done — L0 tested on all 8** (`backtest_l0_v2.py::simulate_l0()`, same in-memory
whitelist bypass pattern as oro/metalli, one-off scratch script, never committed). Result:
**0 trades across all 8 families, 78 tickers, 3-year Golden Dataset window** — a much
cleaner negative than oro/metalli (which had 3 and 13 trades respectively). Confirms these
8 aren't just unsuited to trend-following (L1) — mean-reversion-on-drawdown (L0) finds
literally nothing either. No further L0 research planned for these 8 without new evidence.

## 🔴 Correction, same day: L0-on-8-families "0 trades" was a bug, not a finding

The original "0 trades across all 8 families" result (section 2 above, as first written)
was **wrong** — caused by a real bug, not a genuine negative signal. `suggest_level_0()`
checks `l0_whitelist` and `l0_blacklist` independently
(`technical_analysis.py:927-933`) — bypassing only the whitelist doesn't help if the family
is ALSO in the blacklist, which blocks regardless. All 8 families tested (and
`oro_metalli_preziosi`/`metalli_industriali`) are in `l0_blacklist` in the current YAML.
The one-off test script (and, more seriously, the **already-live**
`shadow_monitor_l0_oro.py`/`shadow_monitor_l0_metalli.py`, deployed the evening before)
only cleared the whitelist — both were structurally guaranteed to find zero entries,
forever, regardless of how long they ran.

**Fixed same session**: both shadow monitor files now clear the family from
`l0_blacklist` too, not just add it to `l0_whitelist`. Hot-patched into the running
container immediately, then committed/deployed normally.

**Rerun with the real fix — numbers change a lot**:
- Oro/metalli (same 2023-08-05→today window): **oro N=12** (not 3), **metalli N=23** (not
  13). Extending to the earliest safe start date given the frozen dataset's actual range
  (2022-02-15/03-08, ~17 months never used by any backtest before — all used
  `--start 2023-08-05`), safe start ≈2023-02-01 after 220-day SMA200 warm-up: **oro N=14,
  metalli N=31** (metalli crosses N≥30 in backtest alone) on a single continuous window.

  **IN/OOS split done same day (closes this item) — the extended window WEAKENS the case,
  doesn't strengthen it**: IN 2023-02-01→2025-08-05 / OUT 2025-08-05→2026-08-05.
  - Oro: IN N=14 WR=38.5% avg+1.88% | **OUT N=0** — all recent activity landed as still-open
    IN-window positions, no closed trades at all to validate out-of-sample. Can't confirm
    anything either way.
  - Metalli: IN N=29 WR=**19.2%** avg=**-2.03%** (P&L -5,283€, negative) | OUT N=4 WR=100%
    avg+14.15% (P&L +5,659€). Adding the 6 previously-unused months (Feb-May 2023) reveals
    a cluster of 6 consecutive January-February 2023 losses that flips the in-sample result
    from the earlier positive read to outright negative. OOS stays strong but N=4 is too
    thin to trust on its own.
  - **Conclusion: extending history doesn't validate oro/metalli — if anything it adds a
    real caution (metalli's true multi-year picture includes a losing stretch the shorter
    window had excluded).** No change made to the live Shadow Monitor parameters (still
    native YAML values, unchanged) — they keep running and accumulating real forward data,
    which remains more trustworthy than any further backtest slicing on these two noisy
    asset classes. This closes the "extend the backtest window" line of investigation for
    oro/metalli — don't re-open without new data or a different approach.

## CANDIDATE_L0_PAC_20260824 — DCA/PAC execution idea, tested, not promoted

User's idea, same day: for high-volatility mean-reverting families, instead of a lump-sum
L0 entry, accumulate a fixed daily amount (default €1,000/day) while the dip is still
valid, then manage the resulting average-cost position with the same dynamic SL/TP already
used for lump-sum L0. Designed as a genuine new state machine (`backtest_l0_pac.py`,
scratch): idle → accumulating (triggered by the same `suggest_level_0().l0_entry`, buys
another €1,000 increment each day unless RSI<25 invalidates — same threshold as the
existing dashboard beta rule — or price recovers above EMA20 / hits a cap of 10 days or
€10,000, which moves it to holding) → holding (manages the position via
`calculate_sl_suggerito_l0`/`calculate_tp_suggerito_l0` applied to the weighted average
cost instead of a single entry price — both functions already generic, no changes needed).
Realistic costs modeled: every daily buy pays the full €5 Directa fee, not just one entry
fee — this matters at €1,000 increments.

**Single-window result** (2023-02-01→today): oro N=13 WR=41.7% **PF=6.82** (vs lump-sum's
same-window N=14 PF implied lower) P&L+2,429€ — better than lump-sum. Metalli N=27
WR=20.8% PF=0.68 P&L**-830€** — still negative, but **less negative than lump-sum's -5,283€
on the same window** — PAC didn't fix the underlying weak signal but did reduce the
severity of the loss during the bad Feb-2023 cluster (smaller position built before hitting
SL, vs one big lump sum at the worst possible day).

**IN/OOS split immediately after (same discipline as everything else today)**: oro OUT
N=0 — same data limitation as the lump-sum extended-window test, no closed OOS trades
exist to validate either way. Metalli IN N=27 PF=0.68 (still negative) | OUT N=4 PF=inf
(all wins, too thin to trust alone).

**Verdict: PAC works as designed (validated: smaller drawdown during bad periods, no
runaway risk since SL is still % based on avg cost) but doesn't fix the underlying weak
signal on oro/metalli — the problem is signal quality, not execution style.** Not promoted,
no new Shadow Monitor built. Worth keeping the mechanism in mind for a future candidate
with a genuinely validated entry edge on a volatile asset (the execution technique itself
is sound), but don't re-propose it for oro/metalli specifically without new data changing
the underlying signal picture.

Also tried, same day, three follow-up designs on `equity_sviluppati` (all rejected):
1. **Flat position-sizing ladder on buy_count** (2/7→20%...7/7→100%): entry threshold too
   loose (buy_count>=2) — N=2,896 IN / 1,576 OUT, PF only 1.04/1.53, operationally
   unmanageable (thousands of positions, can't execute by hand on Directa).
2. **Empirical TP(+3%)/FP(0%) threshold curve** (diagnostic, not a tradeable system):
   confirmed quality rises monotonically with buy_count, 6/7 is the clear standout
   (narrowest gap of all thresholds) — independently corroborates `smart_6_macd`'s existing
   6-with-MACD-mandatory threshold, doesn't suggest an earlier entry point.
3. **Missing-single-condition ranking at 6/7**: `adx_ok` missing is by far the worst gap
   to have (TP rate 6.9%) — a weak/absent trend-strength reading is a strong false-signal
   marker even when everything else lines up. `allineamento_ok` missing alone is the least
   bad (TP rate 38.8%) — the stock is often about to complete it. But there are real
   interaction effects (adx_ok+macd_ok missing together scores BETTER than adx_ok missing
   alone) — a flat per-condition importance weighting would be a lossy oversimplification.
4. **Automated day-over-day quality-lookup exit** (train IN-sample only, frozen table
   applied OOS, genuine no-lookahead test): failed badly — N=5,731, PF=0.49, P&L=-54,028€,
   ~€200-285k capital required. Two real bugs in the approach: the lookup table scores 7/7
   WORSE than 6/7 (native 7/7 is so rare, N=2, that its sample is pure noise) causing the
   automation to exit exactly when a position reaches its best state; and comparing quality
   day-over-day as the sole exit trigger is far more trigger-happy than a real price-based
   trailing stop, causing constant premature exits.

## PAC vs. active system head-to-head (same day) — directly motivated the smart_6_macd promotion below

User asked for a fair "same money in" comparison: same €1,000/month contribution, same
2023-08-05→2026-08-05 window, comparing a genuine passive PAC (no signal, buy VWCE.DE —
Vanguard FTSE All-World, a real diversified benchmark — every month, never sell) against
the active system's real dated trades (via `backtest_l1.py::simulate()`, unmodified),
deploying the same monthly cash into a pool that only gets spent when a real signal fires.

| | Contributed | Final value | Return |
|---|---:|---:|---:|
| PAC on VWCE.DE | €37,000 | €45,634 | **+23.34%** |
| native_7 (equity_sviluppati) | €37,000 | €37,380 | +1.03% (only 1 trade fired all period — rest of the cash sat idle) |
| smart_6_macd (equity_sviluppati) | €37,000 | €39,598 | +7.02% (13 trades taken, 1 skipped for insufficient cash) |

PAC wins both times, but the gap narrows a lot with smart_6_macd (+€6,037 vs +€8,254)
because it actually deploys capital instead of leaving it idle waiting for a 7/7 signal
that almost never comes. Not a condemnation of the active system (built for capital
protection in downturns, which a pure PAC doesn't do) — just an honest fact about this
specific mostly-bullish 3-year window: staying invested beat waiting for the perfect entry.
**This result is what the user cited when asking to promote smart_6_macd to production
immediately (2026-08-24) rather than waiting for the 06/09 checkpoint** — see
[[etf_post_lockdown_todo_20260906]] item 1 for the promotion details.
- The 8 "dead" families: single-window result showed 5 of 8 positive (bond_governativi,
  bond_corp_hy_em, real_estate_reit, commodities, crypto_digital_assets) — but a proper
  IN/OOS split (`test_l0_8families_inout.py`, scratch) immediately after showed **none of
  the 5 hold up**:

  | Family | IN: N/WR/avg | OUT: N/WR/avg | Verdict |
  |---|---|---|---|
  | bond_governativi | 7/100%/+4.94% | 4/**0%**/-4.45% | Complete reversal |
  | bond_corp_hy_em | 4/33%/-0.91% | 7/100%/+12.08% | N too small both sides |
  | real_estate_reit | 9/29%/-0.43% | 2/100%/+9.71% | N=2 OOS, pure noise |
  | commodities | 11/**0%**/-4.65% | 3/100%/+15.75% | Already 0% WR on 11 IN trades |
  | crypto_digital_assets | 21/47%/+13.56% | 7/**0%**/-5.06% | Classic overfitting signature |

  **Final verdict: none of the 8 blocked families warrant an L0 Shadow Monitor** — same
  practical conclusion as the original (buggy) test, but now for the right reason. For
  crypto/commodities this actually retroactively confirms why the L0 whitelist excluded
  them in the first place (real bear-market failures, consistent with the negative OOS
  here). `bond_corp_hy_em` is already covered — better, with a robust IN=83/OUT=45 N — by
  the dedicated Bond-Trend model (see below), so no second L0 mechanism needed there.

- Also found and excluded a **corrupted data point**: `3LAM.MI` (`leva_single_stock`) had
  one trade with entry_price=0.13€ → exit=25.58€ (+19,147% gross) — a data glitch, not a
  real market move — which alone inflated the whole family's average to +101.9%/trade and
  P&L to +1.4M€. Corrected (excluding that ticker): N=124, WR=22.1%, avg=-0.61%,
  P&L=-7,410€ — negative, consistent with `leva_single_stock`'s already-known bad track
  record elsewhere in this project. Frozen-dataset corruption is a separate issue from the
  live `etf_price_history` corruption cleaned earlier this same session (different table) —
  not fully audited, just this one instance found and worked around.

**2. Done same day — CANDIDATE_BOND_TREND_20260824 designed, backtested, Shadow Monitor
live.** User explicitly asked to proceed with a third mechanism. Diagnosed first (not
guessed): walked all 7 native_7 conditions day-by-day over 40,711 ticker-days (61 tickers,
Golden Dataset) — 7/7 never happens (0.00%), 6/7 only 0.21% of days. Dominant blockers:
`allineamento_ok` (EMA20>SMA50, true only 19.1% of days) and `rsi_ok` (24.8%) — equity-
calibrated momentum filters don't fit rate-driven bond price action.

Built a genuinely separate 4-condition mechanism (`ETFTechnicalAnalyzer.
suggest_bond_trend_entry()`): price>EMA20, persistence (days_above_ema20 + slope>0),
tight distance-from-EMA20 cap, kill switch — no RSI/ADX/MACD/SMA50 at all. Exit reuses
the real `calculate_sl_suggerito_l1`/`calculate_stop_gain_dynamic` unmodified, just with a
much smaller TP target (3% vs equity's 15%).

Grid search (`backtest_bond_trend.py`, scratch) over persistence (5/8/12/15/20 days) ×
dist_max (0.3/0.5/1.0/1.5%) × TP target (3%/5%): wider bands/targets consistently degrade
out-of-sample (same overfitting signature as `mm200_delta=-1` elsewhere in this project);
longer persistence (12-20 days, vs equity's 3) is more stable, consistent with rate trends
moving over weeks not days. Chosen params (persistence=20, dist_max=0.5%, target=3%,
floor=2%) gave the most IN→OUT-stable PF of everything tested (1.71→1.68), not the
highest single in-sample number.

**Results (Golden Dataset, 61 tickers)**: IN N=191 WR=60.8% PF=1.71 P&L=+8,604€
(10k€/trade) | OUT N=76 WR=45.2% PF=1.68 P&L=+2,267€. By far the largest N of any
candidate in this project's history — but with a real caveat: many trades open on the
same calendar day across different tickers of the same family (bonds move together on
rate news), so the effective independent sample is closer to ~15-20 market events than
191 uncorrelated bets. PF is still solid and consistent IN→OUT despite that.

**Shipped, not promoted**: `shadow_monitor_bond_trend.py` (STEP 8f in `monitor.py`),
`model_name='candidate_bond_trend_20260824'`, params in `global_params.bond_trend_model`
(YAML) — never touches `min_buy_count`/native_7. Deployed via `./deploy.sh`, first real
cycle confirmed clean same day: 62 tickers checked, 4 new shadow entries (AFRN.PA,
EFRN.DE, ECR3.DE, AFLT.PA — all `bond_corp_hy_em`), 0 errors, shadow-entry email sent
successfully. Same discipline as every other candidate: N≥30 forward + explicit user
decision before any production promotion, no automatic upgrade.

Extraction query for next checkpoint:
```sql
SELECT ticker, entry_date, exit_date, exit_reason, gross_pct_gain, status
FROM etf_shadow_positions WHERE model_name = 'candidate_bond_trend_20260824'
ORDER BY entry_date;
```

## Same-day correction: pooled result was hiding a broken family — restricted to bond_corp_hy_em only

User asked (correctly) whether the 5 bond/defensive families should have DIFFERENT
parameters instead of one shared set, same as equity families do. Re-ran the grid
segmented by family (`backtest_bond_trend_perfamily.py`, scratch) instead of pooled —
found the pooled result was dangerously misleading:

| Family | IN WR/PF | OUT WR/PF | Verdict |
|---|---|---|---|
| bond_corp_hy_em | 70-76% / 2.65-3.67 | 67-80% / **4.22-6.24** | Strong on every combo tested — OOS PF systematically BETTER than IN (cleanest anti-overfitting pattern in this project) |
| bond_governativi | 54-60% / 1.54-2.19 (looks fine) | **7-13% / 0.01-0.18** | Collapses almost to zero OOS — something broke structurally for govvies in 2025-2026 |
| settoriali_difensivi | 25-46% / 0.27-0.73 | mixed, N=4 tickers | Too thin to trust |
| real_estate_reit | 40-55% / 0.54-0.93 | mixed, N=3 tickers | Too thin to trust |
| private_equity_buffer | 20-33% / 0.21-0.5 | 25-33% / 0.31-0.41 | Loses on both windows, every combo |

The pooled positive result (IN PF=1.71, OUT PF=1.68) only looked fine because
bond_corp_hy_em's excellent performance was averaging out bond_governativi's near-total
OOS collapse — a real risk had this shipped: shadow (and eventually real) positions on
government bonds under a broken model, invisible in the aggregate metric.

**Fixed same session**: `global_params.bond_trend_model` in YAML restricted to
`families: [bond_corp_hy_em]` only, params re-tuned for that family specifically
(persistence_days 20→12, dist_max_pct 0.5%→0.3%; target unchanged at 3%). New certified
metrics (26 tickers): IN N=83 WR=72.6% PF=3.43 P&L=+7,306€ | OUT N=45 WR=77.3% PF=5.89
P&L=+5,147€. Deployed via `./deploy.sh`, verified next cycle imports/runs clean. The 4
shadow positions already open (AFRN.PA, EFRN.DE, ECR3.DE, AFLT.PA) were all already
`bond_corp_hy_em` — nothing to clean up.

**Lesson for future candidates**: when a candidate spans multiple families/tickers grouped
by a cluster (not a single family), always check the per-family breakdown before trusting
the pooled aggregate — a pooled backtest can hide a badly-broken sub-segment behind a
well-performing one, exactly like `min_buy_count=6`'s 2024-vs-other-years issue found
earlier this month, but at the family level instead of the year level.
