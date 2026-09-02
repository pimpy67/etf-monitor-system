---
name: etf-directa-trigger-vs-limit-confusion
description: "The user repeatedly confuses a Directa Stop order's Trigger price with its actual execution (Prezzo Limite) price when filling in the portfolio's personal SL field — expect to have to re-explain this, and check their inputs before trusting them."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8e77372c-670e-4a4a-8be8-419a0ec0398b
  modified: 2026-08-19T10:39:45.370Z
---

On a Directa Stop order there are always two numbers: the **Trigger** (activation price) and the **Prezzo** shown in the confirmation as "Sell N a X€ Trigger Y€" (the real execution/limit price, set ~1% below trigger so the order still fills on a gap). See [[etf_session_2026_08_09_dedup_and_pnl_ux]] for the full session where the field/label were reworked around this. **Labels renamed again 2026-08-19** (see [[etf_session_2026_08_19_directa_ratchet_and_terminology]]): "Prezzo Limite (Stop) Personale" → "Prezzo Limite Personale", "Prezzo Limite (TP) Personale" → "Target TP Personale" — same fields, same confusion risk, just matching Directa's own field names exactly per explicit user request.

**The user consistently wants to type the Trigger** (the more salient number when placing the order on Directa) into the "Prezzo Limite (Stop) Personale" field, even after several direct corrections in one session (2026-08-09/10) using their own real position (Amundi MSCI Water, `FR0010527275`, real order: Trigger 71,77€ / Prezzo 71,05€). They pushed back twice on the same point before accepting it.

**Why it matters**: that field drives the P&L calc shown in the ETF detail modal. Using the Trigger instead of the real execution price overstates the P&L by roughly the 1% Stop/Limit gap (on their Water position, a difference of about 50€ on a ~5,000€ position — not negligible).

**How to apply**:
- When the user pastes portfolio/detail-screen numbers and asks "is this right," check whether the "Prezzo Limite Personale" value they entered looks like it could be a Trigger rather than an execution price (e.g., compare it to the system's own computed "Prezzo Stop (Trigger)" vs "Prezzo Limite" columns — if their personal value matches "Prezzo Stop (Trigger)," it's probably the trigger, wrong).
- If correcting them, point to Directa's own order-confirmation wording ("Sell N a X€ Trigger Y€") as the authoritative source rather than arguing about which broker UI field is labeled what — that's what finally landed it.
- They also confused the *separate* "Target TP Personale" field (a wholly different order, a plain Limit sell near the take-profit target) with the Stop's execution price — don't assume fixing one field's semantics fixes the other; check both when reviewing their inputs.
