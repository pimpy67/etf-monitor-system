---
name: next_steps
description: Tasks for next session - optional enhancements and refactoring opportunities
metadata: 
  node_type: memory
  type: project
  originSessionId: 3e4881d1-06ca-40b4-9317-4a66d61e5f13
---

# NEXT STEPS — ETF Monitor System v2.0

## 🎯 PRIORITY LEVELS

### 🔴 CRITICAL (if needed)
- **If L1 remains empty indefinitely**: Consider relaxing thresholds
  - Option A: Reduce to 4/6 for all families
  - Option B: Lower ADX threshold (15 instead of 20)
  - Option C: Widen RSI entry ranges
  - Decision: Monitor for 2-3 weeks first, decide based on data

### 🟠 HIGH (recommended soon)
1. **Piede Dentro (90%/10% Partial Exit)**
   - Regola D (RSI > 78) → partial 90% exit
   - Auto-buy XEON (money market ETF)
   - Track partial positions in dashboard
   - Code location: technical_analysis.py:680-700 (D rule, currently commented)
   - Status: Rule exists in schema, not implemented in logic

2. **ISIN Resolution for 13 ETF**
   - Found 13 ETF with nan ISIN (used Ticker as fallback)
   - One resolved: HLTH.DE = GB0003692513
   - Remaining 12: WSML.DE, VHYL.MI, IWMO.DE, IWQU.DE, MVOL.DE, LTAM.MI, EMV.MI, EMID.L, ALUM.MI, ZINC.MI, BATE.DE, DX2G.DE
   - Action: Manual lookup via https://query1.finance.yahoo.com/v1/finance/search?q={ISIN}
   - Impact: Better DB tracking, cleaner portfolio analysis

3. **L1 Entry Diagnostics**
   - Check if any ETF is close to meeting 6/6 (e.g., 5.5/6 = 1 condition away)
   - Analyze which conditions are most common blockers
   - Report: "ADX too low" vs "RSI out of range" vs "price < EMA20", etc.
   - Tool: SQL query on etf_price_history + technical indicators

### 🟡 MEDIUM (nice-to-have)
1. **Advanced Dashboard Metrics**
   - ATR normalized visualization (volatility heatmap)
   - Drawdown 52W chart (stress levels)
   - Price Range indicators (potential moves)
   - Correlation matrix (L1 portfolio overlap detection)
   - Status: Metrics calculated, not displayed on dashboard

2. **Backtest Framework**
   - Historical test of 6-condition logic on past 100 days
   - Regime accuracy measurement (how often regime was correct?)
   - L0 recovery success rate (% of L0 → L1 promotions)
   - Win/loss ratio on L1 entries
   - Tool: New script `backtest.py` querying historical data from DB

3. **Bond-Specific Enhancements**
   - Duration filtering (short/medium/long bond buckets)
   - Spread compression signals (credit cycle indicator)
   - Yield vs ECB rate comparison (carry opportunity)
   - Status: Parameters exist, signals not implemented

4. **Crypto-Specific Enhancements**
   - Volatility indexing (BTC VIX-like metric)
   - On-chain metrics integration (whale movement detection)
   - Micro cap risk flags (< $100M market cap → L3 only)
   - Status: Not started

### 🟢 LOW (long-term)
1. **Refactor L0 Logic**
   - Current: 4 conditions for L0 entry
   - Potential: Family-specific L0 thresholds (drawdown % varies)
   - Would improve recovery signal quality for bond/crypto

2. **Multi-Portfolio Support**
   - Current: Single "portfolio_entries" table
   - Potential: Support multiple user portfolios with different risk profiles
   - Would need: User auth, portfolio dashboard, separate P&L tracking

3. **Real-time Dashboard Updates**
   - Current: JSON regenerated daily + refresh on demand
   - Potential: WebSocket updates (L1 entry/exit in real time)
   - Would reduce latency but add infrastructure complexity

4. **Mobile App**
   - Current: Web dashboard (desktop-optimized)
   - Potential: Native iOS/Android app with push notifications
   - Effort: High, ROI depends on user base

---

## 📋 RECOMMENDED SEQUENCE FOR NEXT SESSION

### Session N+1 (recommended, ~3 hours)
1. **L1 Entry Diagnostics** (30 min)
   - Query DB to find "closest misses" (5/6 conditions)
   - Identify blocker conditions by family
   - Report findings

2. **Piede Dentro Implementation** (90 min)
   - Implement Regola D (RSI > 78 → 90%/10% split)
   - Auto-buy XEON logic
   - Partial exit tracking in DB
   - Dashboard display for partial positions

3. **ISIN Resolution** (30 min)
   - Lookup and update 12 remaining ISIN values
   - Update etf_monitoraggio.xlsx
   - Run monitor to verify tracking improves

4. **Deploy & Test** (30 min)
   - Git commit + push
   - VPS deploy
   - Monitor manual trigger
   - Verify partial exits tracked correctly

### Session N+2 (if time, ~2 hours)
1. **Backtest Framework** (60 min)
   - Build backtest.py querying historical data
   - Measure: win rate, avg gain/loss, regime accuracy

2. **Dashboard Enhancements** (60 min)
   - Add ATR normalized heatmap
   - Add Drawdown 52W chart
   - Display correlation matrix (L1 overlap)

---

## 📞 QUICK REFERENCE

### Critical Paths (if something breaks)
- Monitor not running: SSH to VPS, check `docker logs etf_monitor_system-app-1`
- L1 empty: Check regime calculation (BULL requirement)
- File sync issue: Use `docker cp` to sync /app/data/ to /root/

### Useful Commands
```bash
# Check monitor is healthy
curl -s http://localhost:5001/api/health | jq .

# Run manual monitor trigger
ssh root@76.13.37.133 "curl -X POST http://localhost:5001/api/trigger-update"

# Query L1 ETF
ssh root@76.13.37.133 "docker exec etf_monitor_system-postgres-1 psql -U etfmonitor -d etfs -c 'SELECT COUNT(*) FROM etf_l1_tracking'"

# Pull latest from GitHub
cd etf_monitor_system && git pull origin main

# Push local changes
git add -A && git commit -m "message" && git push origin main
```

---

## 📊 DECISION POINTS FOR NEXT SESSION

**Q: Should we relax L1 thresholds?**
- Current: 6/6 for 11 families, 5/6 for bond/crypto
- Result: L1 = 0 ETF
- Decision: Monitor for 2 weeks before changing (let market normalize)
- Trigger for change: If L1 < 5 ETF after 2 weeks, revisit thresholds

**Q: Implement Piede Dentro now?**
- Status: Code exists, not logic-integrated
- Benefit: Better partial exit handling, reduced tax drag
- Effort: 90 minutes
- Recommendation: YES, implement next session

**Q: Focus on backtest or diagnostics first?**
- Diagnostics: faster, provides data for threshold decisions
- Backtest: longer-term value, validates historical accuracy
- Recommendation: Diagnostics first (informs next threshold decision)

---

**Last Updated:** 2026-06-29 21:50
**Status:** Ready for next session
**Blocker:** None (system stable)
