#!/usr/bin/env python3
"""
Weekly Validation — L1 & L0 Monitoring (30-day window: 2026-08-06 → 2026-09-06)
Runs every Monday 09:00 CEST
Checks: WR, P&L, parameter integrity, L0/L1 distribution, no crashes
"""
import sys
import os
from datetime import datetime, timedelta
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from database import db
    import yfinance as yf
    import pandas as pd
    import numpy as np
except ImportError as e:
    print(f"❌ Errore import: {e}")
    sys.exit(1)

VALIDATION_WINDOW_START = datetime(2026, 8, 6)
VALIDATION_WINDOW_END = datetime(2026, 9, 6)

report = {
    'timestamp': datetime.now().isoformat(),
    'week': f"W{(datetime.now() - VALIDATION_WINDOW_START).days // 7 + 1}",
    'status': 'PASS',
    'checks': {},
    'alerts': []
}

print("=" * 70)
print(f"📊 WEEKLY VALIDATION — {datetime.now().strftime('%d/%m/%Y')}")
print("=" * 70)

# ============================================================================
# CHECK 1: L1 ROLLING BACKTEST (7 giorni)
# ============================================================================
print("\n1️⃣ L1 ROLLING BACKTEST (7 giorni)")

try:
    conn = db._get_connection()
    if not conn:
        report['checks']['l1_backtest'] = 'FAIL: DB unavailable'
        report['status'] = 'FAIL'
    else:
        cur = conn.cursor()

        # Leggi gli ultimi 7 giorni di L1 trades chiusi
        seven_days_ago = (datetime.now() - timedelta(days=7)).date()
        cur.execute("""
            SELECT COUNT(*), SUM(CASE WHEN pct_gain > 0 THEN 1 ELSE 0 END),
                   AVG(pct_gain)
            FROM etf_l1_exit_history
            WHERE exit_date >= %s
        """, (seven_days_ago,))
        result = cur.fetchone()
        conn.close()

        if result and result[0] > 0:
            total_trades = result[0]
            wins = result[1] or 0
            avg_gain = result[2] or 0
            wr_7d = (wins / total_trades * 100) if total_trades > 0 else 0

            check_pass = 50 <= wr_7d <= 70  # Target: 60 ± 10
            status = '✅ PASS' if check_pass else '⚠️  WARNING'

            report['checks']['l1_backtest'] = {
                'trades_7d': total_trades,
                'wr_7d': f"{wr_7d:.1f}%",
                'avg_gain': f"{avg_gain:+.2f}%",
                'status': status,
                'target': '60% ± 10%'
            }

            print(f"   Trades (7d): {total_trades}")
            print(f"   Win Rate: {wr_7d:.1f}% {status}")
            print(f"   Avg Gain: {avg_gain:+.2f}%")

            if not check_pass:
                report['status'] = 'WARNING'
                report['alerts'].append(f"L1 WR out of range: {wr_7d:.1f}% (target 60±10%)")
        else:
            report['checks']['l1_backtest'] = 'No trades in 7 days (OK if weekend)'
            print("   No trades in 7 days (possibly weekend)")

except Exception as e:
    report['checks']['l1_backtest'] = f'ERROR: {str(e)}'
    report['status'] = 'FAIL'
    print(f"   ❌ Errore: {e}")

# ============================================================================
# CHECK 2: L0 ACTIVE POSITIONS & HOLDING PERIOD
# ============================================================================
print("\n2️⃣ L0 ACTIVE POSITIONS & HOLDING PERIOD")

try:
    conn = db._get_connection()
    if not conn:
        report['checks']['l0_positions'] = 'FAIL: DB unavailable'
        report['status'] = 'FAIL'
    else:
        cur = conn.cursor()

        # L0 entries in ultimi 30 giorni
        thirty_days_ago = (datetime.now() - timedelta(days=30)).date()
        cur.execute("""
            SELECT COUNT(*), AVG(JULIANDAY('now') - JULIANDAY(entry_date))
            FROM etf_l0_tracking
            WHERE entry_date >= %s
        """, (thirty_days_ago,))
        result = cur.fetchone()

        if result:
            l0_count = result[0] or 0
            avg_holding = result[1] or 0

            check_pass = 1 <= l0_count <= 5  # 1-5 entries per month è normal
            status = '✅ PASS' if check_pass else '⚠️  WARNING'

            report['checks']['l0_positions'] = {
                'active_l0_30d': l0_count,
                'avg_holding_days': f"{avg_holding:.0f}",
                'status': status,
                'target': '1-5 entries/month, 40-60 days avg'
            }

            print(f"   L0 Entries (30d): {l0_count}")
            print(f"   Avg Holding: {avg_holding:.0f} giorni {status}")

            if avg_holding < 30 or avg_holding > 90:
                report['alerts'].append(f"L0 holding period anomaly: {avg_holding:.0f}d (target 40-60d)")

        conn.close()

except Exception as e:
    report['checks']['l0_positions'] = f'ERROR: {str(e)}'
    print(f"   ❌ Errore: {e}")

