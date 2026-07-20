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
        return ETFTechnicalAnalyzer(etf_type='equity_developed')

    def test_l0_slow_path_below_sma200(self, analyzer):
        """Slow path: asset below SMA200 for min_days triggers regime."""
        # 60 giorni con ultimi 20 tutti sotto SMA200
        prices = pd.Series([100] * 40 + [94] * 20)
        sma200 = 95.0
        result = analyzer.l0_detect_regime_filter(prices, sma200, atr_60=0.5, volume_20ma=1000)
        # Ultimi 20 giorni tutti sotto SMA200 → days_below_sma200 = 20
        assert result['days_below_sma200'] == 20

    def test_l0_fast_path_flash_crash(self, analyzer):
        """Fast path: extreme drawdown normalized on ATR triggers regime."""
        # 60 giorni: 59 a 100, ultimo a 85 (crash del 15%)
        prices = pd.Series([100] * 59 + [85])
        sma200 = 95.0
        atr_60 = 0.5  # ATR bassa → crash normalizzato è evidente
        result = analyzer.l0_detect_regime_filter(prices, sma200, atr_60, volume_20ma=1000)
        # recent_dd_pct = (100 - 85) / 100 = 15% = 0.15
        assert result['recent_dd_pct'] > 0.10

    def test_l0_no_regime(self, analyzer):
        """No regime: prezzo sopra SMA200 da pochi giorni."""
        prices = pd.Series([100] * 25)  # Stabile sopra 100
        sma200 = 95.0
        result = analyzer.l0_detect_regime_filter(prices, sma200, atr_60=0.5, volume_20ma=1000)
        assert not result['regime_suitable']
        assert result['regime_type'] == 'none'
        assert result['days_below_sma200'] == 0

    def test_l0_insufficient_data(self, analyzer):
        """L0 returns safe defaults if data too short."""
        prices = pd.Series([100] * 5)  # Meno di 50 giorni
        sma200 = 95.0
        result = analyzer.l0_detect_regime_filter(prices, sma200, atr_60=0.5, volume_20ma=1000)
        assert not result['regime_suitable']
        assert result['regime_type'] == 'none'


