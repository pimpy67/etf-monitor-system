#!/usr/bin/env python3
"""
Test: Verifica calcolo Stop Loss dinamici
"""

from technical_analysis import ETFTechnicalAnalyzer
import pandas as pd
import numpy as np

# Test 1: Calcolo SL iniziale per equity sviluppati
print("=" * 60)
print("TEST 1: Calcolo SL Iniziale — Equity Sviluppati")
print("=" * 60)

analyzer_equity = ETFTechnicalAnalyzer(famiglia='equity_sviluppati')

# Simula ATR14 = €1.50, prezzo entry = €85
atr = 1.50
current_price = 85.00
entry_price = 85.00
gain_pct = 0.0

sl_data = analyzer_equity.calculate_stop_loss(
    current_price=current_price,
    atr=atr,
    family_config=analyzer_equity.p,
    entry_price=entry_price,
    current_gain_pct=gain_pct,
    regime_str='BULL'
)

print(f"Entry: €{entry_price}")
print(f"ATR14: €{atr}")
print(f"Prezzo corrente: €{current_price}")
print(f"Guadagno: {gain_pct}%")
print(f"→ SL Iniziale: €{sl_data['stop_loss_initial']:.4f}")
print(f"   Atteso: €82.00 (85 - 1.50×2.0)")
expected_sl = entry_price - (atr * 2.0)
assert abs(sl_data['stop_loss_initial'] - expected_sl) < 0.01, f"ERRORE: SL non corrisponde!"
print("✅ TEST PASSATO\n")

# Test 2: Calcolo SL trailing per profitto
print("=" * 60)
print("TEST 2: Calcolo SL Trailing — In Profitto (+5%)")
print("=" * 60)

current_price_profit = 89.25  # +5% da €85
gain_pct_profit = 5.0

sl_data_trailing = analyzer_equity.calculate_stop_loss(
    current_price=current_price_profit,
    atr=atr,
    family_config=analyzer_equity.p,
    entry_price=entry_price,
    current_gain_pct=gain_pct_profit,
    regime_str='BULL'
)

print(f"Entry: €{entry_price}")
print(f"Prezzo corrente: €{current_price_profit} (+{gain_pct_profit}%)")
print(f"→ SL Trailing attivo: €{sl_data_trailing['stop_loss_trailing']:.4f}")
print(f"   Logica: max(€{entry_price*0.98:.4f}, €{current_price_profit*0.95:.4f})")
expected_trailing = max(entry_price * 0.98, current_price_profit * 0.95)
assert abs(sl_data_trailing['stop_loss_trailing'] - expected_trailing) < 0.01, "ERRORE: Trailing SL non corrisponde!"
assert sl_data_trailing['should_use_trailing'] == True, "ERRORE: Trailing non attivato!"
print("✅ TEST PASSATO\n")

# Test 3: Bond — SL più stretto
print("=" * 60)
print("TEST 3: Calcolo SL Iniziale — Bond Governativi")
print("=" * 60)

analyzer_bond = ETFTechnicalAnalyzer(famiglia='bond_governativi')

atr_bond = 0.30
current_price_bond = 102.50
entry_price_bond = 102.50

sl_data_bond = analyzer_bond.calculate_stop_loss(
    current_price=current_price_bond,
    atr=atr_bond,
    family_config=analyzer_bond.p,
    entry_price=entry_price_bond,
    current_gain_pct=0.0,
    regime_str='BULL'
)

print(f"Entry: €{entry_price_bond}")
print(f"ATR14: €{atr_bond}")
print(f"→ SL Iniziale: €{sl_data_bond['stop_loss_initial']:.4f}")
print(f"   Atteso: €{entry_price_bond - (atr_bond * 1.5):.4f} (102.50 - 0.30×1.5)")
expected_sl_bond = entry_price_bond - (atr_bond * 1.5)
assert abs(sl_data_bond['stop_loss_initial'] - expected_sl_bond) < 0.01, "ERRORE: Bond SL non corrisponde!"
print("✅ TEST PASSATO\n")

# Test 4: Crypto — SL molto largo
print("=" * 60)
print("TEST 4: Calcolo SL Iniziale — Crypto/Digital Assets")
print("=" * 60)

analyzer_crypto = ETFTechnicalAnalyzer(famiglia='crypto_digital_assets')

atr_crypto = 0.500
current_price_crypto = 10.00
entry_price_crypto = 10.00

sl_data_crypto = analyzer_crypto.calculate_stop_loss(
    current_price=current_price_crypto,
    atr=atr_crypto,
    family_config=analyzer_crypto.p,
    entry_price=entry_price_crypto,
    current_gain_pct=0.0,
    regime_str='BULL'
)

print(f"Entry: €{entry_price_crypto}")
print(f"ATR14: €{atr_crypto}")
print(f"→ SL Iniziale: €{sl_data_crypto['stop_loss_initial']:.4f}")
# Nota: ATR-based SL sarebbe €8.50 (10 - 0.50×3), ma protezione minima = 95% = €9.50
expected_atr_sl = entry_price_crypto - (atr_crypto * 3.0)
expected_protected_sl = max(expected_atr_sl, entry_price_crypto * 0.95)
print(f"   ATR-based SL: €{expected_atr_sl:.4f} (10.00 - 0.50×3.0)")
print(f"   Protezione minima (95%): €{entry_price_crypto * 0.95:.4f}")
print(f"   Risultato: €{expected_protected_sl:.4f} (max dei due)")
assert abs(sl_data_crypto['stop_loss_initial'] - expected_protected_sl) < 0.01, "ERRORE: Crypto SL non corrisponde!"
print("✅ TEST PASSATO (protezione minima attivata)\n")

# Test 5: Regime BEAR per Crypto → exit immediato
print("=" * 60)
print("TEST 5: Regime BEAR per Crypto — Exit Immediato")
print("=" * 60)

sl_data_bear = analyzer_crypto.calculate_stop_loss(
    current_price=current_price_crypto,
    atr=atr_crypto,
    family_config=analyzer_crypto.p,
    entry_price=entry_price_crypto,
    current_gain_pct=5.0,
    regime_str='BEAR'
)

print(f"Regime: BEAR")
print(f"→ SL Trailing (regime trigger): €{sl_data_bear['stop_loss_trailing']:.4f}")
print(f"   Atteso: €{current_price_crypto * 0.90:.4f} (10.00 × 0.90)")
expected_bear_sl = current_price_crypto * 0.90
assert abs(sl_data_bear['stop_loss_trailing'] - expected_bear_sl) < 0.01, "ERRORE: Bear regime SL non corrisponde!"
assert sl_data_bear['should_use_trailing'] == True, "ERRORE: Regime BEAR non triggerato!"
print(f"   Trigger: {sl_data_bear['trigger_reason']}")
print("✅ TEST PASSATO\n")

print("=" * 60)
print("✅ TUTTI I TEST PASSATI!")
print("=" * 60)
print("\nSintesi:")
print("• SL iniziale: ATR-based per famiglia (evita whipsaw)")
print("• SL trailing: Attivato al raggiungimento guadagno soglia")
print("• SL trailing: max(entry×0.98, current×0.95) = sale con prezzo, non scende")
print("• Regime BEAR (Crypto): Exit immediato a 90% del prezzo")
