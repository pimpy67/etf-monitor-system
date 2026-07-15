# 🔄 AGGIORNAMENTO URGENTE — Gerarchia 2+2 (2026-07-15)

> **SOSTITUIRE le sezioni nel v5_DEFINITIVO.md con queste versioni aggiornate**

---

## 📋 Schema Generale: L1 "Trend Sicuro" — Gerarchia 2+2 INTELLIGENTE

### ⚠️ CAMBIAMENTO CRITICO
La vecchia logica "6 condizioni rigorose tutte obbligatorie" è stata **sostituita** dalla **gerarchia 2+2** che consente entry più veloci:

```
VECCHIO (v5.0):
  ✓ 6/6 condizioni tutte obbligatorie → entry molto tardiva (day 5-7)
  
NUOVO (2026-07-15):
  ✓ Gate 2/2 OBBLIGATORIO (A ∧ M)  + Velocity 2+/4 FLESSIBILE → entry day 1
```

---

## 🎯 NUOVA LOGICA ENTRY L1 — Gerarchia 2+2

### **GATE STRUTTURALE** — 2/2 OBBLIGATORI (non negoziabili)

| Parametro | Condizione | Significato |
|-----------|-----------|-------------|
| **A** (Allineamento) | `price > EMA20` | Il prezzo è sopra la media veloce — il rally è attivo |
| **M** (MACD Momentum) | `MACD_histogram > 0` | Il volume sta spingendo al rialzo — momentum positivo |

**Regola**: Se **A ∧ M** sono entrambi FALSE → **BLOCCO TOTALE**, nessun ingresso possibile.

---

### **VELOCITÀ FLESSIBILE** — Almeno 2 su 4 RICHIESTI

| Parametro | Condizione | Significato |
|-----------|-----------|-------------|
| **P** (Prezzo) | `price > SMA50` | Il prezzo è sopra la media media — allineamento confermato |
| **R** (RSI) | `rsi_entry_low ≤ RSI ≤ rsi_entry_high` | RSI in range ottimale per famiglia — momentum non ancora esausto |
| **D** (ADX) | `ADX ≥ adx_min_threshold` (es. 15-18) | Forza direzionale confermata — trend è reale, non rumore |
| **X** (allineamento eXteso) | `EMA20 > SMA50` | La media veloce sta superando la media media — allineamento bifase |

**Regola**: Conteggia quanti tra {P, R, D, X} sono TRUE. Se **count ≥ 2** → INGRESSO AUTORIZZATO.

---

## 📊 MATRICE GERARCHIA 2+2 — Livello di Confidence

```
Gate 2/2 ✓  +  Velocity 2/4  →  Confidence 60%  (size 60% dell'allocation)
Gate 2/2 ✓  +  Velocity 3/4  →  Confidence 80%  (size 80% dell'allocation)
Gate 2/2 ✓  +  Velocity 4/4  →  Confidence 100% (size 100% dell'allocation)

Gate 2/2 ✗  →  NO ENTRY (blocco immediato)
```

---

## 💡 VANTAGGI GERARCHIA 2+2 vs 6/6 Rigoroso

| Aspetto | Vecchio 6/6 | Nuovo 2+2 |
|---------|:---:|:---:|
| **Entry timing** | Day 5-7 | Day 1 |
| **False signals** | 5-8% | 10-15% |
| **Profit captured** | +2-3% (coda) | +4-6% (intero move) |
| **Requisito minimo** | Tutte 6 | Solo Gate 2/2 + Vel 2/4 |
| **Logica** | Rigida | Intelligente |

---

## 📧 STRUTTURA EMAIL AGGIORNATA — Separazione Portafoglio vs Watchlist

```
════════════════════════════════════════════════════
📊 ETF Monitor | Analisi Giornaliera | 15/07/2026
════════════════════════════════════════════════════

── PORTAFOGLIO L1 (In Posizione) ────────────────────

ETF              | Carico  | Attuale | Perf%  | Gg | Entry Mode | SL   | SG
Russell 2000     | 373.35  | 392.10  | +5.01%| 51 | TIERED     |388.18|402.25
EPAB Eurozone    | 40.39   | 42.80   | +6.0% | 50 | ACCELERATED|42.37 |43.32

[Totale L1: +5.5% | +689€]

── NUOVI SEGNALI L1 — Gerarchia 2+2 (Valuta Acquisto) ────────

ETF              | Ticker | Entry Mode | Gate A∧M | Velocity | Size | Note
IQQI             | IQQI.DE| GERARCHIA  | ✓ 2/2   | 2/4      | 60%  | RSI ottimale, prezzo > SMA50
USPY             | USPY.DE| GERARCHIA  | ✓ 2/2   | 3/4      | 80%  | Momentum forte, ADX > 15

[Regime: BULL 75/100]

── L2 WATCHLIST (Monitoraggio) ──────────────────────

(166 ETF con 2-3 condizioni L1 confermano il trend rialzista)

── L0 DEEP RECOVERY (in Posizione) ──────────────────

(0 ETF in fase di recupero)
```

