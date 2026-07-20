# ETF Monitor System v4.0 — Deployment Checklist

**Date**: 2026-07-21  
**Version**: 4.0 (PRODUCTION READY)  
**Status**: ✅ All 6 STEP Complete

---

## 📋 PRE-DEPLOYMENT VALIDATION

### Code Quality
- [x] Python syntax validated (app.py, monitor.py, technical_analysis.py, database.py, etc.)
- [x] YAML configuration valid (config/etf_families.yaml)
- [x] Unit tests: 12/12 passing (L0/L1/L2 engines)
- [x] Database migration SQL verified
- [x] Git commits clean and organized

### Features Implemented
- [x] **STEP 1**: Configuration layer (YAML with 14 ETF families)
- [x] **STEP 2**: Python engines (L0/L1/L2 logic)
- [x] **STEP 3**: Monitor integration (STEP 13-15)
- [x] **STEP 4**: Database persistence (6 helper methods + 1 view)
- [x] **STEP 5**: Dashboard UI (L2 Readiness tab + API endpoint)
- [x] **STEP 6**: Unit tests (12 comprehensive test cases)

---

## 🚀 DEPLOYMENT STEPS

### Step 1: Local Verification (DONE)
```bash
✅ pytest test_l0_l1_l2.py -v          # 12/12 passed
✅ python3 -m py_compile *.py           # All OK
✅ git log --oneline -6                 # 6 clean commits
```

### Step 2: Apply Database Migration (NEXT)
```bash
# SSH to VPS
ssh root@76.13.37.133

# Enter database container
docker exec etf_monitor_system-postgres-1 psql -U etfmonitor -d etfs -f /root/etf_monitor_system/migrations/001_add_l0_l1_l2_columns.sql

# Verify migration success
docker exec etf_monitor_system-postgres-1 psql -U etfmonitor -d etfs -c "SELECT COUNT(*) FROM etf_l2_watchlist;"
```

### Step 3: Deploy to VPS
```bash
# From local (Mac)
./deploy.sh

# This will:
# 1. git push origin main
# 2. VPS: git fetch && git reset --hard origin/main
# 3. VPS: docker compose build app
# 4. VPS: docker compose up -d --force-recreate app
```

### Step 4: Verify Deployment (24h monitoring)
```bash
# Live logs
ssh root@76.13.37.133 "docker logs etf_monitor_system-app-1 --tail=50 -f"

# Look for STEP 13-15 log entries:
# 📍 L0 REGIME: fast_crash | days_below_sma200=X | dd=Y%
# 🔷 L1 7/7 CONDITIONS: ALL TRUE | space=METHOD
# 🟨 L2 READINESS: score=X (watchlist candidate)

# Dashboard check (wait for 18:30 CEST run)
https://etf.andreapavan.tech
# Click 🟨 L2 Readiness tab → should show live watchlist
```

### Step 5: Enable Email Alerts (after 24h verification)
```bash
# Verify email sent successfully
ssh root@76.13.37.133 "tail /root/etf_monitor_system/logs/monitor.log | grep 'EMAIL_SENT'"
```

---

## 📊 DEPLOYMENT VALIDATION CRITERIA

| Check | Pass | Notes |
|-------|------|-------|
| Migration executes without errors | [ ] | Use `docker exec ... -f migration.sql` |
| Container starts successfully | [ ] | `docker ps --filter name=etf_monitor_system` |
| Monitor runs on schedule | [ ] | Check logs at 18:30 CEST |
| L0 regime detected on test data | [ ] | Monitor logs STEP 13 |
| L1 7/7 conditions evaluated | [ ] | Monitor logs STEP 14 |
| L2 watchlist populated | [ ] | Monitor logs STEP 15 + `GET /api/l2-watchlist` |
| Dashboard L2 tab displays live | [ ] | https://etf.andreapavan.tech |
| Email digest sent | [ ] | Check andreapavan67@gmail.com |
| No errors in logs (24h) | [ ] | `docker logs ... grep ERROR` should be empty |

---

## ⚠️ ROLLBACK PLAN

If issues occur after deployment:

```bash
# 1. Revert to last stable commit
cd /root/etf_monitor_system
git reset --hard HEAD~1
docker compose -p etf_monitor_system build app
docker compose -p etf_monitor_system up -d --force-recreate app

# 2. Check logs
docker logs etf_monitor_system-app-1 --tail=30

# 3. Database: migration is idempotent (IF NOT EXISTS), safe to run twice
```

---

## 📝 POST-DEPLOYMENT TASKS

- [ ] Send notification to team: v4.0 live
- [ ] Monitor logs for 24 hours
- [ ] Verify email alerts are working
- [ ] Check L2 watchlist accuracy (false-positive rate < 10%)
- [ ] Update documentation with new features
- [ ] Archive previous v3.x config (backup)

---

## 🎯 EXPECTED BEHAVIOR (v4.0)

### L0 Deep Recovery
- Detects bear markets (slow path: price < SMA200 for 10+ days)
- Detects flash crashes (fast path: 8%+ drawdown, ATR-normalized)
- State persists across cycles → avoids re-entry on noise

### L1 Rally Veloci (7/7 conditions)
- ALL 7 conditions must be true for entry approval
- Returns entry_l1=true, level=1 when all pass
- space_residuo check verifies adequate upside space to next resistance

### L2 Readiness Score
- Calculates 0-100 score for watchlist candidates
- Isteresi: enter at score ≥70, exit at score <60
- Dashboard shows live scores with color coding:
  - 🟨 WATCH (score ≥70)
  - 🟡 NEAR (score ≥60)
  - ⚪ LOW (score <60)

---

## 🔗 REFERENCES

- **Commit**: 559e626 (latest: "Fix unit tests...")
- **Config**: config/etf_families.yaml (14 families, all parametrized)
- **Tests**: test_l0_l1_l2.py (12 test cases, 100% passing)
- **Migration**: migrations/001_add_l0_l1_l2_columns.sql
- **Dashboard**: https://etf.andreapavan.tech (L2 Readiness tab)
- **API**: GET /api/l2-watchlist (returns active watchlist)

---

**Status**: ✅ READY FOR DEPLOYMENT

**Next Action**: Execute STEP 2 (Database Migration) when ready.

---

Generated: 2026-07-21  
Version: 4.0  
Author: Claude Haiku 4.5
