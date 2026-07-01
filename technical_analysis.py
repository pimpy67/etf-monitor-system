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

    # ── L0 Deep Recovery ──────────────────────────────────────────────────────

    def suggest_level_0(self, prices: pd.Series, current_level: int) -> Dict:
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

        l0_rsi_thr = self.p['l0_rsi_max']

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
        peak_price         = float(prices.max())
        result['peak_price']  = round(peak_price, 4)
        result['peak_days']   = len(prices)
        dist_peak              = (current - peak_price) / peak_price * 100
        result['distance_from_peak'] = round(dist_peak, 2)

        # Cond 1: drawdown check (skip if not applicable for this family)
        cond1 = self.p['l0_drawdown'] is not None and dist_peak <= -self.p['l0_drawdown']
        cond2 = rsi_val < l0_rsi_thr
        result['rsi_oversold'] = cond2
        cond3 = self._detect_positive_divergence(prices, rsi)
        result['divergence'] = cond3
        rsi_rec    = self._detect_rsi_recovery(rsi, oversold=l0_rsi_thr, recovery=32.0)
        micro_brk  = self._detect_micro_breakout(prices)
        cond4      = rsi_rec or micro_brk
        result['rsi_recovery']   = rsi_rec
        result['micro_breakout'] = micro_brk

        entry_ok = cond1 and cond2 and cond3 and cond4
        if entry_ok and kill_switch:
            result['l0_entry']      = False
            result['reason_codes']  = ['KILL_SWITCH', 'L0_ENTRY_BLOCKED']
        elif entry_ok:
            result['l0_entry']      = True
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
        is_bond = self.etf_type == 'bond'
        is_equity_family = self.etf_type in self.EQUITY_FAMILY or self.etf_type == 'commodity'

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

            elif rsi_val is not None and rsi_val > p['rsi_overbought']:
                # D — Eccesso RSI: uscita parziale 90% (piede dentro)
                partial_exit = True

        # ── 6 condizioni L1 ───────────────────────────────────────────────────
        # Determina regime a 3 stati
        lateral_band = p.get('lateral_band', 0.01)
        regime_str = self.calculate_regime(ema20_v, sma50_v, lateral_band)
        regime_ok = regime_str == "BULL"  # L1 richiede regime BULL

        # 1. Allineamento: price > EMA20 > SMA50 (+ regime SMA200 come filtro aggiuntivo)
        price_ema_ok  = ema20_v is not None and current > ema20_v
        ema_sma50_ok  = ema20_v is not None and sma50_v is not None and ema20_v > sma50_v
        regime_ok_mm200 = True
        if p['mm200_filter'] and sma200_v is not None:
            regime_ok_mm200 = current > sma200_v
        allineamento  = price_ema_ok and ema_sma50_ok and regime_ok and regime_ok_mm200

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

        conditions = {
            'allineamento_ok':    allineamento,
            'persistenza_ok':     persistenza,
            'rsi_ok':             rsi_ok,
            'distance_ok':        dist_ok,
            'adx_ok':             adx_ok,
            'macd_ok':            macd_ok,
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
        }
        buy_count = sum([allineamento, persistenza, rsi_ok, dist_ok, adx_ok, macd_ok])

        # ── Determina livello ──────────────────────────────────────────────────
        reason_codes = []

        # Min buy count richiesto per L1 (dipende dalla famiglia)
        min_buy_required = self.p.get('min_buy_count', 6)

        if current_level == 1:
            if exit_rule:
                conditions['exit_rule']    = exit_rule
                conditions['exit_trigger'] = exit_rule
                suggested = 3
                reason    = f'Uscita L1 — {exit_rule}'
                reason_codes.append('L1_EXIT')
            elif buy_count < min_buy_required or regime_str != "BULL":
                # Demote if no longer meets min conditions or regime changed
                conditions['exit_rule']    = None
                suggested = 2
                reason    = f'Downgrade L1→L2: {buy_count}/{min_buy_required} condizioni, regime {regime_str}'
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

        elif allineamento and persistenza and rsi_ok and dist_ok and adx_ok and macd_ok:
            # L1 richiede regime BULL (non accetta LATERALE o BEAR)
            if regime_str != "BULL":
                suggested = 2
                reason    = f'Watchlist (regime {regime_str}): {buy_count}/6 condizioni L1'
                reason_codes.append('L2_REGIME_LATERAL' if regime_str == "LATERALE" else 'L2_REGIME_BEAR')
            elif kill_switch:
                suggested = current_level
                chg_str = f'{daily_chg:.1f}' if daily_chg is not None else '?'
                reason    = f'Kill Switch [{chg_str}%]: nuovo ingresso L1 bloccato'
                reason_codes.extend(['KILL_SWITCH', 'L1_ENTRY_BLOCKED'])
            else:
                suggested = 1
                regime_note = '' if regime_ok else ' (no SMA200)'
                macd_note   = '↑' if (macd_hp is not None and macd_h is not None and macd_h > macd_hp) else '~'
                # Safe formatting with None checks
                rsi_str = f'{rsi_val:.0f}' if rsi_val is not None else '?'
                dist_str = f'{dist_ema20:.1f}' if dist_ema20 is not None else '?'
                adx_str = f'{adx_val:.0f}' if adx_val is not None else '?'
                reason = (
                    f'L1 Trend Sicuro (regime {regime_str}): EMA20>SMA50 ✓, {days_above_ema20}gg sopra EMA20 ✓, '
                    f'RSI {rsi_str} ✓, dist {dist_str}% ✓, ADX {adx_str} ✓, '
                    f'MACD {macd_note} ✓{regime_note}'
                )
                reason_codes.append('L1_ENTRY')

        elif days_above_ema20 >= p['days_above_ema'] or (ema20_v and sma50_v and ema20_v > sma50_v):
            suggested = 2
            reason    = f'Watchlist: {buy_count}/6 condizioni L1 ({days_above_ema20}gg sopra EMA20)'
            reason_codes.append('L2_WATCHLIST')

        elif price_ema_ok:
            suggested = 2
            reason    = f'Prezzo sopra EMA20 da {days_above_ema20} giorni'
            reason_codes.append('L2_WATCHLIST')

        else:
            suggested = 3
            reason    = 'Monitoraggio passivo'
            reason_codes.append('L3_MONITOR')

        return {
            'suggested_level': suggested,
            'current_level':   current_level,
            'level_change':    suggested != current_level,
            'reason':          reason,
            'reason_codes':    reason_codes,
            'conditions':      conditions,
            'buy_count':       buy_count,
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
        l0 = self.suggest_level_0(close, current_level)

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
