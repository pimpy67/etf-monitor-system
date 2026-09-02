---
name: etf-webank-order-verification-2026-08-10
description: "How to read Webank's conditional-order export/list correctly, and how to get the right SL/TP target for an L0 position — both caused real confusion in a live order-verification session."
metadata:
  type: feedback
  originSessionId: current
  modified: 2026-08-10T21:26:07.026Z
---

**Webank's "Prezzo ordine" column in the .xls export can be misleading — always cross-check against the live order list page, not just the raw export.**

In the raw `.xls` conditional-orders export downloaded from Webank, the "Prezzo Ordine" field showed a plain number (e.g. 474,0 or 268,94) for orders that are actually **"Al meglio" (market order)** — the live web page's order list shows "Al meglio" as text in that column, but the .xls export substitutes some numeric placeholder instead (sometimes the last price, sometimes an unclear internal reference price). Reading only the .xls led to a false alarm about "limit price set above the trigger, order might not fill" — the order was actually fine (market execution, no limit-price risk at all).

**How to apply**: when checking a user's Webank/Directa conditional orders, prefer the live order-list page text (or ask the user to paste it) over a parsed `.xls` export when the "Prezzo ordine" / order-type semantics matter — the export's encoding of "Al meglio" is not trustworthy as a literal price.

---

**L0 positions use a different, fixed-percentage Take Profit formula than L1 — don't use the `sg_suggerito` DB column for them, it's stale/wrong for L0.**

`etf_portfolio_entries.sg_suggerito` and the `exit_rule` note field (e.g. `"SG_target_raggiunto: 272.41"`) are populated by logic that doesn't match the real L0 TP formula (`calculate_tp_suggerito_l0` in `technical_analysis.py`, ~line 1940: `tp = entry_price * (1 + l0_take_profit_pct)`, family-specific, e.g. 16% for `equity_sviluppati`). On a real case (iShares MSCI Canada, L0, entry €261.13, family `equity_sviluppati`), `sg_suggerito` showed €275.03 and `exit_rule` claimed the target was already reached at €272.41 — both wrong. The correct value, read directly from the code and YAML, was **€302.91** (16% above entry). The user's price (€276.36 at the time) was still well below the correct target, not above it as the stale DB note implied.

**How to apply**: for any L0 real-portfolio TP check, always compute `entry_price * (1 + l0_take_profit_pct)` from the YAML directly (or read `calculate_tp_suggerito_l0`) rather than trusting `sg_suggerito`/`exit_rule` in the DB — those fields carry over generic/L1-style logic that doesn't apply to L0. Worth fixing at the source eventually (`monitor.py`'s L0 update path), not yet done as of this session.
