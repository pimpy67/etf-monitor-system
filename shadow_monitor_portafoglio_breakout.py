#!/usr/bin/env python3
"""
Shadow Monitor Portafoglio Breakout — Trading classico (Candidato 2026-09-14)

Logica rottura dinamica:
1. Calcola Resistance 1 = massimo ultimi 20 giorni
2. Se prezzo ROMPE resistance → TP aggressivo (esteso al rialzo)
3. Se prezzo RIMBALZA da resistance → SL stretto, exit tattica

Meccanica:
- Sopra resistance: cerca Resistance 2 (massimo prima del picco), oppure resistance + ATR×2
- Sotto resistance: SL = resistance × 0.98 (stretto), TP = entry (bail out)

Salva in etf_shadow_positions con model_name='candidate_portafoglio_breakout_20260914'
"""

import sys
import os
import json
from datetime import datetime
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import ETFDatabase
from technical_analysis import ETFTechnicalAnalyzer
import pandas as pd
import numpy as np


def calculate_resistances_and_atr(
    current_price: float,
    isin: str,
    db: ETFDatabase,
    lookback_days: int = 20,
    lookback_extended: int = 60,  # Per trovare Resistance 2
) -> Dict:
    """
    Calcola Resistance 1 (vicina) e Resistance 2 (lontana) per breakout.

    Returns: {
        'resistance_1': float,      # Massimo ultimi 20gg (breakout trigger)
        'resistance_2': float,      # Massimo precedente (target se breakout)
        'atr': float,               # ATR per sizing
        'atr_multiple': float,      # Target ATR × 2 (alternativa a R2)
        'above_r1': bool,           # True se prezzo > R1
        'breakout_active': bool,    # True se stai in breakout
        'tp_breakout': float,       # Target se breakout
        'tp_nobreak': float,        # Target se NO breakout (exit rapida)
        'sl_breakout': float,       # SL se breakout
        'sl_nobreak': float,        # SL se NO breakout (stretto)
        'reason': str
    }
    """
    try:
        # Leggi storico OHLCV
        hist = db.get_ohlc_by_isin(isin, days=lookback_extended + 5)
        if hist is None or hist.empty or len(hist) < 20:
            return {
                'resistance_1': current_price * 1.05,
                'resistance_2': current_price * 1.15,
                'atr': current_price * 0.02,
                'atr_multiple': current_price * 1.04,
                'above_r1': False,
                'breakout_active': False,
                'tp_breakout': current_price * 1.15,
                'tp_nobreak': current_price * 1.00,
                'sl_breakout': current_price * 0.97,
                'sl_nobreak': current_price * 0.98,
                'reason': 'Storico insufficiente'
            }

        close_prices = hist['Close'].astype(float).dropna()
        high_prices = hist['High'].astype(float).dropna()
        low_prices = hist['Low'].astype(float).dropna()

        if len(close_prices) < 20:
            return {
                'resistance_1': current_price * 1.05,
                'resistance_2': current_price * 1.15,
                'atr': current_price * 0.02,
                'atr_multiple': current_price * 1.04,
                'above_r1': False,
                'breakout_active': False,
                'tp_breakout': current_price * 1.15,
                'tp_nobreak': current_price * 1.00,
                'sl_breakout': current_price * 0.97,
                'sl_nobreak': current_price * 0.98,
                'reason': 'Chiusure insufficienti'
            }

        # Resistance 1: massimo ultimi 20gg (escludendo oggi)
        recent_highs = high_prices.iloc[-21:-1] if len(high_prices) >= 21 else high_prices.iloc[:-1]
        resistance_1 = recent_highs.max() if not recent_highs.empty else current_price * 1.05

        # Resistance 2: massimo su periodo più esteso, escludendo R1
        # Cerca il massimo prima del picco recente
        extended_highs = high_prices.iloc[:-21] if len(high_prices) > 21 else high_prices.iloc[:-1]
        resistance_2 = extended_highs.max() if not extended_highs.empty else resistance_1 * 1.15

        # Se R2 < R1, significa che R1 è il massimo storico; usa ATR per proiezione
        if resistance_2 <= resistance_1:
            # Calcola ATR
            tr_list = []
            for i in range(1, len(high_prices)):
                h = high_prices.iloc[i]
                l = low_prices.iloc[i]
                cp = close_prices.iloc[i-1]
                tr = max(h - l, abs(h - cp), abs(l - cp))
                tr_list.append(tr)

            atr = np.mean(tr_list[-14:]) if len(tr_list) >= 14 else np.mean(tr_list)
            resistance_2 = current_price + (atr * 2)  # Proiezione ATR
            use_atr = True
        else:
            # Usa ATR per confirmazione
            tr_list = []
            for i in range(1, len(high_prices)):
                h = high_prices.iloc[i]
                l = low_prices.iloc[i]
                cp = close_prices.iloc[i-1]
                tr = max(h - l, abs(h - cp), abs(l - cp))
                tr_list.append(tr)

            atr = np.mean(tr_list[-14:]) if len(tr_list) >= 14 else np.mean(tr_list)
            use_atr = False

        # Stato breakout
        above_r1 = current_price > resistance_1

        # Target e SL per entrambi gli scenari
        if above_r1:
            # Scenario breakout: estendi al rialzo
            tp_breakout = resistance_2 if resistance_2 > resistance_1 else current_price + (atr * 3)
            sl_breakout = resistance_1 * 0.99  # SL sotto R1 con margine
            tp_nobreak = current_price * 1.02  # Se si inverte, esci veloce
            sl_nobreak = resistance_1 * 0.995
        else:
            # Scenario NO breakout: rimbalzo dalla resistenza
            tp_breakout = resistance_1  # Prova a raggiungere R1
            sl_breakout = current_price * 0.97  # SL stretto
            tp_nobreak = current_price * 1.00  # Pareggio
            sl_nobreak = resistance_1 * 0.98  # SL dalla resistenza

        return {
            'resistance_1': float(resistance_1),
            'resistance_2': float(resistance_2),
            'atr': float(atr),
            'atr_multiple': float(current_price + (atr * 2)),
            'above_r1': bool(above_r1),
            'breakout_active': bool(above_r1),
            'tp_breakout': float(tp_breakout),
            'tp_nobreak': float(tp_nobreak),
            'sl_breakout': float(sl_breakout),
            'sl_nobreak': float(sl_nobreak),
            'reason': f"R1={resistance_1:.4f}, R2={resistance_2:.4f}, ATR={atr:.4f}, Above_R1={above_r1}"
        }

    except Exception as e:
        return {
            'resistance_1': current_price * 1.05,
            'resistance_2': current_price * 1.15,
            'atr': current_price * 0.02,
            'atr_multiple': current_price * 1.04,
            'above_r1': False,
            'breakout_active': False,
            'tp_breakout': current_price * 1.15,
            'tp_nobreak': current_price * 1.00,
            'sl_breakout': current_price * 0.97,
            'sl_nobreak': current_price * 0.98,
            'reason': f'Errore: {str(e)}'
        }


