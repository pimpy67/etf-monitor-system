---
name: etf-502-cpu-steal-incident-2026-09-07
description: "2026-09-07 dashboard 502 Bad Gateway — root cause was ~80% CPU steal on the Hostinger VPS (host contention), amplified by the app running the single-threaded werkzeug dev server. Recovered with app-container restart + stale-process cleanup."
metadata: 
  node_type: memory
  type: project
  originSessionId: 1fd19430-4ed1-4493-996f-9b331a726e27
  modified: 2026-09-07T20:52:48.770Z
---

**2026-09-07 ~11:50 UTC**: `etf.andreapavan.tech` returned Cloudflare **502 Bad Gateway**.

## Root cause — CONFIRMED via Hostinger panel (evening 07/09)

- **Hostinger applied a deliberate CPU throttle** to the VPS for "utilizzo eccessivo delle
  risorse" (excessive resource usage). The panel (VPS → Utilizzo del server) shows a
  **"Rimuovi limitazioni"** button — the user must click it *after* addressing the cause;
  the throttle then takes **1-3 hours** to lift. The sustained `80% st` in `top` WAS this
  throttle in action, NOT a noisy-neighbour host contention (initial hypothesis, wrong).
- **What triggered it**: sustained high CPU. Contributors, in rough order:
  - `dockerd` chronically ~30% CPU (many Docker projects on this box: etf_monitor_system,
    fund_monitor_system, social_effata/effata-bot, others — plus accumulated hung
    `docker logs`/`docker compose logs` processes days old).
  - **The item-15 backtests run this session** — L0 baseline ~3.5h at ~25% CPU, then L1
    smokes ~2h. On a 1-vCPU VPS that sustained load is significant and almost certainly
    pushed it over Hostinger's threshold / kept the throttle from lifting.
  - Other projects deploying (`docker compose up -d --build` seen running, not ours).
- Load average climbed to **35-43** during the initial 502 window.
- **Amplifier**: the ETF app runs the **single-threaded Flask/werkzeug development server**
  (`python main.py` → `INFO:werkzeug` in logs), not gunicorn. Under CPU starvation each
  dashboard page load (~10 API calls) serializes, each request takes seconds, Cloudflare
  hits its timeout → 502. Active dashboard browsing during the event compounded it.
- Postgres was **fine** (23/150 connections — NOT the 2026-08-28 slot-exhaustion leak,
  though transient `idle in transaction` OHLCV-fetch connections were visible; they
  self-clear at the 120s `idle_in_transaction_session_timeout`).
- Also found: several **hung `docker logs` processes days old** from past sessions (the
  known "docker logs hangs on this VPS" bug), keeping `dockerd` busy (~31% CPU). Killed them.

## Fix applied

1. `kill -9` the stale hung `docker logs` / curl-loop processes (days-old cruft).
2. `docker restart etf_monitor_system-app-1` (took ~34s under load; `RestartCount` stayed 0
   afterwards — no crash loop).
3. Load subsided on its own (1-min avg 43 → 13 over ~10 min); public URL back to **HTTP 200
   in ~0.8s**. **CPU steal was still ~84% after recovery** — the host contention itself
   never cleared, the box just had less queued work.

## Follow-ups

- **User action to clear it**: Hostinger panel → VPS → Utilizzo del server → **"Rimuovi
  limitazioni"** once load has settled. Lift takes 1-3h.
- **Do NOT run the heavy item-15 backtests on this VPS again** — L0 full (~3.5h) / L1 full
  (~10h+) sustained CPU will re-trigger the throttle. The clean-vs-directa deltas from the
  smoke tests (L0 full 103 tickers + L1 12-ticker sample) already answer Step 3; proceed to
  Step 4 (code-only) with those. If a full backtest is truly needed, run ONE, overnight,
  alone, and warn the user it may re-throttle.
- **Recommend switching `main.py` from werkzeug dev server to gunicorn** (2-3 workers) —
  would keep the dashboard responsive under any CPU starvation instead of serializing every
  request into a 502.
- General hygiene: kill accumulated hung `docker logs`/`docker compose logs` processes
  (found several days old across projects) — they keep `dockerd` busy.
- If 502s recur: check `top` `st%` first. High `st` with the panel showing limitations =
  the throttle is (still) active.

See [[etf_session_2026_08_28_db_connection_leak_incident]] for the *different* (DB) outage
pattern — don't confuse them.
