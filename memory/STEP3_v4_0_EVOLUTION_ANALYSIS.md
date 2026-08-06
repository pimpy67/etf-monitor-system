---
name: step3-v4-0-evolution-analysis
description: Architectural review v4.0 — Analisi comparativa v2/v3/v4 + rischi + mitigazioni
metadata: 
  node_type: memory
  type: project
  date: 2026-07-22
  originSessionId: 2f9d89cf-c8ec-4cb5-8314-7d617accdaa5
  modified: 2026-07-22T20:43:34.299Z
---

# STEP 3 v4.0 Evolution — Architectural Review & Mitigations

## PARTE 1: Analisi Comparativa (v2.0 → v3.0 → v4.0)

### Sintesi della Transizione

| Aspetto | v2.0 (Iniziale) | v3.0 (PDF/Dashboard) | v4.0 (prompt.md) | Stato |
|---------|---|---|---|---|
| **L1 Ingresso** | Buy Count 4/6 elastico | 6 condizioni rigide | **7 condizioni ALL mandatory** | ⚠️ Disallineato |
| **L1 Profit Exit** | Piede Dentro 90/10 (XEON) | Uscita per Stanchezza RSI | Stop Gain Dinamico + Trailing | ⚠️ Stravolto |
| **L0 Logica** | Drawdown % fissa + RSI | Pragmatico (4-10%) | **Doppio percorso + regime filter + ATR-normalized** | ⚠️ Completamente riscritto |
| **L2 Ruolo** | Watchlist (Buy Count 3-4) | Non dettagliato | **Readiness Score 0-100 + anti-flickering** | ⚠️ Riconcettualizzato |
| **Regime Filter** | Bull/Laterale/Bear visivo | Nessuna penalità | **Integrato in L0 come vincolo quantitativo** | ⚠️ Semplificato/Sostituito |

**Conclusione**: Transizione da sistema **euristico-elastico** (v2.0) a architettura **quantitativa a 2 marce** (v4.0). Non è un'evoluzione incrementale — è una riscrittura strutturale.

---

## PARTE 2: Validità Tecnica di v4.0

### ✅ PRO (Punti di Forza Reali)

#### 1. **Normalizzazione Volatilità su L0** (ATR/Z-Score)
- **Problema risolto**: Drawdown fisso (-8%) scatta su mercati tranquilli (falsi segnali), manca rimbalzi su crypto ad alta volatilità (+25%)
- **Soluzione**: `dd_threshold_effettivo = dd_threshold_atr_multiple * ATR(60) / prezzo_medio` → adatta il trigger a ogni asset
- **Impatto**: ✅ Riduce falsi L0 su asset low-vol (bond), cattura rimbalzi su asset high-vol
- **Rischio**: Richiede storico ATR(60) pulito; se malcalcolato → ancora più falsi segnali

#### 2. **Anti-Flickering su L2** (Isteresi 70/60 + EMA3 + Hard-Reset)
- **Problema risolto**: Readiness Score oscilla nei mercati laterali (whipsaw, notifiche spam)
- **Soluzione**: 
  - Entrata L2 a score 70, uscita solo sotto 60 (banda isteresi 10 punti)
  - EMA3 smoothing riduce il rumore giornaliero
  - Hard-reset su salti >25 punti per rimanere reattivo sui cambi regime
- **Impatto**: ✅ Elimina 70-80% del noise, mantiene reattività sui trend veri
- **Validazione necessaria**: Testare su periodo 2022-2023 chop market (laterale 14 mesi eurostoxx)

#### 3. **State Machine L0 + Lock/Invalidation**
- **Problema risolto**: Stateless recalc ad ogni candela generava incoerenze (entra/esce/rientra nello stesso giorno)
- **Soluzione**: Memorizza `l0_confirmation_mode` (fast/slow), `l0_trigger_low_price` → invalidazione se prezzo rompe al ribasso
- **Impatto**: ✅ Coerenza sequenziale, evita esposizioni errate in downtrend prolungati
- **Rischio CRITICO**: Se DB si corrompe → perdita stato → incoerenza permanente fino al reset manuale

#### 4. **Override Squeeze su L1** (Perché no? Perché sì?)
- **Idea**: Se prezzo in compressione di volatilità + breakout confermato (ADX salita, volume) → bypassare il check spazio residuo
- **Impatto**: ✅ Cattura i breakout migliori (pre-esplosione), non scarta per compressione artificiale
- **RISCHIO GRAVE**: Senza **volume filter**, entra in false breakout su illiquidità mattutina Borsa Italia
- **Mitigazione**: Richiedi `volume_avg_20gg * 1.5 < volume_odierno` PRIMA di scattare override

---

