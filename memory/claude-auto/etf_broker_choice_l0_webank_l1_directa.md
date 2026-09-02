---
name: etf-broker-choice-l0-webank-l1-directa
description: "SUPERSEDED 2026-08-19 — was L0 on Webank / L1 on Directa, now Directa-only for all new positions. Kept for history; see the update note below before applying the old rule."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 71293b1b-838b-4981-a59e-79e7180bdb98
  modified: 2026-08-19T11:25:12.496Z
---

> ⚠️ **SUPERSEDED 2026-08-19**: the user switched to **Directa-only for all new positions**
> (both L0 and L1) — no more new Webank entries. Reason given: consolidating on one broker.
> They're manually closing/removing the two existing Webank positions (Amundi DJ Industrial
> Average L1, iShares MSCI Canada L0) via the dashboard themselves — not a code/DB task.
> Code-wise, chose the minimal-scope option: default broker was already `'Directa'`
> everywhere in the code (`database.py::add_portfolio_entry`, `app.py`'s three broker-reading
> call sites, dashboard.html's add-position form) — **no code change was actually needed**,
> it already worked this way. The Webank/OCO branch (`OCO_CAPABLE_BROKERS = {'Webank'}` in
> `order_pricing.py`, the tightening-ratchet skip logic, the dashboard's broker dropdown)
> was deliberately **left in place but now inert** — the user chose not to rip it out, in
> case Webank (or another OCO-capable broker) comes back into use later. See
> [[etf_session_2026_08_19_directa_ratchet_and_terminology]] for the ratchet mechanism this
> refers to.
>
> **How to apply now**: when the user opens a new position or asks which broker to use,
> the answer is **Directa**, full stop — don't suggest Webank for L0 anymore, that
> cost/risk tradeoff (below, kept for history) is no longer the operative decision.

**Old rule (2026-08-10 → 2026-08-19, no longer active): L0 positions → Webank. L1 positions → Directa.** Confirmed by the user 2026-08-10 after a cost/risk discussion.

**Why**: Webank supports a real simultaneous SL+TP (OCO) but costs ~12€/operation vs Directa's ~5€/operation (~14€ extra per round-trip trade). Directa can only keep one sell order active at a time on a cash account — approaching the other target requires manually cancelling and replacing (see [[etf_directa_trigger_vs_limit_confusion]] and CLAUDE.md's "Esecuzione ordini reali su Directa" section).
- L0 (mean-reversion off a crash, can move sharply in either direction, more frequent entries/exits per the backtests) — the risk of being briefly unprotected during a manual cancel/replace is worth the extra ~14€/trade → **Webank**.
- L1 (trend positions, rare 7/7 entries, slower-moving) — there's time to react manually, so the extra Webank cost isn't worth it → **Directa**.

**How to apply**: Applies only to NEW positions going forward — when the user opens a new position or asks which broker to use, default to this rule without re-litigating the cost/risk tradeoff unless they ask. **Not retroactive**: do not flag or suggest moving existing positions that don't follow it (e.g. DJE, an L1 sitting on Webank as of 2026-08-10 — leave it there, no need to migrate).
