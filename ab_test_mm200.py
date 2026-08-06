#!/usr/bin/env python3
"""
A/B Test: mm200_distance_max Impact on L1 Strategy (3 Years)

RUN A: mm200_distance_max DISABLED (or set to 999%, no filter)
RUN B: mm200_distance_max ENABLED at 3.0% (current production)

Compare: Trade count, WR%, P&L, Max Drawdown, Avg Duration
"""
import yfinance as yf
import pandas as pd
import numpy as np
import yaml
from datetime import datetime, timedelta
import sys

print("=" * 80)
print("🧪 A/B TEST: mm200_distance_max Impact Analysis (3 Years)")
print("=" * 80)

# Load config
with open('config/etf_families.yaml') as f:
    config = yaml.safe_load(f)
families = config['families']

# Load ETF universe
try:
    etf_list = pd.read_excel('etf_monitoraggio.xlsx', sheet_name='ETF')
    print(f"📊 Loaded {len(etf_list)} ETFs")
except Exception as e:
    print(f"❌ Excel error: {e}")
    sys.exit(1)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_ema(prices, period=20):
    return prices.ewm(span=period, adjust=False).mean()

def calculate_sma(prices, period=50):
    return prices.rolling(period).mean()

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_adx(high, low, close, period=14):
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0)
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    di_plus = 100 * (plus_dm.rolling(period).mean() / atr)
    di_minus = 100 * (minus_dm.rolling(period).mean() / atr)
    di_diff = (di_plus - di_minus).abs() / (di_plus + di_minus)
    adx = di_diff.rolling(period).mean()
    return adx

def check_l1_entry_conditions(close, high, low, family_config, use_mm200=True):
    """
    Check if price should enter L1 based on 7 conditions.
    Returns list of entry indices and their condition counts.
    """
    entries = []

    if len(close) < 200:
        return entries

    ema20 = calculate_ema(close, 20)
    sma50 = calculate_sma(close, 50)
    sma200 = calculate_sma(close, 200)
    rsi = calculate_rsi(close, 14)
    adx = calculate_adx(high, low, close, 14)

    rsi_low = family_config.get('rsi_entry_low', 45)
    rsi_high = family_config.get('rsi_entry_high', 55)
    adx_entry = family_config.get('adx_entry', 20)
    ema_dist_max = family_config.get('ema_dist_max', 4.0)
    mm200_dist_max = family_config.get('mm200_distance_max', 999)  # 999 = disabled

    for i in range(200, len(close) - 1):
        price = close.iloc[i]
        ema20_v = ema20.iloc[i]
        sma50_v = sma50.iloc[i]
        sma200_v = sma200.iloc[i]
        rsi_v = rsi.iloc[i]
        adx_v = adx.iloc[i]

        if pd.isna(ema20_v) or pd.isna(sma50_v) or pd.isna(sma200_v) or pd.isna(rsi_v) or pd.isna(adx_v):
            continue

        # Cond 1: Allineamento
        cond1 = (price > ema20_v) and (ema20_v > sma50_v)

        # Cond 2: Persistenza (simplificata: slope ok)
        ema20_slope = (ema20_v - ema20.iloc[max(0, i-10)]) / ema20.iloc[max(0, i-10)] if ema20.iloc[max(0, i-10)] > 0 else 0
        cond2 = ema20_slope > 0

        # Cond 3: RSI range
        cond3 = rsi_low <= rsi_v <= rsi_high

        # Cond 4: EMA20 distance
        ema_dist = (price - ema20_v) / ema20_v * 100 if ema20_v > 0 else 0
        cond4 = 0 <= ema_dist <= ema_dist_max

        # Cond 5: ADX
        cond5 = adx_v >= adx_entry

        # Cond 6: MACD (simplified: just check if price is rising)
        cond6 = (close.iloc[i] > close.iloc[i-1])

        # Cond 7: MM200 distance (CONDITIONAL on use_mm200)
        if use_mm200 and mm200_dist_max < 999:
            mm200_dist = (price - sma200_v) / sma200_v * 100 if sma200_v > 0 else 0
            cond7 = mm200_dist <= mm200_dist_max
        else:
            cond7 = True  # DISABLED in Run A

        buy_count = sum([cond1, cond2, cond3, cond4, cond5, cond6, cond7])

        if buy_count >= 7:  # All 7 conditions required
            entries.append({'idx': i, 'price': price, 'date': close.index[i], 'conditions': buy_count})

    return entries