### 👎 CONTRO e RISCHI (Criticità Gravi)

#### 1. **Rischio Overfitting Catastrofico** ⚠️⚠️⚠️
**Stato**: CRITICO

Ogni famiglia ha 25-30 parametri:
```
rsi_entry_low, rsi_entry_high, adx_entry, days_above_ema, ema_dist_max,
l0_dd_threshold, l0_rsi_max, l0_recovery_min_pct,
sl_initial_pct, trailing_base_pct, trailing_sensitivity, trailing_min_pct,
sg_target_max, sg_target_floor, sg_slope_window, sg_slope_sensitivity,
l2_score_weights (6 componenti), isteresi_enter, isteresi_exit, ...
```

**Domanda critica**: Come sono stati ottenuti questi valori?
- ✅ Se: Walk-Forward Optimization su 3+ anni di dati, convalidati su periodi holdout
- ❌ Se: Manually tuned guardando i grafici negli ultimi 6 mesi → **OVERFITTING TOTALE**

**Evidenza sospetta**: I valori nel YAML sono perfetti (nessuno è "tondo" come 20, 50, 100) → suggerisce ottimizzazione, ma su quale periodo?

**Impatto se vero**: 
- Sistema scatta su segnali che rispecchiano il 2026-01 / 2026-07 ma non generalizzano
- Live: 30-50% dei segnali L1 chiuderanno in perdita entro 5 giorni

**Mitigazione OBBLIGATORIA** (vedi PARTE 3):
- Eseguire backtest walk-forward su 2020-2025
- Testare su chop zone (2022-2023)
- Congelamento parametri fino a ottobre 2026 (min 3 mesi di live)

---

#### 2. **Latenza del Percorso Lento L0** ⚠️⚠️
**Stato**: MODERATO

Requisiti percorso lento:
- Prezzo sotto SMA200 per **regime_min_days_below_sma200** giorni (default 5-7?)
- Drawdown sostenuto per **dd_min_duration_days** giorni (default 3-5?)
- Reclaim della EMA50

**Scenario reale**:
```
22 Lug: Crash -5% intraday → Prezzo attraversa SMA200 (Day 1)
23 Lug: +2% rimbalzo → Prezzo ancora sotto SMA200 (Day 2)
24 Lug: +1.5% → Prezzo ancora sotto (Day 3)
25 Lug: +3% BREAKOUT sopra SMA200 → Entra L0

Risultato: L0 entra il QUARTO GIORNO, quando il primo 70% del rimbalzo è già fatto.
Entrata @ €108 vs picco €100, invece di €102 ideale.
```

**Impatto**: 
- ❌ Reward/Risk ratio degradato (margine ridotto)
- ❌ Stop loss L0 triggered prima che target sia raggiunto

**Mitigazione**: 
- Rendere `regime_min_days_below_sma200` **dinamico** → se calo giornaliero > -5%, entra subito (fast-track)
- Aggiungere percorso **ultra-rapido** (Z-score > 3 in 1 giorno) → entry immediato senza attesa regime lento

---

#### 3. **Complessità State Machine & Rischi DB** ⚠️⚠️
**Stato**: ELEVATO

Richieste di persistenza:
- `l0_trigger_low_price` (float) per ogni ISIN
- `l0_confirmation_mode` (string: 'fast' o 'slow')
- `l0_trigger_date` (timestamp)
- `l1_entry_price` (float) per calcolare SL
- `l2_readiness_score_ema` (float, la media smoothed)
- `l2_score_last_hard_reset` (timestamp)

**Rischi**:
- 🔴 Se database PostgreSQL ha failover → perdita stato intermedio
- 🔴 Se `l0_trigger_low_price` si corrrompe → invalidazione bloccata, false posizioni
- 🔴 Se EMA3 smoothed su L2 perde memoria → oscillazioni erratiche

**Mitigazione**:
- Backup giornaliero dello stato (fatto, ma verificare)
- Health check sullo stato all'avvio di monitor.py
- Log di ogni transizione di stato (audit trail)

---

#### 4. **Dipendenza da Parametri Configurabili Non Testati** ⚠️
Alcuni parametri nuovi non sono mai stati validati live:
- `flash_crash_zscore_threshold` (default 4) → non è mai stato attivato
- `reclaim_ema_fast_period` (20) vs `reclaim_ema_slow_period` (50) → mai verificato quale è migliore
- `capitulation_volume_multiplier` → volume non sempre disponibile per ETF europei

**Rischio**: L0 potrebbe non scattare mai (o scattare male) su asset reali perché parametri non convalidati.

---

## PARTE 3: Proposte di Mitigazione & Implementazione

### 3.1 Volume Filter su Override Squeeze (CRITICO)

