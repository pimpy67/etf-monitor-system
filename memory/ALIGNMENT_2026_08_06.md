---
name: alignment-2026-08-06
description: Stato sistema ETF Monitor dopo allineamento remoto — v4.0 LIVE con backtest 6/7 vs 7/7
metadata: 
  node_type: memory
  type: project
  originSessionId: e67eaca6-74dc-4036-81a9-5dc2cb642f2d
  modified: 2026-08-06T07:44:47.023Z
---

## STATO SISTEMA — 2026-08-06 ALLINEATO

**Status**: ✅ LOCAL = REMOTE (HEAD = 3bdb52e)

### Cosa è Nuovo (ultimi 32 commit dal 2026-07-31)

#### L1 Entry — 7 Condizioni TUTTE Obbligatorie (LIVE)
```
1. Allineamento        (price > EMA20 > SMA50 [+SMA200])
2. Persistenza         (giorni >= 3 + slope(EMA20) > 0)
3. RSI ottimale        (rsi_entry_low ≤ RSI ≤ rsi_entry_high)
4. Distanza EMA20      (0% ≤ dist ≤ ema_dist_max)
5. ADX forte           (ADX ≥ adx_entry)
6. MACD momentum       (histogram > 0 AND rising)
7. Spazio residuo      (resistenza OR ATR*mult >= min_reward_pct)
```
**+ Fondamenta irrinunciabili**:
- Regime BULL (non LATERALE/BEAR)
- Prezzo > SMA50
- No kill switch (calo ≤ -3%)
- min_buy_count = 7 (YAML, tutte le 14 famiglie)

**Parametri morti nel YAML** (scoperti 2026-08-04):
- `ema20_slope_min`: presente in YAML ma **MAI usato** nel codice
  - La condizione 2 verifica solo `slope(EMA20) > 0`, senza soglia minima
  - Candidato per rimozione dal YAML

#### L1 Exit — DUE MOTORI DISTINTI (fisso 2026-08-04)

**1) Dashboard** (`suggest_level()`):
- F: Kill switch (calo ≤ -3%)
- A: Stop loss (prezzo < EMA20 da 3gg)
- B: Trailing (EMA10 < EMA20)
- C: Stanchezza (RSI era ≥70, ora <70, non-bond)
- E: ADX debole (ADX < 18 + prezzo < EMA20, solo equity/commodity)
- Downgrade: buy_count < 7 OR regime lascia BULL

**2) Portfolio reale** (`check_l1_exit()`):
- F: Kill switch
- SL dinamico (EMA20−buffer se <2% profitto, EMA20×0.99 se ≥2%)
- B: Trailing
- C: Stanchezza
- SG dinamico (TP calcolato con slope EMA20)
- E: ADX debole

**Non automatico**: il broker esegue SL/TP manuali, non il codice

#### L0 — 3 Percorsi (LIVE 2026-08-05)

```
FAST (flash crash):         z-score ATR rilevato + conferma recovery
SLOW (bear sostenuto):      giorni sotto SMA200 + drawdown normalizzato + conferma
PRAGMATIC_4CONDITIONS:      dd_threshold + RSI + divergenza + recovery
```

**Fisso 2026-08-05**: FAST/SLOW ora richiedono **conferma recovery** prima di entry
- Prima entravano al rilevamento del crollo (falsi L0)
- Ora: `_get_l0_confirmation_signal()` → RSI > soglia O prezzo > EMA20/50

#### L2 — Smoothing Anti-Flickering (LIVE)

```
EMA 3gg + isteresi (enter ≥70, exit <60) + jump override (delta > 25)
→ Elimina fluttuazioni intraday, evita messaggi falsi
```

#### Nuovi File

1. **`backtest_l1.py`** (463 linee)
   - Backtest 7/7 vs 6/7 vs "smart 6/7 MACD obbligatorio"
   - Risultato: **smart 6/7 batte entrambi** (win rate più alto)
   - Feature extraction: TP vs SL, segmentazione per condizione mancante

2. **`templates/portfolio.html`** (1174 linee)
   - Nuova pagina portfolio reale (etf_portfolio_entries)
   - SL/TP dinamici, tracking P&L in tempo reale
   - Sincronizzato con dashboard L0/L1/L2

