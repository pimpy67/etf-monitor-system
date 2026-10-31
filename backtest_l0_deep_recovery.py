#!/usr/bin/env python3
"""
Backtest L0 Deep Recovery su 3 anni (2023-08 → 2026-08)
Misura FAST/SLOW/PRAGMATIC entry logic con exit SL/TP
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict
import yfinance as yf
import pandas as pd
import numpy as np

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Parametri L0 per famiglia (da YAML)
L0_FAMILIES = {
    'equity_sviluppati': {'dd_threshold': 0.065, 'rsi_max': 45, 'tp_pct': 0.16},
    'mercati_emergenti': {'dd_threshold': 0.065, 'rsi_max': 45, 'tp_pct': 0.18},
    'settoriali_growth': {'dd_threshold': 0.08, 'rsi_max': 50, 'tp_pct': 0.22},
    'settoriali_difensivi': {'dd_threshold': 0.055, 'rsi_max': 42, 'tp_pct': 0.10},
    'bond_governativi': {'dd_threshold': 0.04, 'rsi_max': 38, 'tp_pct': 0.06},
    'bond_corp_hy_em': {'dd_threshold': 0.05, 'rsi_max': 40, 'tp_pct': 0.08},
    'commodities': {'dd_threshold': 0.075, 'rsi_max': 45, 'tp_pct': 0.20},
    'oro_metalli_preziosi': {'dd_threshold': 0.065, 'rsi_max': 43, 'tp_pct': 0.16},
    'metalli_industriali': {'dd_threshold': 0.075, 'rsi_max': 45, 'tp_pct': 0.18},
    'real_estate_reit': {'dd_threshold': 0.065, 'rsi_max': 44, 'tp_pct': 0.13},
    'crypto_digital_assets': {'dd_threshold': 0.15, 'rsi_max': 30, 'tp_pct': 0.45},
    'leva_single_stock': {'dd_threshold': 0.10, 'rsi_max': 42, 'tp_pct': 0.30},
    'private_equity_buffer': {'dd_threshold': 0.065, 'rsi_max': 44, 'tp_pct': 0.12},
}

# ETF rappresentativi per famiglia
ETF_SAMPLES = {
    'equity_sviluppati': 'SWDA.L',
    'mercati_emergenti': 'EIMI.L',
    'settoriali_growth': 'SMOG.L',
    'settoriali_difensivi': 'XDSI.L',
    'bond_governativi': 'XGLE.L',
    'bond_corp_hy_em': 'IEAA.L',
    'commodities': 'CMOD.L',
    'oro_metalli_preziosi': 'IAUF.L',
    'metalli_industriali': None,  # Skip — scarsi dati
    'real_estate_reit': 'XREO.L',
    'crypto_digital_assets': 'BITC.L',
    'leva_single_stock': None,  # Skip — troppo volatile
    'private_equity_buffer': None,  # Skip — pochi dati
}

class L0Backtester:
    def __init__(self):
        self.results = defaultdict(list)
        self.trades = []

    def _fetch_data(self, ticker: str, period: str = '3y') -> pd.DataFrame:
        """Fetch OHLCV data da Yahoo Finance"""
        try:
            data = yf.download(ticker, period=period, interval='1d', progress=False)
            if data.empty:
                return None
            data = data.sort_index()
            return data
        except Exception as e:
            logger.warning(f"  ⚠️  Fetch {ticker} failed: {e}")
            return None

    def _rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Calcola RSI"""
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _sma(self, close: pd.Series, period: int) -> pd.Series:
        """Calcola SMA"""
        return close.rolling(window=period).mean()

    def _ema(self, close: pd.Series, period: int) -> pd.Series:
        """Calcola EMA"""
        return close.ewm(span=period, adjust=False).mean()

    def _atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Calcola ATR"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr

    def _detect_positive_divergence(self, close: pd.Series, rsi: pd.Series, lookback: int = 20) -> bool:
        """Divergenza rialzista: prezzo min ↓, RSI min ↑"""
        if len(close) < lookback:
            return False

        close_lookback = close.iloc[-lookback:]
        rsi_lookback = rsi.iloc[-lookback:]

        # Ultimi 2 minimi di prezzo
        min1_idx = close_lookback.iloc[:-5].idxmin()
        min2_idx = close_lookback.iloc[-5:].idxmin()

        if min1_idx >= min2_idx:  # min2 deve essere dopo min1
            return False

        min1_price = close.loc[min1_idx]
        min2_price = close.loc[min2_idx]
        min1_rsi = rsi.loc[min1_idx]
        min2_rsi = rsi.loc[min2_idx]

        # Divergenza: min2_price < min1_price AND min2_rsi > min1_rsi
        return min2_price < min1_price and min2_rsi > min1_rsi

    def _detect_recovery(self, close: pd.Series, rsi: pd.Series, recovery_min_pct: float = 0.01) -> bool:
        """Segnale di recupero: RSI > 40 O micro-breakout >= 1%"""
        if len(close) < 10:
            return False

        rsi_val = rsi.iloc[-1]
        if pd.isna(rsi_val) or rsi_val is None:
            return False

        rsi_recovery = rsi_val > 40

        # Micro-breakout su 10gg
        low_10d = close.iloc[-10:].min()
        recovery_pct = (close.iloc[-1] - low_10d) / low_10d if low_10d > 0 else 0
        micro_brk = recovery_pct >= recovery_min_pct

        return rsi_recovery or micro_brk

    def _simulate_l0_entry(self, close: pd.Series, rsi: pd.Series, family: str,
                          entry_idx: int) -> dict:
        """Simula ingresso L0 pragmatico per entry_idx"""
        params = L0_FAMILIES.get(family, {})
        dd_threshold = params.get('dd_threshold', 0.065)
        rsi_max = params.get('rsi_max', 45)
        tp_pct = params.get('tp_pct', 0.16)

        # Condizioni pragmatiche
        # 1. Drawdown
        peak_90d = close.iloc[max(0, entry_idx-90):entry_idx+1].max()
        current = close.iloc[entry_idx]
        dd_pct = (peak_90d - current) / peak_90d if peak_90d > 0 else 0
        cond1 = dd_pct >= dd_threshold

        # 2. RSI ipervenduto
        rsi_val = rsi.iloc[entry_idx]
        cond2 = pd.notna(rsi_val) and rsi_val < rsi_max

        # 3. Divergenza
        cond3 = self._detect_positive_divergence(close.iloc[:entry_idx+1],
                                                  rsi.iloc[:entry_idx+1],
                                                  lookback=20)

        # 4. Recovery signal
        cond4 = self._detect_recovery(close.iloc[:entry_idx+1],
                                      rsi.iloc[:entry_idx+1],
                                      recovery_min_pct=0.01)

        entry_ok = cond1 and cond2 and cond3 and cond4

        return {
            'entry_ok': entry_ok,
            'entry_price': current,
            'entry_date_idx': entry_idx,
            'dd_pct': dd_pct,
            'rsi': rsi_val if pd.notna(rsi_val) else None,
            'tp_target': current * (1 + tp_pct),
            'sl_initial': current * 0.98,  # SL minimo 2%
        }

    def _find_exit(self, close: pd.Series, rsi: pd.Series, entry_idx: int,
                   tp_target: float, sl_initial: float) -> dict:
        """Trova exit point (SL o TP) dopo entry_idx"""
        if entry_idx >= len(close) - 1:
            return {'exit_found': False}

        for exit_idx in range(entry_idx + 1, len(close)):
            price = close.iloc[exit_idx]
            rsi_val = rsi.iloc[exit_idx]

            # Uscita per trappola ribassista (RSI < 25)
            if pd.notna(rsi_val) and rsi_val < 25:
                return {
                    'exit_found': True,
                    'exit_idx': exit_idx,
                    'exit_price': price,
                    'exit_rule': 'trap_rsi_25',
                    'pnl_pct': (price - close.iloc[entry_idx]) / close.iloc[entry_idx]
                }

            # Uscita per SL
            if price <= sl_initial:
                return {
                    'exit_found': True,
                    'exit_idx': exit_idx,
                    'exit_price': price,
                    'exit_rule': 'sl_hit',
                    'pnl_pct': (price - close.iloc[entry_idx]) / close.iloc[entry_idx]
                }

            # Uscita per TP
            if price >= tp_target:
                return {
                    'exit_found': True,
                    'exit_idx': exit_idx,
                    'exit_price': price,
                    'exit_rule': 'tp_hit',
                    'pnl_pct': (price - close.iloc[entry_idx]) / close.iloc[entry_idx]
                }

        # Nessun exit nel periodo
        final_price = close.iloc[-1]
        return {
            'exit_found': False,
            'exit_idx': len(close) - 1,
            'exit_price': final_price,
            'exit_rule': 'end_of_data',
            'pnl_pct': (final_price - close.iloc[entry_idx]) / close.iloc[entry_idx]
        }

    def backtest_family(self, family: str, ticker: str) -> dict:
        """Backtest L0 per una famiglia"""
        logger.info(f"\n📊 Backtest {family} ({ticker})...")

        # Fetch dati
        data = self._fetch_data(ticker, period='3y')
        if data is None or len(data) < 100:
            logger.warning(f"  Insufficient data for {ticker}")
            return None

        close = data['Close'].dropna()
        rsi = self._rsi(close)

        trades = []
        entry_idx = 30  # Inizia da 30 giorni (warm-up per indicatori)

        while entry_idx < len(close) - 20:  # Leave 20 days for exit
            # Simula ingresso L0
            entry_result = self._simulate_l0_entry(close, rsi, family, entry_idx)

            if entry_result['entry_ok']:
                # Trova exit
                exit_result = self._find_exit(close, rsi, entry_idx,
                                              entry_result['tp_target'],
                                              entry_result['sl_initial'])

                if exit_result['exit_found']:
                    holding_days = exit_result['exit_idx'] - entry_idx
                    trade = {
                        'family': family,
                        'ticker': ticker,
                        'entry_idx': entry_idx,
                        'exit_idx': exit_result['exit_idx'],
                        'entry_price': entry_result['entry_price'],
                        'exit_price': exit_result['exit_price'],
                        'pnl_pct': exit_result['pnl_pct'],
                        'exit_rule': exit_result['exit_rule'],
                        'holding_days': holding_days,
                        'dd_at_entry': entry_result['dd_pct'],
                    }
                    trades.append(trade)

                    # Salta avanti dopo exit
                    entry_idx = exit_result['exit_idx'] + 1
                else:
                    entry_idx += 1
            else:
                entry_idx += 1

        # Calcola statistiche
        if not trades:
            logger.info(f"  ⚠️  No L0 trades generated")
            return {
                'family': family,
                'ticker': ticker,
                'trades': 0,
                'win_rate': 0,
                'avg_return': 0,
                'pnl_total': 0,
            }

        wins = len([t for t in trades if t['pnl_pct'] > 0])
        win_rate = wins / len(trades) if trades else 0
        avg_return = np.mean([t['pnl_pct'] for t in trades])
        pnl_total = sum([t['pnl_pct'] for t in trades]) / len(trades) * 10000  # Scaled to €10k

        logger.info(f"  ✅ {len(trades)} trades | WR: {win_rate*100:.1f}% | Avg: {avg_return*100:.2f}% | P&L €10k: €{pnl_total:.0f}")

        return {
            'family': family,
            'ticker': ticker,
            'trades': len(trades),
            'win_rate': win_rate,
            'avg_return': avg_return,
            'pnl_total': pnl_total,
            'trades_detail': trades,
        }

    def run(self):
        """Esegui backtest per tutte le famiglie"""
        logger.info("=" * 70)
        logger.info("🚀 L0 DEEP RECOVERY BACKTEST — 3 ANNI (2023-08 → 2026-08)")
        logger.info("=" * 70)

        all_results = []

        for family, ticker in ETF_SAMPLES.items():
            if ticker is None:
                logger.info(f"\n⏭️  Skipping {family} (no ETF sample)")
                continue

            result = self.backtest_family(family, ticker)
            if result:
                all_results.append(result)

        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("📈 SUMMARY — L0 BACKTEST RESULTS")
        logger.info("=" * 70)

        summary_data = []
        total_trades = 0
        total_wins = 0

        for r in all_results:
            summary_data.append({
                'Famiglia': r['family'],
                'Ticker': r['ticker'],
                'Trade': r['trades'],
                'WR %': f"{r['win_rate']*100:.1f}",
                'Avg %': f"{r['avg_return']*100:.2f}",
                'P&L €10k': f"€{r['pnl_total']:.0f}",
            })
            total_trades += r['trades']
            total_wins += int(r['trades'] * r['win_rate'])

        # Print table
        if summary_data:
            df_summary = pd.DataFrame(summary_data)
            logger.info("\n" + df_summary.to_string(index=False))

        # Overall stats
        overall_wr = total_wins / total_trades if total_trades > 0 else 0
        overall_pnl = sum([r['pnl_total'] for r in all_results]) / len(all_results) if all_results else 0

        logger.info("\n" + "-" * 70)
        logger.info(f"📊 OVERALL: {total_trades} trades | WR: {overall_wr*100:.1f}% | Avg P&L: €{overall_pnl:.0f}")
        logger.info("-" * 70)

        # Save detailed results
        output_file = '/tmp/l0_backtest_results.json'
        with open(output_file, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        logger.info(f"\n✅ Detailed results saved to {output_file}")

        return all_results

if __name__ == '__main__':
    backtester = L0Backtester()
    backtester.run()
