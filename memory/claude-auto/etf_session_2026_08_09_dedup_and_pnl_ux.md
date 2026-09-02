---
name: etf-session-2026-08-09-dedup-and-pnl-ux
description: "Session 2026-08-09/10 — found and fixed a DB-wide price-history duplication bug (92% of ETFs, live signals affected), an isin=NULL write bug, a None-comparison crash for monetario_liquidita, and reworked the personal SL/TP UI + P&L display (gross+net) after repeated user confusion between Stop Trigger and Prezzo Limite."
metadata: 
  node_type: memory
  type: project
  originSessionId: 8e77372c-670e-4a4a-8be8-419a0ec0398b
  modified: 2026-08-09T22:03:26.200Z
---

## What happened (chronological, most important first)

**1. `etf_price_history` duplicate-row bug — found while investigating a UI complaint about duplicate dates in the ETF detail history table.**
- Root cause: table has UNIQUE(ticker, date), not UNIQUE(isin, date). Before the 2026-08-04 fix (see main CLAUDE.md), the monitor saved daily rows keyed by the raw Yahoo ticker (e.g. `WAT.MI`), Close-only (via the old `save_close_bulk`). After the fix, it saves keyed by `ticker=isin` with full OHLCV. Both series coexisted for the same isin+date without colliding (different `ticker` values), so nothing enforced dedup.
- Scope (verified via SQL, not estimated): **217 of 236 ETFs**, **56,246 duplicate rows**, period ~2025-05/06 → 2026-07-08. Every duplicate pair was exactly one OHLCV-complete `ticker=isin` row + one Close-only legacy row — zero exceptions found.
- **Real impact, not cosmetic**: `get_ohlc_by_isin()` — the function `monitor.py` uses *every day* to compute EMA20/SMA50/**SMA200**/RSI/ADX for live L0/L1/L2/L3 decisions — does `ORDER BY date DESC LIMIT 260` with no dedup. With ~half the rows duplicated in that window, a "260 day" fetch only covered ~140 real calendar days, so SMA200 (the bear/bull regime filter) was computed on a shorter real window than intended, for 217/236 ETFs, for about a month.
- Fix applied: backed up the table (`etf_price_history_backup_20260809`), deleted the 56,246 legacy rows (always keeping the OHLCV-complete one), added `UNIQUE(isin, date) WHERE isin IS NOT NULL` as a safety net, re-triggered the monitor.
- **Checked same-day impact**: compared the last pre-fix run vs the first post-fix run — both showed all 236 ETFs at L3, zero L0/L1/L2 in either. So no visible level flip *that specific day* — the bug was real but nothing was at the margin when it got fixed. Don't assume "no visible change" generalizes to other days.
- **Backtests are NOT affected** — verified this explicitly since the user asked "does this invalidate everything we tested." All backtest/grid-search scripts (`backtest_l1.py`, `optimize_hyperparameters.py`, `backtest_l0_v2.py`, `optimize_l0*.py`) read from the separate `etf_price_history_frozen` Golden Dataset table (populated 2026-08-07 by `freeze_historical_dataset.py` fetching live from Yahoo, independent of `etf_price_history`). Confirmed that table has zero duplicates too. So `CANDIDATE_MODEL_B_20260807`, `CANDIDATE_MODEL_L0_20260808`, `BASELINE_OFFICIAL_20260807` all still stand.
- **What WAS affected and is still only partially resolved**: `shadow_monitor.py` (tracking the L1 candidate live since 2026-08-07) uses `get_ohlc_by_isin()`, i.e. the buggy table — its first ~3 days of live tracking (08-07 → 08-09) ran on dirty data. Validation window runs to 2026-09-06, so it's a small fraction, but worth remembering when the results get pulled — don't treat those first 3 days' worth of entries as clean if precision matters.

