---
name: etf-dashboard-readability-preference
description: "User repeatedly asks to enlarge/restyle small, low-contrast text across the ETF dashboard's dark theme — a standing preference to check proactively when adding new UI, not just react to complaints."
metadata: 
  node_type: memory
  type: feedback
  modified: 2026-08-10T14:12:12.961Z
  originSessionId: 81d60b8f-be19-4a4a-9d32-670549ee969d
---

Across the 2026-08-10 session, the user asked at least 4 separate times to enlarge/restyle text that had been left small and low-contrast: the ISIN under each ETF name (twice — once in the main table, once more after the first fix wasn't enough), the ☆ favorite icon, the Preferiti table's values, the detail-modal ISIN subtitle, and the Portfolio SL/TP price values.

**Why**: the original dashboard styling defaults to small/dim secondary text — `font-size:0.7-0.85em`, `color:#555` (a dark gray with weak contrast against the near-black background) — for anything considered "metadata" (ISIN, tickers, labels). The user finds this genuinely hard to read, not a one-off nitpick.

**How to apply**: when adding new UI elements to this dashboard (`dashboard.html`), default to the already-corrected pattern instead of the old dim style:
- Secondary/meta text (ISIN, labels, captions): `font-size:~0.85-0.95em`, `color:#8b949e` or lighter, not `#555`.
- Values the user actually needs to read at a glance (prices, key numbers): bigger still, `font-size:1.2-1.5em`, `font-weight:700`.
- Icons meant to be clickable (star toggles, etc.): `font-size:1.3em+`, with a visible-but-muted default color (`#8b949e`) rather than near-invisible `#555`.

Don't wait for a complaint on the next new panel — apply this by default, then adjust further if asked.
