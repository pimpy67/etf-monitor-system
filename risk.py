"""
risk.py - Market Regime Analysis & Risk Assessment
====================================================
Add-on informativo: calcola Risk Score, correlazione, suggerisce allocation.
NON cambia la logica L1/L2/L3 — è solo layer reporting per dashboard.

Funzioni:
- calculate_risk_on_score() → Risk Appetite 0-100
- calculate_equity_bond_correlation() → Corr90 rolling
- calculate_correlation_velocity() → Cambio velocità correlazione
- suggest_allocation() → % allocation Equity/Bond/Monetario
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional


class MarketRegimeAnalyzer:
    """Analizza il regime di mercato (Risk-On/Off) e suggerisce allocation."""

    def __init__(self, equity_regime: str, equity_adx: Optional[float],
                 equity_rsi: Optional[float], equity_score: float,
                 bond_regime: str, bond_adx: Optional[float],
                 corr_90: Optional[float] = None):
        """
        Inizializza con i dati dei due asset class principali.

        Args:
            equity_regime: 'BULL', 'LATERALE', 'BEAR'
            equity_adx: ADX dell'equity (0-100), es. 25
            equity_rsi: RSI dell'equity (0-100), es. 55
            equity_score: Score base L1 (0-6 condizioni)
            bond_regime: 'BULL', 'LATERALE', 'BEAR'
            bond_adx: ADX dei bond (0-100), normalmente 5-20
            corr_90: Correlazione rolling 90gg tra equity e bond (-1 a +1)
        """
        self.equity_regime = equity_regime
        self.equity_adx = equity_adx or 0
        self.equity_rsi = equity_rsi or 50
        self.equity_score = equity_score
        self.bond_regime = bond_regime
        self.bond_adx = bond_adx or 0
        self.corr_90 = corr_90 or 0.0

    def calculate_risk_on_score(self) -> Tuple[int, str]:
        """
        Calcola Risk Appetite Score (0-100) basato su regime equity/bond.

        Formula:
        - +30: Equity in BULL
        - +20: ADX equity normalizzato (0-30 → 0-20 punti)
        - -20: Bond in BULL (meno rischio se bond forti)
        - -15: Correlazione positiva (se correlati, no diversificazione)
        - +10: RSI equity < 60 (spazio al rialzo)

        Returns:
            (risk_score: 0-100, regime_label: "BULL" | "NEUTRAL" | "BEAR")
        """
        score = 50  # Baseline neutro

        # Component 1: Equity Regime (+30 se BULL)
        if self.equity_regime == "BULL":
            score += 30
        elif self.equity_regime == "LATERALE":
            score += 10

        # Component 2: Equity ADX forza (+20 max, normalizzato)
        # ADX 0-30: mapping a 0-20 punti
        if self.equity_adx is not None and self.equity_adx > 0:
            adx_points = min(20, (self.equity_adx / 30) * 20)
            score += adx_points

        # Component 3: Bond regime (-20 se BULL, agisce come freno)
        # Se i bond sono forti, c'è meno appetito per rischio
        if self.bond_regime == "BULL":
            score -= 20
        elif self.bond_regime == "LATERALE":
            score -= 5

        # Component 4: Correlazione equity-bond (-15 se positiva)
        # Se corr > 0.3, penalizza (no diversificazione)
        if self.corr_90 > 0.3:
            penalty = min(15, (self.corr_90 - 0.3) * 20)
            score -= penalty

        # Component 5: RSI equity < 60 (+10)
        # Se RSI basso, c'è spazio al rialzo, propensione al rischio
        if self.equity_rsi < 60:
            score += 10

        # Clamp to 0-100
        score = max(0, min(100, score))

        # Label
        if score > 70:
            label = "BULL"
        elif score >= 40:
            label = "NEUTRAL"
        else:
            label = "BEAR"

        return int(score), label

    def calculate_correlation_velocity(self, corr_90_yesterday: Optional[float] = None) -> Tuple[float, bool]:
        """
        Calcola la velocità di cambio della correlazione.

        Se la correlazione cambia rapidamente, la diversificazione è inaffidabile.

        Args:
            corr_90_yesterday: Correlazione di ieri (per calcolare delta)

        Returns:
            (velocity: cambio giornaliero %, is_volatile: True se |velocity| > 15%)
        """
        if corr_90_yesterday is None or abs(corr_90_yesterday) < 0.01:
            return 0.0, False

        # Cambio percentuale della correlazione
        velocity = ((self.corr_90 - corr_90_yesterday) / abs(corr_90_yesterday)) * 100

        # Volatile se cambio > ±15%
        is_volatile = abs(velocity) > 15.0

        return velocity, is_volatile

    def suggest_allocation(self) -> Dict[str, int]:
        """
        Suggerisce allocation % basata su Risk Score e correlazione.

        Returns:
            {
                'equity': int (0-100),
                'bond': int (0-100),
                'monetario': int (0-100)
            }
        """
        risk_score, _ = self.calculate_risk_on_score()

        # Allocation base su risk score
        if risk_score > 70:
            # Risk-ON: Equity dominante
            allocation = {
                'equity': 75,
                'bond': 20,
                'monetario': 5
            }
        elif risk_score >= 50:
            # Neutro: Balanced
            allocation = {
                'equity': 50,
                'bond': 40,
                'monetario': 10
            }
        elif risk_score >= 40:
            # Cauto: Bond dominante
            allocation = {
                'equity': 35,
                'bond': 55,
                'monetario': 10
            }
        else:
            # Risk-OFF: Monetario rifugio
            allocation = {
                'equity': 20,
                'bond': 60,
                'monetario': 20
            }

        # Aggiustamento per correlazione positiva (riduce diversificazione)
        if self.corr_90 > 0.5:
            # Se altamente correlati, riduci sia equity che bond
            allocation['equity'] = max(20, allocation['equity'] - 15)
            allocation['monetario'] = min(30, allocation['monetario'] + 15)
            allocation['bond'] = 100 - allocation['equity'] - allocation['monetario']

        return allocation

    def generate_regime_report(self) -> Dict:
        """
        Genera report completo per dashboard.

        Returns:
            {
                'risk_score': 73,
                'regime_label': 'BULL',
                'equity_regime': 'BULL',
                'bond_regime': 'LATERALE',
                'correlation_90': -0.68,
                'correlation_velocity': 0.02,
                'is_volatile': False,
                'suggested_allocation': {'equity': 75, 'bond': 20, 'monetario': 5},
                'interpretation': 'Ambiente favorevole a equity trend...',
            }
        """
        risk_score, regime_label = self.calculate_risk_on_score()
        corr_velocity, is_volatile = self.calculate_correlation_velocity()
        allocation = self.suggest_allocation()

        # Interpretazione
        if regime_label == "BULL":
            interpretation = (
                f"🟢 Risk-ON ATTIVO (Score {risk_score}/100). "
                f"Ambiente favorevole a equity. "
                f"Correlazione {'VOLATILE ⚠️' if is_volatile else 'stabile'}. "
                f"Mantieni sempre 20% bond per diversificazione."
            )
        elif regime_label == "NEUTRAL":
            interpretation = (
                f"🟡 NEUTRO (Score {risk_score}/100). "
                f"Mercato bilanciato. "
                f"Diversificazione ottimale 50/40/10. "
                f"Segui L1/L2/L3 del monitor."
            )
        else:
            interpretation = (
                f"🔵 Risk-OFF (Score {risk_score}/100). "
                f"Ambiente cauto, fuga dal rischio. "
                f"Entra solo in Bond L1, evita equity volatile. "
                f"Aumenta copertura monetaria."
            )

        return {
            'risk_score': risk_score,
            'regime_label': regime_label,
            'equity_regime': self.equity_regime,
            'bond_regime': self.bond_regime,
            'equity_adx': round(self.equity_adx, 1),
            'equity_rsi': round(self.equity_rsi, 1),
            'equity_score': round(self.equity_score, 1),
            'bond_adx': round(self.bond_adx, 1),
            'correlation_90': round(self.corr_90, 3),
            'correlation_velocity': round(corr_velocity, 2),
            'is_correlation_volatile': is_volatile,
            'suggested_allocation': allocation,
            'interpretation': interpretation,
            'timestamp': pd.Timestamp.now().isoformat()
        }


# ── Funzioni di utilità per integrare con il database ──

def calculate_correlation_from_prices(equity_prices: pd.Series,
                                      bond_prices: pd.Series,
                                      window: int = 90) -> pd.Series:
    """
    Calcola la correlazione rolling tra due serie di prezzi.

    Args:
        equity_prices: Serie pandas di prezzi equity
        bond_prices: Serie pandas di prezzi bond
        window: Finestra rolling (default 90gg)

    Returns:
        Serie pandas con correlazione rolling
    """
    # Normalizza i prezzi per rendimenti giornalieri
    equity_returns = equity_prices.pct_change()
    bond_returns = bond_prices.pct_change()

    # Calcola correlazione rolling
    correlation = equity_returns.rolling(window=window).corr(bond_returns)

    return correlation


def aggregate_regime_data(etf_list: list, price_db: dict) -> Dict:
    """
    Aggrega i dati di regime da una lista di ETF.

    Estrae i principali benchmark (equity globale, bond governativi).

    Args:
        etf_list: Lista di ETF analizzati dal monitor
        price_db: Database dei prezzi

    Returns:
        {
            'equity_benchmark': {...regime data...},
            'bond_benchmark': {...regime data...},
            'correlation_90': float,
        }
    """
    # Benchmark: VWCE (equity globale), EGOV (bond gov EUR)
    # In futuro, estrai da database etf_price_history

    return {
        'equity_benchmark': None,  # TODO: integrare con database
        'bond_benchmark': None,    # TODO: integrare con database
        'correlation_90': 0.0
    }