**2. Separate, related bug found while backfilling isin after the above: `save_ohlcv_bulk()` in `database.py` never wrote the `isin` column at all** (only `ticker`). Existing rows got `isin` populated by a one-off historical backfill; every new row from ~2025-07-21 onward (3,280 rows across 227 tickers) had `isin=NULL`. Didn't break lookups (both `get_close_by_isin`/`get_ohlc_by_isin` fall back to `ticker=%s`), but silently defeated the new UNIQUE(isin,date) safety net for any new duplicate-causing bug. Fixed: added an `isin` param to `save_ohlcv_bulk`, `ON CONFLICT ... DO UPDATE SET isin = COALESCE(EXCLUDED.isin, ...)`, `monitor.py` now passes it. Backfilled the 3,280 rows; found and removed one genuinely bad data point in the process (`PHAU.MI` legacy ticker, one row with a price ~15% off-trend, from the same pre-08-06 ticker-migration mess documented in CLAUDE.md).

**3. `suggest_level()` crash for `monetario_liquidita`**: `rsi_entry_low`/`rsi_entry_high`/`adx_entry` are `null` in the YAML for this family (by design — "no ADX/RSI"), but the comparisons (`p['rsi_entry_low'] <= rsi_val <= ...`) didn't guard against the *threshold* being None (only guarded `rsi_val`/`adx_val`). Caught per-ETF by the monitor's try/except (fell back to L3, didn't crash the run) but was silently erroring every single day for this family. Fixed: both conditions now short-circuit to `True` (not-applicable → doesn't block) when the family has no threshold defined.

**4. `%1G`/`%1W`/`RSI14` columns in the ETF detail history table were hardcoded to `—`** — literally never computed, with a stale `# TODO: need to compute` comment in the code. Fixed by computing them server-side in `app.py`'s `/api/etf-detail` (same Wilder RSI formula used elsewhere, pct_change over 1/5 trading days matching `technical_analysis.py`'s own pct_1d/pct_1w convention).

**5. UI: PDF download added for the ETF detail modal.** Discovered `html2pdf.js` was already loaded in `dashboard.html` (`<script src=...>`) but never used anywhere — added the 📄 button + `downloadDetailPDF()` using it.

## SL/TP personal-field UX rework — see [[etf_directa_trigger_vs_limit_confusion]] for the recurring confusion this caused

Renamed "SL Personale"/"TP Personale" to "Prezzo Limite (Stop) Personale"/"Prezzo Limite (TP) Personale" for non-OCO brokers (Directa), conditional on `order_prices['parallel_ok']` (from `order_pricing.py`, keyed off `broker` — Webank keeps the old SL/TP naming since it has real parallel OCO). Same relabeling applied in the portfolio table row *and* the ETF detail modal's SL-management panel (had to add `broker`/`order_parallel_ok` to `/api/portfolio-sl`'s response — it didn't carry broker info before).

Also added a **net P&L line** (gross − €10 Directa round-trip commission, then 26% capital-gains tax only on the residual if positive) directly under the existing gross P&L box in the detail modal — user explicitly asked for this to become permanent, not a one-off calc. Constants: `DIRECTA_COMMISSION_ROUNDTRIP = 10`, `CAPITAL_GAIN_TAX_RATE = 0.26`, both in `dashboard.html`.

Found and fixed one more pre-existing bug in the same area: the personal-SL input (`sl-pers-${isin}`) never had a `value=` binding to the saved DB value (unlike the TP one) — so it silently reset to blank every ~2 minutes (the periodic `loadPortfolio()` refresh), making it *look* like saves weren't persisting even though they were.

## How to apply
- If asked to re-verify anything about L0/L1 levels or SMA200-based regime decisions from **before 2026-08-09**, flag that the price history had this duplication bug up to that date — don't treat pre-fix dashboard snapshots as ground truth for SMA200-driven decisions.
- The Golden Dataset (`etf_price_history_frozen`) is the one to trust for anything backtest-related, always was, independent of this whole story.
- When editing `etf_price_history` writes in the future, always populate `isin` explicitly — don't rely on `ticker == isin` convention alone.
