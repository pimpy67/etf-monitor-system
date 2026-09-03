---
name: etf_candlestick_heikin_ashi_idea_2026_09_04
description: "User asked (via a pasted external AI analysis) whether Japanese candlestick patterns / Heikin-Ashi could give buy & exit signals. Verdict: only use-case #2 (tighten SL on a bearish reversal candle when profit >8%) is worth pursuing, folded into the already-queued L1 EXIT analysis (item 17). Not now. Frozen-backtest + IN/OOS + N>=30 + Shadow first, same as everything else."
metadata: 
  node_type: memory
  type: project
  originSessionId: f0161496-431a-4e32-b1ad-b7395c4f0d9e
  modified: 2026-09-03T22:11:34.933Z
---

2026-09-04. User forwarded an external analysis proposing 3 candlestick use-cases and
asked "le candele giapponesi possono servire per dare i segnali di acquisto e uscita".

## Verdict (per this project, not in the abstract)

The external analysis is directionally fine (candles standalone = noise; as a confirmation
trigger / exit-tightener = some value). But filtered for this system:

1. **Candle confirmation for L0 entry (Hammer / Bullish Engulfing / close > prev high)**
   → **low value-add.** L0 already has a recovery-confirmation condition: PRAGMATIC #4 =
   "RSI back > 32 OR micro-breakout >= 0.3% over 5d", and FAST/SLOW got
   `_get_l0_confirmation_signal()` (05/08). "Close > prev high" *is* the micro-breakout.
   Skip unless a backtest shows the candle version beats the existing one.

2. **Tighten SL below the low of a Shooting Star / Bearish Engulfing when profit > 8%**
   → **the only one worth pursuing.** The system's real weak spot is the EXIT — the
   2026-09-01/02 analysis found 78-83% of L1 exits are stop losses. This belongs *inside*
   the already-queued **item 17 (L1 EXIT analysis: wider / ATR / confirm-delay SL variants)**
   as one more variant to sweep. See [[etf_post_lockdown_todo_20260906]] item 17.

3. **Heikin-Ashi for L1 trend-following** → interesting, low priority. Test as a backtest
   variant: replace the dashboard Regola B (EMA10 < EMA20) with "first red HA candle, no
   lower wick" and see if it stabilises the L1 classification. Separate item, behind item 17.

## Why not now

Queue is: 06/09 checkpoint → item 15 (Directa-faithful exit model) → item 17 (L1 exits —
fold candles #2 in here) → item 18b (momentum shadow). Candles are behind all of that.

**How to apply**: if/when this comes up again, don't build on the strength of the plausible
write-up — every "this should help" idea in this project (ADX filter on 6/7, mm200_delta,
grind 5 ways, momentum) was tested and mostly rejected. Same bar: frozen Golden Dataset,
IN/OOS split, must beat baseline out-of-sample at N>=30, Shadow Monitor before promotion.

Technical caveat: candlestick pattern-matching on daily European-ETF bars is noisier than on
stocks (NAV micro-gaps, low relative volume, and this repo has had OHLC-NULL / ticker
issues). Testable on the frozen OHLC dataset; live reliability is a separate worry.
