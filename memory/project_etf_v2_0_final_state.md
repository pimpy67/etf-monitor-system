---
name: etf_v2_0_final_state
description: ETF Monitor v2.0 — complete implementation state (taxonomy + parametric rules + relaxed bond/crypto)
metadata: 
  node_type: memory
  type: project
  date: 2026-06-29
  status: PRODUCTION
  originSessionId: 3e4881d1-06ca-40b4-9317-4a66d61e5f13
---

# ETF Monitor System v2.0 — FINAL STATE (June 29, 2026)

## 🎯 PROJECT COMPLETION

### ✅ Implemented Features

**1. TASSONOMIA 13 FAMIGLIE (14 con monetario)**
- ✅ config/etf_families.yaml: complete parametric configuration
- ✅ 226 ETF correctly mapped to 14 families (100% coverage)
- ✅ Pattern matching via detect_family() in technical_analysis.py

**Distribution:**
- equity_sviluppati: 99 ETF
- bond_governativi: 24 ETF
- bond_corp_hy_em: 26 ETF
- mercati_emergenti: 22 ETF
- leva_single_stock: 12 ETF
- oro_metalli_preziosi: 5 ETF
- crypto_digital_assets: 5 ETF
- commodities: 4 ETF
- monetario_liquidita: 4 ETF
- metalli_industriali: 6 ETF
- settoriali_growth: 10 ETF
- real_estate_reit: 3 ETF
- settoriali_difensivi: 4 ETF
- private_equity_buffer: 2 ETF

**2. 3-STATE REGIME (BULL / LATERALE / BEAR)**
- ✅ calculate_regime() in technical_analysis.py
- ✅ Parametric lateral_band per family
- ✅ BULL regime required for L1 (strictly enforced)
- ✅ Dashboard shows regime for each ETF

**3. PARAMETRIC RULES (min_buy_count)**
- ✅ bond_governativi: 5/6 for L1 (less volatile)
- ✅ bond_corp_hy_em: 5/6 for L1 (less volatile)
- ✅ crypto_digital_assets: 5/6 for L1 (high volatility tolerance)
- ✅ All other families: 6/6 for L1 (rigorous)
- ✅ Implemented via self.p.get('min_buy_count', 6)

**4. TECHNICAL INDICATORS**
- ✅ EMA10, EMA20, SMA50, SMA200
- ✅ RSI14, ADX14, MACD(12,26,9)
- ✅ ATR normalized, Drawdown 52W, Price Range (in conditions dict)
- ✅ L0 Deep Recovery: 4 conditions + divergence detection

**5. L1 ENTRY CONDITIONS (ALL 6 REQUIRED)**
1. Alignment: price > EMA20 > SMA50 (+ SMA200 filter if mm200_filter=true)
2. Persistence: days_above_EMA20 ≥ 3 + slope(EMA20) > 0
3. RSI optimal: rsi_entry_low ≤ RSI ≤ rsi_entry_high (family-specific)
4. Distance EMA20: 0% ≤ dist_EMA20 ≤ ema_dist_max
5. ADX: ADX ≥ adx_entry (family-specific)
6. MACD momentum: macd_h > 0 AND (macd_h > macd_h_prev OR dist < 2%)

**PLUS: REGIME BULL MANDATORY + KILL SWITCH PROTECTION**

**6. L1 EXIT RULES (6 RULES, PRIORITY ORDER)**
- F: Kill Switch (daily change ≤ -3%) → total
- A: Stop Loss (price < EMA20 for ≥ 3 days) → total
- B: Trailing Stop (EMA10 < EMA20) → total
- C: Fatigue (RSI_prev ≥ 70 AND RSI < 70) → total (non-bond)
- E: Weak ADX (ADX < 18 AND price < EMA20) → total
- D: Partial Exit (RSI > 78) → 90% + keep 10% (not yet implemented)

---

## 🚀 DEPLOYMENT STATUS

### Latest Commits
- 28726e3: Feature: Parametric min_buy_count for L1 entry (relaxed to 5/6 for bond & crypto)
- 7588065: Fix: Complete taxonomy mapping — 14 families with 226 ETF correctly assigned
- 66bbbcc: Cleanup: Remove debug logging and temp files

