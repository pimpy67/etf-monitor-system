---
name: etf-pac-plan-autotracking-2026-09-02
description: "Feature request (approved, NOT yet built) — auto-generate PAC contributions from a stored plan instead of manual entry each time. Confirmed plan params inside."
metadata: 
  node_type: memory
  type: project
  originSessionId: 8ac1bdd4-8873-403f-82c8-16bc1c375114
  modified: 2026-09-02T07:38:16.131Z
---

User set up a recurring PAC on **Directa** and wants the ETF monitor's `/pac` page to
track it **automatically** from a stored plan, no manual entry per contribution.

## Confirmed plans (2026-09-02) — TWO plans, equity + bond

| field | Plan 1 — Equity | Plan 2 — Bond |
|---|---|---|
| ETF | VWCE — Vanguard FTSE All-World Acc | Amundi IS Core Global Aggregate Bond Acc |
| ISIN | `IE00BK5BQT80` | `LU1437024729` |
| Listing traded (Directa) | **VWCE.MI** (Excel row is `VWCE.DE` → switch) | **GAGG.MI** (Excel row is `GAGG.PA` → switch) |
| Execution type | **fixed quantity: 2 shares/exec** | **fixed quantity: 1 share/exec** |
| Days | 1, 8, 15, 23 of every month | 1, 8, 15, 23 of every month |
| Commission | 0 € (Directa PAC) | 0 € |
| Start | 2026-09-01 (backfill 01/09) | 2026-09-01 (backfill 01/09) |
| Amount recorded/exec | shares × close price of exec day, fee 0 | same |

Both ETFs already tracked in the universe with ISIN-keyed price history (VWCE since
2025-05, GAGG since 2025-05). Resulting monthly € flow ≈ 1330 equity / 195 bond = 87/13
(user's real portfolio is ~75/25 — flagged to user, they chose 1 GAGG lot anyway).

## ✅ DEPLOYED & VERIFIED 2026-09-02 (commit 374478a code, 4e72a20 memory sync)

- Migration 008 applied by hand (`psql -f` — deploy.sh does NOT run migrations).
  `scripts/seed_pac_plans.sql` run → 2 plans live, stale test row (id 2) deleted.
- STEP 3b `_process_pac_plans()` verified end-to-end: created the 01/09 backfill —
  VWCE.MI 2q @166.115=332.23€, GAGG.MI 1q @48.54=48.54€, `source='auto'`.
- Excel tickers switched VWCE.DE→VWCE.MI, GAGG.PA→GAGG.MI (container restarted).
- `templates/pac.html`: manual "Registra versamento" form REMOVED (user asked — all auto
  now), "Piani PAC automatici" section + `auto` badge added. **Commit still pending.**
- yfinance has NO 2026-09-01 for VWCE.MI/GAGG.MI (spotty coverage, known) though 01/09 was
  a trading day → inserted an interpolated 01/09 close (source='interp-pac') so the
  backfill could price it. Watch that the 08/09 exec gets a real price — the monitor's
  daily save wasn't reliably landing new VWCE.MI/GAGG.MI rows.
- The deploy was rough: `docker compose build` on the loaded 1-vCPU VPS took ~48 min
  (layer export alone 18 min), looked hung at 30 min — killed it (image was already
  built), finished the container recreate manually.
- Also fixed during the session: real Turkey L0 position (`LU1900067601`, id 19) had
  `shares` NULL → set to 100, wrote SL 48.96 / TP 60.18 (family mercati_emergenti).
  Ticker is `TUR.PA` — should be `TUR.MI` for Directa, batch with future ticker cleanup.

## Build plan (deploy-gated — CANNOT deploy while a backtest runs in the container;
## `./deploy.sh` force-recreates `etf_monitor_system-app-1` and would kill it)

1. **Tickers**: switch Excel `etf_monitoraggio.xlsx` `VWCE.DE`→`VWCE.MI` AND `GAGG.PA`→`GAGG.MI`
   (verify `yfinance.Ticker('VWCE.MI'/'GAGG.MI').history()` works first — per
   [[etf_ticker_must_match_directa_listing]]). `etf_price_history` is keyed by ISIN so the
   PAC lookup (`/api/pac`) is unaffected by the ticker change. Also fix stale old tickers in
   `etf_favorites`/`etf_portfolio_entries` if present. **Restart container after editing xlsx
   (bind-mount inode gotcha).**
2. **New table** `etf_pac_plan` (migration): `isin, ticker, fund_name, shares_per_exec,
   exec_days (int[] = {1,8,15,23}), fee_eur, start_date, active, created_at`.
   `database.py`: get/add/update helpers.
3. **`monitor.py` new STEP** (after price fetch): for each active plan, for each nominal day
   in `exec_days` for every month from `start_date` to today: compute the target execution
   date = first trading day ≥ nominal day; if `today >= target_date` AND no
   `etf_pac_contributions` row exists for `(isin, target_date)` AND a close price is
   available for that date → insert `shares=shares_per_exec, price=<close on target_date>,
   amount_eur=shares*price, fee_eur=<plan fee>, broker='Directa'`. Marks it auto-generated
   (add a `source` column: 'auto' | 'manual', default 'manual' for backcompat).
4. **Backfill 2026-09-01**: insert the 01/09 execution (2 × VWCE.MI close of 2026-09-01).
5. **Cleanup**: delete the stale test row `etf_pac_contributions` id=2 (VWCE.DE, 998.04,
   6sh, fee 9.50, 2026-08-25 — the "prova" from 2026-08-24 that memory said was removed but
   wasn't).
6. **`/pac` page** (`templates/pac.html` + `/api/pac` in `app.py`): show the active plan,
   mark auto rows, allow editing/deleting a generated row if the real Directa fill differed
   (rare: close vs execution price < 0.3-0.5%, noise for the PAC-vs-active comparison).

## Context / why it matters

The `/pac` page (built 2026-08-24, see [[etf_pac_feature_2026_08_24]]) is the reality check
for "Decision 3 / meta" in [[etf_l1_gate_widening_analysis_2026_09_01]] — passive VWCE PAC
vs the active L1/L0 system. Making contribution entry automatic keeps that comparison
honest over time without relying on the user to log every one.