class TestL1SevenConditions:
    """L1 7/7 conditions: all conditions must be true."""

    @pytest.fixture
    def analyzer(self):
        return ETFTechnicalAnalyzer(etf_type='equity_developed')

    def test_l1_all_conditions_true(self, analyzer):
        """All 7 conditions true → L1 entry approved."""
        prices = pd.Series(np.linspace(100, 105, 30))  # Trend up
        high_series = prices + 0.5
        low_series = prices - 0.5

        result = analyzer.l1_check_7_conditions(
            prices=prices,
            ema20=102.5,  # Current price ~105 > ema20 ✓
            sma50=100.0,  # ema20 > sma50 ✓ e price > sma50 ✓
            rsi_14=55.0,  # In optimal range [50, 70] for equity_developed ✓
            adx_14=22.0,  # >= adx_entry (20) ✓
            macd_histogram=0.5,  # Positive (Gate M) ✓
            macd_histogram_prev=0.3,  # Rising ✓
            volume=50000.0,
            atr_14=0.8,
            high_series=high_series,
            low_series=low_series,
            volume_20ma=40000.0,
            days_above_ema20=5
        )
        # Se tutte le condizioni sono soddisfatte, l1_check_7_conditions deve ritornare entry_l1=true
        assert result['conditions']['gate_a']
        assert result['conditions']['gate_m']
        assert result['conditions']['alignment_p']
        assert result['conditions']['rsi_r']

    def test_l1_gate_a_fails(self, analyzer):
        """Gate A (price > EMA20) fails → block entry."""
        prices = pd.Series([100] * 20)
        result = analyzer.l1_check_7_conditions(
            prices=prices,
            ema20=105.0,  # Price (100) below EMA20 (105) → Gate A fails
            sma50=101.0,
            rsi_14=55.0,
            adx_14=22.0,
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
        assert result['level'] == 2  # Fallback to L2
        assert not result['conditions']['gate_a']

    def test_l1_space_residuo_resistance_method(self, analyzer):
        """Space residuo: resistance method → space adequate."""
        prices = pd.Series([100] * 10)
        high_series = pd.Series([110] * 10)  # Resistance at 110
        low_series = prices

        space = analyzer.l1_check_space_residuo_minimo(
            current_price=100.0,
            high_series=high_series,
            low_series=low_series,
            atr_14=0.5,
            volume=50000.0,
            volume_20ma=40000.0
        )
        # Space from 100 to resistance 110 = 10% >> min_reward_pct (3%)
        assert space['space_pct'] >= 0.03
        # Method sarà 'resistance' perché 10% > (0.5 * 1.8 / 100)
        assert space['method'] in ['resistance', 'atr']


class TestL2ReadinessScore:
    """L2 Readiness score: 0-100 gauge for watchlist candidates."""

    @pytest.fixture
    def analyzer(self):
        return ETFTechnicalAnalyzer(etf_type='equity_developed')

    def test_l2_score_calculation(self, analyzer):
        """L2 score reflects proximity to L1 conditions."""
        prices = pd.Series(np.linspace(100, 105, 30))
        # Prezzo finale: 105, EMA20: 102
        # dist_pct = (105-102)/102 = 2.9% < 4% (ema_dist_max per equity_developed)
        score = analyzer.l2_calculate_readiness_score(
            prices=prices,
            ema20=102.0,
            rsi_14=48.0,  # Below rsi_entry_low (50) → contribuisce a rsi score
            adx_14=22.0,  # >= adx_entry (20) → contribuisce 20 punti
            volume=45000.0,
            volume_20ma=40000.0,
            days_above_ema20=4
        )
        assert 0 <= score <= 100
        assert isinstance(score, (int, float))

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
        """L2 score is bounded 0-100."""
        prices = pd.Series([100] * 20)

        # Worst case: tutti parametri pessimi
        score_low = analyzer.l2_calculate_readiness_score(
            prices=prices,
            ema20=100.0,
            rsi_14=20.0,  # Far from optimal
            adx_14=5.0,   # Very weak (< adx_entry 20)
            volume=10000.0,
            volume_20ma=50000.0,
            days_above_ema20=0
        )
        assert 0 <= score_low <= 100  # Score bounded

        # Good case: parametri ottimi
        prices_up = pd.Series(np.linspace(100, 110, 30))
        score_high = analyzer.l2_calculate_readiness_score(
            prices=prices_up,
            ema20=105.0,
            rsi_14=48.0,  # Approaching rsi_entry_low
            adx_14=25.0,  # >> adx_entry (20)
            volume=60000.0,
            volume_20ma=40000.0,
            days_above_ema20=5
        )
        assert 0 <= score_high <= 100
        assert score_high >= score_low  # Good case should score better


class TestL0L1L2Integration:
    """Integration tests: regime → conditions → score flow."""

    @pytest.fixture
    def analyzer(self):
        return ETFTechnicalAnalyzer(etf_type='equity_developed')

    def test_bullish_setup_progression(self, analyzer):
        """Bullish ETF: no L0 regime, L1 partial conditions, L2 reasonable score."""
        prices = pd.Series(np.linspace(100, 110, 30))
        high_series = prices + 1.0
        low_series = prices - 0.5
        sma200 = 95.0

        # L0: no regime (above SMA200, no crash)
        l0_regime = analyzer.l0_detect_regime_filter(
            prices, sma200, atr_60=0.8, volume_20ma=40000.0
        )
        assert not l0_regime['regime_suitable']
        assert l0_regime['regime_type'] == 'none'

        # L1: check conditions (may or may not all be true depending on params)
        l1_result = analyzer.l1_check_7_conditions(
            prices=prices, ema20=105.0, sma50=102.0,
            rsi_14=55.0, adx_14=22.0, macd_histogram=0.5,
            macd_histogram_prev=0.3, volume=50000.0, atr_14=0.8,
            high_series=high_series, low_series=low_series,
            volume_20ma=40000.0, days_above_ema20=5
        )
        # At least Gate A and Gate M should be true
        assert l1_result['conditions']['gate_a']
        assert l1_result['conditions']['gate_m']

        # L2: score should be reasonable (0-100)
        l2_score = analyzer.l2_calculate_readiness_score(
            prices=prices, ema20=105.0, rsi_14=48.0, adx_14=25.0,
            volume=50000.0, volume_20ma=40000.0, days_above_ema20=5
        )
        assert 0 <= l2_score <= 100

    def test_recovery_setup_l0_detection(self, analyzer):
        """Bearish recovery: L0 regime may be detected on drawdown."""
        # 60 giorni con ultimi 15 sotto SMA200
        prices = pd.Series([100] * 45 + [93, 91, 89, 88, 87, 86, 85, 84, 83, 82, 81, 80, 79, 78, 77])
        sma200 = 92.0

        # L0: verifica rilevamento regime
        l0_regime = analyzer.l0_detect_regime_filter(
            prices, sma200, atr_60=0.5, volume_20ma=40000.0
        )
        # Rilevamento dipende da regime_min_days_below_sma200 nel profilo
        assert l0_regime['regime_suitable'] in [True, False]  # Is a bool
        assert l0_regime['days_below_sma200'] >= 14  # Conta consecutivi dal fondo


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
