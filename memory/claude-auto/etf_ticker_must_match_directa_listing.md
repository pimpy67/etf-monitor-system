---
name: etf_ticker_must_match_directa_listing
description: Standing rule — every ETF ticker in etf_monitoraggio.xlsx must track the SAME listing/currency the user trades on Directa; audit of .SW tickers 2026-08-28
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fc7b7d69-6812-47b3-ae17-2ddfa5c1230e
  modified: 2026-09-03T09:09:04.894Z
---

**Rule (user, 2026-08-28)**: the monitor must always reference the **same exchange
listing and currency the user actually trades on Directa**. "I nostri ETF sono quelli
che negozia Directa." A same-ISIN listing on a different venue/currency is NOT
acceptable — the dashboard price, EMA/SMA/RSI, SL/TP must all be in the currency the
user sees on Directa.

**Why**: found via WATC — the user's Directa price (~€7,00) didn't match the dashboard
(~6,55). Same fund (ISIN FR0014002CH1) but our system tracked `WATC.SW` (SIX Swiss, in
**CHF**) while the Excel column said EUR — so a CHF price was shown as if it were EUR.

**How to apply**:
- When adding/fixing a ticker, verify currency via
  `https://query1.finance.yahoo.com/v8/finance/chart/<TICKER>?interval=1d&range=5d` →
  check `meta.currency` and `meta.regularMarketPrice` against what Directa shows.
- Prefer the Milan (`.MI`) or Paris (`.PA`) EUR listing. `.SW` (SIX Swiss) listings are
  often USD or CHF even when the fund is European — a trap.
- Cross-check the Excel `Valuta` column actually matches the ticker's real currency.
- After changing a ticker, the DB `etf_price_history` for that ISIN still holds the OLD
  currency's prices → the indicator series is discontinuous until it rolls off. For
  L3/watchlist ETFs, delete the stale rows so it rebuilds clean:
  `DELETE FROM etf_price_history WHERE isin = '<ISIN>' OR ticker = '<old_ticker>';`
- **`etf_favorites` also freezes the ticker at add-time** → if the ETF is in Preferiti,
  update it too: `UPDATE etf_favorites SET ticker='<new>' WHERE isin='<ISIN>';`
  (also applies to `etf_portfolio_entries` if a real position exists.)
- Ticker-fix caution from [[etf_session_2026_08_25_rsi_gate_pac_fixes_radar]]: a bad
  remap can be worse than the original. Always confirm the new ticker returns real,
  current data (regularMarketTime = today) before committing.

**Fix 2026-09-03** (`etf_monitoraggio.xlsx`, commit `d6a00d9`): `3MIB.MI` (GraniteShares
3x Long FTSE MIB Daily ETP, no ISIN, `leva_single_stock`) was delisted on Yahoo → yfinance
error every run. GraniteShares' European ETP business was acquired by WisdomTree; the
product is now **`3ITL.MI`** ("WisdomTree FTSE MIB 3x Daily Leveraged", Milano, EUR — same
FTSE MIB 3x daily long). Verified via `yf.Ticker('3ITL.MI').info` longName + currency.
0 rows in `etf_price_history` for `3MIB.MI` (delisted the whole time) so nothing to clean —
just the ticker + name swap; monitor backfills `3ITL.MI` on the next run. Same WisdomTree
rebrand may affect other surviving GraniteShares `3xxx.MI` rows — check if they error.

**Fixes 2026-08-28** (`etf_monitoraggio.xlsx`):
| Row | Was | Now | Status |
|---|---|---|---|
| WATC (FR0014002CH1) | `WATC.SW` Svizzera EUR (really CHF ~6,55) | `WATC.PA` Parigi EUR (~€7,00) | ✅ KEPT (commit `8efa967`) — clean, no conflict |
| INRG (IE00B1XNHC34) | `INRG.SW` Svizzera, USD Dist share class | `INRG.MI` → **reverted to `INRG.SW`/USD** (commit `94e78b6`) | ❌ REVERTED — row R208 already has ticker `INRG.MI` for a *different* ISIN (IE00B1W57M07 "Clean Energy Transition") → two rows same ticker = `idx_ticker` unique violation |

