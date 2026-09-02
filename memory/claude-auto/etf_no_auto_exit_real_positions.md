---
name: etf-no-auto-exit-real-positions
description: "standing rule — etf_monitor_system must never mark a real L0/L1 portfolio position 'exited' automatically; only the user's manual dashboard confirmation (with the real Directa fill price) closes a position. Applies to any future code path that touches etf_portfolio_entries.status."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 314498d2-60e3-4552-9a4f-b3774e2c977a
  modified: 2026-08-22T22:27:12.145Z
---

The system must **never** flip `etf_portfolio_entries.status` to `'exited'` on its own, for any reason (SL touched, TP touched, kill switch, RSI/ADX rule, timeout, whatever). This is not a preference, it's the core operating model: the user places and manages every real order manually on Directa (or another broker); the monitor's job is only to *calculate and suggest* SL/TP/trigger prices, never to *execute or record* an exit. Only the user's own manual action in the dashboard (`/api/portfolio/<isin>/exit`, with the price/date they actually got filled at) may close a position.

**Why**: caught 2026-08-22 on a real position — PHAG/WisdomTree Physical Silver (L0) got auto-marked `exited` in the DB the moment the monitor's own calculated close price crossed its TP target, using that calculated price as the recorded `exit_price`. The user still held all 48 shares in reality (confirmed by pasting the live Directa portfolio screenshot). The calculated "price touched" is never proof of a real fill — gaps, the user not having updated their real order yet, slippage, etc. This same violation had already been found and fixed once before on the L1 side (2026-08-05, see [[etf-l1-two-exit-mechanisms]]) but the identical pattern had been reintroduced/left in place on the L0 side — it's an easy mistake to reintroduce because it "feels" harmless (just recording what should have happened), so it's worth stating as an explicit standing rule rather than trusting it'll stay fixed by inertia.

**How to apply**: when reviewing or writing any code that touches a real portfolio table for this project (not the Shadow Monitor tables — those are explicitly hypothetical and SHOULD auto-track), grep for `status`, `exited`, `SET status=` before shipping. If a code path computes "SL/TP was hit," the correct action is: log it, optionally email an alert, keep the position `active`, and keep recalculating/persisting SL/TP normally (including any tightening ratchet — see the order_pricing.py correction in [[etf-l1-two-exit-mechanisms]]) — never touch `status`/`exit_price`/`exit_date` from a monitor-computed value.

A second general lesson from the same session: when the user manually corrects a monitor-suggested number for a live real-money order (see [[etf-session-2026-08-22-no-auto-exit-atr-fix-and-email-links]] for the ATR/wide-tier case), treat that as a signal to find and fix the *underlying* code gap that produced the wrong suggestion — not just accept the one-off manual override. The user explicitly asked "cambia anche il codice di conseguenza" after doing this once.
