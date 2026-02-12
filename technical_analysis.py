"""
technical_analysis.py - Analisi tecnica per ETF (solo Close)
=============================================================
Indicatori basati solo sul prezzo di chiusura (Close):
- EMA 13 (Exponential Moving Average veloce)
- SMA 50 (Simple Moving Average lenta)
- RSI 14 (Relative Strength Index)
- MACD (Moving Average Convergence Divergence - conferma momentum)
- Bollinger Band Width (misura volatilita'/forza trend)

Logica BUY (tutte e 5 le condizioni):
1. Prezzo > EMA13 e Prezzo > SMA50 per 3+ giorni
2. EMA13 > SMA50 (golden cross)
3. RSI tra 55 e 65
4. MACD positivo e crescente (conferma momentum)
5. Bollinger Band Width in espansione (trend forte)

Logica SELL:
1. Prezzo < EMA13 e Prezzo < SMA50 per 3+ giorni
2. EMA13 < SMA50 (death cross)
3. RSI > 75 o RSI < 25
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict


class ETFTechnicalAnalyzer:
    """Analisi tecnica per ETF basata solo su prezzi Close"""

    def __init__(self, config: dict = None):
        self.config = config or {}

        # Medie mobili
        self.ema_fast_period = self.config.get('ema_fast_period', 13)
        self.sma_slow_period = self.config.get('sma_slow_period', 50)

        # RSI
        self.rsi_period = self.config.get('rsi_period', 14)
        self.rsi_buy_low = self.config.get('rsi_buy_low', 55)
        self.rsi_buy_high = self.config.get('rsi_buy_high', 65)
        self.rsi_overbought = self.config.get('rsi_overbought', 75)
        self.rsi_oversold = self.config.get('rsi_oversold', 25)

        # MACD
        self.macd_fast = self.config.get('macd_fast', 12)
        self.macd_slow = self.config.get('macd_slow', 26)
        self.macd_signal = self.config.get('macd_signal', 9)

        # Bollinger Bands
        self.bb_period = self.config.get('bb_period', 20)
        self.bb_std = self.config.get('bb_std', 2)

        # Giorni sopra MA per conferma
        self.days_above_ma = self.config.get('days_above_ma', 3)

        # Filtro Pullback: distanza max da EMA13 per BUY diretto
        self.pullback_max_distance = self.config.get('pullback_max_distance', 5.0)  # 5%
        self.pullback_limit_offset = self.config.get('pullback_limit_offset', 2.0)  # EMA13 + 2%

    def calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """Calcola Exponential Moving Average"""
        return prices.ewm(span=period, adjust=False).mean()

    def calculate_sma(self, prices: pd.Series, period: int) -> pd.Series:
        """Calcola Simple Moving Average"""
        return prices.rolling(window=period).mean()

    def calculate_rsi(self, prices: pd.Series, period: int = None) -> pd.Series:
        """Calcola Relative Strength Index (0-100)"""
        period = period or self.rsi_period
        delta = prices.diff()

        gains = delta.where(delta > 0, 0)
        losses = (-delta).where(delta < 0, 0)

        avg_gain = gains.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = losses.ewm(com=period - 1, min_periods=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_macd(self, prices: pd.Series) -> Dict:
        """
        Calcola MACD (Moving Average Convergence Divergence).

        Returns:
            Dict con 'macd_line', 'signal_line', 'histogram' (pd.Series)
        """
        ema_fast = prices.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = prices.ewm(span=self.macd_slow, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return {
            'macd_line': macd_line,
            'signal_line': signal_line,
            'histogram': histogram
        }

    def calculate_bollinger_bands(self, prices: pd.Series) -> Dict:
        """
        Calcola Bollinger Bands e Band Width.

        Returns:
            Dict con 'upper', 'middle', 'lower', 'width', 'pct_b' (pd.Series)
        """
        middle = prices.rolling(window=self.bb_period).mean()
        std = prices.rolling(window=self.bb_period).std()

        upper = middle + (std * self.bb_std)
        lower = middle - (std * self.bb_std)

        # Band Width: (upper - lower) / middle * 100
        width = pd.Series(0.0, index=prices.index)
        mask = middle > 0
        width[mask] = (upper[mask] - lower[mask]) / middle[mask] * 100

        # %B: posizione del prezzo rispetto alle bande (0=lower, 1=upper)
        band_range = upper - lower
        pct_b = pd.Series(0.5, index=prices.index)
        mask = band_range > 0
        pct_b[mask] = (prices[mask] - lower[mask]) / band_range[mask]

        return {
            'upper': upper,
            'middle': middle,
            'lower': lower,
            'width': width,
            'pct_b': pct_b
        }

    def count_days_above(self, prices: pd.Series, ma: pd.Series, max_days: int = 10) -> int:
        """Conta giorni consecutivi con prezzo sopra la media mobile"""
        if len(prices) < 2 or len(ma) < 2:
            return 0

        count = 0
        for i in range(1, min(max_days + 1, len(prices))):
            idx = -i
            if len(prices) >= abs(idx) and len(ma) >= abs(idx):
                price = prices.iloc[idx]
                ma_val = ma.iloc[idx]
                if pd.notna(ma_val) and price > ma_val:
                    count += 1
                else:
                    break
            else:
                break
        return count

    def count_days_below(self, prices: pd.Series, ma: pd.Series, max_days: int = 10) -> int:
        """Conta giorni consecutivi con prezzo sotto la media mobile"""
        if len(prices) < 2 or len(ma) < 2:
            return 0

        count = 0
        for i in range(1, min(max_days + 1, len(prices))):
            idx = -i
            if len(prices) >= abs(idx) and len(ma) >= abs(idx):
                price = prices.iloc[idx]
                ma_val = ma.iloc[idx]
                if pd.notna(ma_val) and price < ma_val:
                    count += 1
                else:
                    break
            else:
                break
        return count

    def detect_crossover(self, ema_fast: pd.Series, sma_slow: pd.Series) -> str:
        """
        Rileva incrocio tra EMA veloce e SMA lenta.

        Returns:
            'golden_cross', 'death_cross' o 'neutral'
        """
        if len(ema_fast) < 2 or len(sma_slow) < 2:
            return 'neutral'

        ema_current = ema_fast.iloc[-1]
        sma_current = sma_slow.iloc[-1]

        if pd.isna(ema_current) or pd.isna(sma_current):
            return 'neutral'

        if ema_current > sma_current:
            return 'golden_cross'
        elif ema_current < sma_current:
            return 'death_cross'
        return 'neutral'

    def analyze_etf(self, close_df: pd.DataFrame, level: int = 3) -> Dict:
        """
        Analisi tecnica completa di un ETF.

        Args:
            close_df: DataFrame con almeno colonna 'Close'
            level: Livello attuale dell'ETF (1, 2, 3)

        Returns:
            Dizionario con tutti gli indicatori e segnali
        """
        min_data = self.sma_slow_period + 5  # ~55 giorni

        if len(close_df) < min_data:
            close_price = float(close_df['Close'].iloc[-1]) if len(close_df) > 0 else None
            return {
                'current_price': close_price,
                'ema13': None,
                'sma50': None,
                'rsi': None,
                'macd': None,
                'macd_signal': None,
                'macd_histogram': None,
                'bb_width': None,
                'bb_pct_b': None,
                'crossover': 'neutral',
                'days_above_ema': 0,
                'days_above_sma': 0,
                'days_below_ema': 0,
                'days_below_sma': 0,
                'final_signal': 'HOLD',
                'signal_strength': 0,
                'buy_conditions': {},
                'sell_conditions': {},
                'suggested_level': level,
                'level_change': False,
                'level_reason': f'Dati insufficienti: {len(close_df)}/{min_data} giorni',
                'pct_change_1d': None,
                'pct_change_1w': None,
                'pct_change_1m': None,
                'data_status': 'insufficient'
            }

        close = close_df['Close'].astype(float)
        current_price = float(close.iloc[-1])

        # === VARIAZIONI PERCENTUALI ===
        pct_1d = round((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100, 2) if len(close) >= 2 else None
        pct_1w = round((close.iloc[-1] - close.iloc[-6]) / close.iloc[-6] * 100, 2) if len(close) >= 6 else None
        pct_1m = round((close.iloc[-1] - close.iloc[-22]) / close.iloc[-22] * 100, 2) if len(close) >= 22 else None

        # === CALCOLO INDICATORI ===
        ema13 = self.calculate_ema(close, self.ema_fast_period)
        sma50 = self.calculate_sma(close, self.sma_slow_period)
        rsi = self.calculate_rsi(close)
        macd_data = self.calculate_macd(close)
        bb_data = self.calculate_bollinger_bands(close)

        ema13_current = float(ema13.iloc[-1]) if pd.notna(ema13.iloc[-1]) else None
        sma50_current = float(sma50.iloc[-1]) if pd.notna(sma50.iloc[-1]) else None
        rsi_current = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else None

        macd_current = float(macd_data['macd_line'].iloc[-1]) if pd.notna(macd_data['macd_line'].iloc[-1]) else None
        macd_signal_current = float(macd_data['signal_line'].iloc[-1]) if pd.notna(macd_data['signal_line'].iloc[-1]) else None
        macd_hist_current = float(macd_data['histogram'].iloc[-1]) if pd.notna(macd_data['histogram'].iloc[-1]) else None
        macd_hist_prev = float(macd_data['histogram'].iloc[-2]) if len(macd_data['histogram']) >= 2 and pd.notna(macd_data['histogram'].iloc[-2]) else None

        bb_width_current = float(bb_data['width'].iloc[-1]) if pd.notna(bb_data['width'].iloc[-1]) else None
        bb_width_prev = float(bb_data['width'].iloc[-2]) if len(bb_data['width']) >= 2 and pd.notna(bb_data['width'].iloc[-2]) else None
        bb_pct_b_current = float(bb_data['pct_b'].iloc[-1]) if pd.notna(bb_data['pct_b'].iloc[-1]) else None

        # Crossover EMA/SMA
        crossover = self.detect_crossover(ema13, sma50)

        # Giorni sopra/sotto MA
        days_above_ema = self.count_days_above(close, ema13)
        days_above_sma = self.count_days_above(close, sma50)
        days_below_ema = self.count_days_below(close, ema13)
        days_below_sma = self.count_days_below(close, sma50)

        # === CONDIZIONI BUY (tutte e 5 devono essere vere) ===

        # 1. Prezzo > EMA13 e SMA50 per 3+ giorni
        buy_cond_1 = (days_above_ema >= self.days_above_ma and
                      days_above_sma >= self.days_above_ma)

        # 2. EMA13 > SMA50 (golden cross)
        buy_cond_2 = crossover == 'golden_cross'

        # 3. RSI tra 55 e 65 (zona ottimale)
        buy_cond_3 = (rsi_current is not None and
                      self.rsi_buy_low <= rsi_current <= self.rsi_buy_high)

        # 4. MACD positivo e crescente (conferma momentum)
        buy_cond_4 = (macd_hist_current is not None and
                      macd_hist_prev is not None and
                      macd_hist_current > 0 and
                      macd_hist_current > macd_hist_prev)

        # 5. Bollinger Band Width in espansione (trend forte)
        buy_cond_5 = (bb_width_current is not None and
                      bb_width_prev is not None and
                      bb_width_current > bb_width_prev)

        buy_conditions = {
            'price_above_ma_3days': buy_cond_1,
            'golden_cross': buy_cond_2,
            'rsi_optimal': buy_cond_3,
            'macd_positive_rising': buy_cond_4,
            'bb_width_expanding': buy_cond_5
        }
        buy_count = sum(buy_conditions.values())

        # === CONDIZIONI SELL ===

        # 1. Prezzo < EMA13 e SMA50 per 3+ giorni
        sell_cond_1 = (days_below_ema >= self.days_above_ma and
                       days_below_sma >= self.days_above_ma)

        # 2. EMA13 < SMA50 (death cross)
        sell_cond_2 = crossover == 'death_cross'

        # 3. RSI > 75 (overbought) o RSI < 25 (oversold)
        sell_cond_3 = (rsi_current is not None and
                       (rsi_current > self.rsi_overbought or
                        rsi_current < self.rsi_oversold))

        sell_conditions = {
            'price_below_ma_3days': sell_cond_1,
            'death_cross': sell_cond_2,
            'rsi_extreme': sell_cond_3
        }
        sell_count = sum(sell_conditions.values())

        # === FILTRO PULLBACK ===
        # Distanza % del prezzo dalla EMA13
        distance_from_ema = ((current_price - ema13_current) / ema13_current * 100) if ema13_current and ema13_current > 0 else 0.0
        pullback_active = False
        limit_order_price = None

        # === SEGNALE FINALE ===
        if buy_count == 5:
            if distance_from_ema > self.pullback_max_distance:
                # Pullback: prezzo troppo lontano da EMA13, segnale sospeso
                final_signal = 'PULLBACK'
                signal_strength = 5
                pullback_active = True
                # Prezzo limit order suggerito: EMA13 + 2%
                limit_order_price = round(ema13_current * (1 + self.pullback_limit_offset / 100), 4) if ema13_current else None
            else:
                final_signal = 'BUY'
                signal_strength = 5
        elif sell_count >= 2:
            final_signal = 'SELL'
            signal_strength = sell_count
        elif buy_count >= 3:
            final_signal = 'HOLD'
            signal_strength = buy_count
        else:
            final_signal = 'HOLD'
            signal_strength = 0

        # === LIVELLO SUGGERITO ===
        level_suggestion = self._suggest_level(
            buy_conditions, sell_conditions, buy_count,
            crossover, rsi_current, level, pullback_active
        )

        return {
            'current_price': round(current_price, 4),
            'ema13': round(ema13_current, 4) if ema13_current else None,
            'sma50': round(sma50_current, 4) if sma50_current else None,
            'rsi': round(rsi_current, 2) if rsi_current else None,
            'macd': round(macd_current, 4) if macd_current else None,
            'macd_signal': round(macd_signal_current, 4) if macd_signal_current else None,
            'macd_histogram': round(macd_hist_current, 4) if macd_hist_current else None,
            'bb_width': round(bb_width_current, 2) if bb_width_current else None,
            'bb_pct_b': round(bb_pct_b_current, 2) if bb_pct_b_current else None,
            'crossover': crossover,
            'days_above_ema': days_above_ema,
            'days_above_sma': days_above_sma,
            'days_below_ema': days_below_ema,
            'days_below_sma': days_below_sma,
            'buy_conditions': buy_conditions,
            'buy_count': buy_count,
            'sell_conditions': sell_conditions,
            'sell_count': sell_count,
            'final_signal': final_signal,
            'signal_strength': signal_strength,
            'suggested_level': level_suggestion['suggested_level'],
            'level_change': level_suggestion['level_change'],
            'level_reason': level_suggestion['reason'],
            'pct_change_1d': pct_1d,
            'pct_change_1w': pct_1w,
            'pct_change_1m': pct_1m,
            'distance_from_ema': round(distance_from_ema, 2),
            'pullback_active': pullback_active,
            'limit_order_price': limit_order_price,
            'data_status': 'ok',
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M')
        }

    def _suggest_level(self, buy_conditions: dict, sell_conditions: dict,
                       buy_count: int, crossover: str, rsi: float,
                       current_level: int, pullback_active: bool = False) -> Dict:
        """
        Suggerisce il livello appropriato per un ETF.

        - L1 (BUY Alert): 5/5 condizioni + distanza EMA13 < 5%
        - L1 (PULLBACK): 5/5 condizioni ma distanza EMA13 > 5%
        - L2 (Watchlist): EMA13 > SMA50 oppure RSI > 50
        - L3 (Universe): Monitoraggio passivo
        """
        if buy_count == 5:
            suggested = 1
            if pullback_active:
                reason = 'PULLBACK: 5/5 condizioni OK ma prezzo troppo distante da EMA13 (>5%). Attendere ritracciamento.'
            else:
                reason = 'BUY ALERT: Tutte le 5 condizioni soddisfatte, prezzo vicino a EMA13'
        elif crossover == 'golden_cross' or (rsi is not None and rsi > 50):
            suggested = 2
            parts = []
            if crossover == 'golden_cross':
                parts.append('EMA13 > SMA50')
            if rsi is not None and rsi > 50:
                parts.append(f'RSI {rsi:.0f} > 50')
            reason = f'Watchlist: {", ".join(parts)} ({buy_count}/5 condizioni BUY)'
        else:
            suggested = 3
            reason = 'Monitoraggio passivo'

        return {
            'suggested_level': suggested,
            'level_change': suggested != current_level,
            'reason': reason
        }


def test_analyzer():
    """Test dell'analizzatore tecnico ETF (solo Close)"""
    analyzer = ETFTechnicalAnalyzer()

    # Genera dati di test (100 giorni, solo Close)
    np.random.seed(42)
    n = 100
    dates = pd.date_range(end=datetime.now(), periods=n, freq='D')
    close = pd.Series(100 + np.cumsum(np.random.randn(n) * 2), index=dates)

    close_df = pd.DataFrame({'Close': close}, index=dates)

    result = analyzer.analyze_etf(close_df, level=3)

    print("=" * 60)
    print("TEST ETF TECHNICAL ANALYZER (Close-only)")
    print("=" * 60)
    print(f"Prezzo:    {result['current_price']:.2f}")
    print(f"EMA13:     {result['ema13']:.2f}" if result['ema13'] else "EMA13: N/A")
    print(f"SMA50:     {result['sma50']:.2f}" if result['sma50'] else "SMA50: N/A")
    print(f"RSI:       {result['rsi']:.1f}" if result['rsi'] else "RSI: N/A")
    print(f"MACD:      {result['macd']:.4f}" if result['macd'] else "MACD: N/A")
    print(f"MACD Hist: {result['macd_histogram']:.4f}" if result['macd_histogram'] else "MACD Hist: N/A")
    print(f"BB Width:  {result['bb_width']:.2f}" if result['bb_width'] else "BB Width: N/A")
    print(f"BB %B:     {result['bb_pct_b']:.2f}" if result['bb_pct_b'] else "BB %B: N/A")
    print(f"Crossover: {result['crossover']}")
    print(f"\nCondizioni BUY: {result['buy_count']}/5")
    for k, v in result['buy_conditions'].items():
        print(f"  {'V' if v else 'X'} {k}")
    print(f"\nSegnale: {result['final_signal']} (forza: {result['signal_strength']})")
    print(f"Livello suggerito: L{result['suggested_level']}")
    print(f"Motivo: {result['level_reason']}")


if __name__ == "__main__":
    test_analyzer()
