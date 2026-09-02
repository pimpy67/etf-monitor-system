---
name: etf-l1-real-model-and-open-items
description: "The confirmed real-world L1 trading model (2026-08-05). The 3 items once listed as open (TP function, alerts.py, check_l1_exit auto-marking) were all resolved same day — see bottom."
metadata: 
  node_type: memory
  type: project
  originSessionId: 6c15300f-1a71-4a05-b9d0-981a69b89d95
  modified: 2026-08-06T02:09:38.855Z
---

On 2026-08-05 the user (andreapavan67) gave the definitive, simplified real-world model for how they actually trade `etf_monitor_system` L1 signals — this supersedes earlier same-day assumptions in [[etf_l1_two_exit_mechanisms]].

**The model, confirmed by the user**:
- Entry = an ETF reaching L1 (7/7 conditions + fondamenta via `suggest_level()`) = the user manually buys and adds it to their portfolio.
- Exit = ONLY the daily Stop Loss and Take Profit values, which the user inserts/updates manually at Directa (broker) roughly daily, based on system output.
- `check_l1_exit()`, and the dashboard's B/C/E/F exit rules (trailing, stanchezza, ADX debole, kill switch) are **purely internal/informational** — they do NOT represent real sells. The user's own words: "trattiamo l'uscita L1 solo come una cosa interna... i soli stop loss e take profit giornalieri... rappresentano le sole vie di uscita."
- Costs to model: Directa €5 buy + €5 sell flat per trade, 26% flat tax on gains (Italian capital gains).
- Position size to test: **both €5,000 and €10,000** per trade (user wants both compared, not one or the other).

**The 3 items originally listed as open here — all resolved 2026-08-05, same day**:
1. ~~Which TP function is authoritative~~ → **Resolved**: `calculate_stop_gain_dynamic()` is the only TP function in production. `calculate_sg_suggerito_l1()` was removed as dead code (never wired to any real decision).
2. ~~`alerts.py` needs review~~ → **Partially resolved**: the portfolio-report email (`send_portfolio_report()`) was reordered to run *after* the daily SL/TP recalculation (was sending stale/yesterday's values), a duplicate second send at 17:30 UTC was removed, and an L0 TP column was added. A full content/design review is still not done, but the functional bugs (stale data, duplicate emails) are fixed.
3. ~~`check_l1_exit()` auto-marks positions exited~~ → **Resolved**: `check_l1_exit()` was **deleted entirely**. Real exit is now purely `sl_hit or tp_hit` — see [[etf-l1-two-exit-mechanisms]] for detail. Same fix applied to the analogous L0 function `check_l0_exit()`.

Also resolved same day: a real production bug where `etf_portfolio_entries` had two divergent columns (`portafoglio` vs `portfolio_type`) for the same L0/L1 concept — positions added as L0 via the dashboard were silently processed with L1 SL/TP logic. Fixed by syncing both columns on write. And the dashboard was showing `status='exited'` positions as if still active (missing a `WHERE status='active'` filter) — this is why the user believed the portfolio "wasn't empty" while the email correctly found nothing to send.

**How to apply**: when building or discussing backtests, P&L calculations, or portfolio tooling for `etf_monitor_system`, use the confirmed model above (entry=L1 via `suggest_level()`, exit=SL/TP-only via `calculate_sl_suggerito_l1`/`calculate_stop_gain_dynamic`, both position sizes 5k/10k€ tested). See `etf_monitor_system/CLAUDE.md` → "Stato Attuale & Roadmap L1" for the current live decision state (as of 2026-08-05: a new `smart_6_macd` variant — `min_buy_count=6` + MACD always required — beat both the strict 7/7 gate and the plain 6/7 gate in a 3-year backtest; not yet in production, pending live validation).
