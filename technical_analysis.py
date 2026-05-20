"""
technical_analysis.py - Analisi tecnica ETF
=============================================
Schema: EMA20 (fast) + SMA50 (medium) + SMA200 (regime filter)
ADX14 reale (da OHLCV) + RSI14

L0 Deep Recovery: ETF in drawdown profondo con segnali di rimbalzo
L1 Trend Sicuro: 5 condizioni (allineamento, persistenza+slope, RSI, distanza, ADX)
L2 Watchlist: allineamento parziale
L3 Universo: monitoraggio passivo
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional


class ETFTechnicalAnalyzer:
    """Analisi tecnica ETF con EMA20 + SMA50 + SMA200 + ADX + RSI"""

    # Profili parametri per tipo ETF
    PROFILES = {
        'equity_developed': {
            'rsi_entry_low': 50, 'rsi_entry_high': 65,
            'rsi_exit_min': 40,  'rsi_overbought': 78,
            'ema_dist_max': 4.0, 'adx_entry': 20,
            'l0_drawdown': 15.0, 'l0_rsi_max': 35,
            'days_above_ema': 3, 'mm200_filter': True,
        },
        'equity_sector': {
            'rsi_entry_low': 50, 'rsi_entry_high': 68,
            'rsi_exit_min': 38,  'rsi_overbought': 80,
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
            'rsi_entry_low': 48, 'rsi_entry_high': 65,
            'rsi_exit_min': 38,  'rsi_overbought': 75,
            'ema_dist_max': 5.0, 'adx_entry': 22,
            'l0_drawdown': 20.0, 'l0_rsi_max': 40,
            'days_above_ema': 3, 'mm200_filter': False,
        },
        'bond': {
            'rsi_entry_low': 48, 'rsi_entry_high': 62,
            'rsi_exit_min': 42,  'rsi_overbought': 70,
            'ema_dist_max': 2.0, 'adx_entry': 15,
            'l0_drawdown': 8.0,  'l0_rsi_max': 38,
            'days_above_ema': 3, 'mm200_filter': False,
        },
        'thematic': {
            'rsi_entry_low': 50, 'rsi_entry_high': 68,
            'rsi_exit_min': 38,  'rsi_overbought': 80,
            'ema_dist_max': 6.0, 'adx_entry': 22,
            'l0_drawdown': 20.0, 'l0_rsi_max': 40,
            'days_above_ema': 3, 'mm200_filter': True,
        },
    }
    PROFILES['equity'] = PROFILES['equity_developed']  # alias

    EQUITY_FAMILY = frozenset({'equity_developed', 'equity_sector', 'equity_emerging', 'thematic', 'equity'})

    def __init__(self, etf_type: str = 'equity_developed'):
        self.etf_type = etf_type if etf_type in self.PROFILES else 'equity_developed'
        self.p = self.PROFILES[self.etf_type]

        self.ema20_period  = 20
        self.sma50_period  = 50
        self.sma200_period = 200
        self.rsi_period    = 14
        self.adx_period    = 14
        self.macd_fast     = 12
        self.macd_slow     = 26
        self.macd_signal_p = 9

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
        ri  = int(rp.values.argmin())
        r_p = float(rp.iloc[ri]);  r_r = float(rr.iloc[ri])
        op  = pw.iloc[:-recent];   or_ = rw.iloc[:-recent]
        if len(op) < 5:
            return False
        oi  = int(op.values.argmin())
        o_p = float(op.iloc[oi]);  o_r = float(or_.iloc[oi])
        return (r_p < o_p) and (r_r > o_r)

    def _detect_rsi_recovery(self, rsi: pd.Series, oversold: float = 30.0,
                              recovery: float = 32.0, lookback: int = 10) -> bool:
        rc = rsi.dropna()
        if len(rc) < 3:
            return False
        recent = rc.tail(lookback)
        return (any(v < oversold for v in recent.iloc[:-1]) and
                float(recent.iloc[-1]) > recovery)

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
        current = float(prices.iloc[-1])

        result['rsi']           = round(rsi_val, 1)
        result['ema20_current'] = round(ema20_v, 4) if ema20_v else None
        result['current_price'] = round(current, 4)

        # Kill switch: crollo giornaliero >= 3%
        kill_switch = False
        if len(prices) >= 2 and float(prices.iloc[-2]) != 0:
            daily_chg = (float(prices.iloc[-1]) - float(prices.iloc[-2])) / float(prices.iloc[-2]) * 100
            kill_switch = daily_chg <= -3.0
            result['daily_change_pct'] = round(daily_chg, 2)
        result['kill_switch'] = kill_switch

        n_panic = min(30, len(prices))
        result['panic_low'] = float(prices.iloc[-n_panic:].min())

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

        cond1 = dist_peak <= -self.p['l0_drawdown']
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

        5 condizioni L1:
          1. Allineamento: price > EMA20 > SMA50 (+ price > SMA200 se disponibile)
          2. Persistenza: >= 3gg sopra EMA20 + slope EMA20 positivo
          3. RSI: nel range target per l'asset class
          4. Distanza da EMA20: <= ema_dist_max
          5. ADX: >= adx_entry

        Exit L1 (6 regole):
          A: price < EMA20 (stop loss)
          B: EMA20 < SMA50 (death cross)
          C: RSI < rsi_exit_min (momentum perso)
          D: RSI > rsi_overbought (take profit)
          E: ADX < 15 (trend esaurito)
          F: crollo giornaliero >= 3% (kill switch)
        """
        p = self.p

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
        if len(prices) >= 2 and float(prices.iloc[-2]) != 0:
            daily_chg   = (float(prices.iloc[-1]) - float(prices.iloc[-2])) / float(prices.iloc[-2]) * 100
            kill_switch = daily_chg <= -3.0

        close   = prices.astype(float)
        current = float(close.iloc[-1])

        ema20  = self._ema(close, self.ema20_period)
        sma50  = self._sma(close, self.sma50_period) if len(close) >= self.sma50_period else None
        sma200 = self._sma(close, self.sma200_period) if len(close) >= self.sma200_period else None

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

        # ── Exit rules (se gia' in L1) ─────────────────────────────────────
        exit_rule = None
        if current_level == 1:
            if kill_switch:
                exit_rule = f'Regola F — Kill Switch: calo {daily_chg:.1f}% (>= 3%)'
            elif days_below_ema20 >= 3:
                exit_rule = f'Regola A — Stop Loss: prezzo sotto EMA20 da {days_below_ema20}gg'
            elif ema20_v and sma50_v and ema20_v < sma50_v:
                exit_rule = f'Regola B — Death Cross: EMA20 {ema20_v:.2f} < SMA50 {sma50_v:.2f}'
            elif rsi_val is not None and rsi_val < p['rsi_exit_min']:
                exit_rule = f'Regola C — Momentum: RSI {rsi_val:.0f} < {p["rsi_exit_min"]}'
            elif rsi_val is not None and rsi_val > p['rsi_overbought']:
                exit_rule = f'Regola D — Overbought: RSI {rsi_val:.0f} > {p["rsi_overbought"]}'
            elif adx_val is not None and adx_val < 15:
                exit_rule = f'Regola E — Trend: ADX {adx_val:.0f} < 15'

        # ── 5 condizioni L1 ───────────────────────────────────────────────────
        # 1. Allineamento: price > EMA20 > SMA50 (+ regime SMA200)
        price_ema_ok  = ema20_v is not None and current > ema20_v
        ema_sma50_ok  = ema20_v is not None and sma50_v is not None and ema20_v > sma50_v
        regime_ok     = True
        if p['mm200_filter'] and sma200_v is not None:
            regime_ok = current > sma200_v
        allineamento  = price_ema_ok and ema_sma50_ok and regime_ok

        # 2. Persistenza: >= 3gg sopra EMA20 + slope EMA20 positivo
        persistenza   = days_above_ema20 >= p['days_above_ema'] and ema20_slope > 0

        # 3. RSI nel range target
        rsi_ok        = rsi_val is not None and p['rsi_entry_low'] <= rsi_val <= p['rsi_entry_high']

        # 4. Distanza da EMA20 entro limite
        dist_ok       = 0 <= dist_ema20 <= p['ema_dist_max']

        # 5. ADX sopra soglia
        adx_ok        = adx_val is not None and adx_val >= p['adx_entry']

        conditions = {
            'allineamento_ok':    allineamento,
            'persistenza_ok':     persistenza,
            'rsi_ok':             rsi_ok,
            'distance_ok':        dist_ok,
            'adx_ok':             adx_ok,
            # Valori per display
            'ema20_current':      round(ema20_v, 4) if ema20_v else None,
            'sma50_current':      round(sma50_v, 4) if sma50_v else None,
            'sma200_current':     round(sma200_v, 4) if sma200_v else None,
            'rsi':                round(rsi_val, 1) if rsi_val else None,
            'adx':                round(adx_val, 1) if adx_val else None,
            'days_above_ema20':   days_above_ema20,
            'dist_ema20':         round(dist_ema20, 2),
            'ema20_slope':        round(ema20_slope, 6),
            'regime_ok':          regime_ok,
            'kill_switch':        kill_switch,
            'daily_change_pct':   round(daily_chg, 2) if daily_chg is not None else None,
            'macd_histogram':     round(macd_h, 4) if macd_h else None,
            'pct_1d':             pct_1d,
            'pct_1w':             pct_1w,
            'pct_1m':             pct_1m,
            'peak_price':         round(peak, 4),
            'drawdown_from_peak': round(drawdown, 2),
        }
        buy_count = sum([allineamento, persistenza, rsi_ok, dist_ok, adx_ok])

        # ── Determina livello ──────────────────────────────────────────────────
        reason_codes = []

        if current_level == 1:
            if exit_rule:
                conditions['exit_rule']    = exit_rule
                conditions['exit_trigger'] = exit_rule
                suggested = 3
                reason    = f'Uscita L1 — {exit_rule}'
                reason_codes.append('L1_EXIT')
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

        elif allineamento and persistenza and rsi_ok and dist_ok and adx_ok:
            if kill_switch:
                suggested = current_level
                reason    = f'Kill Switch [{daily_chg:.1f}%]: nuovo ingresso L1 bloccato'
                reason_codes.extend(['KILL_SWITCH', 'L1_ENTRY_BLOCKED'])
            else:
                suggested = 1
                regime_note = '' if regime_ok else ' (no SMA200)'
                reason = (
                    f'L1 Trend Sicuro: EMA20>SMA50 ✓, {days_above_ema20}gg sopra EMA20 ✓, '
                    f'RSI {rsi_val:.0f} ✓, dist {dist_ema20:.1f}% ✓, ADX {adx_val:.0f} ✓{regime_note}'
                )
                reason_codes.append('L1_ENTRY')

        elif days_above_ema20 >= p['days_above_ema'] or (ema20_v and sma50_v and ema20_v > sma50_v):
            suggested = 2
            reason    = f'Watchlist: {buy_count}/5 condizioni L1 ({days_above_ema20}gg sopra EMA20)'
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

    def analyze_etf(self, df: pd.DataFrame, current_level: int = 3) -> Dict:
        """
        Analisi tecnica completa di un ETF.

        Args:
            df: DataFrame con colonne Close (+ Open, High, Low, Volume se disponibili).
                Index deve essere Date.
            current_level: Livello attuale (0-3).

        Returns:
            Dict con tutti gli indicatori, condizioni e livello suggerito.
        """
        if len(df) < self.ema20_period:
            price = float(df['Close'].iloc[-1]) if len(df) > 0 else None
            return {
                'current_price': price,
                'ema20': None, 'sma50': None, 'sma200': None,
                'rsi': None, 'adx': None, 'macd_histogram': None,
                'dist_ema20': None, 'ema20_slope': None,
                'days_above_ema20': 0, 'days_below_ema20': 0,
                'peak_price': price, 'drawdown_from_peak': 0.0,
                'pct_change_1d': None, 'pct_change_1w': None, 'pct_change_1m': None,
                'suggested_level': current_level, 'level_change': False,
                'level_reason': f'Dati insufficienti: {len(df)} giorni',
                'conditions': {}, 'buy_count': 0,
                'l0_entry': False, 'l0_exit_rule': None,
                'data_status': 'insufficient',
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            }

        close = df['Close'].astype(float)
        has_ohlc = all(c in df.columns for c in ['Open', 'High', 'Low'])
        high = df['High'].astype(float) if has_ohlc else None
        low  = df['Low'].astype(float)  if has_ohlc else None

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
            'current_price':      round(float(close.iloc[-1]), 4),
            'ema20':              lc.get('ema20_current'),
            'sma50':              lc.get('sma50_current'),
            'sma200':             lc.get('sma200_current'),
            'rsi':                lc.get('rsi'),
            'adx':                lc.get('adx'),
            'macd_histogram':     lc.get('macd_histogram'),
            'dist_ema20':         lc.get('dist_ema20'),
            'ema20_slope':        lc.get('ema20_slope'),
            'days_above_ema20':   lc.get('days_above_ema20', 0),
            'days_below_ema20':   lc.get('days_below_ema20', 0) if 'days_below_ema20' in lc else 0,
            'peak_price':         lc.get('peak_price'),
            'drawdown_from_peak': lc.get('drawdown_from_peak', 0.0),
            'pct_change_1d':      lc.get('pct_1d'),
            'pct_change_1w':      lc.get('pct_1w'),
            'pct_change_1m':      lc.get('pct_1m'),
            'suggested_level':    level['suggested_level'],
            'level_change':       level['level_change'],
            'level_reason':       level['reason'],
            'conditions':         lc,
            'buy_count':          level.get('buy_count', 0),
            'l0_entry':           l0.get('l0_entry', False),
            'l0_exit_rule':       l0.get('l0_exit_rule'),
            'l0_data':            l0,
            'data_status':        'ok',
            'analysis_date':      datetime.now().strftime('%Y-%m-%d %H:%M'),
        }

    # ── Utility ────────────────────────────────────────────────────────────────

    @staticmethod
    def category_to_etf_type(categoria: str) -> str:
        """Mappa la categoria Excel al tipo ETF per il profilo di analisi."""
        if not categoria:
            return 'equity_developed'
        cat = categoria.lower()
        if any(k in cat for k in ('emer', 'asia', 'cina', 'india', 'brasile', 'paesi em')):
            return 'equity_emerging'
        if any(k in cat for k in ('materie', 'gold', 'oro', 'petrolio', 'commodit', 'metal')):
            return 'commodity'
        if any(k in cat for k in ('obblig', 'bond', 'reddito', 'treasury', 'government', 'corporate', 'credit')):
            return 'bond'
        if any(k in cat for k in ('tematic', 'clean', 'biotech', 'robot', 'innov', 'megatr')):
            return 'thematic'
        if any(k in cat for k in ('settori', 'sector', 'tech', 'health', 'finanz', 'energia', 'real estate')):
            return 'equity_sector'
        return 'equity_developed'
