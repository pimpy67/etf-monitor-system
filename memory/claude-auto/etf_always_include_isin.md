---
name: etf-always-include-isin
description: "Whenever an ETF is named/mentioned in conversation, always include its full ISIN alongside the ticker/name"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ec0a532a-69fa-4c75-af65-b95da5b42e74
  modified: 2026-08-20T12:55:41.104Z
---

Whenever I name or reference an ETF (ticker, short name, or full name), always also give the full ISIN code — not just the Yahoo ticker.

**Why:** User explicitly asked for this (2026-08-20) after pasting the daily portfolio digest email, which lists ETFs by ticker/name only, no ISIN.

**How to apply:** In any response mentioning specific ETFs (portfolio recaps, L0/L1/L2 status updates, order suggestions, analysis) — append the ISIN next to the ticker, e.g. "WATC.SW (FR0014002CH1)". Look it up from `data/dashboard_data.json` (fields `ticker`/`isin`) or `etf_monitoraggio.xlsx` if not already known. Note: some tickers were migrated to a different exchange suffix after delisting (see [[project_ticker_issues]] context in CLAUDE.md) but keep the same ISIN — always match by ISIN when a stored ticker looks stale (e.g. `PHAU.MI` in old data vs `PHAU.L` in the current Excel/email, same ISIN `JE00B1VS3770`).
