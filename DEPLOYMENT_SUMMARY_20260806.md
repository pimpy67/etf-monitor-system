# 🎯 ETF MONITOR — DEPLOYMENT SUMMARY (2026-08-06)

**Status:** ✅ **FULL SYSTEM LIVE**  
**Deployment date:** 2026-08-06  
**Validation window:** 2026-08-06 → 2026-09-06 (30 giorni)

---

## 📊 WHAT'S DEPLOYED

### L1 — Core Portfolio (Breve termine, trend-following)

| Aspetto | Stato |
|---------|:---:|
| **Backtest validation** | ✅ 80 trade, 60% WR, €7,177 P&L (10k€) |
| **Feature Extraction** | ✅ 5 metriche, mm200_distance_max discriminant |
| **New filter** | ✅ `mm200_distance_max` (impedisce overextension) |
| **Parameters frozen** | ✅ ADX, RSI, EMA20 distance locked until 2026-09-06 |
| **Deployment report** | ✅ Inviato via email (2026-08-06 13:30) |
| **Production status** | ✅ LIVE (container VPS, port 5001) |

**Email sent:** ✅ ETF Monitor Deployment — Feature Extraction COMPLETE

---

### L0 — Deep Recovery (Medio/lungo termine, mean reversion)

| Aspetto | Stato |
|---------|:---:|
| **Backtest validation** | ✅ 8,424 trade, 52.6% WR, +5.08% P&L |
| **Feature Extraction** | ✅ 5 metriche, Days Held discriminant (-35gg) |
| **Key insight** | ✅ Vincenti mantengono 54gg vs perdenti 19gg |
| **Parameters validated** | ✅ dd_threshold, rsi_max, l0_take_profit_pct OK |
| **Parameters frozen** | ✅ All L0 params locked until 2026-09-06 |
| **Deployment report** | ✅ Inviato via email (2026-08-06 14:00+) |
| **Production status** | ✅ LIVE (same container, same database) |

**Email sent:** ✅ L0 Deep Recovery — Feature Extraction COMPLETE (8,424 trades)

---

## 🔄 DAILY OPERATIONS

### Monitor Schedule
```
📅 Lun-Ven (weekdays only)
   17:00 UTC / 19:00 CEST  → Main run (L0/L1 analysis, Excel update, email alerts)
   09:00 UTC / 11:00 CEST  → Soft run (silent, no email)

📅 Email alerts
   L1 new entries: "🟢 N nuovi in L1 — gg/mm/yyyy"
   L1 exits: "❌ USCITA L1 — regola X"
   L0 new entries: "🟠 N in L0 — Deep Recovery"
   Portfolio report: "📊 Portafoglio L1/L0 — gg/mm/yyyy" (SL/TP suggeriti)
```

### Files Modified Daily
- `etf_monitoraggio.xlsx` — Colonna "Livello" aggiornata (L0/L1/L2/L3)
- Database `etfs` (PostgreSQL):
  - `etf_l1_tracking` — posizioni L1
  - `etf_l0_tracking` — posizioni L0
  - `etf_price_history` — storico prezzi + close
  - `etf_portfolio_entries` — portafoglio personale (status, SL, TP)
  - `etf_l1_exit_history` — storia uscite L1
- Dashboard: `data/dashboard_data.json` (riflette L0/L1/L2/L3 counts)

---

## 🛡️ PROTECTION & LOCKDOWN

### Parameters Frozen (2026-08-06 → 2026-09-06)

**L1 Frozen:**
```yaml
adx_entry: FROZEN (FE gap -0.55 — perdenti hanno ADX più alto)
rsi_entry_low/high: FROZEN (FE validato +2.15)
ema_dist_max: FROZEN (FE validato +0.29)
mm200_distance_max: APPROVED (FE gap -3.38% — NEW, monitored)
```

**L0 Frozen:**
```yaml
dd_threshold: FROZEN (FE gap -0.82% — non discriminant)
rsi_max: FROZEN (FE gap -1.4 — small but OK)
l0_take_profit_pct: FROZEN (holding period validated)
sl_initial_pct: FROZEN (trailing SL OK)
```

### Change Control
- ❌ **NO changes allowed** to frozen parameters until 2026-09-06
- ✅ **New features** require: Feature Extraction + 30-day backtest + approval
- ✅ **Pre-deploy validation** script: `/root/etf_monitor_system/scripts/pre_deploy_validation.py`

---

## 📋 30-DAY VALIDATION WINDOW

### Weekly Checks (Every Monday 09:00 CEST)

**Script:** `/root/etf_monitor_system/scripts/weekly_validation.py`  
**Cron:** `0 7 * * 1 cd /root/etf_monitor_system && python3 scripts/weekly_validation.py`  
**Output:** `data/weekly_validation_YYYYMMDD.json`

#### Check 1: L1 Rolling Backtest (7 giorni)
- Target: WR 60% ± 10%
- Fails if: WR < 50% OR WR > 70%

