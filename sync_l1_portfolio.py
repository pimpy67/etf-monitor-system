"""
sync_l1_portfolio.py — Sincronizzazione automatica Dashboard L1 → Portafoglio
Aggiunge posizioni L1 al portafoglio personale quando la dashboard le identifica.
"""

import os
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class PortfolioL1Syncer:
    """Sincronizza segnali L1 dal monitoring al portafoglio reale."""

    def __init__(self, db_connection):
        self.db = db_connection

    def sync_l1_entries(self, l1_signals: List[Dict]) -> Dict:
        """
        Sincronizza nuovi segnali L1 dalla dashboard al portafoglio.
        
        Args:
            l1_signals: Lista di ETF che hanno appena raggiunto L1
                       [{ticker, isin, fund_name, famiglia, current_price, 
                         ema20, sl_suggerito, sg_suggerito, ...}, ...]
        
        Returns:
            {'added': N, 'skipped': M, 'details': [...]}
        """
        if not l1_signals:
            return {'added': 0, 'skipped': 0, 'details': []}

        added = 0
        skipped = 0
        details = []

        for signal in l1_signals:
            result = self._sync_single_l1(signal)
            if result['added']:
                added += 1
            else:
                skipped += 1
            details.append(result)

        logger.info(f"✅ L1 Portfolio Sync: {added} added, {skipped} skipped")
        return {'added': added, 'skipped': skipped, 'details': details}

    def _sync_single_l1(self, signal: Dict) -> Dict:
        """Sincronizza un singolo segnale L1."""
        try:
            ticker = signal.get('ticker')
            isin = signal.get('isin', ticker)
            fund_name = signal.get('fund_name', 'Unknown')
            famiglia = signal.get('famiglia', 'unknown')
            current_price = signal.get('current_price')
            entry_date = datetime.now().strftime('%Y-%m-%d')

            # Step 1: Verifica se è già nel portafoglio L1
            existing = self._check_existing_entry(isin, 'L1')
            if existing:
                return {
                    'ticker': ticker,
                    'added': False,
                    'reason': f"Already in portfolio (entry_date: {existing['entry_date']})"
                }

            # Step 2: Calcola SL e TP suggeriti (leggi dal segnale o da YAML)
            sl_suggerito = signal.get('sl_suggerito') or self._calculate_sl_l1(
                current_price, familia
            )
            sg_suggerito = signal.get('sg_suggerito') or self._calculate_tp_l1(
                current_price, familia
            )

            # Step 3: Aggiungi al portafoglio
            added = self._add_portfolio_entry(
                isin=isin,
                ticker=ticker,
                fund_name=fund_name,
                entry_date=entry_date,
                entry_price=current_price,
                portafoglio='L1',
                famiglia=famiglia,
                sl_suggerito=sl_suggerito,
                sg_suggerito=sg_suggerito,
                entry_confidence=signal.get('entry_confidence', 1.0)
            )

            if added:
                logger.info(f"  ✅ Added {ticker} to L1 portfolio | Entry: €{current_price:.2f} | SL: €{sl_suggerito:.2f}")
                return {
                    'ticker': ticker,
                    'added': True,
                    'entry_price': current_price,
                    'sl': sl_suggerito,
                    'tp': sg_suggerito
                }
            else:
                return {
                    'ticker': ticker,
                    'added': False,
                    'reason': 'DB insert failed'
                }

        except Exception as e:
            logger.error(f"  ❌ Error syncing {signal.get('ticker')}: {e}")
            return {
                'ticker': signal.get('ticker', 'unknown'),
                'added': False,
                'reason': str(e)
            }

    def _check_existing_entry(self, isin: str, portafoglio: str) -> Optional[Dict]:
        """Verifica se l'ETF è già nel portafoglio."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT id, entry_date, entry_price, status
                        FROM etf_portfolio_entries
                        WHERE isin = %s AND portafoglio = %s AND status = 'active'
                        LIMIT 1
                    """
                    cur.execute(query, (isin, portafoglio))
                    row = cur.fetchone()
                    if row:
                        return {
                            'id': row[0],
                            'entry_date': row[1],
                            'entry_price': row[2],
                            'status': row[3]
                        }
                    return None
        except Exception as e:
            logger.error(f"Error checking existing entry: {e}")
            return None

    def _add_portfolio_entry(self, isin: str, ticker: str, fund_name: str,
                            entry_date: str, entry_price: float, portafoglio: str,
                            famiglia: str, sl_suggerito: float, sg_suggerito: float,
                            entry_confidence: float = 1.0) -> bool:
        """Aggiungi una nuova entry L1 al portafoglio."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        INSERT INTO etf_portfolio_entries (
                            isin, entry_date, entry_price, fund_name,
                            status, portafoglio, portfolio_type, 
                            sl_suggerito, sg_suggerito, entry_confidence
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cur.execute(query, (
                        isin, entry_date, entry_price, fund_name,
                        'active', portafoglio, portafoglio,
                        sl_suggerito, sg_suggerito, entry_confidence
                    ))
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"Error adding portfolio entry: {e}")
            return False

    def _calculate_sl_l1(self, entry_price: float, famiglia: str) -> float:
        """Calcola SL iniziale basato su sl_initial_pct della famiglia."""
        # TODO: Leggere dal YAML config
        sl_pct_map = {
            'equity_sviluppati': 0.05,
            'mercati_emergenti': 0.06,
            'bond_governativi': 0.025,
            'commodities': 0.07,
        }
        sl_pct = sl_pct_map.get(famiglia, 0.05)
        return entry_price * (1 - sl_pct)

    def _calculate_tp_l1(self, entry_price: float, famiglia: str) -> float:
        """Calcola TP iniziale basato su target della famiglia."""
        # TODO: Leggere dal YAML config
        tp_pct_map = {
            'equity_sviluppati': 0.04,
            'mercati_emergenti': 0.05,
            'bond_governativi': 0.02,
            'commodities': 0.06,
        }
        tp_pct = tp_pct_map.get(famiglia, 0.04)
        return entry_price * (1 + tp_pct)


def integrate_sync_into_monitor(monitor_instance, l1_signals: List[Dict]):
    """
    Integrazione nel monitor.py:
    
    Dopo che suggest_level() calcola i livelli, aggiungere:
    
    # STEP 8 — Sincronizza L1 al portafoglio personale
    l1_signals = [r for r in results if r.get('suggested_level') == 1]
    syncer = PortfolioL1Syncer(self.db)
    sync_result = syncer.sync_l1_entries(l1_signals)
    add_log(f"Portfolio L1 Sync: {sync_result['added']} added, {sync_result['skipped']} skipped")
    
    # Invia email con nuove posizioni L1 aggiunte
    if sync_result['added'] > 0:
        alert_system.send_portfolio_sync_alert(sync_result['details'])
    """
    pass
