---
name: fund-monitor-portfolio-reconciliation-2026-08-27
description: "fund_monitor_system real portfolio corrected to match Directa/onlinesim.it (2026-08-27) — 3 phantom positions removed, cost basis fixed via Prezzo fiscale not Costo medio, missing fund added; schema can't represent multi-lot history"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3318254f-a574-4958-aee9-2fddf39954f3
  modified: 2026-08-27T15:15:22.089Z
---

Session where the user pasted their real online broker portfolio (onlinesim.it,
Directa) and asked to sync `fund_monitor_system`'s `portfolio_entries` table
(`fund-monitor-postgres-1`, db `funds`) to match reality. This is the FIRST fund_monitor_system
memory in this store — everything before was ETF-only. See [[etf_session_2026_08_27_radar_ranking_keltner_cooldown]]
for the same-day ETF work.

## What was found and fixed

DB had 6 `portfolio_entries` rows; real portfolio has only 4 holdings. Diff:

- **Removed 3 phantom positions** (fully switched away over time, 0 quote held today):
  `LU1046236037` (Schroder Strategic Credit), `LU1694212348` (Nordea Low Duration Covered
  Bond), `LU0136043394` (Schroder Euro Liquidity). Confirmed correct via the user's Directa
  order export (`ElencoOrdiniPic.xls`) — these were intermediate parking funds in a chain of
  switches, not real current holdings.
- **Corrected cost basis for 2 multi-lot positions** — this is the non-obvious part, worth
  remembering:
  - `LU0106817157` (Schroder ISF Emerg Eur A Acc): DB had 33.5307 (original sub NAV only).
    Real position was built via 3 lots across time (partial redemption + 2 later switch-ins
    on 2026-08-20). Reconstructing the true quote-weighted average from the raw order
    history gave **37.3082**, which matches the broker's own "**Prezzo fiscale**" field
    (37.30824) almost exactly — NOT "Costo medio" (37.82353), which does NOT reconcile with
    the order-history math for a multi-lot position. Fixed to 37.3082.
  - `LU1706106447` (Nordea European Stars): the remaining 5.00 quote are exactly what's left
    of the ORIGINAL lot after a partial switch-out — true cost is the original sub NAV
    202.6053, which is what was ALREADY in the DB. First correction attempt (before checking
    the order file) wrongly changed it to Costo medio 202.89515 — reverted back to 202.6053
    after reconciling with the order history.
  - `LU1213835942` (Fidelity Latin America): single lot, no switches — Costo medio 14.99875
    (fee-inclusive) is correct here, no ambiguity. Left as originally set.
- **Added missing position**: `LU0173784223` (Nordea Norwegian Equity), acquired entirely
  in ONE switch, executed 2026-07-31, 125.965 quote @ 47.9757 — matches the real holding
  exactly (single lot, no ambiguity on cost basis).

## Why Costo medio ≠ Prezzo fiscale for multi-lot positions (verified, not guessed)

Reconstructed from `ElencoOrdiniPic.xls` (Directa's order export, has N.Ordine/Data
eseguito/Operazione/Isin/CTV/N.Quote/Valore quota/Spese/Commissioni/Ritenuta
fiscale/Minus columns): "Prezzo fiscale" is the genuine quote-weighted average NAV across
all fiscal lots still held (verified by hand-computing `sum(lot_quote * lot_NAV) / total_quote`
from the order rows and it matched the broker's displayed Prezzo fiscale to 4 decimals for
both multi-lot funds checked). "Costo medio" does not reconcile the same way for multi-lot
positions — likely a different broker-internal convention (possibly cumulative fees across
the whole switch chain, not just current lots). **Rule going forward**: when reconciling a
multi-lot fund position, trust Prezzo fiscale over Costo medio, and verify against the order
export if in doubt — don't assume Costo medio is "the real cost" just because it's the
first number shown on the portfolio page.

## Known limitation, not fixed (schema constraint)

`portfolio_entries` PK is `isin` alone (`database.py`, fund_monitor_system) — **one row per
ISIN, no lot-level history**. It cannot represent that 85% of the current Schroder Emerging
Europe position (160.72 of 189.19 quote) was actually acquired on 2026-08-20, not April —
`entry_date` stays at the original 2026-04-24 first-purchase date by convention (same
looseness already present in the pre-existing data: none of the DB entry_dates exactly
matched either "Inserito il" or "Data eseguito" from the order file, off by a day or two —
whoever entered these originally used an approximate date, not the exact transaction date).
If lot-level accuracy ever matters (e.g. holding-period-based signals), this schema would
need a real migration — not done, not requested.

## How to verify the real portfolio in the future

Directa's own order export (downloaded by the user as `.xls`, e.g. `ElencoOrdiniPic.xls`) is
the authoritative source for reconstructing real cost basis and catching switch chains — more
reliable than trusting either "Costo medio" or "Prezzo fiscale" blindly, since both can be
right or wrong depending on whether the position is single- or multi-lot. See
[[vps_tooling_notes]] for how to read a local `.xls` file when the Read tool can't (binary).

## Open thread from the same conversation, not yet acted on

User asked whether to migrate from funds to ETFs, motivated by funds having NO real
stop-loss (NAV settles once/day, no exchange order can exist on a fund — structural, not
fixable by more monitoring). Advice given: migrate exposures with a liquid ETF equivalent
(all 4 current holdings likely have one — Latin America, Norway, European sustainable
equity, Emerging Europe), keep the rest tracked via fund_monitor_system's slower
NAV-based exit signals (Regola A/D) as a second-best protection. Not yet actioned — no
ETF ticker lookup done, no fund sold.
