#!/usr/bin/env python3
"""
Shadow Monitor Portafoglio — Resistenze come TP (Candidato 2026-09-14)

Testa resistenze tecniche su TUTTE le posizioni attive:
- L0 (Deep Recovery): compara TP resistenza vs TP 16% fisso
- L1 (Trend): compara TP resistenza vs TP dinamico (slope-based)

Logica:
1. Leggi tutte posizioni attive (L0 + L1)
2. Per ognuna: calcola massimo ultimi 20-30 giorni
3. Valida resistenza: deve essere 2-20% dal prezzo
4. Traccia in etf_shadow_positions con model_name='candidate_portafoglio_resistance_20260914'
5. Confronta al checkpoint (2 settimane): TP resistenza vs TP standard

Parametri:
- lookback_days: 20 (storico per resistenza)
- resistance_min_pct: 2% (min distanza)
- resistance_max_pct: 20% (max distanza)
"""

import sys
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import ETFDatabase
from technical_analysis import ETFTechnicalAnalyzer


def calculate_resistance_tp(
    current_price: float,
    isin: str,
    db: ETFDatabase,
    lookback_days: int = 20,
    resistance_min_pct: float = 0.02,
    resistance_max_pct: float = 0.20,
) -> Dict:
    """
    Calcola TP basato su resistenza (massimo storico).

    Returns: {
        'tp_resistance': float,
        'resistance_price': float,
        'resistance_pct': float,
        'used_fallback': bool,
        'lookback_days': int,
        'max_price': float,
        'reason': str
    }
    """
    try:
        hist = db.get_ohlc_by_isin(isin, days=lookback_days + 5)
        if hist is None or hist.empty or len(hist) < 5:
            return {
                'tp_resistance': current_price * 1.16,
                'resistance_price': None,
                'resistance_pct': 0,
                'used_fallback': True,
                'lookback_days': lookback_days,
                'max_price': current_price,
                'reason': 'Storico insufficiente'
            }

        close_prices = hist['Close'].astype(float).dropna()
        if len(close_prices) < 5:
            return {
                'tp_resistance': current_price * 1.16,
                'resistance_price': None,
                'resistance_pct': 0,
                'used_fallback': True,
                'lookback_days': lookback_days,
                'max_price': current_price,
                'reason': 'Chiusure insufficienti'
            }

        hist_prices = close_prices.iloc[:-1] if len(close_prices) > 1 else close_prices
        if hist_prices.empty:
            hist_prices = close_prices

        max_price = hist_prices.max()
        resistance_pct = (max_price - current_price) / current_price if current_price > 0 else 0

        # Validazione
        if resistance_pct < resistance_min_pct:
            return {
                'tp_resistance': current_price * 1.16,
                'resistance_price': max_price,
                'resistance_pct': resistance_pct,
                'used_fallback': True,
                'lookback_days': lookback_days,
                'max_price': max_price,
                'reason': f'Resistenza troppo vicina ({resistance_pct:.2%})'
            }

        if resistance_pct > resistance_max_pct:
            return {
                'tp_resistance': current_price * 1.16,
                'resistance_price': max_price,
                'resistance_pct': resistance_pct,
                'used_fallback': True,
                'lookback_days': lookback_days,
                'max_price': max_price,
                'reason': f'Resistenza troppo lontana ({resistance_pct:.2%})'
            }

        # Resistenza valida
        return {
            'tp_resistance': max_price,
            'resistance_price': max_price,
            'resistance_pct': resistance_pct,
            'used_fallback': False,
            'lookback_days': lookback_days,
            'max_price': max_price,
            'reason': f'Resistenza: {resistance_pct:.2%}'
        }

    except Exception as e:
        return {
            'tp_resistance': current_price * 1.16,
            'resistance_price': None,
            'resistance_pct': 0,
            'used_fallback': True,
            'lookback_days': lookback_days,
            'max_price': current_price,
            'reason': f'Errore: {str(e)}'
        }