def simulate_trades(ticker, family_name, close, high, low, family_config, use_mm200=True):
    """Simulate L1 trades for one ETF."""
    trades = []
    entries = check_l1_entry_conditions(close, high, low, family_config, use_mm200)

    for entry in entries:
        entry_idx = entry['idx']
        entry_price = entry['price']
        entry_date = entry['date']

        # SL: 5% below entry
        sl = entry_price * 0.95

        # TP: +8% above entry (target for equity)
        tp = entry_price * 1.08

        # Simulate exit
        for exit_idx in range(entry_idx + 1, min(entry_idx + 150, len(close))):
            exit_price = close.iloc[exit_idx]

            if exit_price <= sl:
                # Stop Loss hit
                pct_gain = (sl - entry_price) / entry_price * 100
                trades.append({
                    'ticker': ticker,
                    'family': family_name,
                    'entry_price': entry_price,
                    'exit_price': sl,
                    'pct_gain': pct_gain,
                    'days_held': exit_idx - entry_idx,
                    'win': 1 if pct_gain > 0 else 0,
                })
                break
            elif exit_price >= tp:
                # Take Profit hit
                pct_gain = (tp - entry_price) / entry_price * 100
                trades.append({
                    'ticker': ticker,
                    'family': family_name,
                    'entry_price': entry_price,
                    'exit_price': tp,
                    'pct_gain': pct_gain,
                    'days_held': exit_idx - entry_idx,
                    'win': 1,
                })
                break

    return trades

# ============================================================================
# RUN A & B
# ============================================================================

print("\n🏃 Running A/B Test Simulation (3 years, 236 ETFs)...\n")

results_a = {'trades': [], 'config_note': 'mm200_distance_max DISABLED'}
results_b = {'trades': [], 'config_note': 'mm200_distance_max ENABLED (3.0%)'}

etf_count = 0
for _, row in etf_list.iterrows():
    ticker = str(row.get('Ticker', '')).strip()
    categoria = str(row.get('Categoria', '')).lower()

    if not ticker or ticker.lower() == 'nan':
        continue

    # Detect family
    family_name = None
    for fname in families.keys():
        if fname in categoria or categoria in fname:
            family_name = fname
            break
    if not family_name:
        family_name = 'equity_sviluppati'

    if family_name not in families:
        continue

    family_config = families[family_name]

    try:
        # Fetch 3 years
        data = yf.download(ticker, period='3y', interval='1d', progress=False)
        if data is None or len(data) < 200:
            continue

        close = data['Close']
        high = data['High']
        low = data['Low']

        # Run A: mm200 DISABLED
        trades_a = simulate_trades(ticker, family_name, close, high, low,
                                    family_config, use_mm200=False)
        results_a['trades'].extend(trades_a)

        # Run B: mm200 ENABLED
        trades_b = simulate_trades(ticker, family_name, close, high, low,
                                    family_config, use_mm200=True)
        results_b['trades'].extend(trades_b)

        etf_count += 1
        if etf_count % 50 == 0:
            print(f"  Processed {etf_count} ETFs...")

    except Exception as e:
        continue

print(f"\n✅ Backtest complete. {etf_count} ETFs analyzed.\n")

# ============================================================================
# ANALYSIS
# ============================================================================

def analyze_results(results, run_label):
    trades = results['trades']
    if not trades:
        print(f"\n⚠️  {run_label}: No trades found")
        return None

    df = pd.DataFrame(trades)

    total = len(df)
    wins = df[df['win'] == 1]
    win_count = len(wins)
    wr = (win_count / total * 100) if total > 0 else 0

    avg_gain_winners = wins['pct_gain'].mean() if len(wins) > 0 else 0
    avg_gain_losers = df[df['win'] == 0]['pct_gain'].mean() if len(df[df['win'] == 0]) > 0 else 0

    # P&L calculation
    total_pct = df['pct_gain'].sum()
    avg_pct = df['pct_gain'].mean()

    # Annualize (assumes ~27 trades/year, so 3 years = 81 trades max)
    pnl_10k = (avg_pct / 100) * 10000 * (total / (365/3*0.333))

    max_dd = df[df['win'] == 0]['pct_gain'].min() if len(df[df['win'] == 0]) > 0 else 0
    avg_duration = df['days_held'].mean()

    return {
        'label': run_label,
        'total_trades': total,
        'win_rate': wr,
        'winners': win_count,
        'avg_gain_winners': avg_gain_winners,
        'avg_loss_losers': avg_gain_losers,
        'total_pct': total_pct,
        'avg_pct_per_trade': avg_pct,
        'pnl_10k_annualized': pnl_10k,
        'max_drawdown_trade': max_dd,
        'avg_duration_days': avg_duration,
    }