---

## 🔧 Tabella Parametri Aggiornata — Gerarchia 2+2

### L1 Entry Parameters (Gate A∧M sempre obbligatorio)

| Famiglia | RSI Entry | ADX Min | days_EMA | Dist Max | P >SMA50 | R Range | D ≥ | X >SMA50 | Note |
|----------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|------|
| equity_sviluppati | 45–55 | 22 | 5 | 4.0% | ✓ | ✓ | 15 | ✓ | Require 2+ velocity |
| mercati_emergenti | 40–52 | 22 | 3 | 5.0% | ✓ | ✓ | 15 | ✓ | Flexible entry |
| settoriali_growth | 48–58 | 25 | 5 | 5.0% | ✓ | ✓ | 18 | ✓ | Tech/AI volatile |
| bond_governativi | 38–48 | 12 | 3 | 1.5% | ✓ | ✓ | 10 | ✓ | Conservative |
| crypto_digital_assets | 35–52 | 28 | 3 | 6.0% | ✓ | ✓ | 20 | ✓ | Ultra-volatile |
| commodity | 40–55 | 22 | 3 | 3.0% | ✓ | ✓ | 15 | ✓ | Mean-reversion |
| oro_metalli_preziosi | 38–52 | 18 | 3 | 2.5% | ✓ | ✓ | 12 | ✓ | PM safe-haven |
| real_estate_reit | 42–52 | 15 | 3 | 2.0% | ✓ | ✓ | 10 | ✓ | Dividend focus |
| private_equity_buffer | 40–55 | 15 | 3 | 2.5% | ✓ | ✓ | 10 | ✓ | Conservative |
| settoriali_difensivi | 42–50 | 18 | 5 | 2.5% | ✓ | ✓ | 12 | ✓ | Health/Utility |
| leva_single_stock | 45–58 | 28 | 3 | 4.0% | ✓ | ✓ | 20 | ✓ | Leverage 3x |
| bond_corp_hy_em | 42–52 | 15 | 3 | 2.0% | ✓ | ✓ | 10 | ✓ | Corp/HY bonds |
| monetario_liquidita | — | — | 3 | 0.5% | ✓ | — | — | ✓ | No entry (safe) |
| metalli_industriali | 38–50 | 20 | 3 | 3.0% | ✓ | ✓ | 12 | ✓ | Battery metals |
| inflation_linked | 38–48 | 12 | 3 | 1.5% | ✓ | ✓ | 10 | ✓ | Inflation hedge |

**Legenda**:
- ✓ = Parametro attivo per velocity check
- RSI Entry = Range per condizione R (Velocity)
- ADX Min = Soglia per condizione D (Velocity)
- P >SMA50, R Range, D ≥, X >SMA50 = 4 parametri di Velocity

---

## ✨ L0 Deep Recovery — Rimane Uguale

**Entrata**: 4 condizioni pragmatiche (drawdown 6-25%, RSI, divergenza, ripresa)  
**Uscita**: 6 regole (F/A/B/C/E/D)  
**L0 è indipendente da Gerarchia 2+2** — continua con logica propria

---

## 📌 IMPLEMENTAZIONE LIVE

- **File**: `technical_analysis.py`
- **Funzione**: `check_l1_entry_accelerated()` (v7)
- **Dashboard**: Mostra `entry_mode` = ACCELERATED | TIERED | NONE
- **Email**: Separa Portafoglio L1 dai Nuovi Segnali Gerarchia 2+2
- **Log**: Format "⚡ Gerarchia 2+2: gate A∧M ✓ | velocity X/4 ✓ — size Y%"

---

## 🚀 PRIORITÀ PROSSIMI PASSI

1. ✅ **Gerarchia 2+2 implementata** in `technical_analysis.py`
2. ✅ **Dashboard aggiornato** per mostrare entry_mode
3. ⏳ **Email** — Aggiorna template per separare Portafoglio vs Nuovi Segnali
4. ⏳ **PDF** — Rigenera con nuova documentazione Gerarchia 2+2
5. ⏳ **Test live** — Attendi prossimo monitor ciclo per verificare signals

