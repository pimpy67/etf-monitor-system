# Memory Index — ETF Monitor System

## 📌 LIVE STATUS — 2026-08-06 ALIGNED ✅
- [✅ Alignment 2026-08-06](ALIGNMENT_2026_08_06.md) — System state: LOCAL = REMOTE (3bdb52e) — v4.0 LIVE + backtest 6/7 MACD
- [Current Status](CURRENT_STATUS.md) — Real-time: L1 count, monitor timing, ongoing work
- [Parameters Current](PARAMETERS_CURRENT.md) — Source of truth: 14 families, 7/7 entry, min_buy_count=7
- [Bugs Fixed](BUGS_FIXED.md) — Bug history including 2026-08-04 Regola E fix, L0 confirmation

## 🔬 LEGACY (ARCHIVED — OBSOLETE 2026-08-05)
- [🔴 ADR ARCHITECTURE DECISIONS](ADR_ARCHITECTURE_DECISIONS.md) — SUPERSEDED
- [🔧 ALIGNMENT MATRIX](ALIGNMENT_MATRIX.md) — SUPERSEDED
- [🔴 STEP 3 v4.0 EVOLUTION ANALYSIS](STEP3_v4_0_EVOLUTION_ANALYSIS.md) — SUPERSEDED
- [✅ STEP 3 v4.0 COMPLETE](STEP3_v4_0_COMPLETE.md) — SUPERSEDED (see ALIGNMENT_2026_08_06.md)
- [🟢 V4.0 DEPLOYMENT LIVE](V4_0_DEPLOYMENT_LIVE.md) — SUPERSEDED
- [🎯 V5 DEFINITIVO COMPLETE](V5_DEFINITIVO_COMPLETE.md) — SUPERSEDED
- [Session 2026-07-22](SESSION_2026_07_22_FINAL_CHECKPOINT.md) — ARCHIVED

## 📋 CURRENT SESSION (2026-08-06)
- [🟢 Session 2026-08-06 A/B Test & L0 Safety](SESSION_2026_08_06_AB_TEST_DEPLOYMENT.md) — ✅ **A/B validation mm200 (+€327 P&L), L0 regime filter (BULL only), whitelist restriction (equity_sviluppati), complete docs + roadmap** — 2 commits
- [🟢 Session 2026-07-22 FINAL CHECKPOINT](SESSION_2026_07_22_FINAL_CHECKPOINT.md) — ✅ **Stato sistema, decisioni prese, checkpoint agosto, prossimi step**
- [🔴 Session 2026-07-22 L0 Regime + L1 7-Condition](session_2026_07_22_L0_L1_fixes.md) — ✅ **CRITICAL FIX: L0 regime filter + L1 ALL 7 mandatory + Dashboard update** — 4 commits

## 📚 REFERENCE & ROADMAP
- [💰 Capital Allocation](project_capital_allocation.md) — €10k-€70k scenarios, ROA, scaling strategy
- [🚀 4 Post-Validation Improvements](project_4_improvements_post_validation.md) — ATR sizing, time-based exit, breakeven SL L0, macro filter MSCI
- [📧 Signal Frequency](project_signal_frequency.md) — ~1 new signal per 9-10 days (TBD)

## 🏗️ INFRASTRUCTURE
- **VPS**: Hostinger Ubuntu 24.04 (76.13.37.133) | **Dashboards**: https://etf.andreapavan.tech/ + https://fondi.andreapavan.tech/
- **Git**: pimpy67/etf-monitor-system + pimpy67/monitoraggio-fondi
- **Monitor**: 18:30 CEST (closing prices) + Email 19:30 CEST

## ⚡ QUICK REFERENCE
```bash
ssh root@76.13.37.133 "curl -X POST http://localhost:5001/api/trigger-update"  # Trigger monitor
docker logs etf_monitor_system-app-1 --tail=50 -f  # Live logs
cat /root/etf_monitor_system/data/dashboard_data.json | jq '.summary'  # L0/L1/L2/L3 counts
```