#### Check 2: L0 Positions & Holding Period
- Target: 1-5 new entries/month, avg 40-60 giorni
- Fails if: L0 holding < 30gg OR > 90gg

#### Check 3: Parameter Integrity
- Verifica: NO unauthorized changes to frozen params
- Fails if: Any frozen param modified

#### Check 4: L0/L1 Distribution Sanity
- Target: L1 0-10% of universe, L0 0-5%
- Fails if: L1 > 10% OR L0 > 5% (anomaly)

#### Check 5: System Uptime
- Target: Monitor run in last 48h
- Fails if: Last update > 48h ago

### Validation Success Criteria (2026-09-06)

✅ ALL checks must PASS:
- L1 WR stays 60 ± 10%
- L0 WR stays 50-55%
- Zero parameter drift
- L0/L1 distribution normal
- 100% uptime (< 48h since last run)

**If all pass:** ✅ Deployment CONFIRMED → parameters unlocked  
**If any fail:** ⏸️ Investigate → possible rollback

---

## 📊 MONITORING CHECKLIST (per the user)

### Daily (Automatic — No action needed)
- ✅ Monitor run: 17:00 CEST (L0/L1 analysis, price fetch, Excel update)
- ✅ Email alerts: SL/TP suggerito per portfolio L1/L0
- ✅ Database sync: `etf_price_history`, `etf_l1_tracking`, `etf_l0_tracking`

### Weekly (Monday 09:00)
- ✅ Automated validation: 5-check suite
- ✅ Report: `weekly_validation_YYYYMMDD.json`
- ⏳ Manual review: Check for warnings in the report

### Monthly (2026-09-06)
- ✅ FINAL EVALUATION: Are success criteria met?
- ✅ Decision: Keep deployment vs rollback
- ✅ Next step: Quarterly Feature Extraction (if deployed)

---

## 🚀 NEXT PHASES (Post-Validation)

### Phase 2: OPTIMIZATION (2026-09-07 onwards)

If 30-day validation passes:

**L1 Enhancement:**
- Evaluate: Volatility filter (ATR squeeze)
- Evaluate: Regime macro (VIX correlation)
- Timeline: Q4 2026 Feature Extraction cycle

**L0 Enhancement:**
- Evaluate: Recovery signal strength (RSI divergence details)
- Evaluate: Family-specific TP optimization
- Timeline: Q4 2026

### Phase 3: QUARTERLY FEATURE EXTRACTION (Every 3 months)

**2026-11-06:** Revalidate L1 + L0 with 3 months of new data  
**2027-02-06:** Confirm seasonal patterns, adjust parameters if needed  
**2027-05-06:** Annual review, major parameter refactor if necessary

---

## 📞 SUPPORT & ESCALATION

### If something breaks:

1. **Check dashboard:** https://etf.andreapavan.tech
2. **VPS logs:** `ssh root@76.13.37.133 "docker logs etf_monitor_system-app-1 --tail=100"`
3. **Database check:** `ssh root@76.13.37.133 "docker exec etf_monitor_system-postgres-1 psql -U etfmonitor -d etfs -c 'SELECT COUNT(*) FROM etf_price_history;'"`
4. **Trigger manual run:** `curl -X POST http://76.13.37.133:5001/api/trigger-update`

### If validation fails:

Run rollback:
```bash
# VPS
git revert <commit-hash>  # Revert mm200_distance_max deployment
git push origin main
docker restart etf_monitor_system-app-1
```

---

## 📈 SUCCESS METRICS (Target 2026-09-06)

| Metric | Target | Current |
|--------|:---:|:---:|
| **L1 WR (7d rolling)** | 60% ± 10% | ⏳ TBD (in validation) |
| **L0 WR (new entries)** | 50-55% | ⏳ TBD |
| **P&L L1 (10k€ position)** | +€500+ | ⏳ TBD |
| **L0 holding period avg** | 40-60 giorni | ⏳ TBD |
| **Parameter drift** | ZERO | ✅ ZERO (locked) |
| **Uptime** | >99% | ⏳ TBD |

---

## ✅ DEPLOYMENT COMPLETE

**Date:** 2026-08-06 13:30 CEST  
**Components:** L1 (Feature Extraction + mm200_distance_max filter) + L0 (Feature Extraction validated)  
**Status:** ✅ LIVE & MONITORED  
**Duration:** 30-day validation window (until 2026-09-06)  

**Reports sent to:** andreapavan67@gmail.com
- ✅ L1 Deployment Report
- ✅ L0 Feature Extraction Report
- ✅ System Lockdown Documentation

**Next email:** Weekly validation report (every Monday 09:00 starting 2026-08-13)

---

*Deployment finalized: 2026-08-06*  
*System architect: Feature Extraction Pipeline*  
*Validation window: 30 giorni (08-06 → 09-06)*

