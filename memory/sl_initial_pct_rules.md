---
name: sl_initial_pct_rules
description: All 15 families with transparent sl_initial_pct stop loss rules (2026-07-09)
metadata:
  type: reference
  updated: 2026-07-09
---

# Stop Loss Initial Percentage Rules (2026-07-09)

## CRITICAL CHANGE
All 15 ETF families now have **explicit, transparent `sl_initial_pct` rules** replacing implicit ATR-based calculations.

| Famiglia | sl_initial_pct | Profile | SL at €100 entry |
|----------|:---:|----------|-----------|
| equity_sviluppati | 5.0% | MSCI World | €95.00 |
| mercati_emergenti | 6.0% | EM globale | €94.00 |
| settoriali_growth | 6.0% | Tech/AI | €94.00 |
| settoriali_difensivi | 4.0% | Healthcare | €96.00 |
| bond_governativi | 2.5% | Gov Bond | €97.50 |
| bond_corp_hy_em | 3.0% | Corp/HY | €97.00 |
| commodities | 7.0% | Commodity | €93.00 |
| oro_metalli_preziosi | 5.0% | Precious Metal | €95.00 |
| metalli_industriali | 6.0% | Industrial Metal | €94.00 |
| real_estate_reit | 3.5% | REIT | €96.50 |
| crypto_digital_assets | 12.0% | Bitcoin/ETH | €88.00 |
| leva_single_stock | 8.0% | 3x Long/Short | €92.00 |
| private_equity_buffer | 3.5% | Listed PE | €96.50 |
| monetario_liquidita | 1.0% | XEON | €99.00 |

## Files Changed (2026-07-09)

### config/etf_families.yaml
- Added `sl_initial_pct: X.XX` to each family
- Ordered: conservative bonds → moderate equity → high crypto

### technical_analysis.py
- Function: `calculate_stop_loss()`
- **Changed**: Now uses `sl_initial_pct` from YAML (NOT ATR)
- Formula: `sl_initial = entry_price * (1 - sl_initial_pct)`
- **All families now use explicit percentage rules**

### app.py
- Endpoint: `/api/parameters` now includes `sl_initial_pct`
- Dashboard can display actual rule value for each ETF family

## Daily Monitor Flow
1. Load family config → get `sl_initial_pct`
2. Calculate: `stop_loss_suggested = entry_price * (1 - sl_initial_pct)`
3. Save to `portfolio_entries.stop_loss_suggested`
4. Dashboard displays via `/api/parameters`

## Verification Commands
```bash
# Check YAML values
grep "sl_initial_pct:" config/etf_families.yaml

# API returns all families with sl_initial_pct
curl https://etf.andreapavan.tech/api/parameters | python3 -m json.tool

# Monitor log shows rule being applied
ssh root@76.13.37.133 "docker logs etf_monitor_system-app-1 --tail=100" | grep -i "sl_initial"
```

## Why This Matters
- **Before (implicit ATR)**: SL = price - (ATR × 2.2) — hidden, non-transparent
- **After (explicit %)**: SL = entry_price × (1 − 0.05) — visible, auditable, documented
- **User feedback driven**: "il dinamico deve essere sul SL suggerito perche se adesso è del 5% vuol dire che non rispetta le regole"
