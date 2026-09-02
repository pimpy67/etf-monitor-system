---
name: etf_session_2026_08_28_db_connection_leak_incident
description: "2026-08-28 outage — Postgres \"too many clients\" from a DB connection leak; fixes deployed (leak + safety net + threaded server + radar cache + dashboard resilience); open follow-ups"
metadata: 
  node_type: memory
  type: project
  originSessionId: fc7b7d69-6812-47b3-ae17-2ddfa5c1230e
  modified: 2026-08-28T13:57:27.478Z
---

**Incident (2026-08-28)**: user reported `Errore: Unexpected token '<', "Aggiorna` on the
ETF dashboard, then "the ETFs don't show in the radars", then the site was fully
502 Bad Gateway.

**Root cause**: `FATAL: sorry, too many clients already` — the Flask app **leaked DB
connections** until Postgres exhausted all 100 slots (container had been `Up 3 weeks
(unhealthy)`). Every DB-backed endpoint then hung; on a **single-threaded Werkzeug dev
server** (`main.py` `app.run(...)`, scheduler+monitor in the same process) one stuck
request queued all the rest → Nginx 502/504 → `res.json()` choked on the `<` of the 504
HTML page → "Unexpected token '<'".

**The leaks found & fixed** (commit `7d325e5`):
- `app.py` `/api/portfolio-sl` — `conn.close()` was outside `finally`; endpoint is polled
  every few seconds by the dashboard, so every exception path leaked one
  idle-in-transaction connection. **The dominant leak.**
- `sync_l1_portfolio.py` (×2) — `with self.db.get_connection() as conn:` — in psycopg2 the
  connection context manager manages the **transaction only, not the connection lifecycle**;
  connection never closed. Fixed with explicit `finally: conn.close()`.
- `monitor.py` `_update_portfolio_l0_suggerito` / `_update_portfolio_l1_suggerito` /
  `_collect_l0_candidates` — `conn.close()` skipped on the exception path; moved to `finally`.

**Safety net** (commit `7d325e5`, `docker-compose.yml`): Postgres now started with
`-c idle_in_transaction_session_timeout=120000 -c max_connections=150` — any leaked
connection is force-closed after 2 min, so a future leak can't take the site down. Applied
by recreating the postgres container (`docker compose up -d`), NOT by `deploy.sh` (which
only rebuilds the app).

**Radar / single-thread fix** (commit `0ea03c6`): `main.py` → `app.run(..., threaded=True)`;
`app.py` → `_radar_cached()` TTL 300s wrapper on `/api/approach-radar` + `/api/bounce-radar`.
Those two endpoints are **the heaviest in the system** — each scans ~200 L2/L3 ETFs with a
`db.get_ohlc_by_isin()` round-trip + linear regression, and the dashboard calls them on
every page load AND every 60s auto-refresh. Before this they could lock the whole app.

**`dashboard.html` resilience** (commit `7d325e5`): `loadData()` rewritten with a
`fetchJSON()` helper (20s AbortController timeout + `res.ok` + `content-type: json` check).
`dashboard_data.json` is the only critical fetch; `l1-tracking`/`l1-exits` failing now just
`console.warn` and the dashboard still renders. A slow/504 endpoint no longer blanks
`#mainContent` with a cryptic parse error — shows a clean "Ricarica" message.

**Post-deploy state (verified in browser)**: site green, dashboard fully loads, Radar
Anticipato showed 6 ETF. Radar Rimbalzo had not populated yet on last check — likely still
computing its first (uncached) pass, possibly hitting Nginx's ~60s `proxy_read_timeout`.

**Open follow-ups (not done)** — see also [[etf_proactive_status_reminders]]:
1. Confirm Radar Rimbalzo populates; if it 504s on first compute, either raise Nginx
   `proxy_read_timeout` for `/api/` OR (better) precompute both radars in the monitor cycle
   and serve from a cached file like `dashboard_data.json`.
2. Next day: check `SELECT count(*), state FROM pg_stat_activity WHERE datname='etfs' GROUP
   BY state;` stays low/stable (< ~20-30) for a couple days = leak truly closed.
3. `alerts.py` lines ~682/716/799 — same `conn.close()`-outside-`finally` pattern, leak on
   exception only, 2×/day; backstopped by the 2-min reaper but worth cleaning.
4. `database.py::_get_connection()` tries `sslmode='require'` first (always fails on the
   local Docker Postgres) then retries without SSL → 2 TCP connects per query. Skip the SSL
   attempt for local hosts.
5. `docker-compose.yml` — remove the obsolete `version:` line (warning on every command).
6. Consider real gunicorn (already in `requirements.txt`) instead of the dev server +
   `threaded=True`; needs care so the scheduler/monitor doesn't run once per worker.

**Standing lessons**:
- psycopg2 `with connection as conn:` does NOT close the connection — only commits/rolls
  back the transaction. Always `conn.close()` in a `finally`. Grep new DB code for this.
- The ETF app is a single-process Werkzeug dev server; any endpoint that takes >1s blocks
  everything else. Keep heavy work out of request handlers or cache it.
- The terminal on this VPS/session buffers pasted multi-line command blocks badly (runs
  line 1, queues the rest, interleaves output) — give the user ONE command at a time during
  incidents, and `deploy.sh` is for running from a dev PC, not on the VPS itself (its git
  push step prompts for a GitHub username there).
