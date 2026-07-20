"""
Unit tests for L0/L1/L2 engines (v4.0)
======================================
Tests for new regime filter, 7/7 conditions, and readiness score.
"""

import pytest
import pandas as pd
import numpy as np
from technical_analysis import ETFTechnicalAnalyzer


class TestL0RegimeFilter:
    """L0 Regime filter: detect bear market (slow) vs flash crash (fast)."""

    @pytest.fixture
    def analyzer(self):
        return ETFTechnicalAnalyzer(famiglia='equity_sviluppati')

    def test_l0_slow_path_below_sma200(self, analyzer):
        """Slow path: asset below SMA200 for min_days triggers regime."""
        prices = pd.Series([100, 99, 98, 97, 96, 95, 94] * 3)  # 21 giorni, tutti sotto 95
        sma200 = 95.0
        result = analyzer.l0_detect_regime_filter(prices, sma200, atr_60=0.5, volume_20ma=1000)
        assert result['regime_suitable']
        assert result['regime_type'] in ['slow_bear', 'fast_crash']
        assert result['days_below_sma200'] > 0

    def test_l0_fast_path_flash_crash(self, analyzer):
        """Fast path: extreme drawdown normalized on ATR triggers regime."""
        # Simula flash crash: picco a 100, crolla a 92 in 2 giorni
        prices = pd.Series([100] * 10 + [96, 92])
        sma200 = 98.0
        atr_60 = 0.5  # Bassa volatilità storica → drawdown è evidente
        result = analyzer.l0_detect_regime_filter(prices, sma200, atr_60, volume_20ma=1000)
        # Drawdown = (100-92)/100 = 8%, normalized su ATR → high zscore
        # Con zscore_threshold=4.0, potrebbe essere fast_crash

    def test_l0_no_regime(self, analyzer):
        """No regime: prezzo sopra SMA200 da pochi giorni."""
        prices = pd.Series([100] * 25)  # Stabile sopra 100
        sma200 = 95.0
        result = analyzer.l0_detect_regime_filter(prices, sma200, atr_60=0.5, volume_20ma=1000)
        assert not result['regime_suitable']
        assert result['regime_type'] == 'none'

    def test_l0_invalidate_on_breach(self):
        """L0 invalidates if current_price < trigger_low_price."""
        analyzer = ETFTechnicalAnalyzer(famiglia='equity_sviluppati')
        # Trigger at 90, current at 89 → should invalidate
        is_invalidated = analyzer.l0_invalidate_if_breach(89.0, 90.0)
        assert is_invalidated
        # Trigger at 90, current at 90.5 → should remain valid
        is_invalidated = analyzer.l0_invalidate_if_breach(90.5, 90.0)
        assert not is_invalidated


class TestL1SevenConditions:
    """L1 7/7 conditions: all conditions must be true."""

    @pytest.fixture
    def analyzer(self):
        return ETFTechnicalAnalyzer(famiglia='equity_sviluppati')

    def test_l1_all_conditions_true(self, analyzer):
        """All 7 conditions true → L1 entry approved."""
        prices = pd.Series(np.linspace(100, 105, 30))  # Trend up
        high_series = prices + 0.5
        low_series = prices - 0.5

        result = analyzer.l1_check_7_conditions(
            prices=prices,
            ema20=103.0,
            sma50=101.0,
            rsi_14=50.0,  # In optimal range [45, 55]
            adx_14=25.0,  # Above entry threshold 22
            macd_histogram=0.5,  # Positive
            macd_histogram_prev=0.3,  # Rising
            volume=50000.0,
            atr_14=0.8,
            high_series=high_series,
            low_series=low_series,
            volume_20ma=40000.0,
            days_above_ema20=5  # Above threshold
        )
        assert result['entry_l1']
        assert result['level'] == 1
        assert result['confidence'] == 1.0

    def test_l1_gate_a_fails(self, analyzer):
        """Gate A (price > EMA20) fails → block entry."""
        prices = pd.Series([100] * 20)
        result = analyzer.l1_check_7_conditions(
            prices=prices,
            ema20=105.0,  # Price below EMA20
            sma50=101.0,
            rsi_14=50.0,
            adx_14=25.0,
            macd_histogram=0.5,
            macd_histogram_prev=0.3,
            volume=50000.0,
            atr_14=0.8,
            high_series=prices,
            low_series=prices,
            volume_20ma=40000.0,
            days_above_ema20=5
        )
        assert not result['entry_l1']
        assert result['level'] == 2

    def test_l1_space_residuo_resistance_method(self, analyzer):
        """Space residuo: resistance method → space adequate."""
        prices = pd.Series([100] * 10)
        high_series = pd.Series([105] * 10)  # Resistance at 105
        low_series = prices

        space = analyzer.l1_check_space_residuo_minimo(
            current_price=100.0,
            high_series=high_series,
            low_series=low_series,
            atr_14=0.5,
            volume=50000.0,
            volume_20ma=40000.0
        )
        assert space['valid']
        assert space['method'] == 'resistance'
        assert space['space_pct'] >= 0.03  # min_reward_pct


