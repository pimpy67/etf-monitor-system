"""
technical_analysis.py - Analisi tecnica per ETF
=================================================
Indicatori specifici per ETF (piu' volatili dei fondi):
- EMA 13 (Exponential Moving Average veloce)
- SMA 50 (Simple Moving Average lenta)
- RSI 14 (Relative Strength Index)
- ADX 14 (Average Directional Index - forza del trend)
- Volume Ratio (volume vs media 20gg)

Logica BUY (tutte e 5 le condizioni):
1. Prezzo > EMA13 e Prezzo > SMA50 per 3+ giorni
2. EMA13 > SMA50 (golden cross)
3. RSI tra 55 e 65
4. Volume > 1.5x media 20 giorni
5. ADX > 25

Logica SELL:
1. Prezzo < EMA13 e Prezzo < SMA50 per 3+ giorni
2. EMA13 < SMA50 (death cross)
3. RSI > 75 o RSI < 25
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Tuple


class ETFTechnicalAnalyzer:
    """Analisi tecnica per ETF con EMA, ADX, Volume"""

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

        # ADX
        self.adx_period = self.config.get('adx_period', 14)
        self.adx_threshold = self.config.get('adx_threshold', 25)

        # Volume
        self.volume_multiplier = self.config.get('volume_multiplier', 1.5)
        self.volume_avg_period = self.config.get('volume_avg_period', 20)

        # Giorni sopra MA per conferma
        self.days_above_ma = self.config.get('days_above_ma', 3)

    def calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """
        Calcola Exponential Moving Average

        Args:
            prices: Serie di prezzi
            period: Periodo EMA

        Returns:
            Serie con valori EMA
        """
        return prices.ewm(span=period, adjust=False).mean()

    def calculate_sma(self, prices: pd.Series, period: int) -> pd.Series:
        """
        Calcola Simple Moving Average

        Args:
            prices: Serie di prezzi
            period: Periodo SMA

        Returns:
            Serie con valori SMA
        """
        return prices.rolling(window=period).mean()

    def calculate_rsi(self, prices: pd.Series, period: int = None) -> pd.Series:
        """
        Calcola Relative Strength Index

        Args:
            prices: Serie di prezzi
            period: Periodo RSI (default: self.rsi_period)

        Returns:
            Serie con valori RSI (0-100)
        """
        period = period or self.rsi_period
        delta = prices.diff()

        gains = delta.where(delta > 0, 0)
        losses = (-delta).where(delta < 0, 0)

        avg_gain = gains.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = losses.ewm(com=period - 1, min_periods=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_adx(self, high: pd.Series, low: pd.Series,
                      close: pd.Series, period: int = None) -> pd.Series:
        """
        Calcola Average Directional Index (ADX)
        Misura la forza del trend (non la direzione).
        ADX > 25 = trend forte, ADX < 20 = trend debole/laterale.

        Args:
            high: Serie prezzi massimi
            low: Serie prezzi minimi
            close: Serie prezzi chiusura
            period: Periodo ADX (default: self.adx_period)

        Returns:
            Serie con valori ADX
        """
        period = period or self.adx_period

        # True Range
        high_low = high - low
        high_close_prev = (high - close.shift(1)).abs()
        low_close_prev = (low - close.shift(1)).abs()
        tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)

        # Directional Movement
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low

        plus_dm = pd.Series(0.0, index=high.index)
        minus_dm = pd.Series(0.0, index=high.index)

        # +DM: up_move > 0 AND up_move > down_move
        plus_dm = np.where((up_move > 0) & (up_move > down_move), up_move, 0)
        plus_dm = pd.Series(plus_dm, index=high.index)

        # -DM: down_move > 0 AND down_move > up_move
        minus_dm = np.where((down_move > 0) & (down_move > up_move), down_move, 0)
        minus_dm = pd.Series(minus_dm, index=high.index)

        # Smoothed TR, +DM, -DM (EMA)
        atr = tr.ewm(span=period, adjust=False).mean()
        plus_di = 100 * plus_dm.ewm(span=period, adjust=False).mean() / atr
        minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / atr

        # DX e ADX
        di_sum = plus_di + minus_di
        di_diff = (plus_di - minus_di).abs()

        # Evita divisione per zero
        dx = pd.Series(0.0, index=high.index)
        mask = di_sum > 0
        dx[mask] = 100 * di_diff[mask] / di_sum[mask]

        adx = dx.ewm(span=period, adjust=False).mean()
        return adx

    def calculate_volume_ratio(self, volume: pd.Series, period: int = None) -> float:
        """
        Calcola il rapporto tra volume corrente e media volume

        Args:
            volume: Serie dei volumi
            period: Periodo media volume (default: self.volume_avg_period)

        Returns:
            Rapporto volume corrente / media (es. 1.5 = 50% sopra media)
        """
        period = period or self.volume_avg_period

        if len(volume) < period + 1:
            return 1.0  # Dati insufficienti

        avg_vol = volume.iloc[-(period + 1):-1].mean()
        current_vol = volume.iloc[-1]

        if avg_vol > 0:
            return round(current_vol / avg_vol, 2)
        return 1.0

    def count_days_above(self, prices: pd.Series, ma: pd.Series, max_days: int = 10) -> int:
        """
        Conta giorni consecutivi con prezzo sopra la media mobile

        Args:
            prices: Serie di prezzi
            ma: Serie della media mobile
            max_days: Massimo giorni da controllare

        Returns:
            Numero di giorni consecutivi sopra MA
        """
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
        Rileva incrocio tra EMA veloce e SMA lenta

        Returns:
            'golden_cross' se EMA > SMA (rialzista)
            'death_cross' se EMA < SMA (ribassista)
            'neutral' se nessun incrocio significativo
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

    def analyze_etf(self, ohlcv_df: pd.DataFrame, level: int = 3) -> Dict:
        """
        Analisi tecnica completa di un ETF

        Args:
            ohlcv_df: DataFrame con colonne Open, High, Low, Close, Volume
            level: Livello attuale dell'ETF (1, 2, 3)

        Returns:
            Dizionario con tutti gli indicatori e segnali
        """
        min_data = max(self.sma_slow_period, self.adx_period) + 5

        if len(ohlcv_df) < min_data:
            close_price = float(ohlcv_df['Close'].iloc[-1]) if len(ohlcv_df) > 0 else None
            return {
                'current_price': close_price,
                'ema13': None,
                'sma50': None,
                'rsi': None,
                'adx': None,
                'volume_ratio': None,
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
                'level_reason': f'Dati insufficienti: {len(ohlcv_df)}/{min_data} giorni',
                'data_status': 'insufficient'
            }

        close = ohlcv_df['Close'].astype(float)
        high = ohlcv_df['High'].astype(float)
        low = ohlcv_df['Low'].astype(float)
        volume = ohlcv_df['Volume'].astype(float)

        current_price = float(close.iloc[-1])

        # Calcola indicatori
        ema13 = self.calculate_ema(close, self.ema_fast_period)
        sma50 = self.calculate_sma(close, self.sma_slow_period)
        rsi = self.calculate_rsi(close)
        adx = self.calculate_adx(high, low, close)
        vol_ratio = self.calculate_volume_ratio(volume)

        ema13_current = float(ema13.iloc[-1]) if pd.notna(ema13.iloc[-1]) else None
        sma50_current = float(sma50.iloc[-1]) if pd.notna(sma50.iloc[-1]) else None
        rsi_current = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else None
        adx_current = float(adx.iloc[-1]) if pd.notna(adx.iloc[-1]) else None

        # Crossover EMA/SMA
        crossover = self.detect_crossover(ema13, sma50)

        # Giorni sopra/sotto MA
        days_above_ema = self.count_days_above(close, ema13)
        days_above_sma = self.count_days_above(close, sma50)
        days_below_ema = self.count_days_below(close, ema13)
        days_below_sma = self.count_days_below(close, sma50)

        # === CONDIZIONI BUY (tutte e 5 devono essere vere) ===
        buy_cond_1 = (days_above_ema >= self.days_above_ma and
                      days_above_sma >= self.days_above_ma)  # Prezzo > EMA13 & SMA50 per 3+ gg
        buy_cond_2 = crossover == 'golden_cross'             # EMA13 > SMA50
        buy_cond_3 = (rsi_current is not None and
                      self.rsi_buy_low <= rsi_current <= self.rsi_buy_high)  # RSI 55-65
        buy_cond_4 = vol_ratio >= self.volume_multiplier     # Volume > 1.5x media
        buy_cond_5 = (adx_current is not None and
                      adx_current >= self.adx_threshold)     # ADX > 25

        buy_conditions = {
            'price_above_ma_3days': buy_cond_1,
            'golden_cross': buy_cond_2,
            'rsi_optimal': buy_cond_3,
            'volume_high': buy_cond_4,
            'adx_strong': buy_cond_5
        }
        buy_count = sum(buy_conditions.values())

        # === CONDIZIONI SELL ===
        sell_cond_1 = (days_below_ema >= self.days_above_ma and
                       days_below_sma >= self.days_above_ma)  # Prezzo < EMA13 & SMA50 per 3+ gg
        sell_cond_2 = crossover == 'death_cross'              # EMA13 < SMA50
        sell_cond_3 = (rsi_current is not None and
                       (rsi_current > self.rsi_overbought or
                        rsi_current < self.rsi_oversold))     # RSI > 75 o < 25

        sell_conditions = {
            'price_below_ma_3days': sell_cond_1,
            'death_cross': sell_cond_2,
            'rsi_extreme': sell_cond_3
        }
        sell_count = sum(sell_conditions.values())

        # === SEGNALE FINALE ===
        if buy_count == 5:
            final_signal = 'BUY'
            signal_strength = 5
        elif sell_count >= 2:
            final_signal = 'SELL'
            signal_strength = sell_count
        elif buy_count >= 3:
            # BUY parziale (3-4 condizioni su 5)
            final_signal = 'HOLD'
            signal_strength = buy_count
        else:
            final_signal = 'HOLD'
            signal_strength = 0

        # === LIVELLO SUGGERITO ===
        level_suggestion = self._suggest_level(
            buy_conditions, sell_conditions, buy_count,
            crossover, rsi_current, level
        )

        return {
            'current_price': round(current_price, 4),
            'ema13': round(ema13_current, 4) if ema13_current else None,
            'sma50': round(sma50_current, 4) if sma50_current else None,
            'rsi': round(rsi_current, 2) if rsi_current else None,
            'adx': round(adx_current, 2) if adx_current else None,
            'volume_ratio': vol_ratio,
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
            'data_status': 'ok',
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M')
        }

    def _suggest_level(self, buy_conditions: dict, sell_conditions: dict,
                       buy_count: int, crossover: str, rsi: float,
                       current_level: int) -> Dict:
        """
        Suggerisce il livello appropriato per un ETF

        Logica:
        - L3 (Universe): Tutti gli ETF monitorati
        - L2 (Watchlist): EMA13 > SMA50 oppure RSI > 50
        - L1 (BUY Alert): Tutte e 5 le condizioni BUY soddisfatte
        """
        if buy_count == 5:
            suggested = 1
            reason = 'BUY ALERT: Tutte le 5 condizioni soddisfatte'
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
    """Test dell'analizzatore tecnico ETF"""
    analyzer = ETFTechnicalAnalyzer()

    # Genera dati OHLCV di test (100 giorni)
    np.random.seed(42)
    n = 100
    dates = pd.date_range(end=datetime.now(), periods=n, freq='D')

    close = pd.Series(100 + np.cumsum(np.random.randn(n) * 2), index=dates)
    high = close + np.abs(np.random.randn(n))
    low = close - np.abs(np.random.randn(n))
    open_p = close + np.random.randn(n) * 0.5
    volume = pd.Series(np.random.randint(100000, 1000000, n), index=dates)

    ohlcv = pd.DataFrame({
        'Open': open_p,
        'High': high,
        'Low': low,
        'Close': close,
        'Volume': volume
    }, index=dates)

    result = analyzer.analyze_etf(ohlcv, level=3)

    print("=" * 60)
    print("TEST ETF TECHNICAL ANALYZER")
    print("=" * 60)
    print(f"Prezzo: {result['current_price']:.2f}")
    print(f"EMA13:  {result['ema13']:.2f}" if result['ema13'] else "EMA13: N/A")
    print(f"SMA50:  {result['sma50']:.2f}" if result['sma50'] else "SMA50: N/A")
    print(f"RSI:    {result['rsi']:.1f}" if result['rsi'] else "RSI: N/A")
    print(f"ADX:    {result['adx']:.1f}" if result['adx'] else "ADX: N/A")
    print(f"Vol Ratio: {result['volume_ratio']:.2f}")
    print(f"Crossover: {result['crossover']}")
    print(f"\nCondizioni BUY: {result['buy_count']}/5")
    for k, v in result['buy_conditions'].items():
        print(f"  {'V' if v else 'X'} {k}")
    print(f"\nSegnale: {result['final_signal']} (forza: {result['signal_strength']})")
    print(f"Livello suggerito: L{result['suggested_level']}")
    print(f"Motivo: {result['level_reason']}")


if __name__ == "__main__":
    test_analyzer()
