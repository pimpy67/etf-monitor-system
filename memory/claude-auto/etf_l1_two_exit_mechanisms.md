---
name: etf-l1-two-exit-mechanisms
description: etf_monitor_system has TWO distinct L1 exit mechanisms — dashboard classification (suggest_level) vs real portfolio exit (SL/TP-only, since 2026-08-05). check_l1_exit() no longer exists.
metadata: 
  node_type: memory
  type: project
  originSessionId: 6c15300f-1a71-4a05-b9d0-981a69b89d95
  modified: 2026-08-22T22:26:50.001Z
---

`etf_monitor_system` has two separate, non-equivalent exit mechanisms for L1 positions — conflating them was a real mistake made during the 2026-08-04 L1 tuning session and caught by the user. **Update 2026-08-05: the real-portfolio side was rebuilt — `check_l1_exit()` no longer exists.**

**1. `suggest_level()` in `technical_analysis.py`** — drives the *dashboard* classification (which level, L0-L3, an ETF shows as in the monitored universe). Its exit logic = Regole A-F embedded in the function, plus an automatic L1→L2 downgrade whenever the buy_count score drops below `min_buy_count` or regime leaves BULL ("L1_DEMOTED"). This is NOT what happens to a real bought position. Still current.

**2. Real portfolio exit — `monitor.py::_update_portfolio_l1_suggerito()`** (rewritten 2026-08-05): `check_l1_exit()` was **removed entirely** (was dead-weight duplicating a philosophy the user explicitly rejected: no automated exit on kill-switch/trailing/RSI/ADX). The real exit today is purely `sl_hit or tp_hit`:
- SL: `calculate_sl_suggerito_l1()` — hybrid stop-loss, EMA20−buffer if profit<2%, EMA20×0.99 if profit≥2%.
- TP: `calculate_stop_gain_dynamic()` — the **only** TP function left in production (`calculate_sg_suggerito_l1()` was also removed as dead code the same day).
- Checked once/day on Close, matching the real monitor cadence.

**Production quirks noted 2026-08-04 — all fixed 2026-08-05, keeping for context only (do not re-apply as if still true)**:
- ~~`ema20_series` never populated~~ → fixed via `database.py::get_ohlc_by_isin()`, now correctly fetched and passed to `calculate_stop_gain_dynamic()`.
- ~~`is_equity_commodity`/`is_bond` compared against legacy profile names, never matching YAML family names~~ → fixed with `YAML_BOND_FAMILIES`/`YAML_EQUITY_COMMODITY_FAMILIES` frozensets in `technical_analysis.py`.
- The `rsi_5` quirk is moot — the whole `check_l1_exit()` path that used it is gone.

**How to apply**: for anything analyzing real investment performance (backtests, "what return would this have produced") — use the SL/TP-only model above (see `backtest_l1.py`, and [[etf-l1-real-model-and-open-items]] for the confirmed user-facing trading model). Entry logic (buy_count + fondamenta via `suggest_level()`) is shared/correct to use for both dashboard and real-portfolio purposes — only the exit differs.

**⚠️ CORRECTION 2026-08-22 — "sl_hit or tp_hit → mark 'exited' automatically" above is WRONG, was itself a violation of the no-automation rule.** Found via a real case: PHAG/WisdomTree Physical Silver (L0, not L1, but the exact same code pattern existed in both `_update_portfolio_l0_suggerito` and `_update_portfolio_l1_suggerito`) got auto-marked `status='exited'` in the DB the moment the monitor's calculated close price crossed the TP trigger — using the calculated price as `exit_price`, not a real Directa fill. User still held all 48 shares. Fixed same day: **both** L0 and L1 real-portfolio update functions no longer touch `status` on SL/TP hit — they only log `🟢 TARGET RAGGIUNTO`/`🔴 SL RAGGIUNTO` and keep computing/persisting SL/TP normally; the position stays `active` until the user manually confirms the exit via the dashboard (`/api/portfolio/<isin>/exit`, real fill price/date). See [[etf-no-auto-exit-real-positions]] for the standing rule this establishes and [[etf-session-2026-08-22-no-auto-exit-atr-fix-and-email-links]] for full session detail.

Collateral fix same session: `order_pricing.py`'s TP-proximity ratchet used to stop tightening once price reached/passed the TP (`tp_suggerito > current_price` guard) — harmless before because the position always force-closed right at that point anyway. Now that nothing force-closes, that guard left the Stop stuck at a stale, un-tightened value past target. Removed the guard so the ratchet keeps tightening (toward `current_price × 0.99`/`0.985`) even past the target, since the position can stay open indefinitely now.
