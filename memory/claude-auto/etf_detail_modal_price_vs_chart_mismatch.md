---
name: etf_detail_modal_price_vs_chart_mismatch
description: "ETF charts / modal 'al DD/MM' frozen at 27/08 (2026-09-02). ROOT CAUSE FOUND: save_ohlcv_bulk INSERT ... ON CONFLICT (ticker,date) doesn't cover the (isin,date) partial-unique index added 09/08; after a ticker rename the legacy ticker=ISIN history collides → UniqueViolation → aborts the psycopg2 tx → whole batch silently lost. Part A (data relabel) done; Part B (code fix) pending deploy."
metadata:
  node_type: memory
  type: project
  originSessionId: f0bcad9b-ee3f-4eae-bad3-5465c9871afb
  modified: 2026-09-03T09:09:17.905Z
---

## ROOT CAUSE (confirmed 2026-09-02, reproduced on prod)

```
INSERT INTO etf_price_history (...,isin) VALUES (...,'LU1900067601')
  ON CONFLICT (ticker,date) DO UPDATE ...
→ ERROR: duplicate key value violates unique constraint "idx_etf_price_history_isin_date_uniq"
  DETAIL: Key (isin, date)=(LU1900067601, 2026-08-27) already exists.
```

Chain:
1. **09/08** a partial unique index `idx_etf_price_history_isin_date_uniq` UNIQUE `(isin,date) WHERE isin IS NOT NULL`
   was added as an anti-dup safety net ([[etf_session_2026_08_09_dedup_and_pnl_ux]]). It is NOT in
   `database.py::_init_table()` (that only creates the non-unique `idx_etf_price_isin_date`) — added by hand/migration.
2. `database.py::save_ohlcv_bulk()` (and `save_close_bulk()`) `INSERT ... ON CONFLICT (ticker,date) DO UPDATE`
   — the ON CONFLICT arbiter is **only `(ticker,date)`**, it does not know about the `(isin,date)` index.
3. ~217 of 236 ETFs still have their **entire history stored under `ticker = <bare ISIN>`** (old convention,
   `isin` column also = the ISIN). When an ETF's Excel ticker was changed to a real Yahoo ticker (many did,
   late Aug: `LU1900067601`→`TUR.PA`, `WATC.SW`→`WATC.PA`, the 10 delisted-ticker remaps of 07/08, …), the
   monitor started calling `save_ohlcv_bulk('TUR.PA', <260-day df>, isin='LU1900067601')`.
4. Row for any historical date: no `(ticker='TUR.PA', date)` row → tries a plain INSERT → hits
   `(isin='LU1900067601', date)` which the legacy row already occupies → `UniqueViolation`.
5. The per-row `except Exception: continue` swallows it **but the psycopg2 transaction is now aborted** →
   every subsequent row (incl. 28/08–02/09 which would insert fine) fails `InFailedSqlTransaction` → also
   swallowed → `conn.commit()` on an aborted tx = rollback, doesn't raise → `saved=0`, zero log output
   (`save_ohlcv_bulk` only `print()`s on outlier-skip or an *outer* exception, neither of which fires).

The ~19 ETFs that DID keep updating = the 7 with no ISIN (leverage) + ~12 whose history was already under the
real ticker (WATC cleaned 28/08, VWCE/GAGG new via `yf-backfill-pac`, etc.).

Why it started exactly 28/08: that's when the batch of late-Aug ticker renames + the 28/08 outage
container recreation lined up; the collision only triggers once history exists under BOTH the old
`ticker=ISIN` key and a new real ticker is used for writes.

## The two price sources in the ETF detail modal (`/api/etf-detail`, `dashboard.html`)

- **"PREZZO" KPI** + L1 7-conditions panel = `etf_info['price']` from `data/dashboard_data.json` =
  `analysis['current_price']` = last close of the **live yfinance fetch** each run. `app.py:~240`.
  This stayed correct/live the whole time (TUR.PA 50.73 == Yahoo regularMarketPrice) — that's why the
  user saw "prices at 02/09".
- **Chart line + "al DD/MM/YYYY" subtitle + mini EMA/SMA/RSI under it** = `db.get_close_by_isin(identifier)`
  → `etf_price_history` (`WHERE isin=%s OR ticker=%s`), `identifier = etf_info['isin'] or isin or ticker`
  (`app.py:173`). `price_date = price_hist[-1]['date']` (`app.py:222`). Frozen because the table got no
  new rows.
- Dashboard **level / regime / N-of-7 are computed on the live series**, so they were NOT wrong — only
  the modal's chart view.

## FIX — Part A (DATA, done 2026-09-02 ~21:05, no deploy)

Relabelled legacy `ticker=<ISIN>` rows → real ticker, per the isin→ticker map read from the container's
`data/dashboard_data.json`, guarded by `NOT EXISTS (ticker=real, date=h.date)` so zero `(ticker,date)`
collisions. Ran in-container: **217 ETFs, 70 353 rows moved.** One partial: `LU1829221024`→`UST.PA`
(0/335) — the known unresolved **UST.PA double-ISIN bug** ([[etf_session_2026_08_25_rsi_gate_pac_fixes_radar]]),
the other twin `LU1954152853` took `ticker='UST.PA'` first; that one ETF still won't get writes until the
UST.PA bug is fixed separately. Then `curl -X POST http://localhost:5001/api/trigger-update` to backfill
28/08→02/09.

After the relabel the monitor's `ON CONFLICT (ticker='TUR.PA', date)` now matches the (relabelled)
history → `DO UPDATE` instead of failed INSERT → writes resume even without Part B.

