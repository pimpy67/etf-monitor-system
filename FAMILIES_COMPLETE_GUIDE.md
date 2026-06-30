# 📘 ETF Monitor System — Guida Completa 14 Famiglie

**Versione**: v2.0 Refactor (29 giugno 2026)  
**Status**: Implementato e operativo  
**Ultimo aggiornamento**: 30 giugno 2026

---

## 🎯 Indice Navigazione

| # | Famiglia | Tipo | Volatilità | Pagina |
|---|----------|------|-----------|--------|
| 01 | **Equity Sviluppati** | Large Cap Global | Bassa-Media | [→](#01-equity-sviluppati) |
| 02 | **Mercati Emergenti** | EM Globale | Media-Alta | [→](#02-mercati-emergenti) |
| 03 | **Settoriali Growth** | Tech, AI, Semi, Nasdaq | Alta | [→](#03-settoriali-growth) |
| 04 | **Settoriali Difensivi** | Salute, Utilities, Food | Bassa | [→](#04-settoriali-difensivi) |
| 05 | **Bond Governativi** | BTP, Bund, UST, Gov Euro | Molto Bassa | [→](#05-bond-governativi) |
| 06 | **Bond Corp/HY/EM** | Corp EUR/USD, HY, EM Bond | Media | [→](#06-bond-corp-hy-em) |
| 07 | **Inflation Linked** | Protezione inflazione | Bassa | [→](#07-inflation-linked) |
| 08 | **Commodities** | Bloomberg Comm, GSCI, Agri, Energia | Alta | [→](#08-commodities) |
| 09 | **Oro/Metalli Preziosi** | Oro, Argento, Platino | Media | [→](#09-oro-metalli-preziosi) |
| 10 | **Metalli Industriali** | Rame, Alluminio, Zinco, Battery | Alta | [→](#10-metalli-industriali) |
| 11 | **Real Estate / REIT** | EPRA Europe, NAREIT, REIT | Media | [→](#11-real-estate-reit) |
| 12 | **Crypto / Digital** | Bitcoin, Ethereum, Solana | Molto Alta | [→](#12-crypto-digital-assets) |
| 13 | **Leva / Single Stock** | 3x Long/Short su titoli | Estrema | [→](#13-leva-single-stock) |
| 14 | **Private Equity / Buffer** | Listed PE, Buffer Strategy | Media-Alta | [→](#14-private-equity-buffer) |
| 15 | **Monetario / Liquidità** | ETF overnight, short-term | Nulla | [→](#15-monetario-liquidita) |

---

## 📊 Schema Generale L1 — 6 Condizioni di Entrata (TUTTE OBBLIGATORIE)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    L1 "TREND SICURO" — ENTRY CONDITIONS                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ✓ CONDIZIONE 1: ALLINEAMENTO (price > EMA20 > SMA50 > SMA200*)            │
│                  *SMA200 richiesto solo se mm200_filter=True per famiglia   │
│                                                                              │
│  ✓ CONDIZIONE 2: PERSISTENZA (giorni_sopra_EMA20 >= N + slope(EMA20) > 0)  │
│                  Evita falsi segnali da singoli giorni di rialzo            │
│                                                                              │
│  ✓ CONDIZIONE 3: RSI OTTIMALE (rsi_entry_low ≤ RSI ≤ rsi_entry_high)      │
│                  Range specifico per famiglia — evita ipercomprato          │
│                                                                              │
│  ✓ CONDIZIONE 4: DISTANZA EMA20 (0% ≤ dist_EMA20 ≤ ema_dist_max)          │
│                  Non entrare troppo esteso da EMA20 (rischio pullback)      │
│                                                                              │
│  ✓ CONDIZIONE 5: ADX (ADX ≥ adx_entry)                                     │
│                  Forza direzionale confermata — trend robusto               │
│                                                                              │
│  ✓ CONDIZIONE 6: MACD MOMENTUM (histogram > 0 AND [rising OR dist<2%])     │
│                  Momentum in accelerazione o riacquisto vicino EMA20        │
│                                                                              │
│  🚫 KILL SWITCH: Se variazione giornaliera ≤ -3.0% → INGRESSO BLOCCATO     │
│                  (solo nuovi ingressi; uscite rimangono operative)          │
│                                                                              │
│  📍 REGIME OBBLIGATORIO: BULL (EMA20 > SMA50 + banda_famiglia)              │
│                          Laterale e Bear escludono ingressi L1              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚪 Schema Generale Uscite L1 — 6 Regole (Priorità dall'Alto)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   L1 "TREND SICURO" — EXIT RULES (PRIORITY)                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1️⃣ F — KILL SWITCH (⚠️ IMMEDIATE)                                          │
│     Trigger: Calo giornaliero ≤ -3.0%                                      │
│     Azione: USCITA TOTALE IMMEDIATA                                         │
│     Tipo: Totale                                                            │
│     Applies: ✓ Tutte le famiglie                                            │
│                                                                              │
│  2️⃣ A — STOP LOSS (⚠️ FIRM)                                                 │
│     Trigger: Prezzo < EMA20 da ≥ 3 giorni CONSECUTIVI                      │
│     Azione: USCITA TOTALE (o skip per bond/monetari)                        │
│     Tipo: Totale                                                            │
│     Applies: ✓ Equity/Commodity | ✗ Bond/Monetari                          │
│     Note: 3 giorni = tolleranza panico, evita falsi segnali                │
│                                                                              │
│  3️⃣ B — TRAILING STOP (📉 REACTIVE)                                         │
│     Trigger: EMA10 < EMA20                                                  │
│     Azione: USCITA TOTALE                                                   │
│     Tipo: Totale                                                            │
│     Applies: ✓ Tutte le famiglie                                            │
│     Note: Molto più rapido del death cross EMA20<SMA50                      │
│                                                                              │
│  4️⃣ C — STANCHEZZA (😴 OVERBOUGHT FATIGUE)                                 │
│     Trigger: RSI_ieri ≥ 70 AND RSI_oggi < 70 (o soglia famiglia)           │
│     Azione: USCITA TOTALE                                                   │
│     Tipo: Totale                                                            │
│     Applies: ✓ Equity/Commodity | ✗ Bond/Monetari                          │
│     Note: Esce dall'ipercomprato quando momentum scema                      │
│                                                                              │
│  5️⃣ E — ADX DEBOLE + PRICE BELOW EMA20 (📉 TREND EXHAUSTION)               │
│     Trigger: ADX < 18 AND prezzo < EMA20                                   │
│     Azione: USCITA TOTALE (se trend esaurito)                               │
│     Tipo: Totale                                                            │
│     Applies: ✓ Equity/Commodity | ✗ Bond/Monetari                          │
│     Note: Condizione congiunta evita falsi segnali in consolidamenti        │
│                                                                              │
│  6️⃣ D — USCITA PARZIALE 90% (💰 PARTIAL TAKE-PROFIT)                       │
│     Trigger: RSI > 78 (rsi_overbought - soglia per presa parziale)         │
│     Azione: VENDI 90% posizione → acquista XEON (ETF monetario EUR €STR)   │
│     Tipo: PARZIALE (90% sold, 10% mantieni come "sensore")                │
│     Applies: ✓ Equity/Commodity | ✗ Bond/Monetari                          │
│     Note: Il 10% rimasto continua a tracciare l'ETF                         │
│                                                                              │
│  🔄 LOGICA "PIEDE DENTRO" (90%/10% STAY):                                   │
│                                                                              │
│     Step 1 (Regola D → RSI > 78):                                           │
│         • Vendi il 90% della posizione equity                               │
│         • Acquista XEON con il ricavato (guadagna ~3-4% annuo €STR)        │
│         • Mantieni 10% dell'ETF equity: è il "sensore"                      │
│                                                                              │
│     Step 2 (Se arriva F/A/B/C/E prima del rientro):                         │
│         • Vendi il 10% rimanente dell'ETF equity                            │
│         • Mantieni XEON fino al rientro (monetario puro)                    │
│                                                                              │
│     Step 3 (Rientro L1 — tutte 6 condizioni di nuovo vere):                 │
│         • Vendi tutto XEON → ricavi                                         │
│         • Rientra 100% su ETF equity                                        │
│         • Il 10% già presente non richiede riacquisto (è rimasto dentro)    │
│                                                                              │
│     ✅ VANTAGGI:                                                             │
│         • 90% guadagna ~3-4% annuo in XEON (no risk)                        │
│         • 10% sensore vede subito il rientro (no timing)                    │
│         • Tassazione solo sul 90% venduto                                   │
│         • Dashboard traccia sempre i prezzi reali                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📚 FAMIGLIE DETTAGLIATE

---

### 01. EQUITY SVILUPPATI
**ID**: `equity_sviluppati`  
**Descrizione**: Azionari sviluppati — Large cap globali, ACWI, All-World  
**Esempi ETF**: IWDA, VWCE, CSPX, MEU, EXSA  
**Volatilità Attesa**: Bassa-Media  
**MA Principale**: EMA20 + SMA50 + SMA200  

#### 📊 Parametri

| Parametro | Valore | Significato |
|-----------|--------|------------|
| **RSI Entry Range** | 45–55 | Entrata ottimale quando prezzo in crescita moderata (non ipercomprato) |
| **RSI Exit Min** | 40 | Uscita se RSI scende troppo (perdita momentum) |
| **RSI Overbought** | 78 | Soglia per presa parziale 90% (regola D) |
| **ADX Entry Min** | 18 | Trend deve essere confermato — forza minima |
| **Dist. EMA20 Max** | 4.0% | Può allontanarsi da EMA20 fino al 4% — ampio margine |
| **Giorni Sopra EMA20** | 3 | Persistenza: 3 giorni consecutivi sopra EMA20 + slope positivo |
| **Banda Laterale** | 1.0% | Regime: BULL se (EMA20-SMA50)/SMA50 > 1.0% |
| **ATR% Max** | 0.03 (3%) | Volatilità giornaliera max 3% |
| **AUM Min** | 50M€ | Liquidità minima — evita ETF illiquidi |
| **SMA200 Filter** | Sì | Esclude bearish assoluti (prezzo < SMA200) |
| **L0 Drawdown** | 15% | Ingresso L0 se prezzo ≥15% sotto picco |
| **L0 RSI Max** | 35 | L0 richiede RSI < 35 (ipervenduto) |
| **Min Buy Count** | 6 | Tutte e 6 le condizioni L1 sono obbligatorie |

#### 🟢 Entrata L1: Logica Passo-Passo

1. **Allineamento** ✓
   - Prezzo > EMA20 (quotazione sopra media mobile veloce)
   - EMA20 > SMA50 (media veloce sopra media intermedia — trend up)
   - Prezzo > SMA200 (sopra trend di lungo termine — no bear assoluto)

2. **Persistenza** ✓
   - Almeno 3 giorni CONSECUTIVI con prezzo > EMA20
   - Slope(EMA20) > 0 (EMA20 in salita, non stagnante)
   - **Razionale**: Evita falsi spike — la salita dev'essere consolidata

3. **RSI Ottimale** ✓
   - 45 ≤ RSI ≤ 55 (range sweet spot per equity sviluppati)
   - **Perché**: RSI 45-55 = crescita moderata senza ipercomprato (>70)
   - RSI troppo basso (<45) = momentum debole
   - RSI troppo alto (>70) = rischio pullback

4. **Distanza EMA20** ✓
   - Prezzo max 4% sopra EMA20
   - (Prezzo - EMA20) / EMA20 ≤ 4%
   - **Perché**: Se prezzo troppo staccato da media, rischia ritorno violento

5. **ADX Confermato** ✓
   - ADX ≥ 18 (forza trend confermata)
   - **Perché**: ADX alto = movimento direzionale forte, no rumori

6. **MACD Momentum** ✓
   - MACD Histogram > 0 (momentum positivo)
   - MACD Histogram > MACD Histogram[ieri] (in accelerazione)
   - **OPPURE** Dist(EMA20) < 2% (riacquisto vicino alla media)
   - **Perché**: Cattura sia continuazioni sia riacquisti quando ancora sottovalutati

#### 🔴 Uscita L1: Quando Vende

| Regola | Condizione | Azione | Quando |
|--------|-----------|--------|--------|
| **F - Kill Switch** | Calo giornaliero ≤ -3% | Vendi 100% SUBITO | Panico/crollo mercato |
| **A - Stop Loss** | Prezzo < EMA20 per 3gg | Vendi 100% | Perdita trend |
| **B - Trailing** | EMA10 < EMA20 | Vendi 100% | Cambio slope veloce |
| **C - Stanchezza** | RSI era ≥70, scende <70 | Vendi 100% | Esce ipercomprato |
| **E - ADX Debole** | ADX < 18 + prezzo < EMA20 | Vendi 100% | Trend esaurito |
| **D - Partial 90%** | RSI > 78 | Vendi 90%, compra XEON | Presa parziale |

#### 🎯 Regime 3-Stati (Banda Laterale 1.0%)

```
BULL:     (EMA20 - SMA50) / SMA50 > +1.0%  → Trend rialzista confermato → L1 ELIGIBILE
LATERALE: abs(EMA20 - SMA50) / SMA50 ≤ 1.0% → Consolidamento → Penalità -1 punto, solo L2
BEAR:     (EMA20 - SMA50) / SMA50 < -1.0% → Trend ribassista → L1 VIETATO, monitoraggio L3
```

---

### 02. MERCATI EMERGENTI
**ID**: `mercati_emergenti`  
**Descrizione**: Emergenti globali — Asia, LatAm, EMEA, volatilità maggiore  
**Esempi ETF**: EIMI, AEME, CI2, KRW, RIO  
**Volatilità Attesa**: Media-Alta  
**MA Principale**: EMA20 + SMA50 + SMA200  

#### 📊 Parametri

| Parametro | Valore | Significato |
|-----------|--------|------------|
| **RSI Entry Range** | 40–52 | Range più stretto (emergenti più volatili) |
| **RSI Exit Min** | 38 | Uscita if momentum lost completamente |
| **RSI Overbought** | 76 | Soglia parziale più bassa che equity (volatilità) |
| **ADX Entry Min** | 22 | Trend deve essere FORTE (22 > 18 equity) |
| **Dist. EMA20 Max** | 5.0% | Più ampio che equity (volatilità naturale) |
| **Giorni Sopra EMA20** | 3 | Stesso: 3 giorni di persistenza |
| **Banda Laterale** | 1.2% | Banda più larga che equity (volatilità) |
| **ATR% Max** | 0.04 (4%) | Volatilità giornaliera max 4% (vs 3% equity) |
| **AUM Min** | 50M€ | Stesso standard di liquidità |
| **SMA200 Filter** | Sì | Stesso filtro bear assoluto |
| **L0 Drawdown** | 20% | Più profondo che equity (naturale volatilità) |
| **L0 RSI Max** | 38 | Più basso (EM oversold più facilmente) |
| **Min Buy Count** | 6 | Tutte 6 condizioni obbligatorie |

#### 🟢 Entrata L1: Logica (Identica a Equity ma Parametri Severi)

Stesso schema di 6 condizioni, ma con soglie più rigorose per la volatilità.

**Punti Chiave**:
- ADX 22 vs 18 equity = richiede trend PROVATO
- RSI 40-52 vs 45-55 = esclude situazioni confuse
- Banda 1.2% vs 1.0% = laterale più larga (emerge oscillano di più)

#### 🔴 Uscita L1: Identiche alle Equity Sviluppati

---

### 03. SETTORIALI GROWTH
**ID**: `settoriali_growth`  
**Descrizione**: Tech, AI, Semi, Nasdaq, Digitale — volatilità elevata, trend lunghi  
**Esempi ETF**: XAIX, CHIP, TNOW, CNDX, EQQQ  
**Volatilità Attesa**: Alta  
**MA Principale**: EMA20 + SMA50 + SMA200  

#### 📊 Parametri

| Parametro | Valore | Significato |
|-----------|--------|------------|
| **RSI Entry Range** | 48–58 | Range ALTO (settoriali trendano a lungo) |
| **RSI Exit Min** | 38 | Uscita se crolla momentum |
| **RSI Overbought** | 78 | Elevato (tech/growth trendano oltre 70) |
| **ADX Entry Min** | 25 | MOLTO ALTO (25 > 22 EM > 18 equity) — trend MUST be strong |
| **Dist. EMA20 Max** | 5.0% | Massimo ampio (volatilità growth) |
| **Giorni Sopra EMA20** | 3 | Stesso |
| **Banda Laterale** | 1.5% | Banda LARGA (growth oscillano) |
| **ATR% Max** | 0.05 (5%) | Volatilità max 5% (highest after crypto) |
| **AUM Min** | 50M€ | Stesso |
| **SMA200 Filter** | Sì | Stesso |
| **L0 Drawdown** | 18% | Tra equity e EM |
| **L0 RSI Max** | 38 | Stesso EM |
| **Min Buy Count** | 6 | Tutte obbligatorie |

#### 🟢 Entrata L1: Logica (Rigorosa)

**Punti Chiave**:
- ADX 25 = MUST HAVE trend forte (esclude laterali growth spesso falsi)
- RSI 48-58 = evita entrate troppo presto (<48) o troppo tardi (>58)
- Banda 1.5% = laterale largo (growth oscillano ma non troppo)

**Razionale**:
Growth trendano a lungo se veri, ma falsi breakout sono comuni. ADX 25 filtra rumore. RSI 48-58 entra a metà del trend, non all'inizio (rischioso) né alla fine (tardi).

#### 🔴 Uscita L1: Identiche a Equity

---

### 04. SETTORIALI DIFENSIVI
**ID**: `settoriali_difensivi`  
**Descrizione**: Salute, Utilities, Insurance, Food — asset poco direzionali, reddito  
**Esempi ETF**: HLT, UTI, LIRU, LFOD, HLTW  
**Volatilità Attesa**: Bassa  
**MA Principale**: SMA50 + SMA200  

#### 📊 Parametri

| Parametro | Valore | Significato |
|-----------|--------|------------|
| **RSI Entry Range** | 42–50 | Range STRETTO e BASSO (asset poco oscillanti) |
| **RSI Exit Min** | 38 | Basso (difensivi poco volatile) |
| **RSI Overbought** | 65 | BASSO (difensivi raramente salgono oltre 70) |
| **ADX Entry Min** | 15 | BASSO (ADX meno rilevante, oscillazioni piccole) |
| **Dist. EMA20 Max** | 2.5% | STRETTO (volatilità bassa) |
| **Giorni Sopra EMA20** | 5 | 5 giorni! (Non 3) — richiede forte persistenza |
| **Banda Laterale** | 1.0% | Stessa equity |
| **ATR% Max** | 0.025 (2.5%) | BASSO (volatilità giornaliera bassa) |
| **AUM Min** | 50M€ | Stesso |
| **SMA200 Filter** | Sì | Stesso |
| **L0 Drawdown** | 15% | Stesso equity |
| **L0 RSI Max** | 35 | Stesso equity |
| **Min Buy Count** | 6 | Tutte obbligatorie |

#### 🟢 Entrata L1: Logica (Paziente)

**Punti Chiave**:
- **5 giorni sopra EMA20** (non 3) = richiede conferma forte per asset che si muove lentamente
- RSI 42-50 = evita entrate ipercomprate (difensivi crescono poco)
- SMA200 + SMA50 primari = trend di lungo è più importante

**Razionale**:
Settoriali difensivi non trendano come growth. Se entri troppo presto, aspetti settimane. 5 giorni garantisce consolidamento. RSI basso evita il 2-3% di rialzo e basta.

#### 🔴 Uscita L1: Identiche a Equity (ma RSI > 65 per Regola C)

---

### 05. BOND GOVERNATIVI
**ID**: `bond_governativi`  
**Descrizione**: BTP, Bund, UST, Gov Euro, IL — bassissima volatilità, sensibili a tassi  
**Esempi ETF**: BTP10, MTE, IBGX, EMI, X1G  
**Volatilità Attesa**: Molto Bassa  
**MA Principale**: SMA50 + SMA200  

#### 📊 Parametri

| Parametro | Valore | Significato |
|-----------|--------|------------|
| **RSI Entry Range** | 38–48 | RANGE STRETTISSIMO (bond poco oscillanti) |
| **RSI Exit Min** | 42 | Alto rispetto entry (bond scarseggia volatilità) |
| **RSI Overbought** | 70 | Standard (bond raramente toccano 70) |
| **ADX Entry Min** | 12 | MINIMO (12 vs 15 reales) — ADX meno rilevante |
| **Dist. EMA20 Max** | 1.5% | STRETTISSIMO (volatilità bassissima) |
| **Giorni Sopra EMA20** | 3 | Stesso (ma movimento è lentissimo) |
| **Banda Laterale** | 0.5% | MINIMA (banda laterale strettissima) |
| **ATR% Max** | 0.015 (1.5%) | BASSISSIMO (volatilità molto contenuta) |
| **AUM Min** | 100M€ | PIÙ ALTO (liquidità cruciale per bond) |
| **SMA200 Filter** | No | Bond non seguono trend di lungo (tassi) |
| **L0 Drawdown** | 8% | BASSO (i bond non crollano rapidamente) |
| **L0 RSI Max** | 38 | Basso (oversold bond è fisiologico) |
| **Min Buy Count** | 6 | Tutte obbligatorie |

#### 🟢 Entrata L1: Logica (Conservativa)

**Punti Chiave**:
- RSI 38-48 = range piccolissimo perché bond sono poco volatili
- Dist EMA20 max 1.5% = posizione rarissimamente è staccata
- Banda 0.5% = laterale strettissima (bond si muovono poco)
- **NO SMA200**: Bond reagiscono ai tassi, non seguono trend di lungo

**Razionale**:
Bond governativi non trendano come equity. Reagiscono alla curva dei tassi, a decisioni BCE, a spread. Il trend di lungo (SMA200) è irrilevante. Entrata conservativa: RSI basso, distanza EMA20 piccola.

#### 🔴 Uscita L1: Variante per Bond

| Regola | Per Bond Gov | Azione |
|--------|-------------|--------|
| **F - Kill Switch** | ✓ Attiva | Uscita totale |
| **A - Stop Loss** | ✗ DISABILITATA | Un giorno sotto EMA20 è rumore |
| **B - Trailing** | ✓ Attiva (EMA10 < EMA20) | Uscita totale |
| **C - Stanchezza** | ✓ Attiva ma RSI ≥ 70 raro | Uscita totale |
| **E - ADX Debole** | ✗ DISABILITATA | ADX non rilevante per bond |
| **D - Partial 90%** | ✗ DISABILITATA | Bond raramente toccano RSI 78 |

**Nota**: Bond hanno meno regole di uscita (A, E, D disable) perché non trendano come equity.

---

### 06. BOND CORP/HY/EM
**ID**: `bond_corp_hy_em`  
**Descrizione**: Corporate EUR/USD, High Yield, EM Bond — rischio medio, spread-driven  
**Esempi ETF**: AHYE, UHYC, IBCX, AGEB, EMBHI  
**Volatilità Attesa**: Media  
**MA Principale**: EMA20 + SMA50  

#### 📊 Parametri

| Parametro | Valore | Significato |
|-----------|--------|------------|
| **RSI Entry Range** | 42–52 | Simile bond, ma un po' più ampio (più volatili) |
| **RSI Exit Min** | 38 | Stesso bond |
| **RSI Overbought** | 70 | Stesso bond |
| **ADX Entry Min** | 15 | Più alto che bond gov (trend più rilevante) |
| **Dist. EMA20 Max** | 2.0% | Più ampio che bond gov (più volatili) |
| **Giorni Sopra EMA20** | 3 | Stesso |
| **Banda Laterale** | 0.8% | Più ampia che bond gov |
| **ATR% Max** | 0.025 (2.5%) | Più alto che bond gov |
| **AUM Min** | 50M€ | Meno rigoroso (più strumenti disponibili) |
| **SMA200 Filter** | No | Bond non seguono trend di lungo |
| **L0 Drawdown** | 10% | Più alto che bond gov (rischio credit) |
| **L0 RSI Max** | 38 | Stesso bond |
| **Min Buy Count** | 6 | Tutte obbligatorie |

#### 🟢 Entrata L1: Logica (Similare a Bond ma Trend-Friendly)

**Punti Chiave**:
- Simile a bond gov, ma parametri leggermente meno stretti
- ADX 15 vs 12 = trend un po' più rilevante (corporate risk asset)
- Dist EMA20 2.0% vs 1.5% = poco più spazio
- EMA20 + SMA50 primari, NO SMA200

**Razionale**:
Corporate/HY/EM sono bond con rischio credit. Più volatili di gov, ma meno di equity. Trend locale è rilevante (EMA20) ma non di lungo (SMA200). Spread allargamento = immediate uscite (Regola B/E).

#### 🔴 Uscita L1: Simile a Bond

| Regola | Per Bond Corp/HY | Azione |
|--------|------------------|--------|
| **F - Kill Switch** | ✓ Attiva | Uscita totale |
| **A - Stop Loss** | ✗ DISABILITATA | Spread volatilità è fisiologica |
| **B - Trailing** | ✓ Attiva | Uscita totale |
| **C - Stanchezza** | ✓ Attiva | Uscita totale |
| **E - ADX Debole** | ✗ DISABILITATA | Trend meno rilevante |
| **D - Partial 90%** | ✗ DISABILITATA | Raramente RSI > 78 |

---

### 07. INFLATION LINKED
**ID**: `inflation_linked`  
**Descrizione**: Bond con protezione inflazione — BTP Linker, TIPS, Gov Bond indicizzati  
**Esempi ETF**: (settore specializzato, pochi ETF europei)  
**Volatilità Attesa**: Bassa  
**MA Principale**: SMA50 + SMA200 + Filtro CPI esterno  

#### 📊 Parametri

| Parametro | Valore | Significato |
|-----------|--------|------------|
| **RSI Entry Range** | 38–48 | Stesso bond gov (bassa volatilità) |
| **RSI Exit Min** | 42 | Stesso bond |
| **RSI Overbought** | 60 | BASSO (inflation linked poco oscillanti) |
| **ADX Entry Min** | 12 | Stesso bond gov |
| **Dist. EMA20 Max** | 1.5% | Stesso bond gov |
| **Giorni Sopra EMA20** | 3 | Stesso |
| **Banda Laterale** | 0.5% | Strettissima (bond) |
| **ATR% Max** | 0.015 (1.5%) | Basso (bassa volatilità) |
| **AUM Min** | 100M€ | Alto (strumenti specializzati) |
| **SMA200 Filter** | No | (ma aggiungi filtro CPI trend esterno) |
| **L0 Drawdown** | 8% | Basso |
| **L0 RSI Max** | 38 | Basso |
| **Min Buy Count** | 6 | Tutte obbligatorie |

#### 🟢 Entrata L1: Logica (Bond con Filtro CPI)

**Punti Chiave**:
- Identica a bond gov MA con filtro CPI aggiuntivo
- Entra L1 solo se: trend technical OK + CPI in rialzo/stabile (non deflazione)
- **Razionale**: Inflation linked guadagnano quando CPI sale; se CPI scende, perdono appeal

#### 🔴 Uscita L1: Identiche a Bond Gov

---

### 08. COMMODITIES
**ID**: `commodities`  
**Descrizione**: Bloomberg Comm, GSCI, Energia, Agricoli — stagionalità, volatilità  
**Esempi ETF**: CMOD, COMO, CRB, ENRG, AIGA  
**Volatilità Attesa**: Alta  
**MA Principale**: SMA50 ± stagionalità  

#### 📊 Parametri

| Parametro | Valore | Significato |
|-----------|--------|------------|
| **RSI Entry Range** | 40–55 | Ampio (commodities volatili) |
| **RSI Exit Min** | 38 | Basso (oversold comune) |
| **RSI Overbought** | 68 | Basso (commodities cyclici) |
| **ADX Entry Min** | 22 | Alto (trend dev'essere PROVATO) |
| **Dist. EMA20 Max** | 3.0% | Medio (volatilità naturale) |
| **Giorni Sopra EMA20** | 3 | Stesso |
| **Banda Laterale** | 1.5% | Larga |
| **ATR% Max** | 0.06 (6%) | ALTISSIMO (commodities fluttuano) |
| **AUM Min** | 50M€ | Stesso |
| **SMA200 Filter** | Sì | Stesso |
| **L0 Drawdown** | 20% | Alto (commodities crollano come equity) |
| **L0 RSI Max** | 40 | Basso (oversold frequente) |
| **Min Buy Count** | 6 | Tutte obbligatorie |

#### 🟢 Entrata L1: Logica (Stagionalità)

**Punti Chiave**:
- ADX 22 = trend MUST be strong (commodities oscillano molto)
- RSI 40-55 ampio = cattura strappi su/giù
- **FILTRO PMI AGGIUNTIVO**: Usa PMI Manifatturiero (fattore esterno)
  - PMI > 50 = espansione, favorevole commodities
  - PMI < 50 = contrazione, commodities in pericolo

**Razionale**:
Commodities sono ciclici, non seguono trend puro. ADX alto filtra falsi segnali. PMI esterno (non nel codice attuale, ma raccomandato) migliora entry quality.

#### 🔴 Uscita L1: Identiche a Equity

---

### 09. ORO / METALLI PREZIOSI
**ID**: `oro_metalli_preziosi`  
**Descrizione**: Oro, Argento, Platino, Basket PM — safe haven, inversamente correlati equity  
**Esempi ETF**: PHAU, IGLN, PHAG, PHPT, PHPM  
**Volatilità Attesa**: Media  
**MA Principale**: SMA200 (primario)  

#### 📊 Parametri

| Parametro | Valore | Significato |
|-----------|--------|------------|
| **RSI Entry Range** | 38–52 | Ampio (metalli preziosi volatili) |
| **RSI Exit Min** | 38 | Basso |
| **RSI Overbought** | 68 | Basso (metalli preziosi raramente ipercomprati) |
| **ADX Entry Min** | 18 | Medio |
| **Dist. EMA20 Max** | 2.5% | Medio |
| **Giorni Sopra EMA20** | 3 | Stesso |
| **Banda Laterale** | 1.5% | Larga |
| **ATR% Max** | 0.04 (4%) | Medio-alto |
| **AUM Min** | 50M€ | Stesso |
| **SMA200 Filter** | Sì (PRIMARIO) | SMA200 è il filtro principale — oro segue SMA200 |
| **L0 Drawdown** | 15% | Medio |
| **L0 RSI Max** | 35 | Basso |
| **Min Buy Count** | 6 | Tutte obbligatorie |

#### 🟢 Entrata L1: Logica (SMA200-Focused)

**Punti Chiave**:
- **SMA200 è filtro PRIMARIO** (non secondario come equity)
- Oro tende a seguire trend di lungo (SMA200) più che EMA20
- Entra L1 solo se: prezzo > SMA200 + trend confirmato + RSI 38-52

**Razionale**:
Oro è safe haven e store of value. Trend di lungo (SMA200) è più rilevante che movimenti giornalieri (EMA20). Inversione di lungo = cambio regime. EMA20 serve solo per timing entrata.

#### 🔴 Uscita L1: Identiche a Equity (ma RSI > 68 per Regola D)

---

### 10. METALLI INDUSTRIALI
**ID**: `metalli_industriali`  
**Descrizione**: Rame, Alluminio, Zinco, Nichel, Battery — ciclici economici, PMI-driven  
**Esempi ETF**: COPA, ALUM, ZINC, BATE, AIGI  
**Volatilità Attesa**: Alta  
**MA Principale**: SMA50 + PMI proxy  

#### 📊 Parametri

| Parametro | Valore | Significato |
|-----------|--------|------------|
| **RSI Entry Range** | 38–50 | Stretto (metalli poco volatili come equity) |
| **RSI Exit Min** | 38 | Basso |
| **RSI Overbought** | 65 | Basso (ciclici poco ipercomprati) |
| **ADX Entry Min** | 20 | Alto (trend deve essere provato) |
| **Dist. EMA20 Max** | 3.0% | Medio |
| **Giorni Sopra EMA20** | 3 | Stesso |
| **Banda Laterale** | 1.2% | Medio |
| **ATR% Max** | 0.05 (5%) | Alto |
| **AUM Min** | 30M€ | BASSO (settore specializzato, AUM minore) |
| **SMA200 Filter** | Sì | Stesso |
| **L0 Drawdown** | 18% | Medio-alto |
| **L0 RSI Max** | 38 | Basso |
| **Min Buy Count** | 6 | Tutte obbligatorie |

#### 🟢 Entrata L1: Logica (PMI-Driven)

**Punti Chiave**:
- **PMI Manifatturiero è filtro CRUCIALE** (non nel codice, raccomandiamo di aggiungere)
  - PMI > 50 = espansione, favorevole metalli industriali
  - PMI < 50 = contrazione, metalli in pericolo
- ADX 20 = trend dev'essere provato
- RSI 38-50 stretto = entra a metà ciclo

**Razionale**:
Metalli industriali sono ciclici economici. PMI è il leading indicator. Entra L1 se PMI espansivo + trend technical OK.

#### 🔴 Uscita L1: Identiche a Equity

---

### 11. REAL ESTATE / REIT
**ID**: `real_estate_reit`  
**Descrizione**: EPRA Europe, NAREIT Global, REIT — reddito, sensibili tassi  
**Esempi ETF**: EPRE, MWO, IPRP, IASP, ZPRE  
**Volatilità Attesa**: Media  
**MA Principale**: SMA50 + Filtro tasso interesse 10Y  

#### 📊 Parametri

| Parametro | Valore | Significato |
|-----------|--------|------------|
| **RSI Entry Range** | 42–52 | Stretto (REIT poco volatili) |
| **RSI Exit Min** | 38 | Basso |
| **RSI Overbought** | 65 | Basso |
| **ADX Entry Min** | 15 | Basso (ADX meno rilevante) |
| **Dist. EMA20 Max** | 2.0% | Stretto |
| **Giorni Sopra EMA20** | 3 | Stesso |
| **Banda Laterale** | 1.0% | Medio |
| **ATR% Max** | 0.03 (3%) | Basso |
| **AUM Min** | 50M€ | Stesso |
| **SMA200 Filter** | No | REIT reagiscono ai tassi, non trend di lungo |
| **L0 Drawdown** | 12% | Basso (REIT meno volatili) |
| **L0 RSI Max** | 38 | Basso |
| **Min Buy Count** | 6 | Tutte obbligatorie |

#### 🟢 Entrata L1: Logica (Tasso-Sensitive)

**Punti Chiave**:
- **Filtro tasso interesse 10Y è CRUCIALE** (non nel codice, raccomandiamo di aggiungere)
  - Tassi in calo → favorevole REIT (valutazioni salgono)
  - Tassi in rialzo → sfavorevole REIT (cedole meno competitive)
- RSI 42-52 = basso (REIT poco oscillanti)
- Entra L1 se: trend OK + tassi in calo o stabili

**Razionale**:
REIT sono strumenti di reddito. Yield è importante. Se tassi salgono, i REIT diventano meno attraenti (yield disponibile altrove). Filtro 10Y esterno è cruciale.

#### 🔴 Uscita L1: Identiche a Equity (ma RSI > 65 per Regola D)

---

### 12. CRYPTO / DIGITAL ASSETS
**ID**: `crypto_digital_assets`  
**Descrizione**: Bitcoin, Ethereum, Solana, Basket crypto — volatilità ESTREMA, beta alto  
**Esempi ETF**: BITC, ETHE, SLNC, BTCE, BDAS  
**Volatilità Attesa**: Molto Alta (Estrema)  
**MA Principale**: EMA20 + SMA200  

#### 📊 Parametri

| Parametro | Valore | Significato |
|-----------|--------|------------|
| **RSI Entry Range** | 35–52 | AMPLISSIMO (crypto volatilissimi) |
| **RSI Exit Min** | 38 | Basso |
| **RSI Overbought** | 70 | Standard (ma crypto spesso > 70) |
| **ADX Entry Min** | 28 | ALTISSIMO (trend MUST be iron-clad) |
| **Dist. EMA20 Max** | 6.0% | MASSIMO (volatilità estrema) |
| **Giorni Sopra EMA20** | 3 | Stesso (ma movimento è velocissimo) |
| **Banda Laterale** | 3.0% | AMPLISSIMA (crypto oscillano selvaggiamente) |
| **ATR% Max** | 0.15 (15%) | ESTREMO (crypto fluttuano 10-15% al giorno) |
| **AUM Min** | 100M€ | ALTO (liquidità essenziale) |
| **SMA200 Filter** | Sì | Filtro bear assoluto necessario |
| **L0 Drawdown** | 25% | Altissimo |
| **L0 RSI Max** | 40 | Basso (oversold frequente) |
| **Min Buy Count** | 5 | 5/6 (non 6) — condizione di ADX può essere skipped a volte |

#### 🟢 Entrata L1: Logica (Ultra-Rigorosa)

**Punti Chiave**:
- ADX 28 = ADX DEVE essere astronomico (filtra 99% dei falsi segnali)
- RSI 35-52 = amplissimo (cattura sia breakout rialzisti sia riacquisti)
- Banda 3.0% = crypto sono selvaggi
- **Min buy count 5 (non 6)**: Se ADX 28 è presente, altre 5 condizioni sono sufficienti
- Dist EMA20 6.0% = massima libertà (crypto saltano rapidamente)

**Razionale**:
Crypto sono altamente speculativi. Entra solo con ADX altissimo (trend PROVATO). Anche così, rischio è elevato. Bands larghe catturano la volatilità naturale.

#### 🔴 Uscita L1: Identiche a Equity (ma soglie RSI diverse)

| Regola | Per Crypto | Azione |
|--------|-----------|--------|
| **F - Kill Switch** | ✓ Attiva | Uscita totale |
| **A - Stop Loss** | ✓ Attiva (3gg) | Uscita totale |
| **B - Trailing** | ✓ Attiva | Uscita totale |
| **C - Stanchezza** | ✓ Attiva (RSI 70→<70) | Uscita totale |
| **E - ADX Debole** | ✓ Attiva | Uscita totale |
| **D - Partial 90%** | ✓ Attiva (RSI > 78) | Vendi 90%, compra XEON |

---

### 13. LEVA / SINGLE STOCK
**ID**: `leva_single_stock`  
**Descrizione**: ETP 3x Long/Short su singoli titoli — trading tattico, hold breve  
**Esempi ETF**: 3LNV, 3SNV, 3LTS, 3MIB, 3MBS, 3LAP, 3LAM, 3LFB  
**Volatilità Attesa**: Estrema  
**MA Principale**: EMA20 + Volatilità Implicita  

#### 📊 Parametri

| Parametro | Valore | Significato |
|-----------|--------|------------|
| **RSI Entry Range** | 45–58 | Ampio (leva volatile) |
| **RSI Exit Min** | 38 | Basso |
| **RSI Overbought** | 65 | Basso (decadimento giornaliero, RSI artificiale) |
| **ADX Entry Min** | 28 | ALTISSIMO (trend MUST be extreme) |
| **Dist. EMA20 Max** | 4.0% | Ampio |
| **Giorni Sopra EMA20** | 3 | Stesso |
| **Banda Laterale** | 2.0% | Larga |
| **ATR% Max** | 0.20 (20%) | ESTREMISSIMO (leva 3x fluttuano 15-20%) |
| **AUM Min** | 50M€ | Stesso |
| **SMA200 Filter** | Sì | Filtro bear assoluto |
| **L0 Drawdown** | 20% | Alto |
| **L0 RSI Max** | 40 | Basso |
| **Hold Days Max** | 30 | **NUOVO PARAMETRO** — massimo 30 giorni di hold |
| **Min Buy Count** | 6 | Tutte obbligatorie |

#### 🟢 Entrata L1: Logica (Tattica)

**Punti Chiave**:
- ADX 28 = trend MUST be extreme (leva entra solo in trend forti)
- **Hold Max 30 giorni** = non è buy-and-hold, è trading tattico
- Entra L1 se: trend 3x long confermato + momentum alto
- No 3x short in L1 (troppo rischio hedging costoso)

**Razionale**:
Leva 3x è tattica. Non è per investimento di lungo. Massimo 30 giorni hold, poi esce automaticamente (protezionismo dal decay). ADX altissimo filtra falsi segnali.

#### 🔴 Uscita L1: Tattica

| Regola | Per Leva | Azione |
|--------|---------|--------|
| **F - Kill Switch** | ✓ Attiva | Uscita totale IMMEDIATA |
| **A - Stop Loss** | ✓ Attiva (3gg) | Uscita totale |
| **B - Trailing** | ✓ Attiva | Uscita totale |
| **C - Stanchezza** | ✓ Attiva (RSI 65 scenario) | Uscita totale |
| **E - ADX Debole** | ✓ Attiva | Uscita totale |
| **D - Partial 90%** | ✗ DISABILITATA | Leva non fa partial |
| **⏰ Hold Max 30gg** | ✓ AUTOMATICA | Uscita totale dopo 30 giorni |

---

### 14. PRIVATE EQUITY / BUFFER ETF
**ID**: `private_equity_buffer`  
**Descrizione**: Listed PE, Buffer strategy ETF — reddito, protezione capitale  
**Esempi ETF**: IPRE, DX2G, IUSB, IUSM  
**Volatilità Attesa**: Media-Alta  
**MA Principale**: SMA50 + Filtro sconto NAV  

#### 📊 Parametri

| Parametro | Valore | Significato |
|-----------|--------|------------|
| **RSI Entry Range** | 40–55 | Ampio (private equity volatile) |
| **RSI Exit Min** | 38 | Basso |
| **RSI Overbought** | 65 | Basso |
| **ADX Entry Min** | 15 | Medio-basso |
| **Dist. EMA20 Max** | 2.5% | Medio |
| **Giorni Sopra EMA20** | 3 | Stesso |
| **Banda Laterale** | 0.8% | Stretto |
| **ATR% Max** | 0.03 (3%) | Medio-basso |
| **AUM Min** | 50M€ | Stesso |
| **SMA200 Filter** | No | PE reagisce a valutazioni, non trend di lungo |
| **L0 Drawdown** | 15% | Medio |
| **L0 RSI Max** | 38 | Basso |
| **Min Buy Count** | 6 | Tutte obbligatorie |

#### 🟢 Entrata L1: Logica (Valore + Trend)

**Punti Chiave**:
- **Filtro sconto NAV è CRUCIALE** (non nel codice, raccomandiamo di aggiungere)
  - PE quotati spesso trade con sconto al NAV
  - Entra L1 se: trend OK + NAV discount ridotto (non pagare di più)
- RSI 40-55 = ampio (cattura sia rialzi sia stagnazioni)
- SMA50 filtro principale (non SMA200)

**Razionale**:
Private Equity listed sono fondi chiusi. Quotati spesso con sconto/premio a NAV. Filtro NAV discount è cruciale per valore. Trend locale (SMA50) è importante per timing.

#### 🔴 Uscita L1: Identiche a Equity (ma RSI > 65 per Regola D)

---

### 15. MONETARIO / LIQUIDITÀ
**ID**: `monetario_liquidita`  
**Descrizione**: ETF overnight, short-term EUR — liquidi, bassissimo rischio, segue €STR  
**Esempi ETF**: XEON.DE (EUR Overnight €STR), IEMX (iShares EM USD overnight)  
**Volatilità Attesa**: Nulla  
**MA Principale**: Nessuno (no analisi tecnica)  

#### 📊 Parametri

| Parametro | Valore | Significato |
|-----------|--------|------------|
| **RSI Entry Range** | — | NULL (no analisi tecnica) |
| **RSI Exit Min** | 42 | Monitoraggio solo |
| **RSI Overbought** | 97 | Altissimo (RSI strutturalmente 80-90) |
| **ADX Entry Min** | — | NULL (no trend) |
| **Dist. EMA20 Max** | 0.5% | Strettissimo |
| **Giorni Sopra EMA20** | 3 | Stesso |
| **Banda Laterale** | 0.0% | ZERO (no regime laterale) |
| **ATR% Max** | 0.005 (0.5%) | MINIMO (no volatilità) |
| **AUM Min** | 100M€ | Liquidità cruciale |
| **SMA200 Filter** | No | No analisi tecnica |
| **L0 Drawdown** | — | NULL |
| **L0 RSI Max** | — | NULL |
| **Min Buy Count** | 6 | Tutte obbligatorie (ma molte NULL) |

#### 🟢 Entrata L1: Logica (Ranking Yield)

**Punti Chiave**:
- **NO ANALISI TECNICA** — solo ranking yield
- Entra L1 se: yield €STR più conveniente che alternative money market
- Regola: semplice paragone di rendimento 
  - €STR overnight = ~3-4% annuo
  - USD overnight = ~5-5.5% annuo
  - Entra il più conveniente per valuta

**Razionale**:
Monetario è puro reddito. No trend, no RSI, no ADX. Solo yield. Usato come:
1. Asset di partenza per portafoglio conservativo
2. **Parcheggio temporaneo durante regimi BEAR** (aspettare rientro)
3. **Destinazione per il 90% venduto** (Regola D uscita parziale equity)

#### 🔴 Uscita L1: Nessuna (sempre mantenuto)

Monetario non esce mai. È l'asset rifugio. Si usa come:
- Ancora del portafoglio in fasi laterali/bear
- Quando tutte le equity sono in uscita (L2/L3 solo)
- Come destinazione del 90% da Regola D

---

## 📋 Tabella Riepilogativa Comparativa

| Aspetto | Equity Sviluppati | Emergenti | Growth | Difensivi | Bond Gov | Corp/HY | Commodity | Oro | Metalli Ind | REIT | Crypto | Leva | Private EQ | Monetario |
|---------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **RSI Entry** | 45-55 | 40-52 | 48-58 | 42-50 | 38-48 | 42-52 | 40-55 | 38-52 | 38-50 | 42-52 | 35-52 | 45-58 | 40-55 | — |
| **ADX Min** | 18 | 22 | 25 | 15 | 12 | 15 | 22 | 18 | 20 | 15 | 28 | 28 | 15 | — |
| **Dist EMA20** | 4% | 5% | 5% | 2.5% | 1.5% | 2% | 3% | 2.5% | 3% | 2% | 6% | 4% | 2.5% | 0.5% |
| **Banda Later** | 1.0% | 1.2% | 1.5% | 1.0% | 0.5% | 0.8% | 1.5% | 1.5% | 1.2% | 1.0% | 3.0% | 2.0% | 0.8% | 0% |
| **ATR Max** | 3% | 4% | 5% | 2.5% | 1.5% | 2.5% | 6% | 4% | 5% | 3% | 15% | 20% | 3% | 0.5% |
| **A - Stop Loss** | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| **C - Stanchezza** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| **D - Partial 90%** | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ |
| **E - ADX Debole** | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✗ |
| **SMA200 Filter** | Sì | Sì | Sì | Sì | No | No | Sì | Sì | Sì | No | Sì | Sì | No | No |
| **Filtro Esterno** | — | — | — | — | — | — | PMI | PMI | PMI | Tassi 10Y | — | — | Sconto NAV | Yield |

---

## 🎯 Checklist di Verifica Dashboard

Quando visualizzi la dashboard, verifica che siano presenti TUTTE queste informazioni:

- [ ] **Tutte 15 famiglie** (equity_sviluppati, mercati_emergenti, ... monetario_liquidita)
- [ ] **Per ogni famiglia**: RSI range, ADX min, Dist EMA20, Banda laterale, ATR max
- [ ] **Schema L1 entry**: 6 condizioni spiegate (Allineamento, Persistenza, RSI, Distanza, ADX, MACD)
- [ ] **Schema L1 exit**: 6 regole spiegate (F, A, B, C, E, D) con priorità
- [ ] **Logica 90%/10%**: Uscita parziale, XEON, rientro spiegati chiaramente
- [ ] **Filtri speciali**: PMI (commodities), Tassi 10Y (REIT), Sconto NAV (PE), Yield (Monetario)
- [ ] **Regime 3-stati**: Bull/Laterale/Bear con banda per famiglia
- [ ] **Kill Switch**: -3% variazione giornaliera = ingresso bloccato
- [ ] **Hold Max 30gg**: Leva single stock non oltre 30 giorni

---

## 📞 Supporto & Note Finali

**Last Updated**: 30 giugno 2026, 23:52  
**Status**: Completo e operativo in produzione  
**Configurazione**: `/config/etf_families.yaml` (YAML)  
**Dashboard**: `https://etf.andreapavan.tech`  
**Monitor Run**: Quotidiano 17:00 CEST (lun-ven) + silent 09:00 CEST

---

**Fine Documento**