def run_shadow_monitor_portafoglio_breakout(
    results: List[Dict],
    db: ETFDatabase,
    add_log=None,
) -> None:
    """
    Shadow Monitor Breakout Trading su portafoglio L0+L1.
    """
    if add_log is None:
        add_log = lambda x: print(x)

    model_name = 'candidate_portafoglio_breakout_20260914'
    add_log(f"\n[STEP 8Q] Shadow Monitor Portafoglio Breakout Trading")

    try:
        conn = db.get_connection()
        if not conn:
            add_log("  ⚠️  Nessuna connessione DB")
            return

        # Leggi posizioni attive
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
        add_log(f"  Testing Breakout Trading su {len(rows)} posizioni: {l1_count} L1 + {l0_count} L0")

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

                # Calcola resistenze e setup breakout
                breakout_data = calculate_resistances_and_atr(
                    current_price=current_price,
                    isin=isin,
                    db=db,
                    lookback_days=20,
                    lookback_extended=60,
                )

                r1 = breakout_data['resistance_1']
                r2 = breakout_data['resistance_2']
                above_r1 = breakout_data['above_r1']

                if above_r1:
                    # Breakout attivo
                    tp = breakout_data['tp_breakout']
                    sl = breakout_data['sl_breakout']
                    status = "🚀 BREAKOUT"
                    dist_tp = (tp - current_price) / current_price * 100
                else:
                    # NO breakout — rimbalza dalla resistenza
                    tp = breakout_data['tp_nobreak']
                    sl = breakout_data['sl_nobreak']
                    status = "🟡 RIMBALZO"
                    dist_tp = (tp - current_price) / current_price * 100

                dist_r1 = (r1 - current_price) / current_price * 100

                # Log
                add_log(
                    f"    [{portafoglio}] {status} {fund_name[:35]:35} | "
                    f"Entry €{entry_price:.4f} | Current €{current_price:.4f} | "
                    f"R1: €{r1:.4f} ({dist_r1:+.1f}%) | R2: €{r2:.4f} | "
                    f"TP: €{tp:.4f} ({dist_tp:+.1f}%) | SL: €{sl:.4f}"
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
                            f"[{portafoglio}] Breakout Trading: {'ABOVE R1' if above_r1 else 'BELOW R1'}",
                            'open',
                            json.dumps(breakout_data)
                        ))
                        conn.commit()
                    else:
                        cur.execute("""
                            UPDATE etf_shadow_positions
                            SET metadata = %s
                            WHERE isin = %s AND model_name = %s AND status = 'open'
                        """, (
                            json.dumps(breakout_data),
                            isin,
                            model_name
                        ))
                        conn.commit()

            except Exception as e:
                add_log(f"    ⚠️  Errore {isin}: {e}")

        add_log(f"  ✓ Shadow Monitor Breakout completato")

    except Exception as e:
        add_log(f"  ⚠️  Errore Shadow Monitor Breakout: {e}")


if __name__ == '__main__':
    db = ETFDatabase()
    from data_fetcher import fetch_all_etf_data

    print("Fetching ETF data...")
    results = fetch_all_etf_data()

    print("Running shadow monitor...")
    run_shadow_monitor_portafoglio_breakout(results, db, add_log=print)
