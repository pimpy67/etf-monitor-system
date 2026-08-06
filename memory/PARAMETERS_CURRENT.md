---
name: parameters_current
description: "All current system parameters (ema20_slope_min, ADX, RSI, etc.) — source of truth"
metadata: 
  node_type: memory
  type: reference
  last_sync: 2026-07-06 19:23
  originSessionId: c74b19e0-7264-4b9a-a514-edc7242ac1fd
---

## 🎛️ PARAMETRI ATTUALI (STRATO 2 + STRATO 3)

### ema20_slope_min per Famiglia (Updated 2026-07-06)
| Famiglia | Valore | Note |
|----------|:------:|------|
| equity_sviluppati | **1.0%** | Stringente (↑ da 0.5%) |
| mercati_emergenti | 0.7% | ↑ da 0.5% |
| settoriali_growth | 0.7% | ↑ da 0.5% |
| settoriali_difensivi | 0.4% | ↑ da 0.3% |
| bond_governativi | 0.15% | Invariato |
| bond_corp_hy_em | 0.2% | Invariato |
| commodities | 0.5% | ↑ da 0.4% |
| oro_metalli_preziosi | 0.3% | Invariato |
| metalli_industriali | 0.4% | Invariato |
| real_estate_reit | 0.25% | Invariato |
| crypto_digital_assets | **0.8%** | ↑ da 0.6% |
| leva_single_stock | 0.5% | Invariato |
| private_equity_buffer | 0.2% | Invariato |
| monetario_liquidita | 0.0% | No slope check |

### RSI Entry Ranges (L1 - per Famiglia)
| Famiglia | RSI Low | RSI High |
|----------|:-------:|:-------:|
| equity_sviluppati | 45 | 55 |
| mercati_emergenti | 40 | 52 |
| settoriali_growth | 48 | 58 |
| settoriali_difensivi | 42 | 50 |
| bond_governativi | 38 | 48 |
| bond_corp_hy_em | 42 | 52 |
| commodities | 40 | 55 |
| oro_metalli_preziosi | 38 | 52 |
| metalli_industriali | 38 | 50 |
| real_estate_reit | 42 | 52 |
| crypto_digital_assets | 35 | 52 |
| leva_single_stock | 45 | 58 |
| private_equity_buffer | 40 | 55 |
| monetario_liquidita | n/a | n/a |

### ADX Entry Thresholds
| Famiglia | ADX Min |
|----------|:-------:|
| equity_sviluppati | 22 |
| bond_governativi | 12 |
| crypto_digital_assets | 28 |

### Distance EMA20 Max (%)
| Famiglia | Max Dist |
|----------|:--------:|
| equity_sviluppati | 4.0% |
| bond_governativi | 1.5% |
| crypto_digital_assets | 6.0% |

### Monitor Timing
- **Main Run**: 18:30 CEST (16:30 UTC) — lun-ven
- **Email**: 19:30 CEST (17:30 UTC)
- **Soft Run**: 09:00 CEST (07:00 UTC) — refresh silenzioso

### Database
- **Host**: PostgreSQL in Docker (etf_monitor_system-postgres-1)
- **DB**: etfs
- **User**: etfmonitor
- **Tables**: etf_price_history, etf_l1_tracking, etf_l0_tracking, portfolio_entries, portfolio_events
