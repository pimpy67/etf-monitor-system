---
name: etf_chart_ranges_and_frozen_backfill_2026_09_03
description: "ETF detail modal now has 30gg/120gg/1anno/Max chart buttons. Live etf_price_history was backfilled from the frozen Golden Dataset → 178 ETFs have ~4.5y history (from 2022-02), 36 ETFs excluded for a pre-2025-05-08 price-scale mismatch. Check here before touching chart code, the frozen table, or wondering why some charts are short."
metadata: 
  node_type: memory
  type: project
  originSessionId: f0161496-431a-4e32-b1ad-b7395c4f0d9e
  modified: 2026-09-03T19:39:38.469Z
---

2026-09-03. User asked for 1-year and 5-year charts in the ETF detail modal.

## What shipped

**Modal chart buttons** (`dashboard.html`): were `30gg / 120gg / 240gg` → now
`30gg / 120gg / 1 anno / Max`. `changeDetailDays(30|120|252|99999)`, button ids
`dbtn30/dbtn120/dbtn252/dbtn99999`. Client slices `price_history.slice(-days)`;
`99999` = whole series. Array in `changeDetailDays` is `[30,120,252,99999]`.

**`app.py::/api/etf-detail`**: was capping the sent series at `df.tail(90)` (that was the
real bug behind "120gg and 240gg look identical" — data was there, endpoint truncated it).
Now `db.get_close_by_isin(identifier, days=2000)` + `df.tail(1600)` → sends the full
series (~1140 points for a 4.5y ETF, ~130KB JSON, on-demand only). Frontend caches the
whole response per ticker/isin and re-slices per button.

**DB backfill** — `migrations/009_backfill_frozen_history.sql` + `010_prune_...sql`:
- `etf_price_history` only held ~12-18 months for the whole universe (min 2024-09-03 was
  one outlier). Backfilled from `etf_price_history_frozen` (batch `2026-08-07`, real Yahoo
  data 2022-02 → 2026-08) for dates before each ISIN's existing live min, matched by ISIN,
  `source='frozen_backfill_20260807'`, `ON CONFLICT DO NOTHING` (re-runnable).
- Result: **178 ETFs now have history from ~2022-02-15** (~113.8k rows added). The other
  ~58: no ISIN (leverage ETFs), not in the frozen batch, or pruned (below).
- **36 ISINs pruned** (`010`): their frozen history and their early live history are on
  **different price scales** — a clean vertical step at exactly **2025-05-07→2025-05-08**
  (the date live `yfinance` fetching started for them), ratio 0.39x–2.63x. Different
  exchange listing / currency / share-class between the two sources. On every non-pruned
  ETF frozen==live to the cent on overlapping dates. The 36 keep their ~15-month live
  history only. **Their live history itself has this scale problem pre-2025-05-08** — a
  pre-existing data issue, not created here, left out of scope. To find them:
  compare last `frozen_backfill_20260807` close vs first non-backfill close per isin.
- `LU1954152853` (UST hedged) explicitly excluded from the backfill — see
  [[etf_ticker_must_match_directa_listing]] / [[etf_detail_modal_price_vs_chart_mismatch]].

## Notes for future work

- The **frozen table is a static snapshot** (ends 2026-08-07) — the backfill is a one-time
  merge; daily `yfinance` writes keep the recent end current. Not repeated automatically.
- Backtests read `etf_price_history_frozen` directly (`--frozen-batch`), **unaffected** by
  this backfill.
- Two ETFs that had <200 live days now get a real SMA200 in the daily monitor — could
  change their level once; correct, not a regression.
- A true "5 years" is not possible: frozen starts 2022-02 (~4.5y) and many ETFs in the
  universe are younger than that anyway. Button is labelled "Max" for that reason.
- Rollback: `DELETE FROM etf_price_history WHERE source='frozen_backfill_20260807';`
