---
name: etf-l0-project-2026-08-07
description: "L0 (Deep Recovery) project, started 2026-08-07, continued 2026-08-08. PRAGMATIC sweep finished (TP=16% confirmed, dd/rsi/recovery non-discriminating). l0_regime (FAST/SLOW) sweep is the current in-flight work — check process status on VPS before trusting any 'finished' claim. Check this first if resuming L0 work."
metadata: 
  node_type: memory
  type: project
  modified: 2026-08-08T18:02:02.017Z
  originSessionId: 1a1d6401-bbcc-42ce-b6a2-6fc42a3f1f19
---

Same-day follow-on to [[etf-session-2026-08-07-golden-dataset-and-sweep]] (that memory covers L1/Golden Dataset/Shadow Monitor — read it first for the day's full arc). This one is specifically the L0 sub-project, started after the user asked "possiamo iniziare ad analizzare L0" and confirmed "OK NUOVO PROGETTO L0".

**Built (all committed+pushed, all on `main`):**
1. `backtest_l0_v2.py` (commit `72d4c04`) — clean L0 backtest engine reusing REAL production functions (`suggest_level_0()`, `calculate_sl_suggerito_l0()`, `calculate_tp_suggerito_l0()`). Explicitly does NOT reuse the pre-existing `backtest_l0.py`/`backtest_l0_full.py`/`backtest_l0_rigorous.py` — those have their own hand-rolled copy of the SL formula with WRONG thresholds (2%/5% instead of the real 5%/15%) and skip whitelist/regime/divergence entirely. Don't trust those old files for anything.
2. `technical_analysis.py::suggest_level_0()` gained an optional `precomputed` dict param (RSI/EMA20/SMA50), same pattern as `suggest_level()`, cross-validated at 0 discrepancies (320 checks).
3. `optimize_l0.py` (commit `c86d479`) — the L0 grid search. Key design: `l0_take_profit_pct` is decoupled from the (dd_threshold, rsi_max, recovery_min_pct) entry scan — TP never changes *which* trades open, only where they exit, so entries are found once per (dd,rsi,recovery) combo and then replayed cheaply for each TP value. Grid: dd∈{0.05,0.065,0.08} × rsi_max∈{40,45,50} × recovery∈{0.010,0.015,0.020} × tp∈{0.10,0.12,0.14,0.16} = 27 "expensive" combos × 4 cheap TP replays.

**Two real production bugs found and fixed while investigating a data anomaly (not a dedicated audit — found by chance, worth remembering that L0 anomalies are worth chasing):**
1. **CRITICAL, commit `600f51b`**: the L0 whitelist/blacklist (meant to restrict L0 entries to `equity_sviluppati` only, added 2026-08-06 commit `e81ae75`) had **never actually been active**. `global_params` is a top-level YAML key (sibling of `families:`), but `self.p` only ever gets assigned the per-family sub-dict — `self.p.get('global_params', {})` always returned `{}`, so `l0_whitelist`/`l0_blacklist` were always empty lists and the gate was always skipped. Confirmed with live data: 6 ETFs were classified L0 on the dashboard at time of discovery, zero of them `equity_sviluppati` (leva_single_stock, commodities, mercati_emergenti×3, oro_metalli_preziosi) — exactly the speculative-sector entries the whitelist was built to prevent. Fixed by reading `global_params` from `self._FAMILIES_CONFIG` (class-level) instead of `self.p`. Verified post-fix: L0 count dropped 6→0. No real portfolio positions were affected (checked against `etf_portfolio_entries`).
2. **Family classification gaps, commit `564de92`**: `family_detection` patterns in `config/etf_families.yaml` didn't match several REAL Excel category strings — `'Obbligazionari Governo'`/`'Obbligazionari Corporate'` (no hyphen, pattern required `'obbligazionari - governativi'`/`'- corporate'` with hyphen) and `'Liquidità'` (accented, pattern was unaccented `'liquidita'`) all fell through to the `equity_sviluppati` default — wrong RSI/ADX/mm200 thresholds for 4 bond/cash ETFs. Also `'Azionari Alternativi'` (`LVO.MI`, "Amundi S&P 500 VIX Futures Enhanced Roll UCITS ETF" — a VIX futures product that decays structurally via contango, -82% over 4 years, daily moves of ±15-17%) fell through the same way and was generating 25 spurious L0 trades in the backtest (vs 0-8 for every other ticker) before being caught. Reclassified to `leva_single_stock` (which is L0-blacklisted, so this also fixes L0 eligibility, not just L1 parameter calibration).

**Impact of fix #2 on the L0 baseline**: removing LVO.MI's distortion changed the 3-year baseline (equity_sviluppati, native params: dd=6.5%, rsi_max=45, recovery=1.5%, tp=16%) from 216→184 trades, and — much more importantly — average net return/trade from a wildly inflated **+17.4%** down to a believable **+3.04%** (win rate 36.6%→39.0%, P&L 10k€/trade €352,834→€53,910). This is the number to trust; the original 216-trade/+17.4% run should never be cited again.

**IN FLIGHT when the session paused (2026-08-07 evening)**: `optimize_l0.py --sweep` launched detached (`docker exec -d`) on the VPS, ~4/27 expensive combos done at pause time (~400s/combo measured, full sweep ETA ~3 hours from launch). Survives session end and SSH disconnect — the only thing that would kill it is a `docker compose ... --force-recreate` deploy, which must NOT be run until the sweep finishes. Results land in `/app/data/optimize_l0_result.json` and the full log in `/app/optimize_l0_output.log` on the VPS.

**Early signal (from the first few combos, NOT final)**: dd=0.05/rsi=40-45/rec=0.01-0.015/tp=0.16 → IN N=146 WR=42.5% PF=**3.18**, OUT N=44 WR=50% PF=**4.51** — much stronger than the native-params baseline (+3%/trade). Also noticed `recovery_min_pct` (0.010 vs 0.015) and `rsi_max` (40 vs 45) both produced IDENTICAL trade counts in early combos — likely non-binding in this range, mirroring the `target_floor_pct`-was-irrelevant finding from the L1 sweep earlier the same day. Not confirmed until the full 27-combo matrix is in.

**Resume checklist for next session**:
1. Check `ssh -i ~/.ssh/id_ed25519_vps root@76.13.37.133 "docker top etf_monitor_system-app-1 | grep optimize_l0"` — if still running, wait; if done, read `/app/optimize_l0_output.log` tail (has the "Top combinazioni" ranked table) or pull `/app/data/optimize_l0_result.json`.
2. Analyze the full dd×rsi×recovery×tp matrix, check in/out-of-sample consistency (same discipline as the L1 sweep — prefer combos where OOS holds up or improves, not just high in-sample PF), find the L0 Candidate Entry Zone.
3. Document as `CANDIDATE_MODEL_L0_20260807` (or similar) in CLAUDE.md, same format as `CANDIDATE_MODEL_B_20260807` for L1.
4. Not in scope yet: SL-side sweep for L0 (`calculate_sl_suggerito_l0`'s formula is hardcoded, not family-parameterized — would need code changes to make it sweepable, same kind of work as L1's Phase 2). Also not started: a Shadow Monitor for the L0 candidate (same pattern as the L1 one already live, but L0 hasn't earned one yet since there's no final candidate).
5. Remember: production is still under the 30-day parameter lockdown until 2026-09-06 — an L0 candidate, however good, does not get deployed to `etf_families.yaml` before then, same rule as L1's candidate.

**IMPORTANT correction to steps 2-3 above, found while checking sweep progress (2026-08-07, ~21/27 combos done)**: `dd_threshold`/`rsi_max`/`recovery_min_pct` turn out to have **zero effect** on entry count in this dataset — every combo from dd=0.05 to dd=0.08, rsi_max 40/45/50, recovery 0.010/0.020 produces the exact same N=146 in-sample trades. Only `tp` changes anything (PF 2.11→3.18 as tp goes 0.10→0.16).

Root cause (verified by reading `technical_analysis.py:972-1041`, not a bug — confirmed by design): `suggest_level_0()` tries the FAST path (flash-crash via ATR z-score) and SLOW path (bear-market via days-below-SMA200) *before* falling through to PRAGMATIC (the only path that reads `dd_threshold`/`rsi_max`/`recovery_min_pct`). `equity_sviluppati` has `l0_regime` configured in the YAML (lines ~70-78), so FAST/SLOW are active — and since entry count never budges across the dd/rsi/rec grid, it looks like **100% of the 146 in-sample trades enter via FAST or SLOW, none via PRAGMATIC**. `optimize_l0.py`'s override code (`find_entries()`) is correct — it's the sweep design that's mistargeted: it varies parameters that gate a path nothing is using.

Revised plan for next session (superseding steps 2-3 exactly as originally written):
1. Let the current sweep finish (harmless, was ~40 min from done as of this note) — its only real signal is the TP curve (16% best so far), everything else in the matrix will be redundant rows.
2. Audit the actual FAST/SLOW/PRAGMATIC split among the 146 trades to confirm the "100% FAST/SLOW" read (not yet directly measured, only inferred from constant N).
3. If further L0 entry optimization is wanted, the real sweep target is `l0_regime` params (`dd_threshold_atr_multiple`, `regime_min_days_below_sma200`, `dd_min_duration_days`, `flash_crash_window_days` etc. — see YAML lines 70-78 for equity_sviluppati's values), not `l0_entry`. Alternative: temporarily disable FAST/SLOW to isolate and measure PRAGMATIC alone.
4. `CANDIDATE_MODEL_L0_20260807` should document TP=16% as the one real finding from this sweep, not present the dd/rsi/rec grid as if it were informative.

---

## Update 2026-08-08 — PRAGMATIC sweep finished, l0_regime (FAST/SLOW) sweep launched

**`optimize_l0.py --sweep` finished clean** (108 combos, 179.7 min, no errors). Result confirms
everything predicted above: `dd_threshold`/`rsi_max`/`recovery_min_pct` are completely
non-discriminating (identical N=146 IN / N=44 OUT across every dd/rsi/rec combination — only
`tp` moves the numbers). **TP=16% is the one real finding**: PF 2.11→3.18 in-sample,
3.97→4.51 out-of-sample as tp goes 0.10→0.16, monotonic, no sign of a peak before 16% (grid
didn't test beyond 16%, worth trying higher next time e.g. 0.18-0.22 the same way the L1
micro-sweep found 15% wasn't the true ceiling by testing further out — see
[[etf_session_2026_08_07_golden_dataset_and_sweep]]).

**Started `optimize_l0_regime.py`** (new file, committed `9d52517`, pushed to `main`) — the
correctly-targeted sweep per step 3 above. Before writing it, read the actual FAST/SLOW code
(`technical_analysis.py::_analyze_l0_fast_path`/`_analyze_l0_slow_path`, lines ~663-758) to
verify which `l0_regime` YAML params are real:
- **Confirmed dead in code** (never read anywhere in `technical_analysis.py`):
  `capitulation_volume_multiplier`, `reclaim_ema_fast_period`, `reclaim_ema_slow_period`. The
  actual EMA-reclaim periods used by `_get_l0_confirmation_signal()` are hardcoded (20 for
  fast, 50 for slow), not read from these YAML keys. Don't waste sweep budget on them.
- **Confirmed non-gating** (read but only feeds a diagnostic field, not the entry decision):
  `dd_threshold_atr_multiple` — only used to compute `drawdown_normalized` for display,
  never compared against anything in `slow_path_valid`.
- **The only 4 params that actually gate entry**: `flash_crash_window_days` +
  `flash_crash_zscore_threshold` (FAST), `regime_min_days_below_sma200` +
  `dd_min_duration_days` (SLOW — misleadingly named, it's actually read and divided by 100
  to become a drawdown % threshold, not a day count).

Design: two separate sweeps (`--sweep-fast`: window∈{2,3,4}×zscore∈{3.0,3.5,4.0,4.5} = 12
combos; `--sweep-slow`: min_days∈{5,8,10,15}×dd_min∈{2,3,4,6} = 16 combos), run **sequentially**
via a single `docker exec -d` chain (`... --sweep-fast ... && ... --sweep-slow ...`) — VPS has
1 vCPU only, don't run both at once, don't contend with the live evening monitor run. PRAGMATIC
left at YAML baseline throughout (proven not to matter). Reuses
`load_and_precompute`/`simulate_exit_for_tp`/`aggregate` from `optimize_l0.py` unchanged, only
`find_entries_regime()` is new (same shape as `find_entries()` but overrides `analyzer.p['l0_regime']`
instead of `analyzer.p['l0_entry']`). Smoke-tested on 5 tickers before the full launch (all
ok, mostly SLOW-mode entries as expected).

**Launched 2026-08-08, ~06:00 UTC**, `docker exec -d etf_monitor_system-app-1`, logs at
`/app/optimize_l0_regime_fast_output.log` and `/app/optimize_l0_regime_slow_output.log`
(SLOW log only appears once FAST finishes). ETA ~3 hours total (12+16=28 combos × ~5-6.7
min/combo, first combo measured at 301s). Survives SSH disconnect (same as the prior sweep) —
the only thing that kills it is a `docker compose ... --force-recreate` deploy, which must NOT
run until this finishes, on top of the existing 30-day parameter lockdown (until 2026-09-06)
that already blocks deploying any resulting candidate to `etf_families.yaml`.

**First combo result (window=2, zscore=3.0, in-sample)**: N=148, entry_modes={FAST: 2, SLOW:
146, PRAGMATIC: 0} — confirms the "100% FAST/SLOW, PRAGMATIC unused" read from the earlier
note, and shows SLOW dominates over FAST by a wide margin even at the most sensitive FAST
setting tested (window=2, zscore=3.0, both more permissive than baseline 3/4.0). Not yet known
whether this holds across the full grid — check the finished log for the entry_modes field the
script logs per row.

**Resume checklist**:
1. `ssh -i ~/.ssh/id_ed25519_vps root@76.13.37.133 "docker exec etf_monitor_system-app-1 sh -c 'for p in /proc/[0-9]*; do cat \$p/cmdline 2>/dev/null | tr \"\\0\" \" \"; echo; done | grep optimize_l0_regime | grep -v grep'"` — `ps`/`docker top` are NOT reliably available in this container image (ps returned "not found" once, worked via piped grep another time — inconsistent, use the /proc scan, it's reliable); empty output = finished (or crashed — check the log tail either way).
2. Read both log tails for the "Top combinazioni" ranked tables, or pull `/app/data/optimize_l0_regime_fast_result.json` / `_slow_result.json`.
3. Compare against the TP=16%-only PRAGMATIC baseline (N=146 IN/N=44 OUT, PF 3.18/4.51) — the question this sweep answers is whether loosening/tightening FAST or SLOW triggers finds something better on the same in/out-of-sample split.
4. Same discipline as every prior sweep this week: distrust a single-run trade count as ground truth (see `backtest_l1.py` non-reproducibility saga in `etf_monitor_system/CLAUDE.md`) — this sweep reads from the frozen Golden Dataset batch `2026-08-07` via `get_frozen_ohlcv`, so it should be reproducible, but if numbers ever look inconsistent between runs, check `--frozen-batch` matches.
5. Document final result as `CANDIDATE_MODEL_L0_20260807` (or a new dated tag if this sweep meaningfully changes the picture) in `etf_monitor_system/CLAUDE.md`, same format as `CANDIDATE_MODEL_B_20260807` for L1. Still blocked from production by the lockdown until 2026-09-06.

---

## Update 2026-08-08 (later same day) — both sweeps finished clean, SLOW candidate found

Checked via the /proc scan: no `optimize_l0_regime` process running, both logs complete with
"Top combinazioni" tables, no errors in either.

**FAST sweep result (54.9 min, 48 rows)**: confirms the prediction — FAST path contributes
only 0-2 of ~146-148 total trades regardless of `flash_crash_window_days`/
`flash_crash_zscore_threshold`, so these params are non-discriminating. Best PF stays 3.18
(tp=0.16), same ceiling as the PRAGMATIC-only sweep already found. Nothing actionable here.

**SLOW sweep result (73.3 min, 64 rows)**: this one has real signal. YAML baseline for
`equity_sviluppati` is `regime_min_days_below_sma200=10, dd_min_duration_days=4` (confirmed
by reading `config/etf_families.yaml:70-78`) → IN N=146 PF=3.18 WR=42.5% | OUT N=44 PF=4.51
WR=50.0% (matches the earlier PRAGMATIC-sweep baseline exactly, as expected — same trades).

Best candidate found, using the same discipline as every prior sweep (prefer OOS holding up
or improving over IN, not just high IN PF — reject anything that looks overfit):
**`regime_min_days_below_sma200=5, dd_min_duration_days=4, tp=0.16`** → IN N=152 PF=**3.38**
WR=44.1% | OUT N=62 PF=**4.84** WR=51.6%. Beats the baseline on *every* metric (IN and OUT
PF, IN and OUT N) — not an isolated in-sample fluke. Runner-up with even larger N:
`min_days=5, dd_min=3` → IN N=169 PF=3.38 WR=43.8% | OUT N=72 PF=4.42 WR=48.6%.

Rejected despite the highest raw in-sample PF in the whole grid: `min_days=15, dd_min=2` (IN
PF=3.7) — OOS collapses to PF=2.88 WR=37.5%, the same overfit signature already seen and
discarded in the L1 sweep (mm200_delta=-1 case). `regime_min_days_below_sma200` more
permissive (5, i.e. shorter time-below-SMA200 required) generalizes better than the YAML
default (10) or tighter (15) in this dataset.

**Documented and Shadow Monitor built, same session (2026-08-08)**:
1. `CANDIDATE_MODEL_L0_20260808` written up in `etf_monitor_system/CLAUDE.md` (same format as
   `CANDIDATE_MODEL_B_20260807`), including a params table (SL row added per user request —
   unchanged, existing tiered `calculate_sl_suggerito_l0` formula) and the corrected note that
   `dd_min_duration_days=4` is actually a 4% drawdown threshold divided by 100, not a day
   count (misleading name, user caught this).
2. `shadow_monitor_l0.py` (new file) — same pattern as `shadow_monitor.py` (L1): copies
   `analyzer.p`, overrides only `p['l0_regime']['regime_min_days_below_sma200'] = 5`, leaves
   everything else (TP=16%, SL formula, PRAGMATIC) at YAML baseline. Filters to
   `L0_FAMILIES = {'equity_sviluppati'}` only (the sole family reachable past the whitelist
   gate). Entry check: `suggest_level_0(close, high, low, current_level=3)` on `days=250`
   history (requires ≥220 rows, same threshold as `backtest_l0_v2.py`). Exit check on open
   shadow positions: `calculate_sl_suggerito_l0`/`calculate_tp_suggerito_l0`, both untouched
   by the candidate. Reuses `etf_shadow_positions` (already model-agnostic via `model_name`
   column) — no migration needed. `MODEL_NAME = 'candidate_model_l0_20260808'`.
3. Hooked into `monitor.py::run()` as STEP 8b, right after the existing L1 Shadow Monitor
   call, same try/except-wrapped non-blocking pattern.
4. **Deployed to VPS via the fast path** (scp → docker cp → `docker restart
   etf_monitor_system-app-1`), not via `./deploy.sh` and **not committed/pushed to git** —
   local working tree and VPS `/root/etf_monitor_system/` now have this change on disk, but
   `main` does not. Verified post-restart: clean container startup (scheduler ready, DB
   connected), `python -c "import shadow_monitor_l0"` succeeds inside the container, override
   confirmed applied (`p['l0_regime']['regime_min_days_below_sma200'] == 5` on the candidate
   analyzer) while a fresh `ETFTechnicalAnalyzer` for the same family still reads `10` —
   confirms the copy-before-override pattern isn't leaking into the shared class-level config.
   `py_compile` clean on both files. No background sweep process was running at restart time
   (checked first), so nothing was killed.
5. **Still open**: commit+push to `main` (ask before doing — not yet requested), SL-side sweep
   for L0 (`calculate_sl_suggerito_l0` still hardcoded, not family-parameterized).
6. **Extraction at end of lockdown (2026-09-06)**: same query pattern as L1, swap
   `model_name`:
   ```sql
   SELECT ticker, entry_date, exit_date, exit_reason, gross_pct_gain
   FROM etf_shadow_positions WHERE model_name = 'candidate_model_l0_20260808'
   ORDER BY entry_date;
   ```
