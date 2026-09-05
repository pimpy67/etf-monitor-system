---
name: etf-financial-advice-boundary
description: "Standing rule: Claude computes lot/€ mechanics for PAC/portfolio when the user supplies the amount and instrument, but never decides allocation % or investment timing — that's personalized financial advice"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7f65ec4c-5f2a-4ff6-bd23-925df2bea115
  modified: 2026-09-05T11:36:48.232Z
---

Established 2026-09-05, twice in the same session (WeBank-funds multi-year deployment
plan tied to BTP maturities/coupons; and initially the crypto/metalli % split before the
user supplied 2%/3% himself). Claude declined to "propose an investment plan" both times,
citing the not-a-licensed-advisor boundary, and instead did the mechanical calculation
once the user supplied the missing decision (percentages, specific ETF tickers, or a
euro amount).

**Why**: real money, real accounts (Directa/WeBank/BancoPosta/Online SIM), system prompt
explicitly prohibits personalized investment/financial advice. The user accepted this
boundary without pushback both times and explicitly confirmed the resulting working
pattern: "memorizza la PAC e ti dirò di volta in volta e tu mi darai i lotti" (remember
the PAC setup, I'll tell you an amount from time to time and you give me the lots).

**How to apply**: 
- OK to do: given a user-specified € amount/instrument/percentage, compute lots, € per
  installment, totals — pure arithmetic on their decision.
- OK to do: report factual data (current holdings, prices, bond maturity dates/coupon
  rates, ISIN/ticker lookups) without editorializing on what to do with it.
- NOT OK: proposing WHICH allocation %, WHEN to invest freed-up capital, WHICH account to
  draw from, or any sequencing/timing recommendation across the multi-year BTP-maturity
  horizon — redirect to "that's your call" (or a real advisor for tax-optimized
  sequencing) every time, even on a second/third ask reframing the same request.

See [[etf_pac_crypto_metalli_planning_2026_09_05]] for the concrete PAC state this
pattern applies to.
