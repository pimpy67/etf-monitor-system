#!/usr/bin/env python3
"""
Feature Extraction L0 — Backtest 3 anni su 240 ETF
Estrae i trade L0 e analizza i parametri discriminanti
"""
import yfinance as yf
import pandas as pd
import numpy as np
import yaml
from datetime import datetime, timedelta
import sys

# Load YAML families
with open('config/etf_families.yaml') as f:
    config = yaml.safe_load(f)
families = config['families']

print("🚀 L0 Feature Extraction — Backtest 3 anni")
print("=" * 70)

# Load ETF list from Excel
try:
    etf_list = pd.read_excel('etf_monitoraggio.xlsx', sheet_name='ETF')
    print(f"📊 Caricati {len(etf_list)} ETF da Excel")
except Exception as e:
    print(f"❌ Errore caricamento Excel: {e}")
    sys.exit(1)

all_l0_trades = []
family_counts = {}

# Process each ETF
total_etfs = len(etf_list)
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
        family_name = 'equity_sviluppati'  # Default
    
    if family_name not in family_counts:
        family_counts[family_name] = {'total': 0, 'trades': 0}
    family_counts[family_name]['total'] += 1
    
    # Get parameters
    p = families[family_name]
    dd_threshold = p.get('l0_entry', {}).get('dd_threshold', 0.065)
    rsi_max = p.get('l0_entry', {}).get('rsi_max', 45)
    recovery_min_pct = p.get('l0_entry', {}).get('recovery_min_pct', 0.003)
    tp_pct = p.get('l0_take_profit_pct', 0.16)
    sl_base = p.get('sl_initial_pct', 0.05)
    
    try:
        # Fetch data
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
        
        # Simple L0 entry detection
        for idx_trade in range(100, len(close) - 50):
            peak = np.max(close[max(0, idx_trade-90):idx_trade+1])
            curr = close[idx_trade]
            dd = (peak - curr) / peak if peak > 0 else 0
            
            rsi_curr = rsi_vals[idx_trade] if not np.isnan(rsi_vals[idx_trade]) else 50
            
            # L0 entry condition
            if dd >= dd_threshold and rsi_curr < rsi_max:
                # Check recovery signal
                recovery_found = False
                for recovery_idx in range(idx_trade + 1, min(idx_trade + 20, len(close))):
                    price_chg = (close[recovery_idx] - curr) / curr if curr > 0 else 0
                    if price_chg >= recovery_min_pct:
                        recovery_found = True
                        break
                
                if recovery_found:
                    # Calculate SL and TP
                    sl = curr * (1 - sl_base)
                    tp = curr * (1 + tp_pct)
                    
                    # Simulate exit
                    for exit_idx in range(idx_trade + 1, min(idx_trade + 150, len(close))):
                        exit_price = close[exit_idx]
                        if exit_price >= tp:
                            pct_gain = (tp - curr) / curr * 100
                            all_l0_trades.append({
                                'ticker': ticker,
                                'family': family_name,
                                'entry_price': curr,
                                'entry_date': idx_trade,
                                'exit_price': exit_price,
                                'exit_date': exit_idx,
                                'pct_gain': pct_gain,
                                'dd_entry': dd * 100,
                                'rsi_entry': rsi_curr,
                                'days_held': exit_idx - idx_trade,
                                'exit_type': 'TP',
                                'win': 1 if pct_gain > 0 else 0,
                            })
                            family_counts[family_name]['trades'] += 1
                            break
                        elif exit_price <= sl:
                            pct_loss = (exit_price - curr) / curr * 100
                            all_l0_trades.append({
                                'ticker': ticker,
                                'family': family_name,
                                'entry_price': curr,
                                'entry_date': idx_trade,
                                'exit_price': exit_price,
                                'exit_date': exit_idx,
                                'pct_gain': pct_loss,
                                'dd_entry': dd * 100,
                                'rsi_entry': rsi_curr,
                                'days_held': exit_idx - idx_trade,
                                'exit_type': 'SL',
                                'win': 0,
                            })
                            family_counts[family_name]['trades'] += 1
                            break
    
    except Exception as e:
        continue
    
    if (idx + 1) % 50 == 0:
        print(f"  [{idx + 1}/{total_etfs}] {len(all_l0_trades)} L0 trades trovati")

