---
name: etf-isin-ticker-fixes-2026-09-04
description: "7 ISIN/ticker errors found and fixed by checking Directa's own \"Ricerca avanzata\" one-by-one (not a bulk catalog download). Also surfaced ETHE/BITC listing mismatch confirmation and SLNC not tradeable on Directa at all."
metadata: 
  node_type: memory
  type: project
  originSessionId: bfa51328-4875-4391-a8a1-5a8b8ed7311a
  modified: 2026-09-04T14:02:36.866Z
---

User noticed system ISINs didn't match Directa (started from CMOD). Method that worked:
**don't bulk-scrape Directa's ~650-instrument catalog — look up individual suspect ISINs
one by one in Directa's own "Ricerca avanzata" search box** (via claude-in-chrome, user's
already-logged-in session). Confirmed against a prior Yahoo-search audit that had flagged
~15-20 suspects (most were false positives — Yahoo returning a different exchange listing
of the *same* ISIN, e.g. `VWCE.MI IE00BK5BQT80 → VWRA.L` is fine, not a bug).

## Fixed and deployed (commits `80bdb26`, `bed8017`)

| Ticker | Old ISIN (wrong) | New ISIN | Note |
|---|---|---|---|
| CMOD.MI | IE00BD6FVP32 | **IE00BD6FTQ80** | ticker was already right, only ISIN wrong |
| ALUM.MI | DE000A0Q4MJ7 | **GB00B15KXN58** | ticker right, ISIN wrong |
| ZINC.MI | DE000A0QLW44 | **GB00B15KY872** | ticker right, ISIN wrong |
| PHPT.MI | DE000A0N62E5 | **JE00B1VS2W53** | ticker right, ISIN wrong |
| IGLN.L | DE000A1RX996 | **IE00B4ND3602** | old ISIN was actually Xetra-Gold (different issuer/product) |
| BATE.DE → **BATT.MI** | IE00BMDX3P59 | **IE00BF0M2Z96** | ticker AND ISIN both wrong; Directa's real ticker is BATT not BATE, listed on Milan not Xetra |
| AIFS.DE → **AINF.MI** | IE000V0H6AD4 | **IE000X59ZHE2** | ticker AND ISIN both wrong; real ticker AINF, Milan not Xetra |

Applied on the HOST xlsx via ssh (per [[etf_ticker_must_match_directa_listing]] bind-mount
gotcha — never edit from inside the container), `docker restart`, stale
`etf_price_history` rows deleted for old ticker/ISIN, `etf_favorites` ticker updated (0
rows affected — none of these were favorited), committed+pushed. Both BATT.MI/AINF.MI
verified fresh-fetchable on Yahoo (2026-09-04, EUR) before committing the ticker swap.

## Found, NOT fixed — needs a decision, not just a lookup

- **ETHE.SW / BITC.SW** (CoinShares Ethereum/Bitcoin, ISINs GB00BLD4ZM24 / GB00BLD4ZL17):
  Directa has **no Swiss (SIX) listing at all** for either — only **Amsterdam** (plain
  ticker CETH/BITC) and **Xetra** (X.CETH/X.BITC). The user's real position (50x CoinShares
  Ethereum, carico €66,09) is the **Xetra** one. System tracks `.SW` in CHF (only Yahoo-
  fetchable option found so far — Xetra/.SG/ECH2.DE all dead on Yahoo, see
  [[etf_sector_taxonomy_and_partB_plan_2026_09_04]] session). Percentages/RSI transfer
  reasonably (CHF↔EUR near parity), absolute prices don't. Currently managed as advised in
  [[etf_user_acts_on_shadow_signals]]-adjacent manual tracking, not in system portfolio.
  Not resolved — no better Yahoo ticker found yet for the Xetra EUR listing.
- **SLNC.SW** (CoinShares Solana Staking, GB00BKJG2L22): searched on Directa →
  **"Nessuno strumento trovato" — not tradeable on Directa at all**, any ticker. Moot point
  for a listing fix; if the user ever wants Solana exposure it can't be this ISIN via Directa.

## Method note for future ISIN audits

A bulk Yahoo-search audit (`search?q=<ISIN>`, checking if the ticker root comes back) is
cheap but noisy — flags legitimate multi-exchange listings as false positives. The
reliable, low-effort method is: **narrow the suspect list first (Yahoo audit or "Yahoo
finds nothing" as the real filter), then look up only those ~10-20 on Directa's own
Ricerca Avanzata one by one** — few minutes, no bulk scrape needed, and it's the single
source of truth for the user's own coverage.
