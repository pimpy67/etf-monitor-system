# ETF Monitor — Prompt di Refactor per Claude (VS Code / Terminale)

> **Come usare questo file**
> Apri VS Code, lancia Claude Code dal terminale (`claude`) e incolla questo contenuto,
> oppure caricalo direttamente come contesto con `/load ETF_Monitor_Refactor_Prompt.md`.
> Il prompt è autosufficiente: Claude leggerà il contesto e proporrà il refactor completo.

---

## 1. Identità del progetto

Stai lavorando su un sistema di monitoraggio ETF attivo su Borsa Italiana (piattaforma Directa SIM, mercato ETFplus).
Il sistema classifica ~207 ETF/ETP in quattro livelli operativi:

| Livello | Significato                        |
|---------|------------------------------------|
| L0      | Deep Recovery — recupero da Bear   |
| L1      | Trend Sicuro — posizione attiva    |
| L2      | Watchlist — vicino ai criteri L1   |
| L3      | Universo — monitoraggio passivo    |

I segnali si basano su uno **score APRDXM a 6 condizioni** (tutte necessarie per L1):
- **A** = Prezzo sopra EMA20
- **P** = Prezzo sopra SMA50
- **R** = RSI sopra soglia
- **D** = ADX sopra soglia (trend forte)
- **X** = Regime Bull (EMA20 > SMA50)
- **M** = Momentum positivo (variazione recente)

Il sistema usa attualmente **4 macro-categorie** con parametri uniformi:
`Equity / Tematici`, `Mercati Emergenti`, `Materie Prime`, `Bond`

---

## 2. Obiettivo del refactor

Trasformare il sistema da "monitor a soglie fisse" a **motore parametrico multi-famiglia**,
mantenendo piena backward compatibility con la struttura esistente.

### Tre domande operative che il sistema deve rispondere:
1. **Che cosa è questo strumento?** (tassonomia)
2. **In che regime di mercato si trova?** (Bull / Laterale / Bear)
3. **È efficiente possederlo adesso?** (qualità, liquidità, costo, correlazione)

---

## 3. Modifiche richieste

### 3.1 — Tassonomia espansa (da 4 a 13 famiglie)

Sostituisci le 4 macro-categorie attuali con le seguenti **13 famiglie operative**.
Ogni ETF deve essere assegnato a esattamente una famiglia.

```
FAMIGLIA                        | ESEMPI TIPICI
--------------------------------|----------------------------------------------
01_equity_sviluppati            | IWDA, VWCE, CSPX, S&P 500, Euro Stoxx 50
02_mercati_emergenti            | EIMI, AEME, India, Corea, LatAm
03_settoriali_growth            | Tech, AI, Semiconduttori, Nasdaq-100
04_settoriali_difensivi         | Salute, Utilities, Insurance, Consumer Staples
05_bond_governativi             | BTP, Bund, UST, Gov Euro, Inflation-linked
06_bond_corporate_hy_em         | Corp EUR, HY EUR/USD, EM bond USD/local
07_commodities                  | Bloomberg Commodity, S&P GSCI, Agri, Energia
08_oro_metalli_preziosi         | PHAU, IGLN, Silver, Platinum, Basket PM
09_metalli_industriali          | Rame, Alluminio, Zinco, Nichel, Battery chain
10_real_estate_reit             | EPRA Europe, NAREIT Global, REIT
11_crypto_digital_assets        | Bitcoin ETP, Ethereum ETP, Solana, Basket crypto
12_leva_single_stock            | GraniteShares 3x Long/Short, ETP strutturati
13_private_equity_buffer        | Listed PE, Buffer ETF, Structured notes
```

**Implementazione:** aggiungi una colonna `famiglia` (o `asset_family`) a ogni ETF.
Se usi YAML/JSON, crea un file `config/families.yaml` con la mappatura ISIN → famiglia.

---

### 3.2 — Regime a 3 stati (BREAKING CHANGE — priorità massima)

Sostituisci il regime binario `Bull / Bear` con un regime a **3 stati**:

```
BULL     : (EMA20 - SMA50) / SMA50 > +soglia_famiglia
LATERALE : abs(EMA20 - SMA50) / SMA50 <= soglia_famiglia
BEAR     : (EMA20 - SMA50) / SMA50 < -soglia_famiglia
```

**Soglie di banda laterale per famiglia:**

| Famiglia                    | Banda laterale (%) |
|-----------------------------|--------------------|
| Equity sviluppati           | 1,0%               |
| Mercati emergenti           | 1,2%               |
| Settoriali growth           | 1,5%               |
| Settoriali difensivi        | 1,0%               |
| Bond governativi            | 0,5%               |
| Bond corporate / HY / EM   | 0,8%               |
| Oro / metalli preziosi      | 1,5%               |
| Commodities                 | 1,5%               |
| Metalli industriali         | 1,2%               |
| REIT / Real Estate          | 1,0%               |
| Crypto / digital assets     | 3,0%               |
| Leva / single stock         | 2,0%               |
| Private equity / buffer     | 0,8%               |

**Impatto sul ranking:**
- Regime `BULL` → nessuna penalizzazione
- Regime `LATERALE` → penalità -1 punto sullo score
- Regime `BEAR` → strumento non eligibile per L1

---

### 3.3 — Parametri tecnici per famiglia

Sostituisci i parametri uniformi con quelli specifici per ogni famiglia.
Leggi questi valori da un file di configurazione esterno (vedi sezione 3.7).

```
FAMIGLIA                | MA_FILTRO           | RSI_IN  | RSI_OUT | ADX_MIN
------------------------|---------------------|---------|---------|--------
Equity sviluppati       | EMA20 + SMA50       | 45-55   | ≥68     | >18
Mercati emergenti       | EMA20 + SMA50       | 40-52   | ≥65     | >22
Settoriali growth       | EMA20 + SMA50       | 48-58   | ≥72     | >25
Settoriali difensivi    | SMA50 + SMA200      | 42-50   | ≥65     | >15
Bond governativi        | SMA50 + SMA200      | 38-48   | ≥62     | >12
Bond corp / HY / EM     | EMA20 + SMA50       | 42-52   | ≥65     | >15
Inflation-linked        | SMA50 + SMA200      | 38-48   | ≥60     | >12
Oro / metalli preziosi  | SMA200              | 38-52   | ≥68     | >18
Commodities             | SMA50 (stagionale)  | 40-55   | ≥68     | >22
Metalli industriali     | SMA50 + PMI proxy   | 38-50   | ≥65     | >20
REIT / Real Estate      | SMA50 + yield 10Y   | 42-52   | ≥65     | >15
Monetario / liquidità   | Tasso BCE           |  —      |  —      |  —
Crypto / digital assets | EMA20 + SMA200      | 35-52   | ≥70     | >28
Leva / single stock     | EMA20 + vol impl.   | 45-58   | ≥65     | >28
Private equity / buffer | SMA50 + NAV disc.   | 40-55   | ≥65     | >15
```

> **Nota:** tutte le soglie sono parametri iniziali da validare con backtest
> sul proprio storico. Non sono regole definitive.

---

### 3.4 — Nuove metriche da calcolare e aggiungere

Aggiungi queste colonne in modo **additivo** (non rompere le colonne esistenti):

#### ATR normalizzato
```
ATR_norm = ATR(14) / Prezzo_corrente
```
- `< 1%` → bassa volatilità (size maggiore, stop stretto)
- `1–3%` → media
- `> 3%` → alta (ridurre size, stop più largo o escludere da L1)

#### Drawdown da massimo 52 settimane
```
DD_52W = (Prezzo_corrente - Max_52W) / Max_52W
```
- `> -10%` → normale
- `-10% / -20%` → attenzione
- `< -20%` → area di potenziale accumulo o uscita
- `< -30%` → bear market conclamato

Rendi questa colonna **visibile su L1, L2 e L3** (attualmente solo su L1).

#### AUM (patrimonio gestito)
- `> 100M€` → sicuro
- `50–100M€` → attenzione
- `< 50M€` → flag rosso (rischio chiusura / delisting)