### Production (VPS)
- ✅ Container: etf_monitor_system-app-1 (port 5001)
- ✅ Database: PostgreSQL etf_monitor_system-postgres-1
- ✅ Dashboard: https://etf.andreapavan.tech/
- ✅ Monitor running: scheduled 17:00 daily (lun-ven)
- ✅ Last run: 2026-06-29 21:39 (with min_buy_count feature)

### Git
- ✅ Remote: https://github.com/pimpy67/etf-monitor-system.git
- ✅ Branch: main (tracking origin/main)
- ✅ Tag: v2.0 (release tag)

---

## 📊 CURRENT L1 STATE (as of Jun 29, 2026)

Expected after min_buy_count feature:
- L0: 1-2 ETF
- L1: 15-25 ETF (bond/crypto relaxed to 5/6)
- L2: 170-180 ETF
- L3: 35-45 ETF

Previous state (before relaxation):
- L0: 1 ETF
- L1: 0 ETF (6/6 too rigorous)
- L2: 180 ETF
- L3: 41 ETF

---

## 🔧 KEY FILES & LOCATIONS

| File | Purpose | Status |
|------|---------|--------|
| config/etf_families.yaml | Parametric config (14 families) | ✅ Complete |
| technical_analysis.py | Core logic (6 conditions + regime + min_buy_count) | ✅ Current |
| monitor.py | Main orchestrator (data fetch, analysis, alerts) | ✅ Working |
| app.py | Flask API + dashboard serving | ✅ Working |
| dashboard.html | Frontend (L0/L1/L2/L3 visualization) | ✅ Updated |
| etf_monitoraggio.xlsx | ETF universe (226 ETF, 42 categories) | ✅ Source of truth |

---

## 📝 NEXT POTENTIAL ENHANCEMENTS

1. **Piede Dentro (90%/10% partial exit)**
   - Regola D (RSI > 78) → partial 90% + keep 10%
   - Automatically buy XEON (money market ETF)
   - Manage partial exits in dashboard

2. **Advanced Dashboard Metrics**
   - ATR normalized visualization
   - Drawdown 52W heatmap
   - Price Range indicators
   - Correlation matrix (L1 portfolio)

3. **Backtest Framework**
   - Historical testing of 6-condition logic
   - Regime accuracy measurement
   - L0 recovery success rate

4. **Bond-specific Enhancements**
   - Duration filtering
   - Spread compression signals
   - Yield vs ECB rate comparison

5. **Crypto-specific Enhancements**
   - Volatility indexing (VIX-like)
   - On-chain metrics integration
   - Micro cap risk flags

---

## 🎓 DESIGN PRINCIPLES IMPLEMENTED

✅ **Parametric over Hardcoded**: All thresholds in YAML, per-family customization
✅ **6/6 Mandatory for L1**: Strict entry, prevents false signals
✅ **BULL Regime Enforced**: Regime protection, no laterale/bear in L1
✅ **Family-Aware**: 14 specialized profiles, not one-size-fits-all
✅ **Kill Switch Protection**: 3% daily drop blocks new entries
✅ **Persistent Exit Tracking**: 3+ day rules prevent whipsaw
✅ **Dashboard Transparency**: Conditions dict shows all calc details

---

## ⚡ MONITORING & ALERTS

- Daily 17:00 run: full analysis + alerts
- Resend API: email notifications (entry/exit/recovery)
- Portfolio tracking: stop_loss_history.json
- Auto-recovery: container restart + health check

---

## 🔐 SECURITY & DATA INTEGRITY

- ✅ PostgreSQL encrypted volumes (Hostinger managed)
- ✅ Cloudflare SSL (Full strict mode)
- ✅ Git versioning (public repo, no secrets in code)
- ✅ .env isolated (credentials not in git)
- ✅ Database backups: daily cron (14-day retention)

---

## 📞 SUPPORT CHECKLIST

- [ ] Monitor logs: `ssh root@76.13.37.133 "docker logs etf_monitor_system-app-1 --tail=50 -f"`
- [ ] Health check: `curl -s http://localhost:5001/api/health`
- [ ] DB query: `docker exec etf_monitor_system-postgres-1 psql -U etfmonitor -d etfs -c "SELECT COUNT(*) FROM etf_price_history"`
- [ ] Manual trigger: `curl -X POST http://localhost:5001/api/trigger-update`

---

**Last Updated**: 2026-06-29 21:45
**Version**: 2.0 (production)
**Status**: STABLE + RELAXED (5/6 for bond/crypto)