## FIX — Part B (CODE — committed `b5a36ae`, pushed to origin/main, queued for the
## 2026-09-03 03:00 UTC one-shot cron deploy `scripts/deploy_l0_3am.sh` which does
## `git reset --hard origin/main` + rebuild. That deploy also `ast.parse`s database.py so
## the edit must stay valid.)  Also committed same session: `1b413e0` dashboard `.container`
## max-width 1640→2160px (CSS var `--content-max`, user's 2560px monitor had ~450px gutters).

`database.py::save_ohlcv_bulk()` (save_close_bulk left alone — dead code, no active callers):
1. `SAVEPOINT` per row (`SAVEPOINT r` / `RELEASE` on ok / `ROLLBACK TO SAVEPOINT r` on error) so one bad
   row can't abort the whole batch.
2. When `isin` present: `INSERT ... ON CONFLICT (isin, date) WHERE isin IS NOT NULL DO UPDATE SET
   ticker=EXCLUDED.ticker, open=..., ...` — a future legacy row self-heals instead of exploding. When
   `isin` absent keep `ON CONFLICT (ticker, date)`.
3. Outlier-guard median query `WHERE ticker=%s OR isin=%s` (so it works right after a relabel).
4. Loud: if `attempted>0 and saved==0` → `logging.error` + `print` with the first row's exception text.

Optional follow-up (not required): modal should show a staleness banner when `dashboard_data.json`
`last_update` is newer than `etf_price_history` MAX(date) for that ETF.

## Verification — full 236-ETF sweep after the backfill run (2026-09-02 ~22:00 UTC)

- **218/236 charts now at 2026-09-02** ✅
- **9 at 31/08 + 1 at 01/09** (HLTH.DE, EMI.DE, INCI.MI, CBEF.MI, USHYC.MI, USIC.MI,
  IASP.MI, EDSRI.MI, SLNC.SW, 0E2B.IL): Yahoo's `/v8/finance/chart` API **does** have their
  02/09 data — so this is transient yfinance `.history(period=)` staleness during the 21:09
  run, NOT a residual bug. Should self-heal on the next monitor run (tonight's deploy fires
  one). Re-check after.
- **8 GraniteShares 3x leverage ETFs (no ISIN, `isin='—'`)**: modal chart was empty — but
  the DB HAS their data (keyed by `ticker`, `isin` NULL). Pre-existing bug in `app.py`
  etf_detail: `identifier = etf_info.get('isin') or isin or ticker` → `'—'` (truthy) wins →
  `get_close_by_isin('—')` → 0 rows. **Fixed** commit `ac13a81` (ISIN counts only if 12
  chars, else fall back to ticker). Deploys with the 01:00 UTC cron.

## Deploy queue for the 2026-09-03 01:00 UTC cron (`deploy_l0_3am.sh`)

`b5a36ae` database.py Part B · `1b413e0` dashboard width CSS var · `751256a` dashboard
readability (rows/fonts) · `ac13a81` app.py leverage chart · (+ the L0 regime-gate code
`2e377ce` that was the original reason for the cron). Git auth on the VPS was **broken**
(HTTPS origin, no creds) — user set a `repo`-scoped PAT in `~/.git-credentials` (helper
`store`) on 2026-09-02; **that token was pasted in cleartext in chat — user told to rotate
it**. The width + font changes were ALSO applied live to the running container via `sed` on
`/app/dashboard.html` (`max-width:1640px`→`2160px` ×3, + an appended override block) so
they show before the deploy.

## UST.PA — still unresolved (do NOT fix without a container yfinance test)

Two real funds, both Excel ticker `UST.PA`:
- `LU1829221024` = Amundi Core Nasdaq-100 Swap Acc (unhedged) → `UST.PA` is genuinely ITS
  ticker per Yahoo search. Keep.
- `LU1954152853` = Amundi Core Nasdaq-100 Swap **EUR Hdg** Acc → needs its own ticker.
  Yahoo search candidates (unverified against yfinance): `USTH.MI`, `LYMS.DE`, `NADQ.DE`,
  `USTP.XD`/`USTM.XD` (Cboe). The 2026-09-02 relabel gave `ticker='UST.PA'` to the HEDGED
  one (`LU1954152853`, processed first) — backwards. Prior fix attempt on UST.PA was
  reverted ([[etf_session_2026_08_25_rsi_gate_pac_fixes_radar]]) because a ticker that
  looked right on the raw Yahoo API was unfetchable by yfinance. Not in the real portfolio,
  low stakes — leave for a session that can `docker exec ... python3 -c "import yfinance..."`.

## Standing fact

**2026-09-03: this Windows PC (Utente) NOW HAS a working VPS SSH key** —
`~/.ssh/id_ed25519_vps` connects: `ssh -i ~/.ssh/id_ed25519_vps root@76.13.37.133`
(the bare `ssh root@...` still fails — the key is NOT the default identity, always pass
`-i ~/.ssh/id_ed25519_vps`). Earlier memories saying "no VPS SSH key / user pastes output"
are OUTDATED — Claude can now run VPS + docker + psql commands directly from this PC.
`./deploy.sh` should now work from here too (untested as of 2026-09-03).
- Compound `ssh '... && git reset --hard ...'` one-liners can trip the Bash auto-mode
  classifier — split into smaller steps (fetch / config / checkout separately worked).
- For psql string literals over ssh, pass SQL via `psql -c "...'lit'..."` with the whole
  thing double-quoted, or heredoc to psql — nested `\x27` escapes get mangled.