def run_shadow_monitor_portafoglio_resistances(
    results: List[Dict],
    db: ETFDatabase,
    add_log=None,
) -> None:
    """
    Shadow Monitor universale per resistenze su tutto il portafoglio.

    Args:
        results: Risultati da monitor.py
        db: Database
        add_log: Funzione log
    """
    if add_log is None:
        add_log = lambda x: print(x)

    model_name = 'candidate_portafoglio_resistance_20260914'
    add_log(f"\n[STEP 8P] Shadow Monitor Portafoglio Resistenze (L0+L1)")

    try:
        conn = db.get_connection()
        if not conn:
            add_log("  ⚠️  Nessuna connessione DB")
            return

        # Leggi TUTTE le posizioni attive (L0 + L1)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, isin, entry_date, entry_price, shares, fund_name, portafoglio
                FROM etf_portfolio_entries
                WHERE status = 'active'
                ORDER BY portafoglio DESC, entry_date DESC
            """)
            rows = cur.fetchall()

        if not rows:
            add_log("  — Nessuna posizione nel portafoglio")
            return

        l0_count = sum(1 for r in rows if r[6] == 'L0')
        l1_count = sum(1 for r in rows if r[6] == 'L1')
        add_log(f"  Testing {len(rows)} posizioni: {l1_count} L1 + {l0_count} L0")

        for entry_id, isin, entry_date_str, entry_price_str, shares_str, fund_name, portafoglio in rows:
            try:
                entry_price = float(entry_price_str) if entry_price_str else None
                if not entry_price or entry_price <= 0:
                    continue

                # Trova prezzo attuale
                result = None
                for r in results:
                    if r.get('isin') == isin or r.get('ticker') == isin:
                        result = r
                        break

                if not result or not result.get('analysis'):
                    continue

                current_price = result['analysis'].get('current_price')
                if not current_price:
                    continue

                current_price = float(current_price)

                # Calcola resistenza
                resistance_data = calculate_resistance_tp(
                    current_price=current_price,
                    isin=isin,
                    db=db,
                    lookback_days=20,
                    resistance_min_pct=0.02,
                    resistance_max_pct=0.20,
                )

                tp_resistance = resistance_data.get('tp_resistance')

                if portafoglio == 'L0':
                    # L0: compara con 16% fisso
                    tp_standard = current_price * 1.16
                    label = "L0"
                elif portafoglio == 'L1':
                    # L1: compara con TP dinamico (approssimazione)
                    # In realtà dovremmo leggere il TP dinamico real-time, per ora usiamo 15%
                    tp_standard = current_price * 1.15  # Approssimazione
                    label = "L1"
                else:
                    continue

                # Distanza dal TP
                dist_resistance = (tp_resistance - current_price) / current_price * 100
                dist_standard = (tp_standard - current_price) / current_price * 100

                advantage = ((tp_resistance - tp_standard) / tp_standard * 100) if tp_standard > 0 else 0

                # Log
                add_log(
                    f"    [{label}] {fund_name[:40]:40} | "
                    f"Entry €{entry_price:.4f} | Current €{current_price:.4f} | "
                    f"TP Res: €{tp_resistance:.4f} ({dist_resistance:+.1f}%) vs "
                    f"TP Std: €{tp_standard:.4f} ({dist_standard:+.1f}%) | "
                    f"Δ {advantage:+.1f}%"
                )

                # Salva in shadow positions
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id FROM etf_shadow_positions
                        WHERE isin = %s AND model_name = %s AND status = 'open'
                    """, (isin, model_name))

                    existing = cur.fetchone()

                    if not existing:
                        cur.execute("""
                            INSERT INTO etf_shadow_positions
                            (isin, model_name, entry_date, entry_price, entry_reason, status, metadata)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            isin,
                            model_name,
                            datetime.now().date(),
                            entry_price,
                            f"[{portafoglio}] Resistance TP test: {tp_resistance:.4f} vs Standard {tp_standard:.4f}",
                            'open',
                            json.dumps({
                                'resistance_data': resistance_data,
                                'portafoglio': portafoglio,
                                'tp_resistance': float(tp_resistance),
                                'tp_standard': float(tp_standard),
                                'advantage_pct': advantage
                            })
                        ))
                        conn.commit()
                    else:
                        cur.execute("""
                            UPDATE etf_shadow_positions
                            SET metadata = %s
                            WHERE isin = %s AND model_name = %s AND status = 'open'
                        """, (
                            json.dumps({
                                'resistance_data': resistance_data,
                                'portafoglio': portafoglio,
                                'tp_resistance': float(tp_resistance),
                                'tp_standard': float(tp_standard),
                                'advantage_pct': advantage
                            }),
                            isin,
                            model_name
                        ))
                        conn.commit()

            except Exception as e:
                add_log(f"    ⚠️  Errore {isin}: {e}")

        add_log(f"  ✓ Shadow Monitor Portafoglio Resistenze completato")

    except Exception as e:
        add_log(f"  ⚠️  Errore Shadow Monitor Portafoglio: {e}")


if __name__ == '__main__':
    db = ETFDatabase()
    from data_fetcher import fetch_all_etf_data

    print("Fetching ETF data...")
    results = fetch_all_etf_data()

    print("Running shadow monitor...")
    run_shadow_monitor_portafoglio_resistances(results, db, add_log=print)