**Stato**: NON IMPLEMENTATO

**Proposta**:
```python
def is_squeeze_override_valid(etf, volume_today, volume_avg_20):
    """
    Override dello squeeze scatta SOLO se:
    1. Range di compressione sotto 1.5% (squeeze confermato)
    2. Volume odierno > 1.5 × volume_avg_20 (conferma volume)
    3. Oppure: volume_expansion > 30% E ADX in salita > 2 punti su 3gg
    """
    squeeze_ok = (max_20 - min_20) / close < 0.015
    volume_ok = volume_today > volume_avg_20 * 1.5
    adx_rising = (adx_today - adx_3gg_ago) > 2
    
    return squeeze_ok AND (volume_ok OR (adx_rising AND volume_expansion > 0.30))
```

**Implementazione**: Aggiungere a `technical_analysis.py::l1_check_space_residuo_minimo()`

**Priorità**: 🔴 CRITICA (evita falsi breakout su illiquidità)

---

### 3.2 Dynamic Reclaim EMA (MIGLIORATIVO)

**Stato**: IN DISCUSSIONE

**Proposta ALTERNATIVA** a EMA20/50 fisse:
```python
def calculate_dynamic_reclaim_ema(etf_family_name, atr_ratio):
    """
    Reclaim EMA varia con la volatilità dell'asset:
    - Asset low-vol (bonds): EMA50 (lento, robusto)
    - Asset normal (equity): EMA30 (equilibrio)
    - Asset high-vol (crypto): EMA15 (reattivo)
    
    Basato su ATR(60) / media_prezzo_60gg:
    - Se atr_ratio < 1% → low vol → EMA50
    - Se 1% < atr_ratio < 3% → normal → EMA30
    - Se atr_ratio > 3% → high vol → EMA15
    """
    if atr_ratio < 0.01:
        return 50
    elif atr_ratio < 0.03:
        return 30
    else:
        return 15
```

**Vantaggi**: Meno hardcoded, più adattivo

**Svantaggi**: Aggiunge complessità, possibile ulteriore fonte di rumore se ATR(60) è sporco

**Raccomandazione**: Testare su 20 ETF diversi (bond, equity, crypto) prima di rollout generale. **Possibile skip** se EMA50 fissa funziona bene live.

---

### 3.3 Robustness Test (OBBLIGATORIO) 🔴

**Stato**: NON FATTO

**Piano di Test**:

#### Phase 1: Backtest Walk-Forward (2 settimane)
```
Dati: 2020-01-01 → 2026-07-22
Suddivisione: 5 periodi di 1 anno ciascuno
Per ogni periodo:
  - Training: primo anno
  - Test: secondo anno
  - Misuramento: % L1 profittevoli entro 5gg, Sharpe ratio L1, Max Drawdown L0
  
Se risultato < 50% profittevoli → parametri troppo aggressivi
Se risultato > 70% profittevoli → possibile overfitting
Target: 55-65% profittevoli, Sharpe > 0.8
```

#### Phase 2: Chop Zone Test (1 settimana)
```
Periodo: 2022-06-01 → 2023-12-31 (laterale totale)
Contare:
  - Quanti L1 falsi (chiudono in loss entro 5 giorni)
  - Quanti L2 flickering (oscillano più di 10 volte)
  - Quanti L0 scattati (dovrebbero essere pochi)
  
Target: < 8% L1 falsi, < 5 flickering per asset, < 2 L0 per asset
```

#### Phase 3: Live Paper Trading (1 mese)
```
Simulare l'esecuzione live senza denaro reale
Contare:
  - Slippage medio vs EMA20 entry (dovrebbe essere <0.5%)
  - Latenza esecuzione (in minuti)
  - Incoerenze stato (rientro senza uscita precedente, ecc)
  
Tolleranza: Slippage < 0.7%, latenza < 5min, zero incoerenze
```

**Timeline**: 3-4 settimane + 1 mese live = 5-6 settimane prima di $ reali

**Responsabilità**: Dovrebbe essere eseguito PRIMA di continuare a sviluppare ulteriormente.

---

### 3.4 Allineamento Documentazione (URGENTE) 🔴

**Stato**: Critico (3 fonti disallineate)

**Piano**:

1. **Scegliere la fonte di verità unica**: `config/etf_families.yaml`
   - Contiene TUTTI i parametri
   - È machine-readable
   - È versionabile in git

2. **Generare PDF automaticamente** da YAML
   - `pdf_generator.py` legge YAML → genera PDF con tutti i parametri e le spiegazioni
   - Eseguito ogni ciclo di monitor
   - Eliminare qualsiasi hardcoding di parametri nel PDF

