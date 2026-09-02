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
