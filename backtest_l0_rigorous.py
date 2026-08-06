#!/usr/bin/env python3
"""
Rigorous L0 Backtest — Como L1
- Uses real SL/TP calculation (calculate_sl_suggerito_l0, calculate_tp_suggerito_l0)
- 3 years of data, all 240 ETFs
- Shows: winners/losers, P&L 5k/10k, annualized returns, SL/TP distribution
"""
import yfinance as yf
import pandas as pd
import numpy as np
import yaml
from datetime import datetime, timedelta
import sys

print("🚀 L0 RIGOROUS BACKTEST — Calculated SL/TP (Like L1)")
print("=" * 80)

# Load YAML families
with open('config/etf_families.yaml') as f:
    config = yaml.safe_load(f)
families = config['families']

# Load ETF list
try:
    etf_list = pd.read_excel('etf_monitoraggio.xlsx', sheet_name='ETF')
    print(f"📊 Caricati {len(etf_list)} ETF")
except Exception as e:
    print(f"❌ Errore Excel: {e}")
    sys.exit(1)

def calculate_sl_suggerito_l0(entry_price, current_price, days_held, family_params):
    """
    Calculate suggested SL for L0 (from code)
    Based on current profit and days held
    """
    if entry_price <= 0:
        return entry_price * 0.95

    current_gain_pct = (current_price - entry_price) / entry_price * 100 if entry_price > 0 else 0

    # Trailing SL logic from code
    if current_gain_pct < 2:
        sl = entry_price * 0.98  # Base: 2% below entry
    elif current_gain_pct < 5:
        sl = entry_price * 1.01  # Move to breakeven
    else:
        # Protect half the gain
        sl = entry_price + (current_price - entry_price) * 0.5

    return max(sl, entry_price * 0.90)  # Min: 10% stop loss

def calculate_tp_suggerito_l0(entry_price, family_params):
    """
    Calculate suggested TP for L0 (fixed per family)
    """
    tp_pct = family_params.get('l0_take_profit_pct', 0.16)
    return entry_price * (1 + tp_pct)

all_trades = []
family_stats = {}

