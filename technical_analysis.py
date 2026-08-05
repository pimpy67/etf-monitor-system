"""
technical_analysis.py - Analisi tecnica ETF
=============================================
Schema: EMA20 (fast) + SMA50 (medium) + SMA200 (regime filter)
ADX14 reale (da OHLCV) + RSI14

L0 Deep Recovery: ETF in drawdown profondo con segnali di rimbalzo
L1 Trend Sicuro: 6 condizioni (allineamento, persistenza+slope, RSI, distanza, ADX, MACD)
L2 Watchlist: allineamento parziale
L3 Universo: monitoraggio passivo
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
import yaml
import os


class ETFTechnicalAnalyzer:
    """Analisi tecnica ETF con EMA20 + SMA50 + SMA200 + ADX + RSI"""

    # Profili parametri per tipo ETF — versione definitiva 22/05/2026
    PROFILES = {
        'equity_developed': {
            'rsi_entry_low': 50, 'rsi_entry_high': 70,
            'rsi_exit_min': 40,  'rsi_overbought': 78,
            'ema_dist_max': 4.0, 'adx_entry': 20,
            'l0_drawdown': 15.0, 'l0_rsi_max': 35,
            'days_above_ema': 3, 'mm200_filter': True,
        },
        'equity_sector': {
            'rsi_entry_low': 50, 'rsi_entry_high': 70,
            'rsi_exit_min': 38,  'rsi_overbought': 78,
            'ema_dist_max': 5.0, 'adx_entry': 22,
            'l0_drawdown': 18.0, 'l0_rsi_max': 38,
            'days_above_ema': 3, 'mm200_filter': True,
        },
        'equity_emerging': {
            'rsi_entry_low': 50, 'rsi_entry_high': 65,
            'rsi_exit_min': 38,  'rsi_overbought': 76,
            'ema_dist_max': 5.0, 'adx_entry': 20,
            'l0_drawdown': 20.0, 'l0_rsi_max': 38,
            'days_above_ema': 3, 'mm200_filter': True,
        },
        'commodity': {
            'rsi_entry_low': 50, 'rsi_entry_high': 65,
            'rsi_exit_min': 38,  'rsi_overbought': 75,
            'ema_dist_max': 5.0, 'adx_entry': 22,
            'l0_drawdown': 20.0, 'l0_rsi_max': 40,
            'days_above_ema': 3, 'mm200_filter': True,
        },
        'bond': {
            'rsi_entry_low': 48, 'rsi_entry_high': 62,
            'rsi_exit_min': 42,  'rsi_overbought': 70,
            'ema_dist_max': 2.0, 'adx_entry': 15,
            'l0_drawdown': 8.0,  'l0_rsi_max': 38,
            'days_above_ema': 3, 'mm200_filter': False,
        },
        'thematic': {
            'rsi_entry_low': 50, 'rsi_entry_high': 70,
            'rsi_exit_min': 38,  'rsi_overbought': 78,
            'ema_dist_max': 6.0, 'adx_entry': 22,
            'l0_drawdown': 20.0, 'l0_rsi_max': 40,
            'days_above_ema': 3, 'mm200_filter': True,
        },
    }
    PROFILES['equity'] = PROFILES['equity_developed']  # alias

    EQUITY_FAMILY = frozenset({'equity_developed', 'equity_sector', 'equity_emerging', 'thematic', 'equity'})

    # Famiglie YAML moderne (config/etf_families.yaml) equivalenti a EQUITY_FAMILY/bond legacy.
    # Bug trovato il 2026-08-04: is_bond/is_equity_family confrontavano self.etf_type solo contro
    # questi nomi legacy, mai contro i nomi famiglia YAML attuali -> per qualunque analyzer creato
    # con famiglia=... (tutto il sistema oggi) risultavano sempre False, disattivando di fatto la
    # Regola E (ADX debole) ovunque e rendendo la Regola C (stanchezza RSI) sempre attiva anche
    # per i bond in suggest_level().
    YAML_BOND_FAMILIES = frozenset({'bond_governativi', 'bond_corp_hy_em'})
    YAML_EQUITY_COMMODITY_FAMILIES = frozenset({
        'equity_sviluppati', 'mercati_emergenti', 'settoriali_growth', 'settoriali_difensivi',
        'commodities', 'oro_metalli_preziosi', 'metalli_industriali',
        'leva_single_stock', 'crypto_digital_assets',
    })

    # Carica configurazione famiglie da YAML una volta all'avvio della classe
    _FAMILIES_CONFIG = None

    def __init__(self, etf_type: str = 'equity_developed', famiglia: Optional[str] = None):
        """
        Inizializza l'analizzatore tecnico.

        Args:
            etf_type: tipo legacy per backward compatibility (ignorato se famiglia fornito)
            famiglia: nome famiglia da config/etf_families.yaml (eg. 'equity_sviluppati')
        """
        # Carica configurazione YAML se non già fatto
        if ETFTechnicalAnalyzer._FAMILIES_CONFIG is None:
            ETFTechnicalAnalyzer._FAMILIES_CONFIG = self._load_families_config()

        # Se famiglia fornito, usa parametri da YAML; altrimenti fallback a PROFILES
        if famiglia and famiglia in (self._FAMILIES_CONFIG.get('families', {}) if self._FAMILIES_CONFIG else {}):
            self.famiglia = famiglia
            self.p = self._FAMILIES_CONFIG['families'][famiglia]
            self.etf_type = famiglia
        else:
            # Backward compatibility: usa PROFILES legacy
            self.famiglia = None
            self.etf_type = etf_type if etf_type in self.PROFILES else 'equity_developed'
            self.p = self.PROFILES[self.etf_type]

        self.ema10_period  = 10
        self.ema20_period  = 20
        self.sma50_period  = 50
        self.sma200_period = 200
        self.rsi_period    = 14
        self.adx_period    = 14
        self.macd_fast     = 12
        self.macd_slow     = 26
        self.macd_signal_p = 9

    @staticmethod
    def _load_families_config() -> Optional[Dict]:
        """Carica configurazione famiglie da config/etf_families.yaml"""
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'etf_families.yaml')
        if not os.path.exists(config_path):
            print(f"⚠️  Config file non trovato: {config_path}")
            return None
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"❌ Errore caricamento YAML: {e}")
            return None

    @staticmethod
    def detect_family(categoria: Optional[str]) -> str:
        """
        Assegna famiglia basandosi sulla categoria Excel.

        Args:
            categoria: stringa categoria da Excel (es. "Settoriale - Energia")

        Returns:
            nome famiglia (es. "equity_sviluppati")
        """
        if not categoria:
            return "equity_sviluppati"  # default

        categoria_lower = categoria.lower()

        # Carica regole di riconoscimento da YAML
        if ETFTechnicalAnalyzer._FAMILIES_CONFIG is None:
            ETFTechnicalAnalyzer._FAMILIES_CONFIG = ETFTechnicalAnalyzer._load_families_config()

        if not ETFTechnicalAnalyzer._FAMILIES_CONFIG:
            return "equity_sviluppati"  # fallback se YAML non disponibile

        rules = ETFTechnicalAnalyzer._FAMILIES_CONFIG.get('family_detection', [])
        for rule in rules:
            patterns = rule.get('pattern', [])
            if any(p in categoria_lower for p in patterns):
                return rule.get('family', 'equity_sviluppati')

        # Default fallback
        return ETFTechnicalAnalyzer._FAMILIES_CONFIG.get('default_family', 'equity_sviluppati')

    # ── Indicator helpers ──────────────────────────────────────────────────────

    def _ema(self, s: pd.Series, period: int) -> pd.Series:
        return s.ewm(span=period, adjust=False).mean()

    def _sma(self, s: pd.Series, period: int) -> pd.Series:
        return s.rolling(window=period).mean()

    def _rsi(self, s: pd.Series) -> pd.Series:
        delta  = s.diff()
        gains  = delta.where(delta > 0, 0.0)
        losses = (-delta).where(delta < 0, 0.0)
        ag = gains.ewm(com=self.rsi_period - 1, min_periods=self.rsi_period).mean()
        al = losses.ewm(com=self.rsi_period - 1, min_periods=self.rsi_period).mean()
        rs = ag / al.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def _adx(self, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """ADX14 vero da dati OHLC."""
        period = self.adx_period
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low  - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        dm_plus  = high.diff()
        dm_minus = -low.diff()
        dm_plus  = dm_plus.where((dm_plus > dm_minus) & (dm_plus > 0), 0.0)
        dm_minus = dm_minus.where((dm_minus > dm_plus) & (dm_minus > 0), 0.0)
        atr  = tr.ewm(com=period - 1, min_periods=period).mean()
        safe = atr.replace(0, np.nan)
        di_p = 100 * dm_plus.ewm(com=period - 1, min_periods=period).mean() / safe
        di_m = 100 * dm_minus.ewm(com=period - 1, min_periods=period).mean() / safe
        dx   = 100 * (di_p - di_m).abs() / (di_p + di_m).replace(0, np.nan)
        return dx.ewm(com=period - 1, min_periods=period).mean()

    def _adx_close_only(self, close: pd.Series) -> pd.Series:
        """ADX approssimato solo da Close (fallback se no OHLC)."""
        period = self.adx_period
        delta    = close.diff()
        plus_dm  = delta.clip(lower=0)
        minus_dm = (-delta).clip(lower=0)
        tr       = delta.abs()
        alpha    = 1.0 / period
        atr      = tr.ewm(alpha=alpha, adjust=False).mean()
        safe     = atr.replace(0, np.nan)
        di_p     = 100 * (plus_dm.ewm(alpha=alpha, adjust=False).mean() / safe)
        di_m     = 100 * (minus_dm.ewm(alpha=alpha, adjust=False).mean() / safe)
        dx       = 100 * (di_p - di_m).abs() / (di_p + di_m).replace(0, np.nan)
        return dx.ewm(alpha=alpha, adjust=False).mean()

    def _macd(self, s: pd.Series) -> Dict:
        fast   = s.ewm(span=self.macd_fast, adjust=False).mean()
        slow   = s.ewm(span=self.macd_slow, adjust=False).mean()
        line   = fast - slow
        signal = line.ewm(span=self.macd_signal_p, adjust=False).mean()
        return {'line': line, 'signal': signal, 'histogram': line - signal}

    def _slope(self, s: pd.Series, window: int = 5) -> float:
        vals = s.dropna().tail(window).values
        if len(vals) < 2:
            return 0.0
        x = np.arange(len(vals))
        return float(np.polyfit(x, vals, 1)[0])

    def _days_above(self, price: pd.Series, ma: pd.Series, max_check: int = 10) -> int:
        count = 0
        for i in range(1, min(max_check + 1, len(price))):
            p, m = price.iloc[-i], ma.iloc[-i]
            if pd.notna(m) and p > m:
                count += 1
            else:
                break
        return count

    def _days_below(self, price: pd.Series, ma: pd.Series, max_check: int = 10) -> int:
        count = 0
        for i in range(1, min(max_check + 1, len(price))):
            p, m = price.iloc[-i], ma.iloc[-i]
            if pd.notna(m) and p < m:
                count += 1
            else:
                break
        return count

    def _fval(self, s: pd.Series) -> Optional[float]:
        v = s.iloc[-1] if len(s) > 0 else None
        return float(v) if v is not None and pd.notna(v) else None

    def calculate_regime(self, ema20: Optional[float], sma50: Optional[float],
                        lateral_band: float = 0.01) -> str:
        """
        Determina regime a 3 stati: BULL / LATERALE / BEAR

        Formula:
          ratio = (EMA20 - SMA50) / SMA50
          BULL     se ratio > +lateral_band
          LATERALE se abs(ratio) <= lateral_band
          BEAR     se ratio < -lateral_band

        Args:
            ema20: EMA20 value (None → LATERALE)
            sma50: SMA50 value (None → LATERALE)
            lateral_band: banda laterale in decimali (es. 0.01 = 1%)

        Returns:
            "BULL", "LATERALE", o "BEAR"
        """
        if ema20 is None or sma50 is None or sma50 == 0:
            return "LATERALE"

        ratio = (ema20 - sma50) / sma50

        if ratio > lateral_band:
            return "BULL"
        elif ratio < -lateral_band:
            return "BEAR"
        else:
            return "LATERALE"

    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series,
                       period: int = 14) -> pd.Series:
        """Calcola ATR (Average True Range)."""
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        return tr.ewm(com=period - 1, min_periods=period).mean()

    def _calculate_atr_normalized(self, high: pd.Series, low: pd.Series,
                                  close: pd.Series, period: int = 14) -> Optional[float]:
        """Calcola ATR normalizzato come % del prezzo attuale."""
        if high is None or low is None or close is None or len(close) < period:
            return None
        atr = self._calculate_atr(high, low, close, period)
        current_price = close.iloc[-1]
        if current_price > 0 and pd.notna(atr.iloc[-1]):
            return float(atr.iloc[-1]) / current_price
        return None

    def _calculate_drawdown_52w(self, close: pd.Series) -> Optional[float]:
        """Calcola drawdown da massimo 52 settimane (ultimo ~250 giorni)."""
        if close is None or len(close) < 20:
            return None
        # Ultimo ~250 giorni (1 anno trading)
        period_52w = min(250, len(close))
        hist_52w = close.iloc[-period_52w:]
        peak = hist_52w.max()
        current = close.iloc[-1]
        if peak > 0:
            dd = (current - peak) / peak
            return float(dd)
        return None

    def _calculate_price_range(self, high: pd.Series, low: pd.Series) -> Optional[float]:
        """Calcola il range di prezzo (High - Low) per i dati disponibili."""
        if high is None or low is None or len(high) == 0:
            return None
        return float(high.iloc[-1] - low.iloc[-1])

    def calculate_stop_loss(self, current_price: float, atr: Optional[float],
                           family_config: Dict, entry_price: float,
                           current_gain_pct: float, regime_str: str = 'BULL') -> Dict:
        """
        Calcola lo stop loss dinamico a due fasi: iniziale + trailing

        Args:
            current_price: prezzo attuale
            atr: valore ATR14 (None se non disponibile)
            family_config: dict con parametri dalla famiglia YAML
            entry_price: prezzo di entry L1
            current_gain_pct: guadagno % attuale
            regime_str: regime di mercato ('BULL', 'BEAR', 'LATERALE')

        Returns:
            dict con: stop_loss_initial, stop_loss_trailing, trigger_reason, should_use_trailing
        """
        # --- STOP LOSS INIZIALE (REGOLA ESPLICITA PER FAMIGLIA) ---
        # Usa parametro sl_initial_pct dalla famiglia YAML (regola trasparente)
        sl_initial_pct = family_config.get('sl_initial_pct')

        if sl_initial_pct is not None:
            # Regola esplicita dalla famiglia
            sl_initial = entry_price * (1 - sl_initial_pct)
        else:
            # Fallback (solo se sl_initial_pct non definito)
            fallback_pct = family_config.get('sl_initial_pct_fallback', 0.02)
            sl_initial = entry_price * (1 - fallback_pct)

        # Protezione minima: non scendere sotto il 95% di entry
        sl_initial = max(sl_initial, entry_price * 0.95)

        # --- STOP LOSS TRAILING CONTINUO (formula lineare progressiva) ---
        sl_trailing = None
        trigger_reason = None
        should_use_trailing = False

        if current_gain_pct > 0:
            # Usa parametri continui se definiti
            threshold = family_config.get('trailing_gain_threshold')
            
            if threshold is not None:
                # Formula continua: SL si stringe gradualmente man mano che i guadagni aumentano
                if current_gain_pct >= threshold:
                    base_pct = family_config.get('trailing_base_pct', 0.05)  # es. 5%
                    sensitivity = family_config.get('trailing_sensitivity', 0.003)  # es. 0.3% per 1%
                    min_pct = family_config.get('trailing_min_pct', 0.93)  # protezione minima
                    
                    # Calcola distanza progressiva
                    excess_gain = current_gain_pct - threshold
                    distance = base_pct - (excess_gain * sensitivity)
                    
                    # Applica protezione minima
                    min_distance = 1.0 - min_pct
                    distance = max(distance, min_distance)
                    
                    trailing_pct = 1.0 - distance
                    sl_trailing = current_price * trailing_pct
                    should_use_trailing = True
                    trigger_reason = f"Trailing continuo: gain {current_gain_pct:.1f}% → SL@{trailing_pct*100:.2f}%"
            else:
                # Fallback al vecchio sistema se parametri continui non definiti
                profit_trigger = family_config.get('sl_profit_trigger_pct', 2.0)
                if current_gain_pct >= profit_trigger:
                    tight_pct = family_config.get('sl_trailing_tight_pct', 0.95)
                    sl_trailing = current_price * tight_pct
                    should_use_trailing = True
                    trigger_reason = f"Trailing legacy: gain {current_gain_pct:.1f}% >= {profit_trigger}%"

        # --- REGIME BEAR per CRYPTO ---
        if family_config.get('sl_trailing_trigger') == 'REGIME_BEAR' and regime_str == 'BEAR':
            sl_trailing = current_price * 0.90  # Exit immediato se regime cambia
            should_use_trailing = True
            trigger_reason = "REGIME_BEAR: Regime cambiato a BEAR"

        return {
            'stop_loss_initial': float(sl_initial),
            'stop_loss_trailing': float(sl_trailing) if sl_trailing else None,
            'trigger_reason': trigger_reason,
            'should_use_trailing': should_use_trailing
        }

    # ── Divergenza / recupero (copiato da fund system) ─────────────────────────

    def _detect_positive_divergence(self, prices: pd.Series, rsi: pd.Series,
                                     window: int = 30, recent: int = 10) -> bool:
        rsi_c = rsi.dropna()
        if len(prices) < window or len(rsi_c) < window:
            return False
        pw = prices.tail(window)
        rw = rsi_c.tail(window)
        rp = pw.tail(recent)
        rr = rw.tail(recent)
        if len(rp) < 3:
            return False
        # Filter out NaN values before argmin
        rp_valid = pd.Series([v for v in rp if pd.notna(v)], index=rp.index[pd.notna(rp.values)])
        rr_valid = pd.Series([v for v in rr if pd.notna(v)], index=rr.index[pd.notna(rr.values)])
        if len(rp_valid) < 2 or len(rr_valid) < 2:
            return False
        ri  = int(rp_valid.values.argmin())
        r_p = float(rp_valid.iloc[ri])
        r_r = float(rr_valid.iloc[ri])
        op  = pw.iloc[:-recent]
        or_ = rw.iloc[:-recent]
        if len(op) < 5:
            return False
        op_valid = pd.Series([v for v in op if pd.notna(v)], index=op.index[pd.notna(op.values)])
        or_valid = pd.Series([v for v in or_ if pd.notna(v)], index=or_.index[pd.notna(or_.values)])
        if len(op_valid) < 2 or len(or_valid) < 2:
            return False
        oi  = int(op_valid.values.argmin())
        o_p = float(op_valid.iloc[oi])
        o_r = float(or_valid.iloc[oi])
        return (r_p < o_p) and (r_r > o_r)

    def _detect_rsi_recovery(self, rsi: pd.Series, oversold: float = 30.0,
                              recovery: float = 32.0, lookback: int = 10) -> bool:
        rc = rsi.dropna()
        if len(rc) < 3:
            return False
        recent = rc.tail(lookback)
        # Filter out None/NaN values explicitly before comparison
        recent_vals = [v for v in recent.iloc[:-1] if pd.notna(v) and v is not None]
        if not recent_vals:
            return False
        last_val = recent.iloc[-1]
        if pd.isna(last_val) or last_val is None:
            return False
        return (any(v < oversold for v in recent_vals) and
                float(last_val) > recovery)

    def _detect_micro_breakout(self, prices: pd.Series, lookback: int = 5,
                                min_pct: float = 0.3) -> bool:
        if len(prices) < lookback + 2:
            return False
        recent_high = float(prices.iloc[-(lookback + 1):-1].max())
        current     = float(prices.iloc[-1])
        return recent_high > 0 and current > recent_high * (1 + min_pct / 100)

    # ── L1 PRIORITÀ 2: Squeeze Override + Spazio Residuo ────────────────────

    def _calculate_squeeze_metrics(self, prices: pd.Series, lookback: int = 20,
                                     lookback_history: int = 252) -> Dict:
        """
        Calcola metriche di squeeze per override L1.

        Ritorna:
        {
            'consolidation_range_pct': range percentuale ultimi N giorni,
            'squeeze_percentile': percentile del range nella storia (0-100),
            'squeeze_valido': bool,
            'squeeze_threshold_pct': valore soglia assoluta (parametro famiglia),
        }
        """
        if len(prices) < max(lookback, lookback_history) + 1:
            return {
                'consolidation_range_pct': None,
                'squeeze_percentile': None,
                'squeeze_valido': False,
                'squeeze_threshold_pct': self.p.get('l1_space_residuo', {}).get('squeeze_threshold_pct', 0.03),
            }

        close = prices.astype(float)

        # Calcola range consolidamento ultimi N giorni
        recent_high = float(close.iloc[-lookback:].max())
        recent_low  = float(close.iloc[-lookback:].min())
        current     = float(close.iloc[-1])

        if current <= 0 or recent_high <= recent_low:
            return {
                'consolidation_range_pct': 0.0,
                'squeeze_percentile': None,
                'squeeze_valido': False,
                'squeeze_threshold_pct': self.p.get('l1_space_residuo', {}).get('squeeze_threshold_pct', 0.03),
            }

        consolidation_range_pct = (recent_high - recent_low) / current

        # Calcola percentile su storia (252 giorni)
        try:
            from scipy.stats import percentileofscore
            history_ranges = []
            for i in range(len(close) - lookback_history, len(close)):
                if i >= lookback:
                    h = float(close.iloc[max(0, i-lookback):i].max())
                    l = float(close.iloc[max(0, i-lookback):i].min())
                    c = float(close.iloc[i])
                    if c > 0:
                        history_ranges.append((h - l) / c)

            if len(history_ranges) >= 10:
                squeeze_percentile = percentileofscore(history_ranges, consolidation_range_pct, kind='weak')
            else:
                squeeze_percentile = None
        except:
            squeeze_percentile = None

        # Determina squeeze_valido
        squeeze_threshold_pct = self.p.get('l1_space_residuo', {}).get('squeeze_threshold_pct', 0.03)
        squeeze_percentile_threshold = self.p.get('l1_space_residuo', {}).get('squeeze_percentile_threshold', 20)

        squeeze_valido = False
        if squeeze_percentile is not None:
            squeeze_valido = squeeze_percentile <= squeeze_percentile_threshold
        if not squeeze_valido and consolidation_range_pct <= squeeze_threshold_pct:
            squeeze_valido = True

        return {
            'consolidation_range_pct': round(consolidation_range_pct, 6),
            'squeeze_percentile': round(squeeze_percentile, 1) if squeeze_percentile is not None else None,
            'squeeze_valido': squeeze_valido,
            'squeeze_threshold_pct': squeeze_threshold_pct,
            'squeeze_percentile_threshold': squeeze_percentile_threshold,
        }

    def _check_reward_space(self, prices: pd.Series, high: pd.Series, low: pd.Series,
                             min_reward_pct: float = 0.03, resistance_lookback_days: int = 30,
                             atr_multiplier: float = 1.8) -> Dict:
        """
        Verifica spazio residuo minimo con due metodi (OR logico).

        Metodo a) Distanza da resistenza: (max_N - prezzo) / prezzo >= min_reward_pct
        Metodo b) Spazio volatilità: (ATR / prezzo) * atr_multiplier >= min_reward_pct

        Ritorna:
        {
            'space_ok': bool (uno dei due metodi OK),
            'method_a_ok': bool,
            'method_b_ok': bool,
            'distance_resistance': float %,
            'space_atr': float %,
        }
        """
        if len(prices) < resistance_lookback_days + 1:
            return {
                'space_ok': False,
                'method_a_ok': False,
                'method_b_ok': False,
                'distance_resistance': None,
                'space_atr': None,
            }

        close = prices.astype(float)
        current = float(close.iloc[-1])

        if current <= 0:
            return {
                'space_ok': False,
                'method_a_ok': False,
                'method_b_ok': False,
                'distance_resistance': None,
                'space_atr': None,
            }

        # Metodo a) Distanza resistenza
        resistance_high = float(close.iloc[-resistance_lookback_days:].max())
        distance_resistance = (resistance_high - current) / current if resistance_high > current else 0.0
        method_a_ok = distance_resistance >= min_reward_pct

        # Metodo b) Spazio volatilità (ATR)
        method_b_ok = False
        space_atr = None
        if high is not None and low is not None and len(high) >= 14:
            atr = self._calculate_atr_normalized(high, low, close)
            if atr is not None:
                space_atr = atr * atr_multiplier
                method_b_ok = space_atr >= min_reward_pct

        space_ok = method_a_ok or method_b_ok

        return {
            'space_ok': space_ok,
            'method_a_ok': method_a_ok,
            'method_b_ok': method_b_ok,
            'distance_resistance': round(distance_resistance, 4) if distance_resistance else None,
            'space_atr': round(space_atr, 4) if space_atr is not None else None,
        }

    def _verify_breakout_confirmed(self, high: pd.Series, low: pd.Series, close: pd.Series) -> Dict:
        """
        Verifica breakout confermato: ADX in salita (5gg) + volume in espansione (1.2x media 20gg).

        Ritorna:
        {
            'adx_rising': bool,
            'volume_expanding': bool,
            'breakout_confirmed': bool,
            'adx_current': float,
            'adx_5gg_ago': float,
            'volume_ratio': float,
        }
        """
        adx_rising = False
        volume_expanding = False
        adx_current = None
        adx_5gg_ago = None
        volume_ratio = None

        # ADX in salita (5 giorni)
        if high is not None and low is not None and len(close) >= 5:
            adx_s = self._adx(high.astype(float), low.astype(float), close.astype(float))
            if len(adx_s) >= 5:
                adx_vals = adx_s.dropna()
                if len(adx_vals) >= 2:
                    adx_current = float(adx_vals.iloc[-1])
                    adx_5gg_ago = float(adx_vals.iloc[-6]) if len(adx_vals) >= 6 else float(adx_vals.iloc[0])
                    adx_rising = adx_current > adx_5gg_ago

        # Volume in espansione (1.2x media 20gg)
        try:
            # Se data è OHLCV con volume, calcola ratio
            # Altrimenti fallback: assume volume_expanding = True se non disponibile
            volume_expanding = True  # Fallback: assume true se close-only
            volume_ratio = 1.2  # Fallback
        except:
            volume_expanding = True
            volume_ratio = 1.2

        breakout_confirmed = adx_rising and volume_expanding

        return {
            'adx_rising': adx_rising,
            'volume_expanding': volume_expanding,
            'breakout_confirmed': breakout_confirmed,
            'adx_current': round(adx_current, 1) if adx_current is not None else None,
            'adx_5gg_ago': round(adx_5gg_ago, 1) if adx_5gg_ago is not None else None,
            'volume_ratio': round(volume_ratio, 2) if volume_ratio is not None else None,
        }

    # ── L0 PRIORITÀ 1: Doppio Percorso (Lento + Rapido) ──────────────────────

    def _analyze_l0_slow_path(self, prices: pd.Series, high: pd.Series, low: pd.Series,
                               regime_params: Dict) -> Dict:
        """
        Percorso LENTO (bear sostenuto): asset sotto SMA200 da N giorni + drawdown sostenuto.

        Ritorna:
        {
            'slow_path_valid': bool,
            'days_below_sma200': int,
            'drawdown_normalized': float,
            'min_reached': float,
        }
        """
        if len(prices) < 200:
            return {
                'slow_path_valid': False,
                'days_below_sma200': 0,
                'drawdown_normalized': 0.0,
                'min_reached': None,
            }

        close = prices.astype(float)
        sma200 = self._sma(close, 200)
        sma200_v = self._fval(sma200)

        # Conta giorni sotto SMA200
        days_below = 0
        if sma200_v is not None:
            below_series = close < sma200_v
            if len(below_series) > 0:
                days_below = int(below_series[-30:].sum()) if len(below_series) >= 30 else int(below_series.sum())

        min_days_required = regime_params.get('regime_min_days_below_sma200', 10)

        # Calcola drawdown normalizzato su ATR
        atr_normalized = self._calculate_atr_normalized(high, low, close) if high is not None and low is not None else None
        current_price = float(close.iloc[-1])
        peak_price = float(close.tail(252).max()) if len(close) >= 252 else float(close.max())

        drawdown_pct = (peak_price - current_price) / peak_price if peak_price > 0 else 0.0
        dd_atr_multiple = regime_params.get('dd_threshold_atr_multiple', 3.0)
        drawdown_normalized = drawdown_pct / (atr_normalized * dd_atr_multiple) if atr_normalized and atr_normalized > 0 else 0.0

        # Slow path valido se: (giorni sotto SMA200 >= min) AND (drawdown sostenuto)
        min_dd_pct = regime_params.get('dd_min_duration_days', 4) / 100.0  # Conversion for simplicity
        slow_path_valid = (days_below >= min_days_required) and (drawdown_pct >= min_dd_pct)

        return {
            'slow_path_valid': slow_path_valid,
            'days_below_sma200': days_below,
            'drawdown_normalized': round(drawdown_normalized, 4),
            'min_reached': round(current_price, 4),
        }

    def _analyze_l0_fast_path(self, prices: pd.Series, high: pd.Series, low: pd.Series,
                               regime_params: Dict) -> Dict:
        """
        Percorso RAPIDO (flash crash): drawdown estremo normalizzato su ATR in 2-3 giorni.

        Ritorna:
        {
            'fast_path_triggered': bool,
            'zscore': float,
            'drawdown_pct': float,
            'trigger_price': float,
        }
        """
        if len(prices) < 14:
            return {
                'fast_path_triggered': False,
                'zscore': 0.0,
                'drawdown_pct': 0.0,
                'trigger_price': None,
            }

        close = prices.astype(float)
        current_price = float(close.iloc[-1])

        # Drawdown su finestra 2-3 giorni
        window = regime_params.get('flash_crash_window_days', 3)
        peak_recent = float(close.iloc[-window:].max())
        drawdown_pct = (peak_recent - current_price) / peak_recent if peak_recent > 0 else 0.0

        # Normalizzazione su ATR
        atr_normalized = self._calculate_atr_normalized(high, low, close) if high is not None and low is not None else None
        zscore = drawdown_pct / (atr_normalized * 100) if atr_normalized and atr_normalized > 0 else 0.0

        # Flash path valido se zscore > soglia (default 4.0 deviazioni)
        zscore_threshold = regime_params.get('flash_crash_zscore_threshold', 4.0)
        fast_path_triggered = zscore >= zscore_threshold

        return {
            'fast_path_triggered': fast_path_triggered,
            'zscore': round(zscore, 2),
            'drawdown_pct': round(drawdown_pct, 4),
            'trigger_price': round(current_price, 4),
        }

    def _get_l0_confirmation_signal(self, prices: pd.Series, mode: str,
                                     trigger_price: float, reclaim_ema_period: int = 20) -> Dict:
        """
        Verifica segnale di recovery per L0: RSI recovery O EMA reclaim.

        Ritorna:
        {
            'recovery_signal': bool,
            'signal_type': 'rsi_recovery' | 'ema_reclaim' | None,
            'rsi_current': float,
            'ema_current': float,
        }
        """
        if len(prices) < max(14, reclaim_ema_period):
            return {
                'recovery_signal': False,
                'signal_type': None,
                'rsi_current': None,
                'ema_current': None,
            }

        close = prices.astype(float)
        current_price = float(close.iloc[-1])

        # RSI recovery: RSI > 40 (fast) o > 32 (slow)
        rsi = self._rsi(close)
        rsi_val = self._fval(rsi)
        rsi_threshold = 40 if mode == 'fast' else 32
        rsi_recovery = rsi_val is not None and rsi_val > rsi_threshold

        # EMA reclaim: prezzo > EMA (fast: 20, slow: 50)
        ema = self._ema(close, reclaim_ema_period)
        ema_val = self._fval(ema)
        ema_reclaim = ema_val is not None and current_price > ema_val

        recovery_signal = rsi_recovery or ema_reclaim
        signal_type = None
        if rsi_recovery:
            signal_type = 'rsi_recovery'
        elif ema_reclaim:
            signal_type = 'ema_reclaim'

        return {
            'recovery_signal': recovery_signal,
            'signal_type': signal_type,
            'rsi_current': round(rsi_val, 1) if rsi_val is not None else None,
            'ema_current': round(ema_val, 4) if ema_val is not None else None,
        }

    # ── L0 Deep Recovery ──────────────────────────────────────────────────────

    def suggest_level_0(self, prices: pd.Series, high: pd.Series, low: pd.Series, current_level: int) -> Dict:
        """
        Valuta le condizioni L0 'Deep Recovery'.

        Entrata (tutte e 4 obbligatorie):
          1. Prezzo almeno l0_drawdown% sotto il picco
          2. RSI < l0_rsi_max (ipervenduto)
          3. Divergenza rialzista
          4. Segnale di recupero: RSI risalito > 32 OPPURE micro-breakout

        Uscita (se gia' in L0, basta 1):
          α: prezzo < panic_low (stop assoluto)    [gestito in monitor.py]
          β: RSI < 25 dopo ingresso (trappola)
          γ: prezzo > EMA20 (take profit → promuovi a L2)
          ε: 30gg senza recupero                   [gestito in monitor.py]
        """
        result = {
            'l0_entry': False, 'l0_exit_rule': None, 'l0_exit_trigger': None,
            'peak_price': None, 'peak_days': None, 'distance_from_peak': None,
            'rsi_oversold': False, 'divergence': False,
            'rsi_recovery': False, 'micro_breakout': False,
            'reason_codes': [],
        }

        if len(prices) < 20:
            result['reason_codes'] = ['INSUFFICIENT_DATA']
            return result

        rsi     = self._rsi(prices)
        rsi_val = float(rsi.dropna().iloc[-1]) if len(rsi.dropna()) > 0 else 50.0
        ema20   = self._ema(prices, self.ema20_period)
        ema20_v = self._fval(ema20)
        # Ensure current price is valid
        curr_price = prices.iloc[-1]
        if pd.isna(curr_price) or curr_price is None:
            result['reason_codes'] = ['NO_CURRENT_PRICE']
            return result
        current = float(curr_price)

        result['rsi']           = round(rsi_val, 1)
        result['ema20_current'] = round(ema20_v, 4) if ema20_v else None
        result['current_price'] = round(current, 4)

        # Kill switch: crollo giornaliero >= 3%
        kill_switch = False
        if len(prices) >= 2:
            p1 = prices.iloc[-1]
            p2 = prices.iloc[-2]
            if pd.notna(p1) and pd.notna(p2) and p1 is not None and p2 is not None:
                p1_f = float(p1)
                p2_f = float(p2)
                if p2_f != 0:
                    daily_chg = (p1_f - p2_f) / p2_f * 100
                    kill_switch = daily_chg <= -3.0
                    result['daily_change_pct'] = round(daily_chg, 2)
        result['kill_switch'] = kill_switch

        n_panic = min(30, len(prices))
        panic_val = prices.iloc[-n_panic:].min()
        result['panic_low'] = float(panic_val) if pd.notna(panic_val) else current

        # Leggi nuovi parametri L0 pragmatici da l0_entry
        l0_entry_params = self.p.get('l0_entry', {})
        l0_enabled = l0_entry_params.get('enabled', False)
        l0_dd_threshold = l0_entry_params.get('dd_threshold', 0.15)  # Default 15% per backward compat
        l0_rsi_max = l0_entry_params.get('rsi_max', 35)  # Default 35 per backward compat
        l0_recovery_min = l0_entry_params.get('recovery_min_pct', 0.01)  # Soglia micro-breakout: 1% (non 1.5%)  # Default 1.5%
        ema_fast_period = l0_entry_params.get('ema_fast_period', 10)

        # ── Uscita (se gia' in L0) ────────────────────────────────────────────
        if current_level == 0:
            if ema20_v and current > ema20_v:
                result['l0_exit_rule']    = 'gamma'
                result['l0_exit_trigger'] = (
                    f'Prezzo {current:.4f} > EMA20 {ema20_v:.4f} — take profit, promuovi a L2'
                )
                result['reason_codes'] = ['L0_EXIT_GAMMA']
            elif rsi_val < 25:
                result['l0_exit_rule']    = 'beta'
                result['l0_exit_trigger'] = (
                    f'RSI={rsi_val:.0f} < 25 dopo ingresso — trappola ribassista, esci'
                )
                result['reason_codes'] = ['L0_EXIT_BETA']
            else:
                result['reason_codes'] = ['L0_HOLD']
            return result

        # ── Entrata ───────────────────────────────────────────────────────────
        if not l0_enabled:
            result['l0_entry'] = False
            result['reason_codes'] = ['L0_DISABLED']
            return result

        # Picco degli ultimi 90 giorni (non assoluto) per evitare falsi positivi su trend down lunghi
        # Calcolato subito, PRIMA dei percorsi FAST/SLOW, così è sempre disponibile per il
        # messaggio "L0 Deep Recovery: X% dal picco" indipendentemente da quale percorso entra.
        n_lookback_peak = min(90, len(prices))
        peak_price = float(prices.iloc[-n_lookback_peak:].max())
        result['peak_price']  = round(peak_price, 4)
        result['peak_days']   = len(prices)
        dist_peak_pct      = (current - peak_price) / peak_price * 100
        result['distance_from_peak'] = round(dist_peak_pct, 2)

        # PRIORITÀ 1 — Percorsi LENTO e RAPIDO (se l0_regime params disponibili)
        l0_regime_params = self.p.get('l0_regime', {})
        regime_check_enabled = bool(l0_regime_params)

        if regime_check_enabled and high is not None and low is not None:
            # Verifica Percorso RAPIDO (flash crash) — ha priorità
            fast_result = self._analyze_l0_fast_path(prices, high, low, l0_regime_params)
            if fast_result['fast_path_triggered'] and not kill_switch:
                result['l0_entry']      = True
                result['l0_regime_mode'] = 'FAST'
                result['reason_codes']  = ['L0_ENTRY_FAST_PATH']
                result['flash_crash_zscore'] = fast_result['zscore']
                result['fast_path_trigger_price'] = fast_result['trigger_price']
                return result

            # Verifica Percorso LENTO (bear sostenuto) — alternativa al rapido
            slow_result = self._analyze_l0_slow_path(prices, high, low, l0_regime_params)
            if slow_result['slow_path_valid'] and not kill_switch:
                result['l0_entry']      = True
                result['l0_regime_mode'] = 'SLOW'
                result['reason_codes']  = ['L0_ENTRY_SLOW_PATH']
                result['days_below_sma200'] = slow_result['days_below_sma200']
                result['drawdown_normalized'] = slow_result['drawdown_normalized']
                return result

        # Cond 1: drawdown check (pragmatico: 6.5% per equity, non 15%)
        cond1 = dist_peak_pct <= -(l0_dd_threshold * 100)
        cond2 = rsi_val < l0_rsi_max
        result['rsi_oversold'] = cond2
        cond3 = self._detect_positive_divergence(prices, rsi)
        result['divergence'] = cond3
        rsi_rec    = self._detect_rsi_recovery(rsi, oversold=l0_rsi_max, recovery=40.0)

        # Micro-breakout: controlla se il recovery è abbastanza forte
        n_lookback = 10
        if len(prices) >= n_lookback:
            low_10d = prices.iloc[-n_lookback:].min()
            recovery_pct = (current - low_10d) / low_10d
            micro_brk = recovery_pct >= l0_recovery_min
        else:
            micro_brk = False

        cond4      = rsi_rec or micro_brk
        result['rsi_recovery']   = rsi_rec
        result['micro_breakout'] = micro_brk
        result['recovery_pct'] = recovery_pct if 'recovery_pct' in locals() else 0.0

        entry_ok = cond1 and cond2 and cond3 and cond4
        if entry_ok and kill_switch:
            result['l0_entry']      = False
            result['reason_codes']  = ['KILL_SWITCH', 'L0_ENTRY_BLOCKED']
        elif entry_ok:
            result['l0_entry']      = True
            result['l0_regime_mode'] = 'PRAGMATIC_4CONDITIONS'
            result['reason_codes']  = ['L0_ENTRY']
        else:
            missing = []
            if not cond1: missing.append('L0_COND_DRAWDOWN')
            if not cond2: missing.append('L0_COND_RSI')
            if not cond3: missing.append('L0_COND_DIVERGENCE')
            if not cond4: missing.append('L0_COND_RECOVERY')
            result['reason_codes'] = missing or ['L0_WAIT']

        return result

    # ── L1 Trend Sicuro (5 condizioni) ────────────────────────────────────────

    def suggest_level(self, prices: pd.Series, current_level: int = 3,
                      high: pd.Series = None, low: pd.Series = None) -> Dict:
        """
        Suggerisce L1/L2/L3.

        6 condizioni L1 (tutte obbligatorie):
          1. Allineamento: price > EMA20 > SMA50 (+ price > SMA200 se mm200_filter)
          2. Persistenza: >= 3gg sopra EMA20 + slope EMA20 positivo
          3. RSI: nel range target per l'asset class
          4. Distanza da EMA20: <= ema_dist_max
          5. ADX: >= adx_entry
          6. MACD momentum: macd_h > 0 AND macd_h > macd_h_prev (sempre pendenza positiva)

        Exit L1 (6 regole, priorità dall'alto):
          F: crollo giornaliero >= 3% (kill switch) — totale
          A: prezzo sotto EMA20 per >= 3 giorni — totale
          B: EMA10 < EMA20 (trailing stop reattivo) — totale
          C: RSI_prev >= 70 AND RSI_oggi < 70 (stanchezza) — totale, solo non-bond
          E: ADX < 18 AND prezzo < EMA20 (trend esaurito) — totale, solo equity/commodity
          D: RSI > 78 (eccesso) — parziale 90%, flag dashboard
        """
        p = self.p
        is_bond = self.etf_type == 'bond' or self.etf_type in self.YAML_BOND_FAMILIES
        is_equity_family = (self.etf_type in self.EQUITY_FAMILY or self.etf_type == 'commodity'
                             or self.etf_type in self.YAML_EQUITY_COMMODITY_FAMILIES)

        if len(prices) < self.ema20_period:
            return {
                'suggested_level': current_level,
                'level_change': False,
                'reason': f'Dati insufficienti ({len(prices)} giorni)',
                'reason_codes': ['INSUFFICIENT_DATA'],
                'conditions': {}
            }

        # Kill switch
        kill_switch = False
        daily_chg   = None
        if len(prices) >= 2:
            p1 = prices.iloc[-1]
            p2 = prices.iloc[-2]
            if pd.notna(p1) and pd.notna(p2) and p1 is not None and p2 is not None:
                p1_f = float(p1)
                p2_f = float(p2)
                if p2_f != 0:
                    daily_chg = (p1_f - p2_f) / p2_f * 100
                    kill_switch = daily_chg <= -3.0

        close   = prices.astype(float)
        # Ensure current price is valid
        curr_val = close.iloc[-1]
        if pd.isna(curr_val) or curr_val is None:
            # Not enough data
            return {
                'suggested_level': current_level,
                'level_change': False,
                'reason': 'Dati insufficienti — prezzo finale non disponibile',
                'reason_codes': ['NO_CURRENT_PRICE'],
                'conditions': {}
            }
        current = float(curr_val)

        ema10  = self._ema(close, self.ema10_period)
        ema20  = self._ema(close, self.ema20_period)
        sma50  = self._sma(close, self.sma50_period) if len(close) >= self.sma50_period else None
        sma200 = self._sma(close, self.sma200_period) if len(close) >= self.sma200_period else None

        ema10_v  = self._fval(ema10)
        ema20_v  = self._fval(ema20)
        sma50_v  = self._fval(sma50) if sma50 is not None else None
        sma200_v = self._fval(sma200) if sma200 is not None else None

        rsi     = self._rsi(close)
        rsi_val = self._fval(rsi)
        rsi_c   = rsi.dropna()
        rsi_prev = float(rsi_c.iloc[-2]) if len(rsi_c) >= 2 else rsi_val

        # ADX: usa OHLC se disponibili, altrimenti Close-only
        if high is not None and low is not None and len(high) == len(close):
            adx_s   = self._adx(high.astype(float), low.astype(float), close)
        else:
            adx_s   = self._adx_close_only(close)
        adx_val = self._fval(adx_s)

        macd_d  = self._macd(close)
        macd_h  = self._fval(macd_d['histogram'])
        macd_hp = float(macd_d['histogram'].iloc[-2]) if len(macd_d['histogram']) >= 2 and pd.notna(macd_d['histogram'].iloc[-2]) else None

        days_above_ema20 = self._days_above(close, ema20)
        days_below_ema20 = self._days_below(close, ema20)
        days_below_sma50 = self._days_below(close, sma50) if sma50 is not None else 0
        ema20_slope      = self._slope(ema20, window=5) if ema20_v else 0.0

        dist_ema20 = ((current - ema20_v) / ema20_v * 100) if ema20_v and ema20_v > 0 else 0.0

        pct_1d = round((close.iloc[-1] / close.iloc[-2] - 1) * 100, 2) if len(close) >= 2  else None
        pct_1w = round((close.iloc[-1] / close.iloc[-6] - 1) * 100, 2) if len(close) >= 6  else None
        pct_1m = round((close.iloc[-1] / close.iloc[-22] - 1) * 100, 2) if len(close) >= 22 else None

        peak_w  = min(252, len(close))
        peak    = float(close.tail(peak_w).max())
        drawdown = (peak - current) / peak * 100 if peak > 0 else 0.0

        # NUOVE METRICHE: ATR, Drawdown 52W, Price Range
        atr_normalized = self._calculate_atr_normalized(high, low, close) if high is not None and low is not None else None
        drawdown_52w = self._calculate_drawdown_52w(close)
        price_range = self._calculate_price_range(high, low) if high is not None and low is not None else None

        # ── Exit rules (se gia' in L1) ─────────────────────────────────────────
        exit_rule    = None
        partial_exit = False  # True = segnale D (vendi 90%, tieni 10%)

        if current_level == 1:
            if kill_switch:
                # F — Kill Switch: uscita totale immediata
                exit_rule = f'Regola F — Kill Switch: calo {daily_chg:.1f}% (>= 3%)'

            elif days_below_ema20 >= 3:
                # A — Stop Loss: prezzo sotto EMA20 da almeno 3 giorni
                exit_rule = f'Regola A — Stop Loss: prezzo sotto EMA20 da {days_below_ema20}gg'

            elif ema10_v and ema20_v and ema10_v < ema20_v:
                # B — Trailing Stop: EMA10 scende sotto EMA20 (più reattivo del death cross)
                exit_rule = f'Regola B — Trailing: EMA10 {ema10_v:.2f} < EMA20 {ema20_v:.2f}'

            elif (not is_bond and rsi_val is not None and rsi_prev is not None
                  and rsi_prev >= 70 and rsi_val < 70):
                # C — Stanchezza: RSI usciva dall'ipercomprato (solo non-bond)
                exit_rule = f'Regola C — Stanchezza: RSI {rsi_prev:.0f}→{rsi_val:.0f} (era ≥70, ora <70)'

            elif (is_equity_family and adx_val is not None
                  and adx_val < 18 and current < (ema20_v or current + 1)):
                # E — ADX debole + prezzo sotto EMA20 (solo equity/commodity)
                exit_rule = f'Regola E — ADX debole: {adx_val:.0f} < 18 e prezzo < EMA20'

        # ── 6 condizioni L1 ───────────────────────────────────────────────────
        # Determina regime a 3 stati
        lateral_band = p.get('lateral_band', 0.01)
        regime_str = self.calculate_regime(ema20_v, sma50_v, lateral_band)
        regime_ok = regime_str == "BULL"  # L1 richiede regime BULL

        # 1. Allineamento: price > EMA20 > SMA50 (+ price > SMA200 se mm200_filter) — puramente geometrico
        #    Il regime BULL/BEAR/LATERALE NON entra qui: è valutato una sola volta, a valle, come fondamenta.
        price_ema_ok  = ema20_v is not None and current > ema20_v
        ema_sma50_ok  = ema20_v is not None and sma50_v is not None and ema20_v > sma50_v
        regime_ok_mm200 = True
        if p['mm200_filter'] and sma200_v is not None:
            regime_ok_mm200 = current > sma200_v
        allineamento  = price_ema_ok and ema_sma50_ok and regime_ok_mm200

        # 2. Persistenza: >= 3gg sopra EMA20 + slope EMA20 positivo
        persistenza   = days_above_ema20 >= p['days_above_ema'] and ema20_slope > 0

        # 3. RSI nel range target
        rsi_ok        = rsi_val is not None and p['rsi_entry_low'] <= rsi_val <= p['rsi_entry_high']

        # 4. Distanza da EMA20 entro limite
        dist_ok       = 0 <= dist_ema20 <= p['ema_dist_max']

        # 5. ADX sopra soglia
        adx_ok        = adx_val is not None and adx_val >= p['adx_entry']

        # 6. MACD momentum: histogram positivo + in accelerazione (o dip vicino EMA20)
        macd_positive  = macd_h is not None and macd_h > 0
        macd_rising    = macd_hp is not None and macd_h is not None and macd_h > macd_hp
        macd_ok        = macd_positive and macd_rising

        # 7️⃣ NUOVA: Spazio Residuo Minimo (resistenza OR volatilità ATR)
        space_residuo_check = self.l1_check_space_residuo_minimo(current, high, low,
                                                                  self._fval(self._calculate_atr(high, low, close)) if high is not None and low is not None else None,
                                                                  None,
                                                                  None) if high is not None and low is not None else {'valid': False}
        space_ok       = space_residuo_check.get('valid', False)

        conditions = {
            'allineamento_ok':    allineamento,
            'persistenza_ok':     persistenza,
            'rsi_ok':             rsi_ok,
            'distance_ok':        dist_ok,
            'adx_ok':             adx_ok,
            'macd_ok':            macd_ok,
            'space_residuo_ok':   space_ok,
            # Valori per display
            'ema10_current':      round(ema10_v, 4) if ema10_v else None,
            'ema20_current':      round(ema20_v, 4) if ema20_v else None,
            'sma50_current':      round(sma50_v, 4) if sma50_v else None,
            'sma200_current':     round(sma200_v, 4) if sma200_v else None,
            'rsi':                round(rsi_val, 1) if rsi_val else None,
            'rsi_prev':           round(rsi_prev, 1) if rsi_prev else None,
            'adx':                round(adx_val, 1) if adx_val else None,
            'days_above_ema20':   days_above_ema20,
            'dist_ema20':         round(dist_ema20, 2),
            'ema20_slope':        round(ema20_slope, 6),
            'regime':             regime_str,  # NUOVO: regime a 3 stati
            'regime_ok':          regime_ok,
            'kill_switch':        kill_switch,
            'daily_change_pct':   round(daily_chg, 2) if daily_chg is not None else None,
            'macd_histogram':     round(macd_h, 4) if macd_h is not None else None,
            'macd_histogram_prev': round(macd_hp, 4) if macd_hp is not None else None,
            'partial_exit':       partial_exit,
            'pct_1d':             pct_1d,
            'pct_1w':             pct_1w,
            'pct_1m':             pct_1m,
            'peak_price':         round(peak, 4),
            'drawdown_from_peak': round(drawdown, 2),
            # NUOVE METRICHE
            'atr_normalized':     round(atr_normalized * 100, 2) if atr_normalized is not None else None,  # in %
            'drawdown_52w':       round(drawdown_52w * 100, 2) if drawdown_52w is not None else None,  # in %
            'price_range':        round(price_range, 4) if price_range is not None else None,
            # PRIORITÀ 2 — 7a condizione (squeeze override + spazio residuo)
            'l1_squeeze_metrics': None,  # Populated later if buy_count == 6
            'l1_breakout_metrics': None,  # Populated later if buy_count == 6
            'l1_reward_space_metrics': None,  # Populated later if buy_count == 6
        }
        buy_count = sum([allineamento, persistenza, rsi_ok, dist_ok, adx_ok, macd_ok, space_ok])

        # ── REGIME A 3 STATI (INFORMATIVO, SENZA PENALITÀ) ───────────────────────────────
        # Calcola il regime per dashboard/reporting, ma NON penalizza il buy_count
        # Questo permette agli ETF di entrare in L1 in base alle loro condizioni tecniche
        buy_count_finale = float(buy_count)
        regime_penalty = 0.0
        # regime_str è già calcolato sopra e disponibile per il report

        # ── Determina livello ──────────────────────────────────────────────────
        reason_codes = []

        # Min buy count richiesto per L1 (dipende dalla famiglia)
        min_buy_required = self.p.get('min_buy_count', 7)

        # [DEBUG] Log per tutte le decisioni L1
        if buy_count_finale >= (min_buy_required - 1):
            famiglia_str = self.famiglia or self.etf_type
            adx_entry = p.get('adx_entry', '?')
            print(f"[L1-CHECK] {famiglia_str} | {buy_count}/{min_buy_required} | regime={regime_str} | ADX={adx_val or 'N/A'} (>={adx_entry}) | dist={dist_ema20:.1f}% (max {p['ema_dist_max']}%)")
            # DEBUGGING: stampa quale condizione fallisce
            if buy_count < min_buy_required:
                failed = []
                if not allineamento: failed.append("ALIGN")
                if not persistenza: failed.append("PERSIST")
                if not rsi_ok: failed.append("RSI")
                if not dist_ok: failed.append("DIST")
                if not adx_ok: failed.append("ADX")
                if not macd_ok: failed.append("MACD")
                print(f"  → Fallisce: {', '.join(failed) if failed else 'NESSUNA (OK 6/6!)'}")

        if current_level == 1:
            if exit_rule:
                conditions['exit_rule']    = exit_rule
                conditions['exit_trigger'] = exit_rule
                suggested = 3
                reason    = f'Uscita L1 — {exit_rule}'
                reason_codes.append('L1_EXIT')
            elif buy_count_finale < min_buy_required or regime_str != "BULL":
                # Demote if no longer meets min conditions or regime changed
                conditions['exit_rule']    = None
                suggested = 2
                reason    = f'Downgrade L1→L2: {buy_count}/{min_buy_required} condizioni (score finale {buy_count_finale:.1f}), regime {regime_str}'
                reason_codes.append('L1_DEMOTED')
            else:
                conditions['exit_rule']    = None
                suggested = 1
                reason    = f'Mantenuto L1 — RSI {rsi_val:.0f}, ADX {adx_val:.0f}' if rsi_val and adx_val else 'Mantenuto L1'
                reason_codes.append('L1_HOLD')

        elif sma50_v is None:
            # Non abbastanza storico per SMA50 — blocca L1
            suggested = 2 if days_above_ema20 >= p['days_above_ema'] else 3
            reason    = f'Storico insufficiente per SMA50 (min {self.sma50_period} giorni)'
            reason_codes.append('L2_WATCHLIST' if suggested == 2 else 'L3_MONITOR')

        elif buy_count_finale >= min_buy_required:
            # ✅ TUTTE e 7 condizioni obbligatorie (no "5/6")
            # FONDAMENTA irrinunciabili: REGIME BULL, prezzo > SMA50, no kill switch

            if kill_switch:
                suggested = current_level
                chg_str = f'{daily_chg:.1f}' if daily_chg is not None else '?'
                reason    = f'Kill Switch [{chg_str}%]: nuovo ingresso L1 bloccato'
                reason_codes.extend(['KILL_SWITCH', 'L1_ENTRY_BLOCKED'])
            elif regime_str != "BULL":
                # FONDAMENTA: regime deve essere BULL
                suggested = 2
                reason    = f'Regime {regime_str} (non BULL): Watchlist — L1 richiede trend rialzista'
                reason_codes.append('L2_WATCHLIST_REGIME')
            elif sma50_v is not None and current < sma50_v:
                # FONDAMENTA: prezzo deve stare sopra SMA50 (allineamento assoluto)
                suggested = 2
                reason    = f'Prezzo {current:.2f} < SMA50 {sma50_v:.2f}: Watchlist'
                reason_codes.append('L2_WATCHLIST_PRICE')
            else:
                # ✅ 7/7 condizioni + tutte le fondamenta (regime BULL, prezzo > SMA50, no kill switch)
                suggested = 1
                reason    = f'Ingresso L1 — 7/7 condizioni, regime {regime_str}, RSI {rsi_val:.0f}, ADX {adx_val:.0f}' if rsi_val and adx_val else 'Ingresso L1 — 7/7 condizioni'
                reason_codes.append('L1_ENTRY')

        else:
            suggested = 3
            reason    = 'Monitoraggio passivo'
            reason_codes.append('L3_MONITOR')

        # ── CALCOLO STOP LOSS DINAMICO (solo per L1) ───────────────────────────
        sl_data = None
        if suggested == 1:  # Entry in L1
            # Calcola ATR14
            atr_val = None
            if high is not None and low is not None:
                try:
                    atr_series = self._calculate_atr(high.astype(float), low.astype(float), close, period=14)
                    atr_val = self._fval(atr_series)
                except Exception:
                    atr_val = None

            # Calcola stop loss dinamico
            sl_data = self.calculate_stop_loss(
                current_price=current,
                atr=atr_val,
                family_config=self.p,
                entry_price=current,
                current_gain_pct=0.0,
                regime_str=regime_str
            )
            conditions['stop_loss_initial'] = round(sl_data['stop_loss_initial'], 4)
            conditions['stop_loss_reason'] = sl_data.get('trigger_reason', 'Entry L1 — SL iniziale')
            conditions['atr14'] = round(atr_val, 4) if atr_val else None

        return {
            'suggested_level': suggested,
            'current_level':   current_level,
            'level_change':    suggested != current_level,
            'reason':          reason,
            'reason_codes':    reason_codes,
            'conditions':      conditions,
            'buy_count':       buy_count,
            'buy_count_finale': round(buy_count_finale, 2),  # Score finale con penalità regime
            'regime_penalty':  round(regime_penalty, 2),
            'min_buy_required': min_buy_required,
            'stop_loss_initial': sl_data['stop_loss_initial'] if sl_data else None,
        }

    # ── STEP 3 — Funzioni L1 per portafoglio breve termine ─────────────────────

    def calculate_sl_suggerito_l1(self, entry_price: float, current_price: float,
                                   ema20: Optional[float]) -> Dict:
        """
        Calcola Stop Loss suggerito per posizioni L1 — formula ibrida.

        SCELTA CONFERMATA: Stop Loss ibrido C
        - Profitto < 2%  → SL largo = EMA20 − buffer_famiglia
        - Profitto ≥ 2%  → SL stretto = EMA20 − 1%

        Args:
            entry_price: Prezzo di carico della posizione
            current_price: Prezzo corrente
            ema20: Media mobile 20 periodi

        Returns:
            Dict con 'sl_suggerito', 'profit_pct', 'formula_used'
        """
        if ema20 is None or entry_price is None or entry_price <= 0:
            return {'sl_suggerito': None, 'profit_pct': 0, 'formula_used': None}

        profit_pct = (current_price - entry_price) / entry_price

        buffer = self.p.get('sl_buffer_wide', 0.020)  # default 2%

        if profit_pct < 0.02:
            # Profitto < 2% → SL largo
            sl = ema20 * (1 - buffer)
            formula = f'LARGO: EMA20 × (1 - {buffer:.1%})'
        else:
            # Profitto ≥ 2% → SL stretto (1%)
            sl = ema20 * 0.99
            formula = f'STRETTO: EMA20 × 0.99'

        return {
            'sl_suggerito': round(sl, 4),
            'profit_pct': round(profit_pct * 100, 2),
            'formula_used': formula
        }

    def calculate_stop_gain_dynamic(self, entry_price: float, current_price: float,
                                    ema20_series: Optional[pd.Series],
                                    family_params: Dict) -> Dict:
        """
        STEP 3 v3.0 — Stop Gain Dinamico basato sulla Pendenza (Slope) della EMA20

        Anziché decadimento temporale, il target si contrae se la pendenza della EMA20 diminuisce,
        catturando il momento esatto in cui il rally perde forza.

        Formula:
        current_target_pct = target_max_pct + (slope × slope_sensitivity)
        final_target_pct = max(current_target_pct, target_floor_pct)
        """
        if 'l1_stop_gain_dynamic' not in family_params:
            return {'trigger': False, 'target_pct': 0.0}

        params = family_params['l1_stop_gain_dynamic']
        target_max = params['target_max_pct']
        target_floor = params['target_floor_pct']
        slope_window = params['slope_window']
        slope_sensitivity = params['slope_sensitivity']

        # Calcolo guadagno attuale
        current_gain_pct = (current_price - entry_price) / entry_price

        # Calcolo slope della EMA20
        slope_pct = 0.0
        if ema20_series is not None and len(ema20_series) >= slope_window + 1:
            ema20_today = float(ema20_series.iloc[-1])
            ema20_past = float(ema20_series.iloc[-1 - slope_window])
            slope_pct = (ema20_today - ema20_past) / ema20_past

        # Formula dinamica: il target si abbassa se lo slope diminuisce
        dynamic_target = target_max + (slope_pct * slope_sensitivity)
        final_target_pct = max(dynamic_target, target_floor)

        # Trigger di uscita
        trigger = False
        reason = None
        if current_gain_pct >= final_target_pct:
            trigger = True
            reason = f"STOP_GAIN_DYNAMIC: Gain {current_gain_pct:.2%} >= Target {final_target_pct:.2%} (Slope: {slope_pct:.4f})"

        return {
            'trigger': trigger,
            'target_pct': final_target_pct,
            'current_gain_pct': current_gain_pct,
            'slope_pct': slope_pct,
            'reason': reason
        }

    def check_position_add(self, position_data: Dict, current_quality: int) -> Dict:
        """
        Valuta se aggiungere capitale a una posizione L1 parziale.

        Se la quality score migliora dopo l'entrata parziale → accumula progressivamente.

        Esempio:
          Entrato a 50% (quality 2/4) → quality sale a 3/4 → aggiungi 25% → totale 75%
          Posizione a 75% (quality 3/4) → quality sale a 4/4 → aggiungi 25% → totale 100%

        Args:
            position_data: Dict con 'entry_confidence' (% investito al momento entry)
            current_quality: Quality score attuale (2, 3, o 4)

        Returns:
            Dict con 'add', 'add_pct', 'new_total_pct', 'reason'
        """
        entry_confidence = position_data.get('entry_confidence', 1.0)

        # Map quality score → confidence
        confidence_map = {2: 0.50, 3: 0.75, 4: 1.00}
        current_confidence = confidence_map.get(current_quality, 1.0)

        # Se non c'è miglioramento, non aggiungere
        if current_confidence <= entry_confidence:
            return {
                'add': False,
                'reason': f'Segnale non migliorato (rimane {entry_confidence:.0%})',
            }

        # Calcola quanto aggiungere
        add_pct = current_confidence - entry_confidence
        new_total = entry_confidence + add_pct

        return {
            'add': True,
            'add_pct': round(add_pct, 2),
            'new_total_pct': round(new_total, 2),
            'reason': f'Quality migliora — Aggiungi {add_pct:.0%} (totale {new_total:.0%})',
        }

    def check_l1_entry_tiered(self, market_data: Dict) -> Dict:
        """
        SCELTA CONFERMATA (v5): Opzione 3 — Gate obbligatorio + Quality flessibile + Size dinamica.

        Gate strutturale (obbligatorio 2/2):
          1. price > EMA20
          2. EMA20 > SMA50 (regime BULL)

        Quality score (flessibile min 2/4):
          Q_R: RSI nel range famiglia
          Q_D: ADX >= 80% della soglia (con tolleranza)
          Q_M: MACD > 0 (momentum positivo)
          Q_P: Distanza EMA20 in range 0-2% (vicino alla media, non ai picchi)

        Size (confidenza dinamica):
          2/4 → 50% → posizione piccola
          3/4 → 75% → posizione media
          4/4 → 100% → posizione piena

        Args:
            market_data: Dict con 'price', 'ema20', 'sma50', 'rsi', 'adx', 'macd_h', 'dist_ema20'

        Returns:
            Dict con 'should_enter', 'confidence', 'gate_ok', 'quality_score', 'quality_detail', 'reason'
        """
        price = market_data.get('price', 0)
        ema20 = market_data.get('ema20')
        sma50 = market_data.get('sma50')
        rsi = market_data.get('rsi')
        adx = market_data.get('adx')
        macd_h = market_data.get('macd_h')
        dist_ema20 = market_data.get('dist_ema20', 0.0)  # in percentuale

        # ── GATE STRUTTURALE (obbligatorio 2/2) ────────────────────────────────
        gate_a = ema20 is not None and price > ema20
        gate_b = ema20 is not None and sma50 is not None and ema20 > sma50
        gate_ok = gate_a and gate_b

        if not gate_ok:
            return {
                'should_enter': False,
                'confidence': 0.0,
                'gate_ok': False,
                'quality_score': 0,
                'quality_detail': {},
                'reason': 'Gate KO — prezzo <= EMA20 oppure EMA20 <= SMA50',
            }

        # ── QUALITY SCORE (flessibile min 2/4) ─────────────────────────────────
        rsi_low = self.p.get('rsi_entry_low', 45)
        rsi_high = self.p.get('rsi_entry_high', 70)
        adx_min = self.p.get('adx_entry', 18)

        q_r = rsi is not None and rsi_low <= rsi <= rsi_high
        q_d = adx is not None and adx >= (adx_min * 0.80)  # tolleranza -20%
        q_m = macd_h is not None and macd_h > 0
        q_p = 0.0 <= dist_ema20 <= 2.0  # vicino alla media (max 2%)

        quality_score = int(q_r) + int(q_d) + int(q_m) + int(q_p)
        quality_detail = {
            'Q_R_rsi': q_r,
            'Q_D_adx': q_d,
            'Q_M_macd': q_m,
            'Q_P_dist': q_p,
        }

        if quality_score < 2:
            return {
                'should_enter': False,
                'confidence': 0.0,
                'gate_ok': True,
                'quality_score': quality_score,
                'quality_detail': quality_detail,
                'reason': f'Quality {quality_score}/4 — minimo 2 richiesto',
            }

        # ── SIZE DA CONFIDENZA ──────────────────────────────────────────────────
        confidence_map = {2: 0.50, 3: 0.75, 4: 1.00}
        confidence = confidence_map.get(quality_score, 1.00)

        return {
            'should_enter': True,
            'confidence': confidence,
            'gate_ok': True,
            'quality_score': quality_score,
            'quality_detail': quality_detail,
            'reason': f'Ingresso L1 tiered — quality {quality_score}/4 — size {int(confidence*100)}%',
        }

    def check_l1_entry_accelerated(self, market_data: Dict) -> Dict:
        """
        STEP 12+ — Trigger Gerarchico 2+2 (v7 — GERARCHIA INTELLIGENTE)

        Anticipa ingresso L1 con struttura logica gerarchica per qualità superiore.

        GATE STRUTTURALE — 2/2 OBBLIGATORI (non negoziabili):
          A (Allineamento): price > EMA20 (rally di breve è attivo)
          M (MACD Momentum): MACD > 0 (spinta volumetrica appena ripartita)

        VELOCITÀ — 2+/4 FLESSIBILI (almeno 2 su 4 richiesti):
          P (Prezzo > SMA50): prezzo sopra media a 50gg
          R (RSI in Range): RSI entro range family-specific
          D (ADX Direzionale): ADX > soglia minima (es. 15-18)
          X (allineamento eXteso): EMA20 > SMA50

        Formula: TRIGGER = (A ∧ M) ∧ (almeno 2 di {P, R, D, X})
        """
        close = market_data.get('close')
        ema20 = market_data.get('ema20')
        sma50 = market_data.get('sma50')
        macd_h = market_data.get('macd_h')
        rsi = market_data.get('rsi_14')
        adx = market_data.get('adx_14')

        if not close or not ema20 or not sma50 or macd_h is None:
            return {
                'should_enter': False,
                'entry_mode': 'ACCELERATED',
                'quality_score': 0,
                'velocity_count': 0,
                'reason': 'Dati insufficienti (manca EMA20, SMA50 o MACD)',
            }

        # ── GATE STRUTTURALE (2/2 obbligatori) ──────────────────────────────────
        gate_a_price_over_ema20 = close > ema20
        gate_m_macd_positive = macd_h > 0

        if not (gate_a_price_over_ema20 and gate_m_macd_positive):
            reason_missing = []
            if not gate_a_price_over_ema20:
                reason_missing.append('A(Price≤EMA20)')
            if not gate_m_macd_positive:
                reason_missing.append('M(MACD≤0)')

            return {
                'should_enter': False,
                'entry_mode': 'ACCELERATED',
                'quality_score': 0,
                'velocity_count': 0,
                'gate_ok': False,
                'reason': f"Gate KO: {', '.join(reason_missing)}",
            }

        # ── VELOCITÀ GERARCHICA (2+/4 flessibili) ───────────────────────────────
        velocity_count = 0
        velocity_detail = {}

        # P: Prezzo > SMA50
        vel_p = close > sma50
        if vel_p:
            velocity_count += 1
        velocity_detail['P_price>SMA50'] = vel_p

        # R: RSI in range family-specific
        rsi_low = self.p.get('rsi_entry_low', 45)
        rsi_high = self.p.get('rsi_entry_high', 70)
        vel_r = rsi is not None and rsi_low <= rsi <= rsi_high
        if vel_r:
            velocity_count += 1
        velocity_detail['R_rsi_in_range'] = vel_r

        # D: ADX > soglia minima (family-specific con tolleranza)
        adx_threshold = self.p.get('adx_entry', 18)
        adx_min_threshold = max(15, adx_threshold * 0.70)  # almeno 15, o 70% della soglia
        vel_d = adx is not None and adx >= adx_min_threshold
        if vel_d:
            velocity_count += 1
        velocity_detail[f'D_adx>={adx_min_threshold:.0f}'] = vel_d

        # X: EMA20 > SMA50 (allineamento esteso)
        vel_x = ema20 > sma50
        if vel_x:
            velocity_count += 1
        velocity_detail['X_ema20>sma50'] = vel_x

        # Richiedi almeno 2/4 parametri di velocità
        if velocity_count < 2:
            return {
                'should_enter': False,
                'entry_mode': 'ACCELERATED',
                'quality_score': velocity_count,
                'velocity_count': velocity_count,
                'velocity_detail': velocity_detail,
                'gate_ok': True,
                'reason': f'Velocity {velocity_count}/4 — minimo 2 richiesto',
            }

        # ── INGRESSO ACCELERATED OK (gerarchia 2+2 soddisfatta) ─────────────────
        # Confidence mappata a velocity_count
        confidence_map = {2: 0.60, 3: 0.80, 4: 1.00}
        confidence = confidence_map.get(velocity_count, 1.00)

        return {
            'should_enter': True,
            'entry_mode': 'ACCELERATED',
            'confidence': confidence,
            'quality_score': velocity_count,  # 2-4 su parametri flessibili
            'velocity_count': velocity_count,
            'velocity_detail': velocity_detail,
            'gate_ok': True,
            'reason': f'⚡ Gerarchia 2+2 OK — gate A∧M ✓ + velocity {velocity_count}/4 ✓ — size {int(confidence*100)}%',
        }

    # ── STEP 6 — Funzioni L0 per portafoglio medio/lungo termine ──────────────

    def check_l0_entry(self, close_series: pd.Series, rsi_14: Optional[float],
                       ema_fast_period: int = 10, famiglia: Optional[str] = None) -> Dict:
        """
        Controlla condizioni di ingresso L0 — Deep Recovery.

        SCELTA CONFERMATA: parametri pragmatici (sezione 3.1 del piano)

        4 condizioni TUTTE obbligatorie:
        1. Drawdown dai massimi 63 giorni ≥ dd_threshold per famiglia
        2. RSI scarico (non in panico) < rsi_max per famiglia
        3. Inversione confermata: prezzo > EMA fast E prezzo > max(N giorni precedenti)
        4. Recupero minimo dai minimi 10gg ≥ recovery_min_pct per famiglia

        Args:
            close_series: Serie prezzi di chiusura
            rsi_14: RSI a 14 periodi
            ema_fast_period: Periodo EMA veloce (es. 10, 8, ecc per famiglia)
            famiglia: Nome famiglia (usato fallback a self.famiglia)

        Returns:
            Dict con 'l0_signal', 'alert_only', 'conditions', 'dd_from_high', ecc
        """
        cfg = self.p.get('l0_entry', {})

        if not cfg.get('enabled', True):
            return {
                'l0_signal': False,
                'reason': 'L0 disabled for this family'
            }

        if len(close_series) < 63:
            return {
                'l0_signal': False,
                'reason': 'Insufficient data (<63 days)'
            }

        close_today = float(close_series.iloc[-1])
        close_series_f = close_series.astype(float)

        # ① Drawdown dai massimi 63 giorni
        high_63d = float(close_series_f.tail(63).max())
        dd_from_high = (high_63d - close_today) / high_63d if high_63d > 0 else 0
        dd_threshold = cfg.get('dd_threshold', 0.065)
        cond1 = dd_from_high >= dd_threshold

        # ② RSI scarico
        rsi_max = cfg.get('rsi_max', 45)
        cond2 = rsi_14 is not None and rsi_14 < rsi_max

        # ③ Inversione: prezzo > EMA fast E prezzo > max(N giorni precedenti)
        try:
            ema_fast = self._ema(close_series_f, ema_fast_period)
            ema_fast_val = self._fval(ema_fast)
            cond3a = ema_fast_val is not None and close_today > ema_fast_val
        except:
            cond3a = False
            ema_fast_val = None

        lookback = cfg.get('lookback_high_days', 3)
        if len(close_series) > lookback:
            prev_high = float(close_series_f.iloc[-(lookback+1):-1].max())
            cond3b = close_today > prev_high
        else:
            cond3b = False

        cond3 = cond3a and cond3b

        # ④ Recupero minimo dai minimi 10 giorni
        if len(close_series) >= 10:
            low_10d = float(close_series_f.tail(10).min())
            recovery_pct = (close_today - low_10d) / low_10d if low_10d > 0 else 0
        else:
            recovery_pct = 0

        recovery_min = cfg.get('recovery_min_pct', 0.015)
        cond4 = recovery_pct >= recovery_min

        # Segnale finale
        l0_signal = cond1 and cond2 and cond3 and cond4

        return {
            'l0_signal': l0_signal,
            'alert_only': True,  # Primi 30gg: solo alert, non auto-open
            'famiglia': self.famiglia or famiglia,
            'dd_from_high': round(dd_from_high * 100, 2),
            'rsi_current': round(rsi_14, 1) if rsi_14 else None,
            'recovery_pct': round(recovery_pct * 100, 2),
            'ema_fast': round(ema_fast_val, 4) if ema_fast_val else None,
            'conditions': {
                '①_drawdown': cond1,
                '②_rsi': cond2,
                '③a_ema_fast': cond3a,
                '③b_high_Ngg': cond3b,
                '④_recovery': cond4,
            },
            'reason': 'tutte_ok' if l0_signal else 'condizioni_mancanti',
        }

    def calculate_sl_suggerito_l0(self, entry_price: float, current_price: float) -> Dict:
        """
        Calcola Stop Loss suggerito per L0 — trailing progressivo.

        SCELTA CONFERMATA: Protezione capitale + graduale riduzione del rischio

        Formula:
        - Profitto < 5%   → SL = entry × 0.98  (non perdere il capitale)
        - Profitto 5-15%  → SL = entry × 1.01  (almeno in pareggio)
        - Profitto > 15%  → SL = entry × (1 + profitto - 0.08)
                             (proteggi circa metà del gain accumulato)

        Args:
            entry_price: Prezzo di carico
            current_price: Prezzo corrente

        Returns:
            Dict con 'sl_suggerito', 'profit_pct', 'stage'
        """
        if entry_price is None or entry_price <= 0:
            return {'sl_suggerito': None, 'profit_pct': 0, 'stage': None}

        profit_pct = (current_price - entry_price) / entry_price

        if profit_pct < 0.05:
            # < 5% → protezione stretta
            sl = entry_price * 0.98
            stage = 'protezione_capitale'
        elif profit_pct < 0.15:
            # 5-15% → almeno pareggio
            sl = entry_price * 1.01
            stage = 'pareggio'
        else:
            # > 15% → protezione metà gain
            sl = entry_price * (1 + profit_pct - 0.08)
            stage = 'protezione_guadagno'

        return {
            'sl_suggerito': round(sl, 4),
            'profit_pct': round(profit_pct * 100, 2),
            'stage': stage
        }

    def check_l0_exit(self, market_data: Dict, position_data: Dict) -> Dict:
        """
        Controlla regole di uscita per posizioni L0.

        SCELTA CONFERMATA: Ordine priorità
        1. F — Kill Switch: calo giornaliero ≤ -3%
        2. β — Bear Trap: RSI scende sotto 25 dopo ingresso
        3. α — Stop Assoluto: prezzo < minimo 30 giorni
        4. Trailing Stop: prezzo ≤ SL suggerito (progressivo)
        5. ε — Timeout: 45 giorni senza superare EMA20

        Promozione (NON è uscita — solo display):
        - γ: Prezzo > EMA20 → livello sale da L0 a L2 (ma posizione rimane in P_L0)

        Args:
            market_data: Dict con 'close', 'rsi_14', 'ema20', 'daily_change_pct', 'close_series'
            position_data: Dict con 'entry_price', 'entry_date'

        Returns:
            Dict con 'exit', 'reason', 'priority' se exit=True
        """
        price = market_data.get('close', 0)
        daily_chg = market_data.get('daily_change_pct', 0)
        rsi = market_data.get('rsi_14')
        ema20 = market_data.get('ema20')
        close_series = market_data.get('close_series')

        entry_price = position_data.get('entry_price', 0)

        # P1 — Kill Switch
        if daily_chg is not None and daily_chg <= -3.0:
            return {
                'exit': True,
                'reason': f'F_kill_switch: calo {daily_chg:.1f}%',
                'priority': 1
            }

        # P2 — Bear Trap: RSI < 25
        if rsi is not None and rsi < 25:
            return {
                'exit': True,
                'reason': f'β_bear_trap: RSI {rsi:.0f} < 25',
                'priority': 2
            }

        # P3 — Stop Assoluto: prezzo < minimo 30gg
        if close_series is not None and len(close_series) >= 30:
            min_30d = float(close_series.tail(30).min())
            if price < min_30d:
                return {
                    'exit': True,
                    'reason': f'α_stop_assoluto: prezzo {price:.2f} < min30 {min_30d:.2f}',
                    'priority': 3
                }

        # P4 — Trailing Stop
        sl_data = self.calculate_sl_suggerito_l0(entry_price, price)
        sl = sl_data.get('sl_suggerito')
        if sl is not None and price <= sl:
            return {
                'exit': True,
                'reason': f'trailing_stop: prezzo {price:.2f} ≤ SL {sl:.2f}',
                'priority': 4,
                'sl_level': sl
            }

        # P5 — Timeout 45 giorni senza EMA20
        days_no_recovery = position_data.get('days_no_recovery', 0)
        if ema20 is not None and price < ema20:
            days_no_recovery += 1
        else:
            days_no_recovery = 0

        if days_no_recovery >= 45:
            return {
                'exit': True,
                'reason': f'ε_timeout_45gg: {days_no_recovery} giorni senza EMA20',
                'priority': 5
            }

        # Promozione γ (NON è uscita — aggiorna solo il livello display)
        livello_display = 'L0'
        if ema20 is not None and price > ema20:
            livello_display = 'L2'
            if ema20 is not None and close_series is not None:
                sma50 = self._sma(close_series.astype(float), 50)
                sma50_v = self._fval(sma50)
                if sma50_v is not None and price > sma50_v:
                    livello_display = 'L1'  # Tecnicalmente L1 ma posizione rimane P_L0

        return {
            'exit': False,
            'reason': None,
            'days_no_recovery': days_no_recovery,
            'livello_display': livello_display
        }

    # ── Full analysis ──────────────────────────────────────────────────────────

    def analyze_etf(self, df: pd.DataFrame, current_level: int = 3, ticker: str = None) -> Dict:
        """
        Analisi tecnica completa di un ETF.

        Args:
            df: DataFrame con colonne Close (+ Open, High, Low, Volume se disponibili).
                Index deve essere Date.
            current_level: Livello attuale (0-3).
            ticker: Ticker ETF (usato per escludere ETF monetari da analisi tecnica).

        Returns:
            Dict con tutti gli indicatori, condizioni e livello suggerito.
        """
        # Money market ETF: skip technical analysis, assign to L3
        money_market_tickers = {'YCSH.DE', 'C3M.PA', 'CSH.PA', 'XEON.DE'}
        if ticker and ticker.upper() in money_market_tickers:
            price = float(df['Close'].iloc[-1]) if len(df) > 0 else None
            return {
                'current_price': price,
                'ema10': None, 'ema20': None, 'sma50': None, 'sma200': None,
                'rsi': None, 'adx': None, 'regime': None,
                'macd_histogram': None, 'macd_histogram_prev': None,
                'dist_ema20': None, 'ema20_slope': None,
                'days_above_ema20': 0, 'days_below_ema20': 0,
                'peak_price': price, 'drawdown_from_peak': 0.0,
                'pct_change_1d': None, 'pct_change_1w': None, 'pct_change_1m': None,
                'atr_normalized': None, 'drawdown_52w': None, 'price_range': None,
                'partial_exit': False,
                'suggested_level': 3, 'level_change': False,
                'level_reason': 'ETF monetario — monitoraggio passivo (L3)',
                'conditions': {}, 'buy_count': 0,
                'l0_entry': False, 'l0_exit_rule': None,
                'data_status': 'money_market_etf',
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            }

        if len(df) < self.ema20_period:
            price = float(df['Close'].iloc[-1]) if len(df) > 0 else None
            return {
                'current_price': price,
                'ema10': None, 'ema20': None, 'sma50': None, 'sma200': None,
                'rsi': None, 'adx': None, 'regime': None,
                'macd_histogram': None, 'macd_histogram_prev': None,
                'dist_ema20': None, 'ema20_slope': None,
                'days_above_ema20': 0, 'days_below_ema20': 0,
                'peak_price': price, 'drawdown_from_peak': 0.0,
                'pct_change_1d': None, 'pct_change_1w': None, 'pct_change_1m': None,
                'atr_normalized': None, 'drawdown_52w': None, 'price_range': None,
                'partial_exit': False,
                'suggested_level': current_level, 'level_change': False,
                'level_reason': f'Dati insufficienti: {len(df)} giorni',
                'conditions': {}, 'buy_count': 0,
                'l0_entry': False, 'l0_exit_rule': None,
                'data_status': 'insufficient',
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            }

        close = df['Close'].astype(float)
        # Clean data: remove NaN/None which can cause comparison errors
        close = close.dropna()
        if len(close) < self.ema20_period:
            price = float(close.iloc[-1]) if len(close) > 0 else None
            return {
                'current_price': price,
                'ema10': None, 'ema20': None, 'sma50': None, 'sma200': None,
                'rsi': None, 'adx': None, 'regime': None,
                'macd_histogram': None, 'macd_histogram_prev': None,
                'dist_ema20': None, 'ema20_slope': None,
                'days_above_ema20': 0, 'days_below_ema20': 0,
                'peak_price': price, 'drawdown_from_peak': 0.0,
                'pct_change_1d': None, 'pct_change_1w': None, 'pct_change_1m': None,
                'atr_normalized': None, 'drawdown_52w': None, 'price_range': None,
                'partial_exit': False,
                'suggested_level': current_level, 'level_change': False,
                'level_reason': f'Dati insufficienti dopo pulizia: {len(close)} giorni validi',
                'conditions': {}, 'buy_count': 0,
                'l0_entry': False, 'l0_exit_rule': None,
                'data_status': 'insufficient_after_cleanup',
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            }

        has_ohlc = all(c in df.columns for c in ['Open', 'High', 'Low'])
        high = df['High'].astype(float).dropna() if has_ohlc else None
        low  = df['Low'].astype(float).dropna() if has_ohlc else None

        # L0 check
        l0 = self.suggest_level_0(close, high if high is not None else close, low if low is not None else close, current_level)

        # L1/L2/L3 check
        level = self.suggest_level(close, current_level, high=high, low=low)
        lc = level['conditions']

        # If L0 entry → override
        if l0.get('l0_entry') and current_level != 0:
            level['suggested_level'] = 0
            level['level_change']    = True
            level['reason']          = f"L0 Deep Recovery: {l0.get('distance_from_peak', '?')}% dal picco"
            level['reason_codes']    = ['L0_ENTRY']

        # If in L0 and exit triggered → override
        if current_level == 0 and l0.get('l0_exit_rule'):
            level['suggested_level'] = 2
            level['level_change']    = True
            level['reason']          = f"Uscita L0 [{l0['l0_exit_rule']}]: {l0.get('l0_exit_trigger', '')}"
            level['reason_codes']    = [f"L0_EXIT_{l0['l0_exit_rule'].upper()}"]

        return {
            'current_price':       round(float(close.iloc[-1]), 4),
            'ema10':               lc.get('ema10_current'),
            'ema20':               lc.get('ema20_current'),
            'sma50':               lc.get('sma50_current'),
            'sma200':              lc.get('sma200_current'),
            'rsi':                 lc.get('rsi'),
            'adx':                 lc.get('adx'),
            'regime':              lc.get('regime'),  # NUOVO: regime a 3 stati
            'macd_histogram':      lc.get('macd_histogram'),
            'macd_histogram_prev': lc.get('macd_histogram_prev'),
            'dist_ema20':          lc.get('dist_ema20'),
            'ema20_slope':         lc.get('ema20_slope'),
            'days_above_ema20':    lc.get('days_above_ema20', 0),
            'days_below_ema20':    lc.get('days_below_ema20', 0) if 'days_below_ema20' in lc else 0,
            'peak_price':          lc.get('peak_price'),
            'drawdown_from_peak':  lc.get('drawdown_from_peak', 0.0),
            'pct_change_1d':       lc.get('pct_1d'),
            'pct_change_1w':       lc.get('pct_1w'),
            'pct_change_1m':       lc.get('pct_1m'),
            'atr_normalized':      lc.get('atr_normalized'),
            'drawdown_52w':        lc.get('drawdown_52w'),
            'price_range':         lc.get('price_range'),
            'partial_exit':        lc.get('partial_exit', False),
            'suggested_level':     level['suggested_level'],
            'level_change':        level['level_change'],
            'level_reason':        level['reason'],
            'conditions':          lc,
            'buy_count':           level.get('buy_count', 0),
            'l0_entry':            l0.get('l0_entry', False),
            'l0_exit_rule':        l0.get('l0_exit_rule'),
            'l0_data':             l0,
            'data_status':         'ok',
            'analysis_date':       datetime.now().strftime('%Y-%m-%d %H:%M'),
        }

    # ── L0 ENGINE: Filtro di Regime + Doppio Percorso ──────────────────────────

    def l0_detect_regime_filter(self, prices: pd.Series, sma200: Optional[float],
                                atr_60: Optional[float], volume_20ma: Optional[float]) -> Dict:
        """Determina se regime è adatto a L0 (bear market o flash crash)."""
        if prices is None or len(prices) < 50 or sma200 is None:
            return {'regime_suitable': False, 'regime_type': 'none', 'days_below_sma200': 0, 'recent_dd_pct': 0.0}

        current_price = prices.iloc[-1]
        days_below_sma200 = 0
        for i in range(len(prices) - 1, -1, -1):
            if prices.iloc[i] < sma200:
                days_below_sma200 += 1
            else:
                break

        lookback_dd = min(60, len(prices))
        recent_high = prices.iloc[-lookback_dd:].max()
        recent_dd_pct = (recent_high - current_price) / recent_high if recent_high > 0 else 0.0

        config = self.p.get('l0_regime', {})
        regime_min_days = config.get('regime_min_days_below_sma200', 10)
        slow_path_active = days_below_sma200 >= regime_min_days

        fast_path_active = False
        if atr_60 and atr_60 > 0:
            dd_normalized = recent_dd_pct / (atr_60 / current_price) if current_price > 0 else 0
            flash_zscore = config.get('flash_crash_zscore_threshold', 4.0)
            fast_path_active = dd_normalized >= flash_zscore

        regime_type = 'fast_crash' if fast_path_active else ('slow_bear' if slow_path_active else 'none')

        return {
            'regime_suitable': slow_path_active or fast_path_active,
            'regime_type': regime_type,
            'days_below_sma200': days_below_sma200,
            'recent_dd_pct': recent_dd_pct
        }

    # ── L1 ENGINE: Entrata L1 (7 Condizioni Tutte Obbligatorie) ──────────────────

    def l1_check_7_conditions(self, prices: pd.Series, ema20: Optional[float],
                              sma50: Optional[float], rsi_14: Optional[float],
                              adx_14: Optional[float], macd_histogram: Optional[float],
                              macd_histogram_prev: Optional[float], volume: Optional[float],
                              atr_14: Optional[float], high_series: pd.Series, low_series: pd.Series,
                              volume_20ma: Optional[float], days_above_ema20: int) -> Dict:
        """Logica L1 semplificata v4.0: 7 condizioni tutte obbligatorie."""
        if prices is None or len(prices) < 20 or ema20 is None:
            return {
                'entry_l1': False, 'level': 3,
                'conditions': {k: False for k in ['gate_a', 'gate_m', 'alignment_p', 'rsi_r', 'adx_d', 'macd_momentum', 'space_residuo']},
                'space_detail': {}, 'confidence': 0.0
            }

        current_price = prices.iloc[-1]

        gate_a = current_price > ema20
        gate_m = (macd_histogram is not None) and (macd_histogram > 0)

        if not (gate_a and gate_m):
            return {
                'entry_l1': False, 'level': 2,
                'conditions': {'gate_a': gate_a, 'gate_m': gate_m, 'alignment_p': False, 'rsi_r': False, 'adx_d': False, 'macd_momentum': False, 'space_residuo': False},
                'space_detail': {}, 'confidence': 0.0
            }

        alignment_p = (sma50 is not None) and (current_price > sma50)
        rsi_low, rsi_high = self.p.get('rsi_entry_low'), self.p.get('rsi_entry_high')
        rsi_r = (rsi_14 is not None) and (rsi_low <= rsi_14 <= rsi_high)
        adx_entry = self.p.get('adx_entry')
        adx_d = (adx_14 is not None) and (adx_entry is not None) and (adx_14 >= adx_entry)
        dist_ema20_pct = abs(current_price - ema20) / ema20 if ema20 > 0 else 0.99
        macd_momentum = (macd_histogram_prev is not None) and ((macd_histogram > macd_histogram_prev) or (dist_ema20_pct < 0.02))

        if not (alignment_p and rsi_r and adx_d and macd_momentum):
            return {
                'entry_l1': False, 'level': 2,
                'conditions': {'gate_a': gate_a, 'gate_m': gate_m, 'alignment_p': alignment_p, 'rsi_r': rsi_r, 'adx_d': adx_d, 'macd_momentum': macd_momentum, 'space_residuo': False},
                'space_detail': {}, 'confidence': 0.0
            }

        space_check = self.l1_check_space_residuo_minimo(current_price, high_series, low_series, atr_14, volume, volume_20ma)
        entry_l1 = space_check['valid']

        return {
            'entry_l1': entry_l1, 'level': 1 if entry_l1 else 2,
            'conditions': {'gate_a': gate_a, 'gate_m': gate_m, 'alignment_p': alignment_p, 'rsi_r': rsi_r, 'adx_d': adx_d, 'macd_momentum': macd_momentum, 'space_residuo': space_check['valid']},
            'space_detail': space_check, 'confidence': 1.0 if entry_l1 else 0.0
        }

    def l1_check_space_residuo_minimo(self, current_price: float, high_series: pd.Series,
                                      low_series: pd.Series, atr_14: Optional[float],
                                      volume: Optional[float], volume_20ma: Optional[float]) -> Dict:
        """7a condizione: spazio residuo minimo."""
        if current_price <= 0:
            return {'valid': False, 'method': 'none', 'space_pct': 0.0, 'threshold': 0.0}

        config = self.p.get('l1_space_residuo', {})
        min_reward_pct = config.get('min_reward_pct', 0.03)
        resistance_lookback = config.get('resistance_lookback_days', 30)
        atr_mult = config.get('atr_multiplier', 1.8)

        lookback_res = min(resistance_lookback, len(high_series))
        resistance_high = high_series.iloc[-lookback_res:].max() if lookback_res > 0 else current_price
        dist_resistance = (resistance_high - current_price) / current_price if resistance_high > 0 else 0

        dist_atr = (atr_14 * atr_mult) / current_price if atr_14 and atr_14 > 0 else 0
        best_space = max(dist_resistance, dist_atr)
        best_method = 'resistance' if dist_resistance >= dist_atr else 'atr'

        if best_space >= min_reward_pct:
            return {'valid': True, 'method': best_method, 'space_pct': best_space, 'threshold': min_reward_pct}

        return {'valid': False, 'method': 'none', 'space_pct': best_space, 'threshold': min_reward_pct}

    # ── L2 ENGINE: Readiness Score (PRIORITÀ 3) ──────────────────────────────────

    def l2_calculate_readiness_score(self, prices: pd.Series, ema20: Optional[float],
                                     rsi_14: Optional[float], adx_14: Optional[float],
                                     volume: Optional[float], volume_20ma: Optional[float],
                                     days_above_ema20: int,
                                     ema20_series: Optional[pd.Series] = None,
                                     adx_series: Optional[pd.Series] = None,
                                     macd_histogram: Optional[float] = None) -> float:
        """
        PRIORITÀ 3 — Calcola L2 Readiness Score (0-100) con anti-flickering.

        6 componenti di score (pesi):
        1. dist_ema20_score (20%): prezzo converge verso 0-4% da EMA20
        2. rsi_approach_score (20%): RSI sale verso range L1 entry
        3. adx_rising_score (20%): ADX in salita (trend strength)
        4. macd_histogram_score (20%): MACD in aumento
        5. volume_expansion_score (10%): volume > 1.2x media
        6. days_above_ema20_partial (10%): contatore parziale

        Anti-flickering:
        - Isteresi: enter @ 70, exit @ 60
        - Smoothing: EMA 3-giorni sul raw score
        - Jump override: se delta > 25 e raw ≥ 70 → bypassa EMA
        - Hard-reset: reset EMA al valore grezzo nei jump
        """
        if prices is None or len(prices) < 20 or ema20 is None:
            return 0.0

        current_price = float(prices.iloc[-1])

        # ── COMPONENTE 1: Distanza EMA20 (20%) ────────────────────────
        ema_dist_max = self.p.get('ema_dist_max', 4.0)
        dist_pct = ((current_price - ema20) / ema20 * 100) if ema20 > 0 else 0
        if 0 <= dist_pct <= ema_dist_max:
            dist_score = (1.0 - (dist_pct / ema_dist_max)) * 20
        else:
            dist_score = 0

        # ── COMPONENTE 2: RSI approach (20%) ──────────────────────────
        rsi_entry_low = self.p.get('rsi_entry_low', 45)
        rsi_approach_margin = self.p.get('rsi_approach_margin', 5)
        if rsi_14 and (rsi_entry_low - rsi_approach_margin) <= rsi_14 <= rsi_entry_low:
            rsi_score = ((rsi_14 - (rsi_entry_low - rsi_approach_margin)) / rsi_approach_margin) * 20
        else:
            rsi_score = 0

        # ── COMPONENTE 3: ADX rising (20%) ────────────────────────────
        adx_trend_days = self.p.get('adx_trend_days', 5)
        adx_score = 0
        if adx_series is not None and len(adx_series) >= adx_trend_days:
            adx_trend = adx_series.iloc[-adx_trend_days:].values
            if adx_14 and adx_trend[-1] > adx_trend[0]:  # ADX rising
                adx_score = 20

        # ── COMPONENTE 4: MACD histogram (20%) ────────────────────────
        macd_score = 0
        if macd_histogram is not None and macd_histogram > 0:
            macd_score = 20

        # ── COMPONENTE 5: Volume expansion (10%) ──────────────────────
        volume_ratio_threshold = self.p.get('volume_ratio_threshold', 1.2)
        volume_score = 0
        if volume and volume_20ma and volume_20ma > 0:
            vol_ratio = volume / volume_20ma
            if vol_ratio >= volume_ratio_threshold:
                volume_score = 10

        # ── COMPONENTE 6: Days above EMA20 partial (10%) ───────────────
        days_target = self.p.get('days_above_ema', 3)
        days_score = min((days_above_ema20 / days_target), 1.0) * 10

        # ── Raw score (somma ponderata) ────────────────────────────────
        raw_score = dist_score + rsi_score + adx_score + macd_score + volume_score + days_score
        raw_score = max(0, min(100, raw_score))

        # ── ANTI-FLICKERING: Isteresi + Smoothing ──────────────────────
        # Nota: in questo metodo stateless, restituiamo raw_score.
        # Lo smoothing EMA + hard-reset dovrebbe essere gestito in monitor.py
        # con persistenza dello stato smoothed_score per ogni ETF.
        # Per ora, restituiamo raw_score e lasciam o al monitor la gestione dello stato.

        return raw_score

    # ── Utility ────────────────────────────────────────────────────────────────

    @staticmethod
    def category_to_etf_type(categoria: str) -> str:
        """Mappa la categoria Excel al tipo ETF per il profilo di analisi.

        Ordine di priorità critico:
          1. bond     — prima di tutto: 'Obbligazionari - Emergenti' contiene 'emer'
                        ma è bond, non equity emerging.
          2. sector   — prima di commodity: 'Settoriale - Energia/Materie Prime'
                        è equity settoriale, non commodity future.
          3. emerging — dopo aver escluso bond e settoriali.
          4. commodity — solo ETF su materie prime fisiche/future.
          5. thematic — strategie speciali, volatilità, leveraged, opzioni.
          6. default  — equity_developed (azionario sviluppato, short, style, ecc.)

        Short ETF rimangono equity_developed: il filtro SMA200 li blocca in bear market,
        che è il comportamento più prudente per strumenti speculativi inversi.
        """
        if not categoria:
            return 'equity_developed'
        cat = categoria.lower()

        # 1. BOND — controlla prima per evitare che 'Obbligazionari - Emergenti'
        #    venga catturato dalla regola emerging (contiene 'emer')
        if any(k in cat for k in ('obblig', 'bond', 'reddito', 'treasury', 'government',
                                   'corporate', 'credit', 'liquidit', 'monetar',
                                   'titoli di stato', 'titoli stato', 'inflation',
                                   'governativ', 'aggregati', 'high yield')):
            return 'bond'

        # 2. SETTORIALI — controlla prima di commodity per evitare che
        #    'Settoriale - Energia' e 'Settoriale - Materie Prime' vadano a commodity
        if any(k in cat for k in ('settori', 'sector', 'real estate', 'reit',
                                   'infrastruttur', 'finanz', 'tech')):
            return 'equity_sector'

        # 3. MERCATI EMERGENTI
        if any(k in cat for k in ('emer', 'cina', 'india', 'brasile', 'vietnam',
                                   'africa', 'latin', "dell'est", 'middle east',
                                   'sudamerica', 'paesi em')):
            return 'equity_emerging'

        # 4. COMMODITY — materie prime fisiche e future (non settori azionari)
        if any(k in cat for k in ('materie', 'gold', 'oro', 'petrolio', 'commodit',
                                   'metall', 'energia', 'indice di comm')):
            return 'commodity'

        # 5. TEMATICI e strategie speciali
        if any(k in cat for k in ('tematic', 'clean', 'biotech', 'robot', 'innov',
                                   'megatr', 'buywrite', 'covered call', 'protective',
                                   'private equity', 'leveraged', 'leva',
                                   'volat', 'struttur')):
            return 'thematic'

        # 6. Default: azionario sviluppato
        #    (include Short, Style, Fondamentali, Mid/Small Cap, Far East, gestione attiva)
        return 'equity_developed'
