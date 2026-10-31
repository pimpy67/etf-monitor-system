#!/usr/bin/env python3
"""
Quick backtest — Analizza dati storici dal database
senza eseguire il monitor completo.
"""

import pandas as pd
from database import PriceDatabase
from technical_analysis import TechnicalAnalyzer
from datetime import datetime, timedelta
import json


def quick_backtest_date(target_date_str):
    """
    Analizza una data storica specifica usando i dati nel DB.

    Args:
        target_date_str: Data da analizzare (es. '2024-08-15')
    """
    target_date = pd.Timestamp(target_date_str)
    db = PriceDatabase()
    analyzer = TechnicalAnalyzer()

    # Leggi tutti gli ETF da Excel
    import openpyxl
    wb = openpyxl.load_workbook('etf_monitoraggio.xlsx')
    ws = wb['ETF']

    results = {
        'date': target_date_str,
        'l0': [],
        'l1': [],
        'l2': [],
        'l3': [],
        'summary': {'L0': 0, 'L1': 0, 'L2': 0, 'L3': 0}
    }

    print(f"\n{'='*70}")
    print(f"📅 Analyzing date: {target_date_str}")
    print(f"{'='*70}\n")

    count = 0
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=False):
        count += 1
        if count > 230:  # Limit per debug
            break

        ticker_cell = row[1]  # Colonna B = Ticker
        ticker = ticker_cell.value

        if not ticker:
            continue

        # Leggi dati dal database per questa data
        try:
            # Ottieni i dati storici fino a target_date
            df = db.get_price_history(ticker=ticker, limit=100)

            if df is None or len(df) == 0:
                continue

            # Filtra i dati fino a target_date
            df_filtered = df[df['date'] <= target_date]

            if len(df_filtered) < 20:  # Almeno 20 giorni di dati
                continue

            # Prepara i dati per l'analisi
            close = df_filtered['close'].astype(float)

            # Analizza il livello
            analysis = analyzer.analyze_etf(
                df_filtered.set_index('date')[['open', 'high', 'low', 'close', 'volume']],
                current_level=3
            )

            level = analysis.get('suggested_level', 3)
            regime = analysis.get('regime', 'N/A')
            ema_slope = analysis.get('ema20_slope', 'N/A')

            # Conta per statistiche
            level_name = f'L{level}'
            results['summary'][level_name] += 1

            # Aggiungi a lista appropriata
            if level == 1:
                results['l1'].append({
                    'ticker': ticker,
                    'regime': regime,
                    'ema_slope': ema_slope
                })
            elif level == 0:
                results['l0'].append(ticker)
            elif level == 2:
                results['l2'].append(ticker)
            else:
                results['l3'].append(ticker)

        except Exception as e:
            pass

    # Stampa risultati
    print(f"✅ RISULTATI:")
    print(f"   L0: {results['summary']['L0']}")
    print(f"   L1: {results['summary']['L1']}")
    print(f"   L2: {results['summary']['L2']}")
    print(f"   L3: {results['summary']['L3']}\n")

    if results['l1']:
        print(f"📊 ETF in L1 ({len(results['l1'])}):")
        for etf in results['l1'][:10]:
            print(f"   • {etf['ticker']:10} regime={etf['regime']:8} slope={etf['ema_slope']}")

    return results


if __name__ == '__main__':
    # Test su 3 date storiche
    test_dates = [
        '2024-08-15',  # Bear phase
        '2025-10-15',  # Panic phase
        '2026-01-15',  # Recovery phase
    ]

    all_results = []

    print("\n" + "="*70)
    print("⚡ QUICK BACKTEST — Analizza dati storici dal DB")
    print("="*70)

    for date_str in test_dates:
        try:
            result = quick_backtest_date(date_str)
            all_results.append(result)
        except Exception as e:
            print(f"❌ Errore per {date_str}: {e}")

    # Salva riepilogo
    print(f"\n{'='*70}")
    print("📋 RIEPILOGO")
    print(f"{'='*70}\n")

    for res in all_results:
        print(f"📅 {res['date']}: L0={res['summary']['L0']} L1={res['summary']['L1']} L2={res['summary']['L2']} L3={res['summary']['L3']}")

    with open('quick_backtest_results.json', 'w') as f:
        json.dump(all_results, f, indent=2)

    print(f"\n✅ Salvato in: quick_backtest_results.json\n")