# Process each ETF
for idx, row in etf_list.iterrows():
    ticker = row.get('Ticker', '')
    if not ticker:
        continue

    categoria = str(row.get('Categoria', '')).lower()

    # Determine family
    family_name = None
    for f_name in families.keys():
        if f_name in categoria or categoria in f_name:
            family_name = f_name
            break
    if not family_name:
        family_name = 'equity_sviluppati'

    if family_name not in family_stats:
        family_stats[family_name] = []

    p = families[family_name]
    dd_threshold = p.get('l0_entry', {}).get('dd_threshold', 0.065)
    rsi_max = p.get('l0_entry', {}).get('rsi_max', 45)
    recovery_min_pct = p.get('l0_entry', {}).get('recovery_min_pct', 0.003)

    try:
        data = yf.download(ticker, period='3y', interval='1d', progress=False)
        if data is None or len(data) < 200:
            continue

        close = data['Close'].values.flatten()

        # Calculate RSI
        delta = np.diff(close)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = pd.Series(gain).rolling(14).mean().values
        avg_loss = pd.Series(loss).rolling(14).mean().values
        rs = avg_gain / (avg_loss + 1e-10)
        rsi_vals = 100 - (100 / (1 + rs))

        # L0 trades
        for idx_trade in range(100, len(close) - 50):
            peak = np.max(close[max(0, idx_trade-90):idx_trade+1])
            curr = close[idx_trade]
            dd = (peak - curr) / peak if peak > 0 else 0

            rsi_curr = rsi_vals[idx_trade] if not np.isnan(rsi_vals[idx_trade]) else 50

            # L0 entry condition
            if dd >= dd_threshold and rsi_curr < rsi_max:
                # Check recovery
                recovery_found = False
                for recovery_idx in range(idx_trade + 1, min(idx_trade + 20, len(close))):
                    price_chg = (close[recovery_idx] - curr) / curr if curr > 0 else 0
                    if price_chg >= recovery_min_pct:
                        recovery_found = True
                        break

                if recovery_found:
                    # Entry confirmed
                    entry_price = curr
                    tp_target = calculate_tp_suggerito_l0(entry_price, p)

                    # Simulate exit with daily SL calculation
                    trade_result = None
                    exit_date = idx_trade

                    for exit_idx in range(idx_trade + 1, min(idx_trade + 150, len(close))):
                        exit_price = close[exit_idx]
                        days_held = exit_idx - idx_trade

                        # Calculate SL for this day
                        sl_suggerito = calculate_sl_suggerito_l0(entry_price, exit_price, days_held, p)

                        # Check exit conditions
                        if exit_price >= tp_target:
                            # TP hit
                            pct_gain = (tp_target - entry_price) / entry_price * 100
                            trade_result = {
                                'ticker': ticker,
                                'family': family_name,
                                'entry_price': entry_price,
                                'exit_price': tp_target,
                                'pct_gain': pct_gain,
                                'days_held': days_held,
                                'exit_type': 'TP',
                                'sl_suggerito': sl_suggerito,
                                'tp_suggerito': tp_target,
                                'win': 1,
                            }
                            exit_date = exit_idx
                            break
                        elif exit_price <= sl_suggerito:
                            # SL hit
                            pct_loss = (sl_suggerito - entry_price) / entry_price * 100
                            trade_result = {
                                'ticker': ticker,
                                'family': family_name,
                                'entry_price': entry_price,
                                'exit_price': sl_suggerito,
                                'pct_gain': pct_loss,
                                'days_held': days_held,
                                'exit_type': 'SL',
                                'sl_suggerito': sl_suggerito,
                                'tp_suggerito': tp_target,
                                'win': 0,
                            }
                            exit_date = exit_idx
                            break

                    # If no exit after 150 days, close at market
                    if trade_result is None:
                        exit_price = close[min(idx_trade + 149, len(close) - 1)]
                        days_held = min(150, len(close) - 1 - idx_trade)
                        pct_gain = (exit_price - entry_price) / entry_price * 100
                        trade_result = {
                            'ticker': ticker,
                            'family': family_name,
                            'entry_price': entry_price,
                            'exit_price': exit_price,
                            'pct_gain': pct_gain,
                            'days_held': days_held,
                            'exit_type': 'TIMEOUT',
                            'sl_suggerito': sl_suggerito,
                            'tp_suggerito': tp_target,
                            'win': 1 if pct_gain > 0 else 0,
                        }

                    if trade_result:
                        all_trades.append(trade_result)
                        family_stats[family_name].append(trade_result)

    except Exception as e:
        continue

    if (idx + 1) % 50 == 0:
        print(f"  [{idx + 1}/{len(etf_list)}] {len(all_trades)} L0 trades")

print(f"\n✅ Backtest completato: {len(all_trades)} L0 trades totali")
print("\n" + "=" * 80)

if not all_trades:
    print("⚠️ Nessun trade trovato")
    sys.exit(0)

df = pd.DataFrame(all_trades)

# ============================================================================
# ANALYSIS (Like L1)
# ============================================================================
print("\n📊 L0 BACKTEST RESULTS — 3 Years (2023-08 → 2026-08)")
print("=" * 80)

total_trades = len(df)
winners = df[df['win'] == 1]
losers = df[df['win'] == 0]
win_count = len(winners)
loss_count = len(losers)
wr_pct = (win_count / total_trades * 100) if total_trades > 0 else 0

print(f"\n📈 OVERALL:")
print(f"   Total trades: {total_trades}")
print(f"   ✅ Winners: {win_count} ({wr_pct:.1f}%)")
print(f"   ❌ Losers: {loss_count} ({100-wr_pct:.1f}%)")