print(f"\n✅ Backtest completato: {len(all_l0_trades)} L0 trades totali")
print("\n" + "=" * 70)

if not all_l0_trades:
    print("⚠️ Nessun L0 trade trovato")
    sys.exit(0)

# Convert to DataFrame
df = pd.DataFrame(all_l0_trades)

# Feature Extraction
print("\n📊 FEATURE EXTRACTION — L0 Discriminating Metrics")
print("=" * 70)

# Split winners/losers
winners = df[df['win'] == 1]
losers = df[df['win'] == 0]

print(f"\n✅ Trades vincenti: {len(winners)} ({len(winners)/len(df)*100:.1f}%)")
print(f"❌ Trades perdenti: {len(losers)} ({len(losers)/len(df)*100:.1f}%)")

# Metric 1: DD Entry (Drawdown al momento dell'ingresso)
dd_win_median = winners['dd_entry'].median() if len(winners) > 0 else 0
dd_loss_median = losers['dd_entry'].median() if len(losers) > 0 else 0
dd_gap = dd_loss_median - dd_win_median

print(f"\n1️⃣ Drawdown Entry (dd_threshold discriminant?)")
print(f"   Vincenti (mediana): {dd_win_median:.2f}%")
print(f"   Perdenti (mediana): {dd_loss_median:.2f}%")
print(f"   Gap: {dd_gap:+.2f}% {'✓ DISCRIMINANT' if abs(dd_gap) > 1 else '— non significativo'}")

# Metric 2: RSI Entry
rsi_win_median = winners['rsi_entry'].median() if len(winners) > 0 else 0
rsi_loss_median = losers['rsi_entry'].median() if len(losers) > 0 else 0
rsi_gap = rsi_loss_median - rsi_win_median

print(f"\n2️⃣ RSI Entry (ipervenduto threshold)")
print(f"   Vincenti (mediana): {rsi_win_median:.1f}")
print(f"   Perdenti (mediana): {rsi_loss_median:.1f}")
print(f"   Gap: {rsi_gap:+.1f} {'✓ DISCRIMINANT' if abs(rsi_gap) > 2 else '— piccolo'}")

# Metric 3: Days Held (Tempo mantenimento)
days_win_median = winners['days_held'].median() if len(winners) > 0 else 0
days_loss_median = losers['days_held'].median() if len(losers) > 0 else 0
days_gap = days_loss_median - days_win_median

print(f"\n3️⃣ Days Held (holding period)")
print(f"   Vincenti (mediana): {days_win_median:.0f} giorni")
print(f"   Perdenti (mediana): {days_loss_median:.0f} giorni")
print(f"   Gap: {days_gap:+.0f} giorni {'✓ DISCRIMINANT' if abs(days_gap) > 5 else '— piccolo'}")

# Metric 4: Avg Gain/Loss
avg_gain_win = winners['pct_gain'].mean() if len(winners) > 0 else 0
avg_gain_loss = losers['pct_gain'].mean() if len(losers) > 0 else 0

print(f"\n4️⃣ Rendimento Medio")
print(f"   Vincenti (media): {avg_gain_win:+.2f}%")
print(f"   Perdenti (media): {avg_gain_loss:+.2f}%")
print(f"   Payoff ratio: {abs(avg_gain_win / (avg_gain_loss + 0.01)):.2f}x")

# Metric 5: Family Performance
print(f"\n5️⃣ Performance per Famiglia")
family_perf = df.groupby('family').agg({
    'win': ['sum', 'count', lambda x: x.sum() / len(x) * 100],
    'pct_gain': 'mean'
}).round(2)

print(family_perf.to_string())

print("\n" + "=" * 70)
print(f"✅ Feature Extraction completata")
print(f"📁 {len(all_l0_trades)} L0 trades analizzati")
print(f"📊 Win rate globale: {df['win'].sum() / len(df) * 100:.1f}%")
print(f"💰 P&L medio: {df['pct_gain'].mean():+.2f}%")
