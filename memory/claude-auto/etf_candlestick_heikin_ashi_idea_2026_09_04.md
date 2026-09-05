---
name: etf_candlestick_heikin_ashi_idea_2026_09_04
description: "TESTED AND CLOSED 2026-09-04 (same day, later session): standalone candlestick reversal patterns (Hammer/Bullish Engulfing/Morning Star) as an entry system show NO edge across 3 independent methodologies (loose, rigorous with confirmation+R:R, pullback-in-uptrend) — all PF<=1 or regime-artifact. Only use-case #2 (tighten SL on a bearish reversal candle when profit >8%) still worth pursuing, folded into the already-queued L1 EXIT analysis (item 17)."
metadata: 
  node_type: memory
  type: project
  originSessionId: f0161496-431a-4e32-b1ad-b7395c4f0d9e
  modified: 2026-09-04T15:26:07.521Z
---

## UPDATE 2026-09-04 (later same day) — use-case #1 tested, definitively rejected

User asked directly to backtest standalone entry on the 3 bullish reversal patterns
(Hammer/Bullish Engulfing/Morning Star), long-only, exit on the 2 bearish ones
(Shooting Star/Bearish Engulfing) + safety nets. Three progressively stricter
methodologies, all on the frozen Golden Dataset (batch 2026-08-07), IN 2023-08-05→
2025-08-05 / OOS →2026-08-05, 6 families (equity_sviluppati/mercati_emergenti/
settoriali_growth/metalli_industriali/oro_metalli_preziosi/crypto), real costs+tax:

| Version | Context filter | Entry | IN PF | OOS PF |
|---|---|---|---|---|
| Loose | downtrend OR near 20d-low(3%) | next-day open | 1.01 | 2.03* |
| Rigorous | near SMA50/200(2%) or 60d-low(1.5%) | breakout confirm ≤5d, SL=pattern low, TP R:R≥1:2 capped by 60d resistance | 0.92 | 0.96 |
| Pullback-in-uptrend | price>SMA200 & SMA50>SMA200 & near SMA50(3%) | same as rigorous | 0.88 | 0.85 |

*Loose version's OOS "win" is a regime artifact, not real edge: IN spans the
already-documented bad 2024, OOS spans the known 2025-26 bull run — it's proxying
"buy dips in a rising market during the window that happened to be rising", not real
pattern predictive power. Confirmed by mechanism: with a rigorous R:R≥1:2 setup and
~48-51% win rate, the theoretical EV is positive (+0.44R), but realized PF stays ≤1
because the take-profit gets capped by real resistance well short of the nominal
target — the "correct" methodology (SL at pattern low, TP before resistance) self-limits.
Hammer — the most common and most iconic pattern — lost in both IN and OOS in both
rigorous variants. Restricting further to "uptrend pullback" made it *worse*, not
better (even equity_sviluppati, the one family with real edge everywhere else in this
project, lost: PF 0.91/0.91) — ruling out "just needs a tighter context" as an escape
hatch. **Closed for good — don't re-test without genuinely new data or a materially
different mechanism**, same discipline as the momentum/rotation verdict in
[[etf-sector-taxonomy-and-partb-plan-2026-09-04]].

Scratch scripts (`candle_patterns_bt.py`/`bt2`/`bt3`/`bt4`) were VPS-only, removed after the run.

**Also tested same day: ATR-range filter on the pattern candle** (only count a reversal
candle if its H-L range >= 1.5x or 2.0x ATR14 — "anomalous candle = real exhaustion/
volume" idea). Makes it worse, not better: at 1.5x (N=155 IN/75 OOS, still usable) OOS
PF drops to **0.64** (worse than the no-filter rigorous version's 0.96); at 2.0x N
collapses to 9 OOS trades — meaningless, and shows the exact overfitting signature
(hammer: IN PF 4.48 N=63 -> OOS PF 0.10 N=10, a complete reversal). Confirms this isn't
a "needs a stricter trigger" problem — every restriction tried (support-only, uptrend-
pullback, ATR-anomaly) either does nothing or actively hurts. Fully closed, 4/4 variants
tested negative.

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