3. **Generare HTML dashboard dinamicamente**
   - Aggiungere endpoint `/api/parameters` che legge YAML
   - `dashboard.html` carica parametri via AJAX da `/api/parameters`
   - Mostra sempre i valori live, non hardcoded

4. **CLAUDE.md rimane come "Spiegazione Concettuale"**
   - NON deve contenere valori numerici
   - Contiene solo descrizioni, razionale, e link al PDF/Dashboard per i valori attuali
   - Aggiornare ONLY quando cambiano i **concetti**, non i parametri

**Implementazione**: ~3 ore (vedi schema sotto)

```
config/etf_families.yaml (FONTE UNICA)
    ↓ (read)
    ├─→ pdf_generator.py → data/ETF_Monitor_Parametri.pdf (auto-gen)
    ├─→ app.py /api/parameters → JSON (live)
    └─→ CLAUDE.md (reference concettuale)
    
dashboard.html:
    ├─→ Legge /api/parameters via AJAX
    ├─→ Mostra parametri dinamicamente
    └─→ Downloader PDF automaticamente aggiornato
```

---

## PARTE 4: Decisioni Architetturali da Prendere

### Decisione 1: Congelare v4.0 o Evolversi a v4.1?

**Opzione A**: Congelare v4.0 adesso
- ✅ Permette backtest/validazione senza target mobile
- ✅ Documentazione stabile
- ❌ Alcuni rischi (latenza L0, overfitting) rimangono non risolti

**Opzione B**: Implementare le mitigazioni prima di live
- ✅ Riduce rischi operativi
- ✅ Sistema più robusto
- ❌ 2-3 settimane di lavoro extra

**Raccomandazione**: **Opzione B** — i rischi sono troppi per andare live "così".

Timeline minimo:
1. Settimana 1: Implementare volume filter + dynamic reclaim (se accettato)
2. Settimana 2-3: Backtest walk-forward + chop zone
3. Settimana 4: Live paper trading
4. Settimana 5+: Live con denaro reale (con stop in standby)

---

### Decisione 2: Rimuovere o Tenere la Regola "Piede Dentro 90/10"?

Osservazione: La v2.0 aveva la regola D (Piede Dentro 90/10 su XEON), ma v4.0 l'ha silenziata in favore di Stop Gain Dinamico.

**Stato attuale nel codice**: Che cosa implementato effettivamente?

Domande:
- ✅ Codice monitor.py ha la logica 90/10 con XEON?
- ✅ Oppure ha solo stop gain dinamico %?

**Se 90/10 è ancora nel codice**: Allinearlo a CLAUDE.md
**Se è rimosso**: Documentare perché (decisione architetturale consapevole)

---

### Decisione 3: L2 come "Readiness Score" vs "Watchlist Tradizionale"

La v4.0 trasforma L2 da categoria trading a "indicatore di pre-allarme".

**Pro**: Anti-flickering, meno falsi segnali
**Contro**: Non è più un livello di ordine → può confondere gli utenti

**Raccomandazione**: Mantenere L2 come livello di ordine (= Buy Count 4-5/6), ma aggiungere il Readiness Score come campo informativo separato nella dashboard (non confondere i due).

---

## PARTE 5: Checklist di Implementazione

- [ ] **Critical Path**
  - [ ] Implementare volume filter su squeeze override
  - [ ] Eseguire backtest walk-forward (2020-2026)
  - [ ] Eseguire chop zone test (2022-2023)
  - [ ] Allineare YAML → PDF → HTML (fonte unica)

- [ ] **Important**
  - [ ] Valutare dynamic reclaim EMA (decide skip/implement)
  - [ ] Verificare quale logica è realmente nel codice (90/10 vs stop gain)
  - [ ] Health check stato DB all'avvio
  - [ ] Audit trail per ogni transizione L0/L1/L2

- [ ] **Nice-to-Have**
  - [ ] Ultra-fast L0 trigger per cali > -5% intraday
  - [ ] Parametri time-varying (es. adx_entry sale in bear market)
  - [ ] Dashboard mostra backtest performance per famiglia

---

## Conclusione

L'architettura v4.0 è **concettualmente sound** ma **operativamente rischiosa** senza validazione. Il salto da v2.0 (euristico) a v4.0 (quantitativo 2-marce) è ambizioso e non completamente stabilizzato.

**Recomandazione finale**: 
1. ✅ Procedere con le mitigazioni della Parte 3
2. ✅ Eseguire rigoroso backtest prima di live
3. ✅ Allineare documentazione a YAML unico
4. ⚠️ **Congelamento live fino a ottobre** (min 3 mesi produzione)

Se questo timeline non è fattibile → considerare rollback a v2.0 (buy count elastico) con miglioramenti incrementali invece che riscrittura totale.
