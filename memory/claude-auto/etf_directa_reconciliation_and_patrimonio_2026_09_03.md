---
name: etf_directa_reconciliation_and_patrimonio_2026_09_03
description: "New /riconciliazione page in the ETF monitor: upload the Directa P_TOTALE_*.xlsx export, compare vs etf_portfolio_entries (active). Decision on linking the separate PATRIMONIO project: DON'T merge — Directa is the single source of truth, both systems reconcile to it. Check here before touching portfolio-sync or the PATRIMONIO project."
metadata: 
  node_type: memory
  type: project
  originSessionId: f0161496-431a-4e32-b1ad-b7395c4f0d9e
  modified: 2026-09-04T19:22:26.791Z
---

2026-09-03. User asked whether to connect this ETF monitor with the separate
**PATRIMONIO** project (`../PATRIMONIO/`) so the ETF holdings coincide "validated and
alla pari".

## PATRIMONIO project — what it is

Single-file `dashboard.html`, vanilla JS, **100% client-side, no server, no DB**. User
drags 4 broker Excel exports (WeBank `.xls`, Directa `P_TOTALE_*.xlsx`, OnlineSIM `.xls`,
BancoPosta `.xlsx`) → parsed in-browser → net-worth aggregation. Data in localStorage
only. **Dormant** — 2 commits, last 2026-08-07. ETF sleeve ~24k€ of ~233k€ total (rest is
mostly BTP on WeBank).

## Decision — DON'T merge the two systems

Different data models, different purposes: PATRIMONIO = monthly accounting snapshot;
monitor = daily operational trading tool (entry/SL/TP/L0-L1/exit). Overlap is only
`{isin, shares, avg cost, broker}`. **Neither is the master — Directa (the broker) is.**
The monitor only knows what it was told and drifts if you forget to register a buy/sell.

- ✅ Build: reconciliation report in the monitor (done, below).
- Later, only if PATRIMONIO is revived: have it pull the ETF sleeve from the monitor's
  `GET /api/portfolio` instead of re-parsing Directa — but keep the Excel fallback
  (offline-by-design is a stated PATRIMONIO principle). Only after the reconciliation
  proves the monitor stays accurate.
- ❌ Never bidirectional auto-sync. ❌ No shared DB/service (overkill for a 24k€ sleeve).

## What shipped — `/riconciliazione`

- **`reconcile_directa.py`**: `parse_directa_export(path|bytes|file)` (header auto-detect —
  the position table starts at a row containing both `Strumento` and `Isin`, ~row 8, after
  metadata rows `Conto:` / `Data estrazione:` / `Valore portafoglio:`; cols
  `Strumento|Ticker|Isin|Prezzo|Trend %|Quantita|Valore di carico|Valore attuale|Gain/Loss €|...|Prezzo medio|Bid|Ask|Divisa`;
  numbers may be IT `1.234,56` or plain float). `reconcile(directa_positions,
  monitor_entries, monitored_isins)` — **joins on ISIN** (Directa tickers are bare `MEU`/`PHAG`,
  monitor uses Yahoo tickers, so ISIN is the only reliable key), aggregates the monitor
  side by ISIN (add-to-position lots summed). Also a CLI: `python reconcile_directa.py file.xlsx`.
- **`app.py`**: `GET /riconciliazione` → `templates/riconciliazione.html`;
  `POST /api/reconcile` (multipart `file`, parsed in RAM, never saved) → JSON
  `{matched, only_directa, only_monitor, summary, directa_meta, warnings}`.
  `matched` flags qty mismatch (`abs Δ > 0.01`) + shows cost-basis Δ%.
- **`dashboard.html`**: nav link `🔀 Riconciliazione` next to `💰 PAC`.
- No DB schema change. Read-only against `etf_portfolio_entries` via `get_portfolio_entries()`.

Tested against a real Directa export (2026-08-07 sample in `../PATRIMONIO/export/`). Parser OK.
Also verified live 2026-09-03 against `P_TOTALE_S7997_20260903.xlsx` (user's current holdings):
4 positions perfectly aligned (TELE.PA/TUR.PA/Water-Acc/EM-Latam), VWCE flagged (it's PAC),
GAGG L0 row had shares=0.

## 2026-09-04 — "Allinea a Directa" button added (committed `<pending>`, deploy slow on overloaded VPS)

- `reconcile()` gained `pac_isins` param (from `db.get_pac_plans()`): PAC holdings on Directa →
  `pac` bucket (no action); a PAC ISIN in the active portfolio → `pac_spurious` (remove).
- `reconcile_directa.apply_alignment(db, plan)` + `POST /api/reconcile/apply`. Plan shape:
  `{qty_updates, new_positions, closures, remove_spurious}`. Directa = truth on qty/cost.
  qty updates auto; new positions need user L0/L1 choice + date; closures need user exit price.
- `database.update_portfolio_shares()` added.
- The spurious **GAGG L0 row (id 21, created 2026-09-03 18:50, shares NULL) was deleted**
  via `DELETE /api/portfolio/LU1437024729` — PAC contributions untouched, did not reappear
  after monitor re-runs (one-off, not a recurring auto-add). Active portfolio now = 4
  positions, all matching Directa.
- **Verified 2026-09-04**: user ran `/riconciliazione` for real (a full pass, not just the
  GAGG cleanup above). DB confirms 4 clean active `etf_portfolio_entries`, all L0, all
  `shares > 0`, no ghost rows: `FR0014002CH1`(800sh), `IE00B27YCK28`(300sh),
  `LU1834988609`(100sh, BRES), `LU1900067601`(100sh). Apply flow works end-to-end.

## Real data issue surfaced by the first test run (needs a fresh Directa export to confirm)

Against the stale Aug-7 sample, the monitor's 5 active L0 positions had **0 overlap** with
Directa. Notably **GAGG (LU1437024729) is an active L0 portfolio entry with `shares` = 0** —
a tracking artifact (added without a share count). Water is held as **Acc** (FR0014002CH1,
800 sh) in the monitor vs **Dist** (FR0010527275) in the old Directa file — different share
class. Run the reconciliation with a current `P_TOTALE` export to get the true picture.

Related: [[fund_monitor_portfolio_reconciliation_2026_08_27]] (same idea, fund side),
[[etf_no_auto_exit_real_positions]], [[etf_l1_two_exit_mechanisms]].