# P&L Analysis
avg_gain_winners = winners['pct_gain'].mean() if len(winners) > 0 else 0
avg_loss_losers = losers['pct_gain'].mean() if len(losers) > 0 else 0
total_pct = df['pct_gain'].sum()
avg_trade_pct = df['pct_gain'].mean()
payoff_ratio = abs(avg_gain_winners / (abs(avg_loss_losers) + 0.01))

print(f"\n💰 P&L METRICS:")
print(f"   Avg gain (winners): {avg_gain_winners:+.2f}%")
print(f"   Avg loss (losers): {avg_loss_losers:+.2f}%")
print(f"   Payoff ratio: {payoff_ratio:.2f}x")
print(f"   Avg trade: {avg_trade_pct:+.2f}%")

# Annual P&L
pnl_5k = avg_trade_pct / 100 * 5000 * total_trades / (total_trades / (365/3))  # Annualized
pnl_10k = avg_trade_pct / 100 * 10000 * total_trades / (total_trades / (365/3))
annual_return_pct = (total_trades / (365/3)) * avg_trade_pct

print(f"\n📅 ANNUALIZED (assuming {total_trades / (365/3):.1f} trades/year):")
print(f"   P&L @ 5k€/trade: €{pnl_5k:,.0f} ({pnl_5k/5000:.1f}%)")
print(f"   P&L @ 10k€/trade: €{pnl_10k:,.0f} ({pnl_10k/10000:.1f}%)")
print(f"   Annual return: {annual_return_pct:+.1f}%")

# Exit Type Distribution
tp_count = len(df[df['exit_type'] == 'TP'])
sl_count = len(df[df['exit_type'] == 'SL'])
timeout_count = len(df[df['exit_type'] == 'TIMEOUT'])

print(f"\n🎯 EXIT DISTRIBUTION:")
print(f"   TP (Take Profit): {tp_count} ({tp_count/total_trades*100:.1f}%)")
print(f"   SL (Stop Loss): {sl_count} ({sl_count/total_trades*100:.1f}%)")
print(f"   Timeout (150d): {timeout_count} ({timeout_count/total_trades*100:.1f}%)")

# Holding period
avg_holding = df['days_held'].mean()
median_holding = df['days_held'].median()
holding_winners = winners['days_held'].mean() if len(winners) > 0 else 0
holding_losers = losers['days_held'].mean() if len(losers) > 0 else 0

print(f"\n📅 HOLDING PERIOD:")
print(f"   Average: {avg_holding:.0f} days")
print(f"   Median: {median_holding:.0f} days")
print(f"   Winners: {holding_winners:.0f} days")
print(f"   Losers: {holding_losers:.0f} days")

# Per-family stats
print(f"\n👥 PERFORMANCE PER FAMIGLIA:")
print(f"{'Famiglia':<30} {'Trades':>8} {'WR':>8} {'Avg %':>10} {'TP':>8} {'SL':>8}")
print("-" * 80)

for fam in sorted(family_stats.keys()):
    trades_fam = family_stats[fam]
    if len(trades_fam) < 5:
        continue

    df_fam = pd.DataFrame(trades_fam)
    wr_fam = (df_fam['win'].sum() / len(df_fam) * 100) if len(df_fam) > 0 else 0
    avg_fam = df_fam['pct_gain'].mean()
    tp_fam = len(df_fam[df_fam['exit_type'] == 'TP'])
    sl_fam = len(df_fam[df_fam['exit_type'] == 'SL'])

    print(f"{fam:<30} {len(df_fam):>8} {wr_fam:>7.1f}% {avg_fam:>9.2f}% {tp_fam:>8} {sl_fam:>8}")

print("\n" + "=" * 80)
print(f"✅ L0 RIGOROUS BACKTEST COMPLETE")
print(f"   {total_trades} trades over 3 years")
print(f"   Win Rate: {wr_pct:.1f}%")
print(f"   Payoff: {payoff_ratio:.2f}x")
print(f"   Annual P&L (10k€): €{pnl_10k:,.0f}")
