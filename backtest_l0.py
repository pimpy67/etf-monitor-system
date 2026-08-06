#!/usr/bin/env python3
import yfinance as yf
import pandas as pd
import numpy as np

ETF_SAMPLES = {'equity_sviluppati': 'SWDA.L'}

for family, ticker in ETF_SAMPLES.items():
    print(f"\n📊 {family} ({ticker})")
    
    data = yf.download(ticker, period='3y', interval='1d', progress=False)
    if data is None or len(data) < 100:
        print(f"  ⚠️  Insufficient")
        continue

    close = data['Close'].values.flatten()
    
    # Simple RSI
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    
    avg_gain = pd.Series(gain).rolling(14).mean().values
    avg_loss = pd.Series(loss).rolling(14).mean().values
    rs = avg_gain / (avg_loss + 1e-10)
    rsi_vals = 100 - (100 / (1 + rs))

    trades = []
    idx = 30

    while idx < len(close) - 20:
        peak = np.max(close[max(0, idx-90):idx+1])
        curr = close[idx]
        dd = (peak - curr) / peak

        r_val = rsi_vals[idx] if not np.isnan(rsi_vals[idx]) else 50

        if dd >= 0.065 and r_val < 45:
            tp = curr * 1.16
            sl = curr * 0.98

            for eidx in range(idx + 1, min(idx + 100, len(close))):
                p = close[eidx]
                if p >= tp or p <= sl:
                    trades.append((p - curr) / curr)
                    idx = eidx
                    break
            else:
                idx += 1
        else:
            idx += 1

    if trades:
        trades = np.array(trades)
        wr = np.sum(trades > 0) / len(trades)
        pnl = np.mean(trades) * 10000
        print(f"  ✅ {len(trades)} | WR {wr*100:.0f}% | P&L €{pnl:.0f}")
    else:
        print(f"  No trades")

print("\n" + "="*60)