**INRG open question**: R174 (IE00B1XNHC34, "iShares Global Clean Energy UCITS ETF USD
Dist") vs R208 (IE00B1W57M07, "...Transition"). The famous `INRG.MI` on Borsa Italiana
is normally ISIN IE00B1XNHC34 — so R208's ISIN may be wrong, or these are genuinely two
share classes. Ask the user which clean-energy line they hold/watch on Directa before
touching either.

**⚠️ Bind-mount gotcha (found 2026-08-28, refined 2026-09-03)**:
`/root/etf_monitor_system/etf_monitoraggio.xlsx` is bind-mounted into the container as a
**single file**. `git pull`/`git checkout` REPLACES the file (new inode) → the running
container keeps reading the OLD one. **`docker restart etf_monitor_system-app-1`** is
required after any host-side change for the container to see it.
- **2026-09-03: editing the xlsx from INSIDE the container** (`docker exec ... python3 -c
  "openpyxl ... wb.save()"`) **does NOT reliably reach the host file** — openpyxl saves via
  temp-file + rename, which on a single-file bind mount lands in the container's overlay
  only; `docker restart` then re-mounts the unchanged host file and the edit vanishes
  silently (the in-container verification passes right up until the restart). **Always edit
  the xlsx on the HOST** (`ssh ... 'cd /root/etf_monitor_system && python3 - <<PYEOF ...'`,
  host has python3 + openpyxl 3.1.5), confirm `git status` shows ` M etf_monitoraggio.xlsx`,
  THEN `docker restart`, THEN commit. (An earlier note said "the monitor's own in-place
  openpyxl writes are fine" — the monitor writes to `data/` which IS a directory mount, no
  problem there; the xlsx single-file case is the trap.)

**Audit of the other `.SW` tickers (2026-08-28) — left as-is, Excel currency matches
Yahoo, internally consistent** (but if the user trades these on Directa in EUR, revisit):
- `BITC.SW` / `ETHE.SW` / `SLNC.SW` — CoinShares crypto ETPs, CHF on SIX. Deliberately
  mapped to `.SW` when the `.MI` listings were delisted from Yahoo (session 2026-08-07).
- `CSBGU7.SW` — iShares $ Treasury 3-7yr, USD (a USD fund, so USD is correct).

**Open**: after `docker restart`, delete stale `etf_price_history` rows for `FR0014002CH1`
(+ ticker `WATC.SW`) so the WATC EUR series rebuilds clean, then trigger a monitor run.
Verify WATC close comes back ~€7,0x. (INRG left alone — reverted.)
NOTE 2026-08-29: WATC `etf_price_history` was already clean EUR (~6,9–7,2 back to March,
no CHF discontinuity) — the CHF issue was a live-display artifact, not stored data. So the
`DELETE` above was likely unnecessary for WATC specifically; still verify for future changes.

**Follow-up bug fixed 2026-08-29 (commit `92b8777`)**: user reported "grafico vuoto" on the
WATC Preferiti modal. Cause chain: `/api/favorites` returned the frozen `WATC.SW`;
`dashboard.html loadETFDetail()` prioritised the `ticker` param → `/api/etf-detail?ticker=WATC.SW`
→ 404 → silent fallback to `allData` object which has **no `price_history`** → blank canvas,
no error shown. Fixes: (1) `app.py` `/api/favorites` now takes `ticker` from live
dashboard_data (`analysis.get('ticker') or entry.get('ticker')`); (2) `loadETFDetail()` sends
`ticker` AND `isin` so the API matches by ISIN even with a stale ticker. Plus the
`UPDATE etf_favorites` above. Deployed manually on VPS (git pull + rebuild, not `./deploy.sh`
which runs from the Mac). Verified at API level: `/api/etf-detail?ticker=WATC.PA&isin=FR0014002CH1`
returns full 90-pt price_history.