#### Spread bid/ask
```
Spread_pct = (Ask - Bid) / Mid_price
```
Usato come costo implicito di esecuzione.
Penalizza strumenti con spread > 0,50% nello score.

#### TER (Total Expense Ratio)
Già presente nel file Excel di configurazione.
Aggiungere al monitor come colonna visibile per confronto rapido.

#### Yield distribuito (solo bond e dividend ETF)
```
Yield = Distribuzione_annua / Prezzo_corrente
```
Comparare automaticamente con tasso BCE overnight.
Se `Yield < tasso BCE` → segnala inefficienza rispetto al monetario.

#### Correlazione rolling 90 giorni
```
Corr90 = rolling_corr(rendimenti_ETF, rendimenti_benchmark, window=90)
```
- Benchmark principale: MSCI World (o S&P 500 per ETF USA)
- Se `Corr90 > 0,90` con un ETF già in portafoglio → segnala ridondanza
- Usare anche correlazione intra-portafoglio tra ETF in L1

---

### 3.5 — Nuovo sistema di scoring e ranking

Mantieni lo **score APRDXM (0–6)** come base.
Aggiungi **bonus e penalità** per le nuove dimensioni:

```
SCORE_FINALE = APRDXM_score + bonus_qualita + bonus_regime - penalita

Penalità:
  - Regime LATERALE         → -1
  - ATR_norm > 3%           → -0,5
  - AUM < 50M€              → -1
  - Spread > 0,50%          → -0,5
  - DD_52W < -20%           → -0,5
  - Corr90 > 0,90 (vs L1)  → -0,5

Bonus:
  + Regime BULL + ADX > 25  → +0,5
  + DD_52W > -5%            → +0,3
  + Corr90 < 0,40           → +0,5 (diversificante)
  + Yield > tasso BCE + 1%  → +0,3 (solo bond)
```

---

### 3.6 — Aggiornamento livelli L0 / L1 / L2 / L3

```
L1 (Trend Sicuro):
  - APRDXM = 6/6
  - Regime = BULL
  - ATR_norm < 3% (o 5% per crypto)
  - AUM > 50M€
  - Score_finale >= 5,5

L2 (Watchlist):
  - APRDXM = 4/6 o 5/6
  - Regime = BULL o LATERALE
  - Mostra motivazione specifica del mancato ingresso in L1
    (es. "ADX sotto soglia", "Regime laterale", "AUM basso")

L3 (Universo passivo):
  - APRDXM < 4/6 o Regime = BEAR
  - Monitoraggio passivo
  - Mostra segnale di transizione verso L2 se condizioni migliorano

L0 (Deep Recovery):
  - Regime = BEAR da almeno N periodi
  - DD_52W < -25%
  - Da monitorare per potenziale inversione
```

---

### 3.7 — Configurazione esterna (YAML / JSON / Excel)

Crea un file di configurazione separato dalla logica di calcolo.

Se usi **Python**, crea `config/etf_config.yaml`:
```yaml
families:
  equity_sviluppati:
    ma_filter: [EMA20, SMA50]
    rsi_in: [45, 55]
    rsi_out: 68
    adx_min: 18
    lateral_band: 0.01
    atr_max: 0.03
    aum_min: 50

  crypto_digital_assets:
    ma_filter: [EMA20, SMA200]
    rsi_in: [35, 52]
    rsi_out: 70
    adx_min: 28
    lateral_band: 0.03
    atr_max: 0.10
    aum_min: 100

  # ... altre famiglie
```

Se usi **Excel**, crea un foglio `Config_Soglie` con queste colonne:
```
famiglia | ma_1 | ma_2 | rsi_in_low | rsi_in_high | rsi_out | adx_min | lateral_band | atr_max | aum_min
```

---

### 3.8 — Architettura modulare (se Python)

Separa il codice in moduli distinti:

