---
name: etf-l1-smart6-macd-candidate
description: 2026-08-05 backtest — a new 'smart_6_macd' L1 entry threshold (min_buy_count=6 + MACD always required) beat both native 7/7 and plain 6/7 on 3 years of data. Leading candidate to replace production min_buy_count=7, not yet live.
metadata:
  node_type: memory
  type: project
  originSessionId: 6c15300f-1a71-4a05-b9d0-981a69b89d95
  modified: 2026-08-06T02:27:12.964Z
---

On 2026-08-05, after an external pasted analysis claimed "73% of 6/7 failures are caused by MACD" (an overreach — that number was just how often MACD was the missing condition, not proof it caused losses), the user asked for it to be tested properly rather than accepted on faith.

**Step 1 — segmentation (real, not overreach)**: split the 469 historical 6/7 trades by which single condition was missing, and looked at actual win rate: `macd_ok` missing → 44.1% win rate (worst), `rsi_ok` missing → 50.0%, `adx_ok` missing → 57.6% (best). A real effect, not noise — but checking year-by-year showed it does NOT specifically explain the bad 2024 (even 2024 trades missing RSI/ADX instead of MACD were still net-negative, -3,559€), so it's a general quality signal, not a fix targeted at 2024.

**Step 2 — real backtest of the hypothesis**: added a `smart_6_macd` variant to `backtest_l1.py` (`min_buy_count=6` but `macd_ok` must always be true — the missing condition must be something else). Result on the same 3-year/236-ETF universe:

| | native_7 | override_6 (plain) | smart_6_macd |
|---|:---:|:---:|:---:|
| Trades | 3 | 469 | **151** |
| Win rate (net) | 100% | 46.1-46.3% | **54.4%** |
| Net P&L, 5k€/trade | +775€ | **-1,304€** | **+2,599€** |
| Net P&L, 10k€/trade | +1,572€ | +1,442€ | **+6,460€** |

`smart_6_macd` beats both alternatives on every metric that matters — 4-4.5x the net P&L of either extreme, using only 32% of the plain-6/7 trade volume, and it flips the sign at 5k€/trade (plain 6/7 loses money at that size, smart_6_macd doesn't).

**How to apply**: this is currently the strongest candidate to replace `min_buy_count=7` in `config/etf_families.yaml` — but it is **backtest-only, not yet validated live and not yet in production**. Before recommending it be made the live default, check `etf_monitor_system/CLAUDE.md` → "Stato Attuale & Roadmap L1" → "Punto di decisione successivo" for whatever decision was made since (this memory reflects the state as of 2026-08-05; the roadmap section in CLAUDE.md is the living source of truth and may have moved on). If a future session is asked to implement it, that means adding a `macd_ok`-required check alongside the existing `min_buy_count` gate in `technical_analysis.py::suggest_level()` — not yet done in the real engine, only in the backtest harness.

Also see: a parallel `analyze_entry_features()` addition to `backtest_l1.py` (commit `16934d6`) was queued to compare absolute indicator values (ADX, RSI, EMA20 slope, distance from SMA200/EMA20, ATR%) between TP-exit and SL-exit trades — a feature-extraction test proposed by the user, run sequentially after this one to avoid overlapping Yahoo Finance fetches on the VPS. It was launched ~02:12 UTC on 2026-08-06 (fully detached via nohup+disown on the VPS, survives SSH/session disconnect — same pattern used all day), expected ~75-90 min runtime. **A future session resuming this thread should first check whether it finished**: `ssh root@76.13.37.133 "docker top etf_monitor_system-app-1 | grep backtest_l1; tail -100 /root/etf_monitor_system/backtest_feature_extraction_output.log"`. If finished but not yet written up, the results still need to be: analyzed, added to `etf_monitor_system/CLAUDE.md`'s Fase 2 section, committed+pushed, emailed, and reported to the user — none of that had happened as of this memory's last edit.

**Sub-finding (2026-08-05, from the smart_6_macd trade data, per-family breakdown)**: `bond_governativi` lost 5-for-5 (0 TP, 5 SL) and `bond_corp_hy_em` 0-for-1 under `smart_6_macd` — small sample, suggestive not proven (5 losses in a row isn't THAT improbable even at a genuine ~35-40% win rate). Precisely recomputed: excluding both bond families from the 147 closed smart_6_macd trades moves win rate 54.4%→**56.7%** and net P&L (10k€/trade) +6,460€→**+7,686€** (a real but modest ~19% improvement — a pasted external analysis claimed ">57%", which was wrong, likely conflating the isolated `equity_sviluppati` win rate of 57.3% with the post-exclusion aggregate). Rationale (also from the user's pasted analysis, judged sound): bonds move via mean-reversion/rate-driven behavior, not momentum — a MACD-based entry structurally doesn't suit them, same category of issue that got `leva_single_stock` excluded earlier. **Not yet tested at proper sample size or implemented** — flagged as a next candidate exclusion to test (same treatment as `leva_single_stock`: exclude via `min_buy_count` override or a family-level gate), not yet actioned.
