---
name: trailing_dynamic_implementation
description: Dynamic trailing stop implementation with family-specific levels (2026-07-09)
metadata:
  type: project
  updated: 2026-07-09
---

# Dynamic Trailing Stop — Complete Implementation (2026-07-09)

## The Problem Solved
Traditional fixed stop loss (SL = entry_price × 0.95) locks profits at minimum:
- Entry at €100 with SL = €95
- Price rises to €150
- Pullback to €96 → **STOP OUT** despite +50% → +1% actual gain

**Dynamic Trailing**: SL moves up WITH the price, protecting gains progressively.

## Solution: trailing_levels in YAML

Each family now has multi-tier trailing logic:

```yaml
trailing_levels:
  - gain_threshold: 5.0
    trailing_pct: 0.96      # If gain >= 5%, SL = price × 96%
  - gain_threshold: 10.0
    trailing_pct: 0.95      # If gain >= 10%, SL = price × 95%
  - gain_threshold: 15.0
    trailing_pct: 0.94      # If gain >= 15%, SL = price × 94%
```

## Calibration by Family (all 15)

| Famiglia | Level 1 | Level 2 | Level 3 | Notes |
|----------|:---:|:---:|:---:|-------|
| **equity_sviluppati** | 5% → 0.96 | 10% → 0.95 | 15% → 0.94 | Moderate |
| **mercati_emergenti** | 5% → 0.97 | 12% → 0.95 | 20% → 0.93 | More space |
| **settoriali_growth** | 5% → 0.97 | 12% → 0.95 | 18% → 0.93 | Space for volatility |
| **settoriali_difensivi** | 3% → 0.97 | 7% → 0.96 | 12% → 0.94 | Tight (stable) |
| **bond_governativi** | 2% → 0.98 | 4% → 0.97 | 7% → 0.96 | Very tight |
| **bond_corp_hy_em** | 2.5% → 0.98 | 5% → 0.97 | 8% → 0.95 | Tight |
| **commodities** | 5% → 0.97 | 12% → 0.95 | 20% → 0.92 | Very wide (volatile) |
| **oro_metalli_preziosi** | 4% → 0.97 | 10% → 0.95 | 15% → 0.93 | Wide |
| **metalli_industriali** | 5% → 0.97 | 12% → 0.95 | 18% → 0.93 | Wide |
| **real_estate_reit** | 3% → 0.97 | 7% → 0.96 | 12% → 0.94 | Moderate-tight |
| **crypto_digital_assets** | 8% → 0.96 | 15% → 0.94 | 25% → 0.92 | Widest (ultra volatile) |
| **leva_single_stock** | 3% → 0.97 | 7% → 0.95 | 12% → 0.93 | Tight (high leverage) |
| **private_equity_buffer** | 3% → 0.97 | 7% → 0.96 | 12% → 0.94 | Moderate-tight |
| **monetario_liquidita** | 0.5% → 0.99 | 1.0% → 0.985 | 2.0% → 0.98 | Tiny (protection only) |

## Code Changes

### config/etf_families.yaml
- Added `trailing_levels` list to each family
- 3 tiers per family (gain_threshold + trailing_pct pairs)
- Calibrated by volatility/asset type

### technical_analysis.py
- Function: `calculate_stop_loss()`
- Logic: **Reads trailing_levels**, applies highest matching tier
- Falls back to old logic if trailing_levels not defined
- Generates: `SL = current_price × trailing_pct` (not entry_price based)

### app.py
- Endpoint: `/api/parameters` now includes `trailing_levels`
- Dashboard receives complete trailing strategy for display

## Daily Monitor Workflow

1. Monitor runs: detects L1 entry → saves `entry_price`
2. Each day: calculates `current_gain_pct = (price - entry_price) / entry_price × 100`
3. Applies trailing: finds highest `gain_threshold <= current_gain_pct`
4. Calculates: `stop_loss_trailing = current_price × trailing_pct` (from that tier)
5. Saves: `stop_loss_trailing` to database
6. Dashboard shows: Real-time SL level adjusting with price

## Example: Equity Sviluppati

Entry: €100 on MSCI World ETF
- Day 1: Price €100, gain 0% → SL = €95 (initial, not trailing yet)
- Day 5: Price €107, gain +7% → **Enters tier 1** → SL = €107 × 0.96 = **€102.72**
- Day 12: Price €115, gain +15% → **Enters tier 3** → SL = €115 × 0.94 = **€108.10**
- Day 15: Price €120, gain +20% → Still tier 3 → SL = €120 × 0.94 = **€112.80**
- Day 17: Pullback to €113, gain +13% → **Back to tier 2** → SL = €113 × 0.95 = **€107.35**

**Net**: Profit protected progressively. Never "give back" the full move.

## Files Modified
- `config/etf_families.yaml` — +trailing_levels to 15 families
- `technical_analysis.py` — Updated `calculate_stop_loss()`
- `app.py` — Added `trailing_levels` to API response

## Verification
```bash
# API returns complete trailing rules
curl https://etf.andreapavan.tech/api/parameters | python3 -m json.tool

# Dashboard displays trailing_levels for each family
# Monitor applies tiers dynamically to all L1 positions daily
```

## Next Phase (Optional)
- Visualize trailing tiers on dashboard chart (visual SL bands)
- Add "lock-in profit" alerts when tier threshold breached
- A/B test: compare trailing vs fixed SL performance in backtest