```
etf_monitor/
├── config/
│   ├── etf_config.yaml          ← soglie e parametri per famiglia
│   └── etf_universe.csv         ← lista ETF con ISIN, famiglia, AUM, TER
├── modules/
│   ├── classify.py              ← assegna famiglia a ogni ETF
│   ├── signals.py               ← calcola EMA, SMA, RSI, ADX, ATR, DD, Corr
│   ├── regime.py                ← determina Bull / Laterale / Bear
│   ├── scoring.py               ← APRDXM + bonus/penalità → score finale
│   ├── risk.py                  ← ATR sizing, drawdown, correlazione, AUM
│   └── report.py                ← output L0/L1/L2/L3, dashboard, alert
├── main.py                      ← orchestratore principale
└── tests/
    └── test_signals.py          ← test base su ciascun modulo
```

---

### 3.9 — Backward compatibility

- **Non rinominare** le colonne esistenti (EMA20, SMA50, RSI, ADX, Regime, Cond.)
- **Aggiungi** nuove colonne a destra delle esistenti
- Se un dato non è disponibile, usa `NaN` o stringa vuota — non crashare
- Il filtro APRDXM deve continuare a funzionare anche senza i nuovi dati

---

## 4. Criteri di accettazione

- [ ] Il sistema distingue chiaramente le 13 famiglie operative
- [ ] Il regime a 3 stati (Bull / Laterale / Bear) è operativo
- [ ] I parametri RSI, ADX e MA sono differenziati per famiglia
- [ ] Le nuove metriche (ATR, DD, AUM, Spread, Yield, Corr) sono calcolate
- [ ] Lo score finale include bonus e penalità
- [ ] L1/L2/L3 usano i nuovi criteri
- [ ] La configurazione è separata dalla logica di calcolo
- [ ] Il refactor non rompe i segnali esistenti

---

## 5. Priorità di implementazione

```
PRIORITÀ 1 (fase 1 — subito):
  ✦ Regime a 3 stati
  ✦ Tassonomia a 13 famiglie

PRIORITÀ 2 (fase 2 — 1/2 mesi):
  ✦ Parametri RSI/ADX/MA per famiglia
  ✦ SMA200 per asset lenti
  ✦ DD_52W su tutti i livelli

PRIORITÀ 3 (fase 3 — 3/6 mesi):
  ✦ ATR normalizzato
  ✦ AUM e Spread come filtri di qualità
  ✦ Yield vs tasso BCE per bond

PRIORITÀ 4 (fase 4 — 6/12 mesi):
  ✦ Correlazione rolling 90gg
  ✦ Score finale con bonus/penalità
  ✦ Sizing automatico basato su ATR
```

---

## 6. Domande da fare a Claude prima di iniziare

Prima di produrre codice, Claude deve chiederti:

1. **Tecnologia:** il sistema usa Excel, Python, JavaScript o altro?
2. **Entry point:** qual è il file principale del progetto (es. `monitor.py`, `etf_monitor.xlsx`)?
3. **Dati:** i prezzi vengono da API (Yahoo Finance, yfinance, Bloomberg) o da file CSV/Excel?
4. **Frequenza:** il calcolo è giornaliero, settimanale o real-time?
5. **Output:** l'output è un file Excel, una web app, un report PDF o altro?
6. **SMA200:** i dati storici disponibili coprono almeno 200 giorni per tutti gli ETF?
7. **Crypto:** gli ETP crypto sono già nell'universo o devono essere aggiunti?

---

## 7. Note finali

- Tutte le soglie sono parametri iniziali, non regole definitive.
  Validare con backtest sul proprio storico prima di usarle in produzione.
- Gli ETP crypto su Borsa Italiana (da febbraio 2026) sono riservati
  agli investitori professionali — verificare l'accesso su Directa SIM.
- La correlazione rolling richiede almeno 90 sessioni di storico per ogni ETF.
- Il sistema è pensato per un utilizzo su orizzonte medio-lungo (settimane/mesi),
  non per trading intraday.
- Documento elaborato con supporto AI (Claude, Anthropic) — verificare
  tutte le implementazioni con backtest proprietario prima del go-live.

---

*Versione documento: 1.0 — Giugno 2026*
*Sistema: ETF Monitor Directa — ETFplus Borsa Italiana*