3. **`pdf_generator_complete.py`** (nuovo PDF completo con parametri)

#### File Rimossi (Obsoleti)

- `DEPLOYMENT_v4.0.md` ❌ (superseded da CLAUDE.md)
- `IMPLEMENTATION_SUMMARY_v4.0.md` ❌
- `Prompt_Implementazione_STEP3_v4_L0_L1_L2.md` ❌
- `STEP3_v4_0_VALIDATION_REPORT.md` ❌

Tutti i dettagli ora sono in **CLAUDE.md** unico (888 linee)

### Parametri YAML (14 Famiglie)

Tutte hanno `min_buy_count: 7`:
```
equity_sviluppati, mercati_emergenti, settoriali_growth, settoriali_difensivi,
bond_governativi, bond_corp_hy_em, commodities, oro_metalli_preziosi,
metalli_industriali, real_estate_reit, crypto_digital_assets, leva_single_stock,
private_equity_buffer, monetario_liquidita
```

Ogni famiglia ha ~20 parametri (rsi_entry_low/high, adx_entry, ema_dist_max, days_above_ema, ecc.)

### Fix Principali (2026-08-04/05)

| Fix | Impatto | Codice |
|-----|---------|--------|
| Regime BULL verificato UNA SOLA VOLTA come fondamenta | Evita doppio controllo | `suggest_level()` |
| Regola E fissata (confronto YAML families) | E non scattava mai | `is_equity_family`, `YAML_EQUITY_COMMODITY_FAMILIES` |
| L0 FAST/SLOW richiedono conferma recovery | Elimina falsi L0 che scendevano | `_get_l0_confirmation_signal()` |
| SG dinamico ora legge EMA20_series reale | TP era statico | `database.get_ohlc_by_isin()` |

### Test Risultati (backtest_l1.py)

```
7/7 puro:              win_rate = X% (baseline)
6/7 puro:              win_rate = Y% (più ingressi, perdenti)
Smart 6/7 MACD obbl:   win_rate = Z% ← MIGLIORE
```
**Conclusione**: 6 condizioni + MACD obbligatorio batte 7/7 rigido.

### Prossimi Step (Suggeriti)

1. **Variare la regola di entry**: implementare "smart 6/7 MACD" come opzione in YAML
2. **Rimuovere `ema20_slope_min`**: parametro morto dal YAML
3. **Testare kill switch e SL/TP dinamici** su dati reali 2026 (backtest portfolio reale)
4. **Monitorare L2 smoothing** (sono state le ultime email fittizie?)
5. **Tracking P&L reale**: aggiorna portfolio.html con trades chiusi ultimi 30gg

---

## MEMORIA DA AGGIORNARE

Rimuovere/aggiornare da memoria precedente:
- ❌ ADR_ARCHITECTURE_DECISIONS.md (obsoleto)
- ❌ STEP3_v4_0_EVOLUTION_ANALYSIS.md (obsoleto)
- ❌ Tutti i memory .md specifici di v3.2/v4.0 interim

Mantieni:
- ✅ CURRENT_STATUS.md
- ✅ PARAMETERS_CURRENT.md
- ✅ BUGS_FIXED.md

---

## Comandi Rapidi Post-Allineamento

```bash
# Verifica stato locale
git log --oneline -5

# Trigger monitor manuale
ssh root@76.13.37.133 "curl -X POST http://localhost:5001/api/trigger-update"

# Vedi L0/L1/L2 counts
cat data/dashboard_data.json | jq '.summary'

# Backtest nuova variante
python3 backtest_l1.py --variant=smart_6_7_macd --output=results.json
```

---

## Note Critiche

1. **Nessun ordine automatico**: il sistema suggerisce L0/L1, l'utente compra/vende manualmente
2. **PDF auto-sincronizzato**: generato da YAML, non hardcoded
3. **Due motori L1 exit**: confondere dashboard vs portfolio porta a metriche sbagliate
4. **Parametro morto**: `ema20_slope_min` va rimosso dal YAML prossima release