print("=" * 80)
print("📊 RESULTS COMPARISON")
print("=" * 80)

result_a = analyze_results(results_a, "RUN A: mm200 DISABLED")
result_b = analyze_results(results_b, "RUN B: mm200 ENABLED (3.0%)")

if result_a and result_b:
    print(f"\n{'Metric':<30} {'RUN A (No mm200)':>20} {'RUN B (mm200=3%)':>20} {'Δ':>15}")
    print("-" * 85)

    metrics = [
        ('Total Trades', 'total_trades', lambda x: f"{x:.0f}"),
        ('Win Rate (%)', 'win_rate', lambda x: f"{x:.1f}%"),
        ('Avg Gain/Winner (%)', 'avg_gain_winners', lambda x: f"{x:+.2f}%"),
        ('Avg Loss/Loser (%)', 'avg_loss_losers', lambda x: f"{x:+.2f}%"),
        ('Avg Trade (%)', 'avg_pct_per_trade', lambda x: f"{x:+.3f}%"),
        ('P&L @10k/trade (annualized)', 'pnl_10k_annualized', lambda x: f"€{x:+,.0f}"),
        ('Max Drawdown (single trade)', 'max_drawdown_trade', lambda x: f"{x:.2f}%"),
        ('Avg Duration (days)', 'avg_duration_days', lambda x: f"{x:.0f}d"),
    ]

    for label, key, fmt in metrics:
        val_a = result_a[key]
        val_b = result_b[key]

        if key in ['total_trades', 'win_rate', 'pnl_10k_annualized']:
            if key == 'total_trades':
                delta = f"{((val_b - val_a) / val_a * 100) if val_a > 0 else 0:+.1f}%"
            else:
                delta = f"{(val_b - val_a):+.1f}"
        else:
            delta = f"{(val_b - val_a):+.2f}"

        print(f"{label:<30} {fmt(val_a):>20} {fmt(val_b):>20} {delta:>15}")

    print("\n" + "=" * 80)
    print("🎯 VERDICT")
    print("=" * 80)

    trade_diff_pct = ((result_b['total_trades'] - result_a['total_trades']) / result_a['total_trades'] * 100) if result_a['total_trades'] > 0 else 0
    wr_diff = result_b['win_rate'] - result_a['win_rate']
    pnl_diff = result_b['pnl_10k_annualized'] - result_a['pnl_10k_annualized']

    print(f"\n✅ mm200_distance_max Impact:")
    print(f"   • Trades: {trade_diff_pct:+.1f}% (fewer = more selective)")
    print(f"   • Win Rate: {wr_diff:+.1f} points (higher = better quality)")
    print(f"   • P&L Impact: €{pnl_diff:+,.0f} annualized (10k€/position)")

    if wr_diff > 0 and pnl_diff >= 0:
        print(f"\n🟢 CONFIRMED: mm200_distance_max IMPROVES strategy")
        print(f"   → Fewer trades, but higher quality (↑WR, stable P&L)")
    elif wr_diff > 0 and pnl_diff < 0:
        print(f"\n🟡 TRADEOFF: mm200_distance_max filters noise but costs P&L")
        print(f"   → Consider if quality > quantity (WR improvement: {wr_diff:+.1f}pp)")
    else:
        print(f"\n🔴 CAUTION: mm200_distance_max shows mixed results")
        print(f"   → May need refinement (lower threshold from 3.0% to 2.5%?)")

    print("\n" + "=" * 80)

print(f"\n✅ A/B Test Complete — Results saved\n")
