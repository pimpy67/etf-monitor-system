#!/usr/bin/env python3
"""
Backtesting script — Testa il monitor su date storiche
per verificare robustezza delle regole L0/L1/L2/L3.

Date di test:
- Agosto 2024: Fase ribassista → verifica che regime BEAR scarichi a L3
- Ottobre 2025: Fase panico → verifica L3 entry corretti
- Gennaio 2026: Fase ripartenza → verifica L2→L1 tempestivo
"""

import sys
from datetime import datetime, date
from unittest.mock import patch
import json

from monitor import ETFMonitor
from database import PriceDatabase


def run_backtest(test_date_str, scenario_name):
    """
    Esegui il monitor su una data storica specifica.

    Args:
        test_date_str: Data da testare (es. '2024-08-15')
        scenario_name: Nome del scenario (es. 'Bear Phase Aug 2024')
    """
    test_date = datetime.strptime(test_date_str, '%Y-%m-%d')

    print(f"\n{'='*70}")
    print(f"🧪 BACKTEST: {scenario_name}")
    print(f"Data di test: {test_date_str}")
    print(f"{'='*70}\n")

    # Patch datetime.now() per tutte le occorrenze
    with patch('datetime.datetime') as mock_datetime:
        mock_datetime.now.return_value = test_date
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        try:
            # Esegui il monitor normalmente
            monitor = ETFMonitor()
            results = monitor.run(send_daily_report=False)

            # Estrai statistiche dai risultati
            l0_count = sum(1 for r in results if r['analysis'].get('suggested_level') == 0)
            l1_count = sum(1 for r in results if r['analysis'].get('suggested_level') == 1)
            l2_count = sum(1 for r in results if r['analysis'].get('suggested_level') == 2)
            l3_count = sum(1 for r in results if r['analysis'].get('suggested_level') == 3)

            print(f"✅ RISULTATI:")
            print(f"   L0 (Deep Recovery): {l0_count}")
            print(f"   L1 (Trend Sicuro):  {l1_count}")
            print(f"   L2 (Watchlist):     {l2_count}")
            print(f"   L3 (Universe):      {l3_count}")
            print(f"   Total: {len(results)}\n")

            # Mostra ETF in L1 (quelli interessanti)
            if l1_count > 0:
                print(f"📊 ETF in L1:")
                l1_etfs = [r for r in results if r['analysis'].get('suggested_level') == 1]
                for etf in l1_etfs[:15]:  # Mostra max 15
                    regime = etf['analysis'].get('regime', 'N/A')
                    ema_slope = etf['analysis'].get('ema20_slope', 'N/A')
                    print(f"   • {etf['ticker']:10} {etf['nome'][:45]:45} (regime:{regime:8}, slope:{ema_slope})")
                if len(l1_etfs) > 15:
                    print(f"   ... e {len(l1_etfs) - 15} altri")

            # Salva risultati per analisi
            backtest_data = {
                'date': test_date_str,
                'scenario': scenario_name,
                'summary': {
                    'l0': l0_count,
                    'l1': l1_count,
                    'l2': l2_count,
                    'l3': l3_count,
                    'total': len(results)
                },
                'l1_etfs': [
                    {
                        'ticker': r['ticker'],
                        'nome': r['nome'],
                        'regime': r['analysis'].get('regime'),
                        'ema20_slope': r['analysis'].get('ema20_slope'),
                        'rsi': r['analysis'].get('rsi'),
                        'adx': r['analysis'].get('adx')
                    }
                    for r in results if r['analysis'].get('suggested_level') == 1
                ]
            }

            return backtest_data

        except Exception as e:
            print(f"❌ ERRORE: {e}")
            import traceback
            traceback.print_exc()
            return None


def main():
    """Esegui i 3 test di robustezza."""

    print("\n" + "="*70)
    print("🧪 TEST DI ROBUSTEZZA — BACKTESTING SU DATE STORICHE")
    print("="*70)

    test_scenarios = [
        ('2024-08-15', 'Bear Phase (Aug 2024) — Regime ribassista'),
        ('2025-10-15', 'Panic Phase (Oct 2025) — Calo di panico'),
        ('2026-01-15', 'Recovery Phase (Jan 2026) — Ripartenza'),
    ]

    results_all = []

    for test_date, scenario_name in test_scenarios:
        result = run_backtest(test_date, scenario_name)
        if result:
            results_all.append(result)

    # Salva il riepilogo completo
    if results_all:
        with open('backtest_results.json', 'w') as f:
            json.dump(results_all, f, indent=2)

        print(f"\n{'='*70}")
        print("📋 RIEPILOGO BACKTESTING")
        print(f"{'='*70}\n")

        for res in results_all:
            print(f"📅 {res['date']} — {res['scenario']}")
            print(f"   L0:{res['summary']['l0']:2} | L1:{res['summary']['l1']:2} | L2:{res['summary']['l2']:3} | L3:{res['summary']['l3']:3}")

        print(f"\n✅ Risultati salvati in: backtest_results.json\n")


if __name__ == '__main__':
    main()