# ============================================================================
# CHECK 3: PARAMETER INTEGRITY (No unauthorized changes)
# ============================================================================
print("\n3️⃣ PARAMETER INTEGRITY CHECK")

try:
    import yaml
    with open('config/etf_families.yaml') as f:
        config = yaml.safe_load(f)

    # Verify frozen parameters
    frozen_params = {
        'adx_entry': {'equity_sviluppati': 22, 'mercati_emergenti': 22},
        'rsi_entry_low': {'equity_sviluppati': 45},
        'rsi_entry_high': {'equity_sviluppati': 58},
    }

    all_ok = True
    for param, families_check in frozen_params.items():
        for family, expected_val in families_check.items():
            if family not in config['families']:
                print(f"   ⚠️  Family {family} non trovata")
                continue

            actual_val = config['families'][family].get(param)
            if actual_val != expected_val:
                all_ok = False
                report['alerts'].append(f"FROZEN PARAM MODIFIED: {family}.{param} = {actual_val} (expected {expected_val})")
                print(f"   ❌ {family}.{param}: {actual_val} (expected {expected_val})")
            else:
                print(f"   ✅ {param}: OK")

    report['checks']['parameter_integrity'] = '✅ PASS' if all_ok else '❌ FAIL'
    if not all_ok:
        report['status'] = 'FAIL'

except Exception as e:
    report['checks']['parameter_integrity'] = f'ERROR: {str(e)}'
    print(f"   ❌ Errore: {e}")

# ============================================================================
# CHECK 4: L0/L1 DISTRIBUTION SANITY
# ============================================================================
print("\n4️⃣ L0/L1 DISTRIBUTION SANITY")

try:
    conn = db._get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM etf_l1_tracking")
        l1_count = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM etf_l0_tracking")
        l0_count = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM etf_price_history GROUP BY isin HAVING COUNT(*) > 0")
        total_etfs = len(cur.fetchall())

        l1_ratio = (l1_count / total_etfs * 100) if total_etfs > 0 else 0
        l0_ratio = (l0_count / total_etfs * 100) if total_etfs > 0 else 0

        l1_ok = 0 <= l1_ratio <= 10  # 0-10% in L1 è normal
        l0_ok = 0 <= l0_ratio <= 5   # 0-5% in L0 è normal
        check_pass = l1_ok and l0_ok

        report['checks']['distribution'] = {
            'total_etfs': total_etfs,
            'l1_count': l1_count,
            'l1_ratio': f"{l1_ratio:.1f}%",
            'l0_count': l0_count,
            'l0_ratio': f"{l0_ratio:.1f}%",
            'status': '✅ PASS' if check_pass else '⚠️  WARNING'
        }

        print(f"   Total ETFs: {total_etfs}")
        print(f"   L1: {l1_count} ({l1_ratio:.1f}%)")
        print(f"   L0: {l0_count} ({l0_ratio:.1f}%)")

        if not check_pass:
            report['alerts'].append(f"Abnormal distribution: L1={l1_ratio:.1f}% (max 10%), L0={l0_ratio:.1f}% (max 5%)")

        conn.close()

except Exception as e:
    report['checks']['distribution'] = f'ERROR: {str(e)}'
    print(f"   ❌ Errore: {e}")

# ============================================================================
# CHECK 5: SYSTEM UPTIME & ERROR RATE
# ============================================================================
print("\n5️⃣ SYSTEM UPTIME & ERROR RATE")

try:
    # Check if monitor ran in last 48 hours
    conn = db._get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT MAX(date) FROM etf_price_history
        """)
        last_update = cur.fetchone()[0]
        conn.close()

        if last_update:
            last_update_dt = datetime.strptime(str(last_update), '%Y-%m-%d')
            hours_ago = (datetime.now() - last_update_dt).total_seconds() / 3600

            uptime_ok = hours_ago < 48
            status = '✅ PASS' if uptime_ok else '❌ FAIL'

            report['checks']['uptime'] = {
                'last_update': str(last_update),
                'hours_ago': f"{hours_ago:.1f}",
                'status': status
            }

            print(f"   Last update: {last_update} ({hours_ago:.1f}h ago) {status}")

            if not uptime_ok:
                report['status'] = 'FAIL'
                report['alerts'].append(f"Monitor not run in 48h (last: {hours_ago:.1f}h ago)")

except Exception as e:
    report['checks']['uptime'] = f'ERROR: {str(e)}'
    print(f"   ❌ Errore: {e}")

# ============================================================================
# FINAL REPORT
# ============================================================================
print("\n" + "=" * 70)
print(f"📋 VALIDATION RESULT: {report['status']}")
print("=" * 70)

if report['alerts']:
    print(f"\n⚠️  ALERTS ({len(report['alerts'])}):")
    for alert in report['alerts']:
        print(f"   • {alert}")

# Save report
report_file = f"data/weekly_validation_{datetime.now().strftime('%Y%m%d')}.json"
with open(report_file, 'w') as f:
    json.dump(report, f, indent=2)

print(f"\n✅ Report saved: {report_file}")
print(f"\n📅 Next check: {(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d 09:00 CEST')}")

sys.exit(0 if report['status'] == 'PASS' else 1)