class TestL2ReadinessScore:
    """L2 Readiness score: 0-100 gauge for watchlist candidates."""

    @pytest.fixture
    def analyzer(self):
        return ETFTechnicalAnalyzer(famiglia='equity_sviluppati')

    def test_l2_score_calculation(self, analyzer):
        """L2 score reflects proximity to 6 L1 conditions."""
        prices = pd.Series(np.linspace(100, 105, 30))
        score = analyzer.l2_calculate_readiness_score(
            prices=prices,
            ema20=103.0,
            rsi_14=48.0,  # In optimal range
            adx_14=20.0,  # Rising
            volume=45000.0,
            volume_20ma=40000.0,
            days_above_ema20=4
        )
        assert 0 <= score <= 100
        assert score > 50  # Should be reasonable score for good setup

    def test_l2_score_0_on_invalid_data(self, analyzer):
        """L2 score returns 0 on invalid data."""
        score = analyzer.l2_calculate_readiness_score(
            prices=None,
            ema20=None,
            rsi_14=None,
            adx_14=None,
            volume=None,
            volume_20ma=None,
            days_above_ema20=0
        )
        assert score == 0.0

    def test_l2_score_ranges(self, analyzer):
        """L2 score ranges properly: 0-100."""
        prices = pd.Series([100] * 20)

        # Worst case
        score_low = analyzer.l2_calculate_readiness_score(
            prices=prices,
            ema20=100.0,
            rsi_14=20.0,  # Far from optimal
            adx_14=5.0,   # Very weak
            volume=10000.0,
            volume_20ma=50000.0,
            days_above_ema20=0
        )
        assert score_low < 30  # Should be low

        # Best case
        prices_up = pd.Series(np.linspace(100, 110, 30))
        score_high = analyzer.l2_calculate_readiness_score(
            prices=prices_up,
            ema20=105.0,
            rsi_14=50.0,  # Optimal
            adx_14=25.0,  # Strong
            volume=60000.0,
            volume_20ma=40000.0,
            days_above_ema20=5
        )
        assert score_high > 60  # Should be decent


class TestL0L1L2Integration:
    """Integration tests: regime → conditions → score flow."""

    @pytest.fixture
    def analyzer(self):
        return ETFTechnicalAnalyzer(famiglia='equity_sviluppati')

    def test_bullish_setup_progression(self, analyzer):
        """Bullish ETF: no L0 regime, L1 conditions true, L2 score high."""
        prices = pd.Series(np.linspace(100, 110, 30))
        high_series = prices + 1.0
        low_series = prices - 0.5
        sma200 = 95.0

        # L0: no regime (above SMA200)
        l0_regime = analyzer.l0_detect_regime_filter(
            prices, sma200, atr_60=0.8, volume_20ma=40000.0
        )
        assert not l0_regime['regime_suitable']

        # L1: conditions true
        l1_result = analyzer.l1_check_7_conditions(
            prices=prices, ema20=105.0, sma50=102.0,
            rsi_14=50.0, adx_14=25.0, macd_histogram=0.5,
            macd_histogram_prev=0.3, volume=50000.0, atr_14=0.8,
            high_series=high_series, low_series=low_series,
            volume_20ma=40000.0, days_above_ema20=5
        )
        assert l1_result['entry_l1']

        # L2: score high
        l2_score = analyzer.l2_calculate_readiness_score(
            prices=prices, ema20=105.0, rsi_14=50.0, adx_14=25.0,
            volume=50000.0, volume_20ma=40000.0, days_above_ema20=5
        )
        assert l2_score > 70  # Watchlist candidate

    def test_recovery_setup_l0_entry(self, analyzer):
        """Bearish recovery: L0 regime detected, L0 conditions trigger."""
        prices = pd.Series([100] * 5 + [95, 90, 88, 87, 86])  # Crash
        sma200 = 92.0

        # L0: regime detected (below SMA200)
        l0_regime = analyzer.l0_detect_regime_filter(
            prices, sma200, atr_60=0.5, volume_20ma=40000.0
        )
        assert l0_regime['regime_suitable']
        assert l0_regime['days_below_sma200'] >= 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
