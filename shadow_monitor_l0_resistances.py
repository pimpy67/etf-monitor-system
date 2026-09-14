#!/usr/bin/env python3
"""
Shadow Monitor L0 — Resistenze come TP (Candidato 2026-09-14)

Testa se TP basato su resistenze tecnici batte il TP fisso al 16%.

Logica:
1. Per ogni posizione L0 attiva, calcola il massimo degli ultimi 20-30 giorni
2. Se resistenza è 2-20% dal prezzo attuale → usa come TP
3. Altrimenti → fallback a 16%
4. Traccia in etf_shadow_positions con model_name='candidate_l0_resistance_tp_20260914'
5. Confronta al checkpoint (06/09 + 2 settimane): TP resistenza vs TP 16%

Parametri tunable:
- lookback_days: 20 (giorni di storico per calcolare resistenza)
- resistance_min_pct: 2% (resistenza deve essere almeno 2% dal prezzo)
- resistance_max_pct: 20% (resistenza non può essere > 20% dal prezzo)
"""

import sys
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List

# Add parent dir to path
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
    Calcola TP basato su resistenza tecnica (massimo storico).

    Returns:
        {
            'tp_resistance': float,      # TP basato su resistenza
            'resistance_price': float,   # Prezzo della resistenza
            'resistance_pct': float,     # % della resistenza dal prezzo
            'used_fallback': bool,       # True se resistenza non valida, usa 16%
            'lookback_days': int,
            'max_price': float,          # Massimo trovato nello storico
            'reason': str
        }
    """
    tp_fallback_pct = 0.16  # Fallback standard

    try:
        # Leggi storico OHLCV
        hist = db.get_ohlc_by_isin(isin, days=lookback_days + 5)
        if hist is None or hist.empty or len(hist) < 5:
            return {
                'tp_resistance': current_price * (1 + tp_fallback_pct),
                'resistance_price': None,
                'resistance_pct': 0,
                'used_fallback': True,
                'lookback_days': lookback_days,
                'max_price': current_price,
                'reason': 'Storico insufficiente, fallback 16%'
            }

        # Calcola massimo
        close_prices = hist['Close'].astype(float).dropna()
        if len(close_prices) < 5:
            return {
                'tp_resistance': current_price * (1 + tp_fallback_pct),
                'resistance_price': None,
                'resistance_pct': 0,
                'used_fallback': True,
                'lookback_days': lookback_days,
                'max_price': current_price,
                'reason': 'Chiusure insufficienti, fallback 16%'
            }

        # Prendi il massimo (escludi il prezzo odierno per non viziare)
        hist_prices = close_prices.iloc[:-1]  # Escludi oggi
        if hist_prices.empty:
            hist_prices = close_prices

        max_price = hist_prices.max()
        resistance_pct = (max_price - current_price) / current_price

        # Validazione: resistenza deve essere 2-20% dal prezzo
        if resistance_pct < resistance_min_pct:
            # Resistenza troppo vicina, non significa nulla
            tp_resistance = current_price * (1 + tp_fallback_pct)
            return {
                'tp_resistance': tp_resistance,
                'resistance_price': max_price,
                'resistance_pct': resistance_pct,
                'used_fallback': True,
                'lookback_days': lookback_days,
                'max_price': max_price,
                'reason': f'Resistenza troppo vicina ({resistance_pct:.2%}), fallback 16%'
            }

        if resistance_pct > resistance_max_pct:
            # Resistenza troppo lontana, probabilmente rumore
            tp_resistance = current_price * (1 + tp_fallback_pct)
            return {
                'tp_resistance': tp_resistance,
                'resistance_price': max_price,
                'resistance_pct': resistance_pct,
                'used_fallback': True,
                'lookback_days': lookback_days,
                'max_price': max_price,
                'reason': f'Resistenza troppo lontana ({resistance_pct:.2%}), fallback 16%'
            }

        # Resistenza valida
        return {
            'tp_resistance': max_price,
            'resistance_price': max_price,
            'resistance_pct': resistance_pct,
            'used_fallback': False,
            'lookback_days': lookback_days,
            'max_price': max_price,
            'reason': f'Resistenza valida: {max_price:.4f} ({resistance_pct:.2%})'
        }

    except Exception as e:
        return {
            'tp_resistance': current_price * (1 + tp_fallback_pct),
            'resistance_price': None,
            'resistance_pct': 0,
            'used_fallback': True,
            'lookback_days': lookback_days,
            'max_price': current_price,
            'reason': f'Errore calcolo: {str(e)}, fallback 16%'
        }


def run_shadow_monitor_l0_resistances(
    results: List[Dict],
    db: ETFDatabase,
    add_log=None,
) -> None:
    """
    Esegui Shadow Monitor L0 resistenze.

    Args:
        results: Risultati da monitor.py (lista di dict con ISIN, prezzo, ecc.)
        db: Connessione database
        add_log: Funzione log
    """
    if add_log is None:
        add_log = lambda x: print(x)

    model_name = 'candidate_l0_resistance_tp_20260914'
    add_log(f"\n[STEP 8x] Shadow Monitor L0 Resistenze")

    try:
        conn = db.get_connection()
        if not conn:
            add_log("  ⚠️  Nessuna connessione DB")
            return

        # Leggi posizioni L0 attive
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, isin, entry_date, entry_price, shares, fund_name, portafoglio
                FROM etf_portfolio_entries
                WHERE status = 'active' AND portafoglio = 'L0'
            """)
            rows = cur.fetchall()

        if not rows:
            add_log("  — Nessuna posizione L0 da testare")
            return

        add_log(f"  Testing {len(rows)} posizioni L0 con resistenze...")

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

                # Calcola TP resistenza
                resistance_data = calculate_resistance_tp(
                    current_price=current_price,
                    isin=isin,
                    db=db,
                    lookback_days=20,
                    resistance_min_pct=0.02,
                    resistance_max_pct=0.20,
                )

                tp_resistance = resistance_data.get('tp_resistance')
                tp_fallback = current_price * 1.16  # TP standard L0

                # Log comparazione
                add_log(
                    f"    {fund_name[:40]:40} | "
                    f"Entry €{entry_price:.4f} | "
                    f"Current €{current_price:.4f} | "
                    f"TP Resistance: €{tp_resistance:.4f} ({(tp_resistance-current_price)/current_price*100:.1f}%) vs "
                    f"TP 16%: €{tp_fallback:.4f} ({(tp_fallback-current_price)/current_price*100:.1f}%) | "
                    f"{'FALLBACK' if resistance_data['used_fallback'] else 'ACTIVE'}"
                )

                # Log reason
                add_log(f"      → {resistance_data['reason']}")

                # Salva in shadow positions (come info per il checkpoint)
                # Non apriamo/chiudiamo effettivamente, solo tracciamo
                with conn.cursor() as cur:
                    # Verifica se esiste già
                    cur.execute("""
                        SELECT id FROM etf_shadow_positions
                        WHERE isin = %s AND model_name = %s AND status = 'open'
                    """, (isin, model_name))

                    existing = cur.fetchone()

                    if not existing:
                        # Crea nuova posizione ombra
                        cur.execute("""
                            INSERT INTO etf_shadow_positions
                            (isin, model_name, entry_date, entry_price, entry_reason, status, metadata)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            isin,
                            model_name,
                            datetime.now().date(),
                            entry_price,
                            f"Resistance TP: {tp_resistance:.4f} vs 16% TP: {tp_fallback:.4f}",
                            'open',
                            json.dumps(resistance_data)
                        ))
                        conn.commit()
                        add_log(f"      ✓ Shadow position opened for testing")
                    else:
                        # Aggiorna metadata
                        cur.execute("""
                            UPDATE etf_shadow_positions
                            SET metadata = %s
                            WHERE isin = %s AND model_name = %s AND status = 'open'
                        """, (
                            json.dumps(resistance_data),
                            isin,
                            model_name
                        ))
                        conn.commit()

            except Exception as e:
                add_log(f"    ⚠️  Errore {isin}: {e}")

        add_log(f"  ✓ Shadow Monitor L0 Resistenze completato")

    except Exception as e:
        add_log(f"  ⚠️  Errore Shadow Monitor L0 Resistenze: {e}")


if __name__ == '__main__':
    # Test standalone
    db = ETFDatabase()
    from data_fetcher import fetch_all_etf_data

    print("Fetching ETF data...")
    results = fetch_all_etf_data()

    print("Running shadow monitor...")
    run_shadow_monitor_l0_resistances(results, db, add_log=print)
