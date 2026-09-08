---
name: etf-pac-plan-autotracking-2026-09-02
description: "PAC auto-tracking in the ETF monitor: how etf_pac_plan / etf_pac_contributions / _process_pac_plans work, and the current real 7-ETF Directa plan (synced 2026-09-08)."
metadata:
  node_type: memory
  type: project
  originSessionId: 8ac1bdd4-8873-403f-82c8-16bc1c375114
  modified: 2026-09-08T21:05:32.583Z
---

The `/pac` page tracks the user's real Directa PAC and compares it to the active L1/L0
system (see [[etf_pac_feature_2026_08_24]], [[etf_l1_gate_widening_analysis_2026_09_01]]).

## How it works

- `etf_pac_plan` (migration 008 + **011**): one row per ETF — `isin, ticker, fund_name,
  shares_per_exec, exec_days int[] (e.g. {1,8,15,23}), amount_eur_per_exec, fee_eur,
  broker, start_date, active`.
- `monitor.py::_process_pac_plans()` (STEP 3b, idempotent, non-blocking): for each active
  plan, for each nominal exec day from `start_date` to today, if no
  `etf_pac_contributions` row exists for `(isin, exec_date)` and a close price is
  available → insert one. **If `amount_eur_per_exec` is set → `shares = floor(amount /
  close)`** (mirrors how Directa fills a fixed-€ order into whole shares); else falls back
  to `shares_per_exec`. `source='auto'`.
- `etf_pac_contributions`: `UNIQUE(isin, contribution_date)`. `source` = `auto` |
  `manual` | `storico`. Real fills entered from Directa's "Storico" tab overwrite the
  auto estimate (delete the auto row / update it — the UNIQUE key means one row per
  ETF per date).
- `/api/pac` current value needs ISIN-keyed price history for **every** PAC ETF — an ETF
  with no history shows `current_value=null` and silently distorts the PAC-vs-L1/L0
  comparison (invested counts, value doesn't). So every PAC ETF must be in
  `etf_monitoraggio.xlsx`.

## Current real plan — 7 ETF, synced to Directa 2026-09-08

Directa PAC "Importi e frequenze" (fixed €/exec, whole shares within budget), max
3.472 €/mo (day 8 = 1.099 €, days 1/15/23 = 791 € each):

| ETF | ISIN | Directa ticker | €/exec | exec days | start_date |
|---|---|---|---|---|---|
| VWCE Vanguard FTSE All-World | IE00BK5BQT80 | VWCE.MI | 336 | 1,8,15,23 | 2026-09-01 |
| XMAE Xtrackers MSCI ACWI ESG Screened 2C **EUR Hedged** | IE000VXC51U5 | XMAE.MI | 328 | 1,8,15,23 | 2026-09-08 |
| GAGG Amundi Core Global Aggregate Bond | LU1437024729 | GAGG.MI | 52 | 1,8,15,23 | 2026-09-01 |
| GBSE WisdomTree Physical Gold **EUR Hedged** | JE00B8DFY052 | GBSE.MI | 50 | 1,8,15,23 | 2026-09-08 |
| DAPP VanEck Crypto & Blockchain Innovators (equity) | IE00BMDKNW35 | DAPP.MI | 25 | 1,8,15,23 | 2026-09-08 |
| HLT Amundi STOXX Europe 600 Healthcare | LU1834986900 | HLT.MI | 161 | **8 only** | 2026-09-08 |
| GOAI Amundi MSCI Robotics & AI ESG | LU1861132840 | GOAI.MI | 147 | **8 only** | 2026-09-08 |

- Only VWCE + GAGG executed on **01/09** (old 2-ETF plan). The other 5 started **08/09**
  — hence their `start_date` is 08/09, else `_process_pac_plans` invents a phantom 01/09
  buy. (Learned the hard way this session: it did, had to delete 3 auto rows.)
- Real executions loaded from Directa "Storico": 01/09 (VWCE 2@166.60, GAGG 1@48.57) +
  08/09 (all 7). **Total invested 1.217,94 € — matches Directa to the cent.**
- HLT/GOAI: `LU1834986900`/`LU1861132840` were already in the universe as `HLT.PA`/
  `GOAI.PA`; the PAC plan/contributions use the `.MI` ticker but lookups are ISIN-keyed
  so it doesn't matter. DAPP/XMAE/GBSE were **added** to `etf_monitoraggio.xlsx` this
  session (`.MI`, EUR — all three have clean Yahoo `.MI` listings matching the Directa
  fill price). Categories chosen so `detect_family()` lands: DAPP→`crypto_digital_assets`,
  XMAE→`equity_sviluppati`, GBSE→`oro_metalli_preziosi`. **Side effect**: XMAE + GBSE are
  in the `smart_6_macd` core set (promoted 24/08) so they *can* fire L1 signals now —
  informational only, user buys them via PAC regardless. Flag if it becomes noise.

## Keeping it updated (no true automation — Directa has no API)

After each PAC date (1/8/15/23) the user sends the Directa **"Storico" screenshot** (or
the daily "Nota Informativa" PDFs). Then: for each execution, upsert the real
`(isin, date, shares, price, amount, fee=0)` into `etf_pac_contributions` with
`source='storico'`, replacing any `auto` row for that (isin,date). The Directa "Nota
Informativa" PDF has everything (ISIN, date, qty, fill price, commissioni — blank = 0 on
Borsa Italiana). If the contract-note emails land in the user's Gmail, they can be
pulled from there on request.

## Commits

- 2026-09-02: migration 008, `_process_pac_plans` STEP 3b, VWCE.DE→VWCE.MI / GAGG.PA→GAGG.MI.
- 2026-09-08: migration 011 (`amount_eur_per_exec`), floor(amount/price) sizing, +3 ETFs
  in xlsx, DB synced to the 7-ETF plan + 9 real executions, `pac.html` "Importo/vers." col.
