# CLAUDE.md — ETF Monitor System

Documento di riferimento tecnico — caricato automaticamente da Claude Code a ogni sessione.

---

## 🔴 REGOLA PERMANENTE DI SINCRONIZZAZIONE AUTOMATICA

> **BINDING PERMANENTE**: Questa regola governa TUTTA la documentazione e i parametri. È non-negoziabile.

### Il Principio
**I parametri del sistema devono SEMPRE rispecchiare il comportamento del codice.** Non è tollerato disallineamento.

### Come Funziona
```
1. Fonte di verità unica:  config/etf_families.yaml
                           ↓
2. Il monitor legge il YAML → calcola L0/L1/L2/L3 → esegue

3. Visualizzazione nel browser:
   - Tab "Parametri di Riferimento" → carica live da /api/parameters
   - Ogni parametro viene letto dal YAML in tempo reale

4. PDF scaricabile:
   - Generato automaticamente da pdf_generator.py
   - Dopo ogni ciclo di monitor (17:00 + 09:00)
   - 100% sincronizzato con il YAML attuale
   - Nessun hardcoding, nessun manuale
```

### Se Modifichi i Parametri nel YAML
```
1. Modifica → config/etf_families.yaml
2. Automatico: il prossimo monitor usa i nuovi valori
3. Automatico: il PDF viene rigenerato con i nuovi parametri
4. Automatico: il browser mostra i nuovi parametri in tempo reale
```

**Responsabilità dello sviluppatore:**
- ✅ Modificare solo il YAML (non PDF, non documenti hardcoded)
- ✅ Testare che il codice legga correttamente i nuovi parametri
- ✗ NON modificare manualmente PDF, tabelle HTML hardcoded, o descrizioni parametri

---

## Concetti Fondamentali

### Cosa Sono i Parametri?
I parametri sono **"regole di comportamento" che il sistema usa per decidere quando comprare (L1) e quando vendere (L0)**.

Immagina di giocare a un videogame: i parametri sono come le impostazioni di difficoltà. Cambiano come il gioco reagisce ai tuoi movimenti.

### Come Funzionano i Parametri nel Nostro Sistema

1. **Il monitor raccoglie dati** di prezzo e volume dell'ETF
2. **Calcola indicatori tecnici** usando i parametri:
   - Medie mobili (EMA20, SMA50, SMA200)
   - Momentum (RSI, ADX, MACD)
   - Distanze di prezzo
3. **Applica le logiche di entrata/uscita** basate sui parametri
4. **Decide il livello** (L0 = compra, L1 = posizione, L2 = attendi, L3 = ignora)

### I Tre Tipi di Parametri

| Tipo | Esempi | Cosa Controllano |
|------|--------|------------------|
| **Indicatori** | EMA20, RSI14, ADX | Come si comporta il prezzo, momentum, forza trend |
| **Soglie** | rsi_entry_low, adx_entry | Quando il sistema dice "OK, entra" |
| **Protezioni** | sl_initial_pct, trailing_min_pct | Come proteggere il capitale se il prezzo crolla |

---

## Parametri Spiegati Didatticamente

### 1️⃣ EMA20 — La Media Veloce (l'umore del prezzo a breve)

**Cosa è?** Una media mobile che cambia rapidamente seguendo i movimenti recenti.

**Come funziona?** Somma gli ultimi 20 giorni di chiusura e divide per 20 — ma i giorni recenti pesano di più.

**Che segnale dà?**
- Se prezzo > EMA20 → il prezzo è SOPRA la media, trend al rialzo (BUONO ✓)
- Se prezzo < EMA20 → il prezzo è SOTTO la media, trend al ribasso (MALE ✗)

**Esempio:**
```
Giorni passati:  €100, €101, €99, €102, €100
EMA20 attuale:   €100.5

Se prezzo = €102 → 102 > 100.5 ✓ Possibile ingresso L1
Se prezzo = €98  → 98 < 100.5 ✗ Possibile uscita L1
```

---

### 2️⃣ SMA50 & SMA200 — Le Medie Lente (la tendenza a lungo)

**SMA50:** Media dei 50 giorni — dice se la tendenza mista è positiva.

**SMA200:** Media dei 200 giorni — dice se siamo in bull (rialzo) o bear (ribasso) market.

**Come vengono usate?**
- Filtraggio: se prezzo > SMA50 > SMA200 → il trend è ORDINATO e al rialzo
- Se prezzo < SMA200 → il mercato è debole, evitare nuovi ingressi

---

### 3️⃣ RSI14 — Relativistic Strength Index (quanto il prezzo è "caldo")

**Cosa misura?** Quantifica se il prezzo è "troppo caldo" (ipercomprato) o "troppo freddo" (ipervenduto).

**Scala:** 0-100
- 0-30: FREDDO (ipervenduto) — rischio ribasso
- 30-70: NORMALE — zona equilibrio
- 70-100: CALDO (ipercomprato) — rischio ribasso per inversione

**Come il sistema lo usa?**

| RSI | Situazione | Azione |
|-----|-----------|--------|
| < 30 | Ipervenduto | Evita ingressi (mercato troppo debole) |
| 40-55 (equity) | Ottimale | INGRESSO! L1 pronto |
| > 70 | Ipercomprato | USCITA! Prendi i profitti |

**Esempio:** Se un ETF di equity vale €100 e RSI è 50, il sistema dice "OK, il prezzo è equilibrato, possiamo comprare". Se RSI sale a 75, dice "Attenzione, è troppo caldo, esci".

---

### 4️⃣ ADX14 — Average Directional Index (la forza del trend)

**Cosa misura?** Quanto il trend è FORTE e ORDINATO (non laterale).

**Scala:** 0-100
- 0-20: Trend DEBOLE o laterale — evita
- 20-50: Trend MODERATO a FORTE — OK
- 50+: Trend MOLTO FORTE — ottimale

**Perché serve?** Evita ingressi quando il prezzo non ha una direzione chiara. Se il prezzo sale ma l'ADX è basso, significa che sta "ondeggiando" senza forza — rischioso.

**Esempio:** Un ETF che sale da €98 a €102 in 5 giorni.
- Se ADX = 15 → sale, ma debolmente (laterale). Evita ingresso.
- Se ADX = 30 → sale con forza ordinata. Ingresso OK ✓

---

### 5️⃣ MACD — Moving Average Convergence Divergence (il momentum)

**Cosa misura?** Se il momentum di prezzo sta ACCELERANDO (positivo) o DECELERANDO (negativo).

**Come funziona?**
- MACD histogram > 0 → momentum positivo, prezzo sta accelerando al rialzo
- MACD histogram < 0 → momentum negativo, prezzo sta rallentando o invertendo

**Segnale:** Blocca ingressi quando il prezzo sale ma il MACD è già negativo (significa che il rally sta esaurendo).

---

### 6️⃣ rsi_entry_low & rsi_entry_high — Il Range Ottimale per Entrare

**Cosa sono?** Limiti inferiore e superiore dell'RSI per dire "OK, puoi comprare".

**Esempio (equity_sviluppati, dal 2026-08-04):**
```
rsi_entry_low: 45
rsi_entry_high: 58

Se RSI = 50 → DENTRO al range, ingresso OK ✓
Se RSI = 30 → SOTTO al range, prezzo troppo debole
Se RSI = 70 → SOPRA al range, prezzo troppo caldo
```

**Perché è personalizzato per famiglia?**
- Bond (conservativi): range stretto 38-48 (non tollerano volatilità)
- Equity (moderato): range medio 45-55
- Crypto (volatile): range largo 35-52 (tollerano più variabilità)

---

### 7️⃣ adx_entry — Soglia Minima di Forza Trend per Entrare

**Cosa dice?** "Il trend deve essere FORTE ALMENO così tanto per permettere ingressi L1".

**Esempio (equity_sviluppati):**
```
adx_entry: 22

Se ADX = 25 → SOPRA il limite, ingresso OK ✓
Se ADX = 18 → SOTTO il limite, trend troppo debole
```

**Perché è diverso per famiglia?**
- Bond (stabili): adx_entry = 12 (accettano trend deboli)
- Equity (dinamici): adx_entry = 22 (richiedono trend forti)
- Crypto (volatili): adx_entry = 28 (richiedono trend MOLTO forti)

---

### 8️⃣ ema_dist_max — Distanza Massima dal Prezzo dalla EMA20

**Cosa misura?** "Quanto lontano puoi stare dalla media mobile e ancora comprare?"

**Formula:** (prezzo - EMA20) / EMA20

**Esempio:**
```
EMA20 = €100
ema_dist_max = 4.0%

Se prezzo = €102 → distanza = 2% → DENTRO al limite, OK ✓
Se prezzo = €105 → distanza = 5% → FUORI dal limite, prezzo troppo staccato
```

**Perché?** Evita di comprare quando il prezzo ha già "staccato" dalla media (ha fatto tutto il rally, adesso rischia pullback).

**Personalizzazione per famiglia:**
- Bond (conservativi): ema_dist_max = 1.5% (comprano solo vicino alla media)
- Commodity (volatili): ema_dist_max = 3.0% (tollerano più distanza)
- Crypto (ultra-volatili): ema_dist_max = 6.0% (tollerano distanza ampia)

---

### 9️⃣ days_above_ema — Persistenza del Segnale

**Cosa dice?** "Il prezzo deve stare sopra la EMA20 per ALMENO X giorni prima di confermare un ingresso".

**Perché?** Evita "falsi segnali": se il prezzo passa sopra la EMA20 per 1 giorno solo, potrebbe essere un'oscillazione, non un trend.

**Esempio:**
```
days_above_ema = 3   # dal 2026-08-04 è 3 per TUTTE le 14 famiglie
                      # (prima equity_sviluppati/settoriali_growth/settoriali_difensivi
                      # erano a 5, allineate alle altre per aumentare le occasioni L1)

Giorno 1: prezzo > EMA20 ✓
Giorno 2: prezzo > EMA20 ✓
Giorno 3: prezzo > EMA20 ✓
→ OK, INGRESSO CONFERMATO

Se Giorno 2: prezzo scende sotto EMA20
→ Falso segnale, counter riazzera, aspetta di nuovo 3 giorni
```

---

### 🔟 Stop Loss Iniziale — sl_initial_pct (Protezione dalla Perdita)

**Cosa è?** La perdita massima che tollerai dalla entry prima di uscire automaticamente.

**Formula:**
```
SL = entry_price × (1 - sl_initial_pct)
```

**Esempio (equity_sviluppati con sl_initial_pct = 0.05):**
```
Entry price = €100
SL = 100 × (1 - 0.05) = €95

Se il prezzo scende a €95, USCITA automatica
Perdita massima = €5 (5%)
```

**Personalizzazione per famiglia (da conservativo a aggressivo):**

| Famiglia | sl_initial_pct | Perdita Max su €100 |
|----------|:---:|:---:|
| Bond governo | 0.025 | 2.5% (ultra-protezione) |
| Equity sviluppati | 0.05 | 5% (protezione standard) |
| Commodity | 0.07 | 7% (protezione ampia) |
| Crypto | 0.12 | 12% (protezione ampia — mercato volatile) |

---

### 1️⃣1️⃣ Trailing Stop Dinamico — trailing_base_pct, trailing_sensitivity

**Cosa è?** Quando il prezzo SALE, il stop loss SALE ANCHE — proteggendo i guadagni senza bloccarti artificialmente.

**Formula:**
```
Se hai guadagnato poco:  SL resta largo (protezione meno stringente)
Se hai guadagnato molto: SL stringe automaticamente (protegge i profitti)
```

**Esempio (equity_sviluppati):**

| Guadagno | Distanza SL | SL su €100 entry |
|:---:|:---:|:---:|
| 0% | 8% | €92 |
| +5% | 8% (base) | €92 |
| +10% | 7.5% | €92.50 |
| +15% | 7.0% | €93 |
| +25% | FLOOR 94% | €94 |

**Logica:** Protezione soft all'inizio (lascia respirare), poi diventa stretta man mano che guadagni.

---

### 1️⃣2️⃣ L0 Entry Parameters — dd_threshold, rsi_max (Compra i Crolli)

**dd_threshold:** Quanto il prezzo deve scendere sotto il picco storico per attivare L0?

**Esempio:**
```
dd_threshold = 0.065 (6.5%)

Se il prezzo era €100 (picco):
  Prezzo crollo a €93.50 → calo di 6.5% ✓ ATTIVA L0
  Prezzo crollo a €96 → calo di 4% ✗ NON attiva L0 (ancora troppo alto)
```

**rsi_max:** RSI massimo per considerare il prezzo "ipervenduto" e quindi candidato per L0.

```
rsi_max = 45

Se RSI = 30 → ipervenduto ✓ BUONO per L0
Se RSI = 50 → non più ipervenduto ✗ NON attiva L0
```

---

## Schema Livelli — L0, L1, L2, L3

### Cos'è un Livello?
Ogni ETF è assegnato a un "livello" che dice cosa fare:

| Livello | Nome | Cosa Significa | Azione |
|:---:|--------|-----------------|--------|
| **L3** | Universe | Monitoraggio passivo | Osserva, non comprare |
| **L2** | Watchlist | Non ancora pronto | Continua a osservare |
| **L1** | Core Portfolio | COMPRA, è il momento | Compra ora, tieni la posizione |
| **L0** | Deep Recovery | Il prezzo è crollato | Compra il crollo, aspetta recupero |

### L1 — Come Si Entra (7 Condizioni TUTTE Obbligatorie — Oppure Smart 6/7 MACD)

**SPECIFICA CORRETTA** (dal Prompt di implementazione STEP 3 v4.0):

L1 richiede **TUTTE e 7** le seguenti condizioni (oppure **6/7 con MACD obbligatorio** se `use_smart_6_7_macd: true`):

| # | Condizione | Significato | Parametro |
|---|-----------|-------------|-----------|
| **1** | **Allineamento** | price > EMA20 > SMA50 (+ price > SMA200 se mm200_filter) + distanza da SMA200 ≤ `mm200_distance_max` (per famiglia, dal 2026-08-06) | `allineamento_ok` |
| **2** | **Persistenza** | giorni_sopra_EMA20 ≥ N + slope(EMA20) > 0 | `persistenza_ok` |
| **3** | **RSI Ottimale** | rsi_entry_low ≤ RSI ≤ rsi_entry_high (per famiglia) | `rsi_ok` |
| **4** | **Distanza EMA20** | 0% ≤ dist_EMA20 ≤ ema_dist_max (non troppo staccato) | `distance_ok` |
| **5** | **ADX Forte** | ADX ≥ adx_entry (forza trend confermata) | `adx_ok` |
| **6** | **MACD Momentum** | histogram > 0 AND (rising OR dist_ema20 < 2%) | `macd_ok` |
| **7** | **Spazio Residuo** | Resistenza > min_reward_pct OR ATR×mult > min_reward_pct | `space_residuo_ok` |

**Regola standard (7/7)**: Se **qualsiasi UNA è FALSE** → **INGRESSO BLOCCATO** (L2)

**Regola smart 6/7 MACD** (se abilitata per famiglia):
- Se **buy_count = 6 E macd_ok = TRUE** → Accetta come ingresso L1
- Se **buy_count = 6 E macd_ok = FALSE** → Blocca (MACD è gating condition)
- Se **buy_count ≥ 7** → Ingresso L1 come sempre

**Parametro di controllo**: `use_smart_6_7_macd` nel YAML (default: false per backward compatibility)
```yaml
equity_sviluppati:
  use_smart_6_7_macd: false  # Metti true per usare la variante sperimentale
```

**Backtest Risultati (2023-2026, 3 anni)**:
| Variante | Trade | Win Rate | P&L (€10k) | Note |
|----------|:---:|:---:|:---:|---------|
| 7/7 nativo | 3 | 100% | +€1,572 | Troppo selectivo, raro |
| 6/7 puro | 469 | 46% | +€1,442 | Troppi falsi, costi enormi |
| **smart 6/7 MACD** | **151** | **54.4%** | **+€6,460** | ✅ OTTIMALE: 4.1x 7/7, 4.6x 6/7 |

**Perché smart 6/7 MACD vince**:
1. **Operatività sostenibile**: ~50 trade/anno (~4/mese), non saturo
2. **Qualità del segnale**: elimina 318 falsi segnali del 6/7 puro mantenendo solo i 151 migliori
3. **Asimmetria payoff**: guadagno medio +4.68%, perdita media −4.10% → aspettativa positiva
4. **Durata uniforme**: 33 giorni sia vincenti che perdenti → tempo fisiologico per trend
5. **Efficienza su pezzature piccole**: +€2,599 netti anche a €5k/trade (6/7 puro andava in loss)

**Fondamenta Irrinunciabili** (no eccezioni, verificate *dopo* il 6/7 o 7/7):
- ✅ Regime BULL: `(EMA20 − SMA50) / SMA50 > lateral_band` (soglia per famiglia, calculate_regime()). Dal fix del 2026-08-04 è verificato **una sola volta qui** — prima era anche incorporato dentro la condizione 1 (Allineamento), rendendo la condizione 1 un doppio controllo mascherato.
  > ⚠️ **Aggiornamento 2026-08-06**: la condizione 1 non è più "puramente geometrica" come scritto dal fix del 04/08 — è stato aggiunto `dist_sma200_ok` (parametro `mm200_distance_max`, per famiglia, blocca ingressi troppo estesi sopra SMA200). Motivato da Feature Extraction su 80 trade nativi 7/7 a 3 anni: gap −3.38pp tra vincenti (12.98% sopra SMA200) e perdenti (16.36%), il segnale più discriminante trovato. A/B test reale (RUN A senza filtro vs RUN B con filtro) conferma il filtro migliorativo: +€327 P&L netto, +2pp win rate su 3 anni. Vedi `technical_analysis.py:1178-1185`, commit `2deb026`/`e81ae75` e `memory/SESSION_2026_08_06_AB_TEST_DEPLOYMENT.md`.
- ✅ Prezzo > SMA50 (allineamento assoluto)
- ✅ No kill switch (calo giornaliero > -3%)
- ✅ **TUTTE e 7 condizioni** (niente "6 su 7") — `min_buy_count: 7` per tutte le 14 famiglie in `config/etf_families.yaml`

> **`ema20_slope_min`** (visto nel YAML per ogni famiglia, es. 1.5% per equity_sviluppati) **non è collegato a nessun controllo nel codice** — è un parametro morto, residuo di un'implementazione precedente. La condizione 2 (Persistenza) verifica solo `slope(EMA20) > 0`, senza soglia minima.

---

### L1 — Come Si Esce — DUE MOTORI DISTINTI (scoperta e corretta il 2026-08-04)

Il codice ha **due regole di uscita separate e non equivalenti**. Confonderle porta a misurare la cosa sbagliata (è successo durante un backtest lo stesso giorno).

**1) Dashboard — `suggest_level()`** (classifica il livello nell'universo monitorato, NON le posizioni reali):

| Priorità | Regola | Trigger | Azione |
|:---:|--------|---------|--------|
| 1 | **F — Kill Switch** | Calo giornaliero ≤ −3% | USCITA totale |
| 2 | **A — Stop Loss** | Prezzo < EMA20 per 3 giorni | USCITA totale |
| 3 | **B — Trailing Stop** | EMA10 < EMA20 | USCITA totale |
| 4 | **C — Stanchezza** | RSI era ≥ 70, scende sotto | USCITA totale (non-bond) |
| 5 | **E — ADX Debole** | ADX < 18 + prezzo < EMA20 | USCITA totale (equity/commodity) |
| — | Downgrade punteggio/regime | buy_count < 7 OPPURE regime lascia BULL | L1→L2 |

**2) Portafoglio reale — `check_l1_exit()`** (le posizioni comprate davvero, tracciate in `etf_portfolio_entries`, aggiornate da `monitor.py::_update_portfolio_l1_suggerito()`):

| Priorità | Regola | Trigger | Azione |
|:---:|--------|---------|--------|
| 1 | **F — Kill Switch** | Calo giornaliero ≤ −3% | USCITA |
| 2 | **SL dinamico** | Prezzo ≤ SL suggerito (`calculate_sl_suggerito_l1`: EMA20−buffer se profitto<2%, EMA20×0.99 se ≥2%) | USCITA |
| 3 | **B — Trailing** | EMA10 < EMA20 | USCITA |
| 4 | **C — Stanchezza** | RSI era ≥70, scende sotto (non-bond) | USCITA |
| 5 | **SG dinamico** | Prezzo ≥ target (`calculate_sg_suggerito_l1`) OPPURE RSI(5)<soglia con profitto>1% | USCITA |
| 6 | **E — ADX Debole** | ADX < 18 + prezzo < EMA20 (equity/commodity) | USCITA |

**Non ha** la Regola A (prezzo<EMA20 da 3gg) né il downgrade per punteggio/regime — quelle esistono solo lato dashboard. Al loro posto usa lo stop loss/stop gain dinamico.

**3) Come opera davvero l'utente (precisato 2026-08-04) — questa è la regola che conta per calcolare rendimenti reali:**

Il sistema **non esegue mai ordini in automatico**. Il flusso reale è:
- L'ETF entra in L1 (7/7 + fondamenta) → acquisto manuale, aggiunto al portafoglio personale
- Ogni giorno il monitor ricalcola SL e TP e li manda via email (`alerts.py`)
- L'utente imposta/aggiorna manualmente questi due ordini su Directa
- La posizione esce **solo** quando il prezzo tocca lo SL o il TP a mercato (eseguito dal broker, non dal codice)
- **B, C, E, F non sono azioni di vendita separate** — servono solo a far uscire l'ETF dalla lista L1 in dashboard, cioè "non è più un candidato per un *nuovo* acquisto". Non toccano le posizioni già aperte.
- Il kill switch (F) non è un ordine a sé: se il crollo è abbastanza forte da bucare lo SL già impostato, esce da lì; altrimenti non succede nulla di automatico.

**Per backtest/calcolo di rendimenti reali usare solo**: entrata = 7/7+fondamenta, uscita = SL (`calculate_sl_suggerito_l1`) o TP (`calculate_sg_suggerito_l1`), **ricalcolati ogni giorno**, il primo dei due che viene toccato. Aggiungere: €5 Directa acquisto + €5 vendita, tassazione 26% flat sulle plusvalenze.

> **Fix 2026-08-04**: prima di oggi la Regola E non scattava **mai** in nessuno dei due motori (bug: `is_equity_family`/`is_equity_commodity` confrontavano contro nomi di famiglia legacy, mai contro i nomi YAML attuali). Fissato con `YAML_BOND_FAMILIES`/`YAML_EQUITY_COMMODITY_FAMILIES` in `technical_analysis.py`. Anche il target SG era di fatto **statico** (nessun decadimento temporale/slope EMA20) perché `ema20_series`/`rsi_5` non venivano mai popolati in `monitor.py` — ora derivati da uno storico Close reale via `database.py::get_ohlc_by_isin()`.

---

### L0 — Come Si Entra (Deep Recovery)

> 🔴 **Gate di famiglia (aggiunto 2026-08-06 — controllato PRIMA di qualunque percorso)**:
> `global_params.l0_whitelist`/`l0_blacklist` in `config/etf_families.yaml` restringono L0 a
> **`equity_sviluppati` soltanto** — la whitelist contiene una sola famiglia, la blacklist
> elenca esplicitamente le altre 13. `technical_analysis.py:890-903` esce subito con
> `L0_DISABLED_NOT_IN_WHITELIST`/`L0_DISABLED_BLACKLISTED` se la famiglia non è
> `equity_sviluppati`, prima di valutare drawdown/RSI/divergenza. Motivazione (commit
> `e81ae75`): entrate L0 fallite su settori speculativi (INRG clean energy, BATE battery,
> BTCN crypto) durante bear market strutturali — L0 è mean-reversion, funziona su indici
> ciclici ampi, non su settori strutturalmente in calo. La tabella `l0_take_profit_pct` più
> sotto resta il riferimento per tutte e 13 le famiglie storicamente attive, ma oggi solo la
> riga `equity_sviluppati` è raggiungibile in pratica.

`suggest_level_0()` ha **tre percorsi di ingresso**, non uno solo. I primi due (FAST/SLOW)
hanno priorità; se nessuno scatta si valuta il terzo (PRAGMATIC_4CONDITIONS). Su tutti e tre,
dal 2026-08-06, si aggiunge un **5° gate obbligatorio di regime**:

1. **FAST** (flash crash): crollo rapido rilevato via z-score ATR su pochi giorni
2. **SLOW** (bear sostenuto): giorni consecutivi sotto SMA200 + drawdown normalizzato
3. **PRAGMATIC_4CONDITIONS** — tutte e 4 obbligatorie:
   1. **Drawdown:** Prezzo almeno X% sotto il picco storico (dd_threshold dal YAML)
   2. **RSI Ipervenduto:** RSI < rsi_max (es. 45 per equity)
   3. **Divergenza Rialzista:** Il prezzo fa un minimo più basso, ma RSI fa un minimo più alto
   4. **Segnale di Recupero:** RSI risorge > 40, OPPURE prezzo sale ≥ 1% su 5 giorni
5. **Regime BULL** (nuovo 2026-08-06): `regime_ok = (calculate_regime(ema20, sma50) == 'BULL')`,
   applicato a tutti e 3 i percorsi (`entry_ok = cond1 and cond2 and cond3 and cond4 and regime_ok`
   in `technical_analysis.py:1003-1008`). Blocca ingressi in mercato strutturalmente ribassista
   ("catching a falling knife"), parametro `global_params.l0_regime_required: BULL` nel YAML.

> **Fix 2026-08-05**: prima FAST e SLOW entravano in L0 al solo rilevamento del crollo,
> senza nessuna prova che l'inversione fosse davvero iniziata — a differenza del
> percorso pragmatico, che richiede sempre divergenza+recovery. Causa sospetta dei
> "falsi L0" che continuavano a scendere o lateralizzavano dopo l'ingresso. Ora
> entrambi richiedono `_get_l0_confirmation_signal()` (RSI risalito sopra soglia
> OPPURE prezzo che riconquista l'EMA20/50) prima di confermare l'ingresso; se non
> confermato, si prosegue al percorso successivo (FAST → SLOW → PRAGMATIC).

> **Fix 2026-08-06 — dati di validazione**: dopo whitelist+regime, backtest a 3 anni su
> `equity_sviluppati`: 24 trade (~8/anno), win rate netto 37.5% (9 vinti, 15 persi — atteso
> per mean-reversion, payoff ratio 7.15x compensa), P&L netto 3 anni €6.524
> (~€2.175/anno per posizione da 10k€). Campione piccolo, quindi ancora dentro la finestra di
> validazione live 2026-08-06→2026-09-06 (vedi "Stato Attuale & Roadmap L1" più sotto — la
> stessa finestra vale anche per questi due fix L0). Dettagli in
> `memory/SESSION_2026_08_06_AB_TEST_DEPLOYMENT.md` e `DEPLOYMENT_REPORT_L0_20260806.md`.

**Esempio (percorso pragmatico):**
```
ETF = €100 (picco)
Scende a €93 (calo 7%) + RSI = 35 → entra L0

Giorni passati: RSI fa minimi sempre più alti mentre prezzo scende
Esempio: giorno 1 RSI = 25 e prezzo = €97
         giorno 2 RSI = 22 e prezzo = €95
         giorno 3 RSI = 20 e prezzo = €93

Poi RSI rimbalza a €42 → INGRESSO L0 CONFERMATO
```

---

### L0 — Come Si Esce — DUE MOTORI DISTINTI (come L1, vedi sopra)

**1) Dashboard — `suggest_level_0()`** (classifica il livello nell'universo monitorato,
NON le posizioni comprate davvero):

| Simbolo | Regola | Trigger | Azione |
|:---:|--------|---------|--------|
| β | Trappola | RSI < 25 dopo entry | Esce da L0, torna a L2/L3 |
| α | Invalidazione | Prezzo < trigger_low_price (il minimo al momento dell'ingresso) | Esce da L0, torna a L3 |
| ε | Tempo Scaduto | 30 giorni senza recupero | Documentato, non implementato — vedi nota sotto |

> **Fix 2026-08-05 — rimossa γ** (prezzo > EMA20 → promuovi a L2): su richiesta esplicita,
> un ETF in L0 non deve passare a L2 solo perché il prezzo supera l'EMA20 — quel segnale
> è già richiesto per CONFERMARE l'ingresso nei percorsi FAST/SLOW (vedi sopra), non ha
> senso riusarlo anche come motivo di uscita. L0 punta a inversioni di medio-lungo periodo:
> un ETF resta classificato L0 finché non perde davvero i requisiti (β o α), non quando il
> recupero si conferma — quello è il punto, non la fine. Rimossi due punti che
> implementavano la stessa promozione gamma per vie diverse (`suggest_level_0()` e un
> blocco ridondante in `monitor.py` via `etf_l0_tracking`).
>
> **ε (timeout 30gg) non è mai stato implementato** a livello di tracking dashboard —
> resta solo documentato. Non bloccante: la maggior parte degli L0 esce comunque via β
> o α prima di 30 giorni; da valutare se serve davvero.

**2) Portafoglio reale — `_update_portfolio_l0_suggerito()`** (le posizioni in
`etf_portfolio_entries` con `portafoglio='L0'`, quelle comprate davvero):

| Priorità | Regola | Trigger |
|:---:|--------|---------|
| 1 | SL trailing | Prezzo ≤ SL suggerito (`calculate_sl_suggerito_l0`: <5% profitto → entry×0.96 [4%, era 2% fino al 2026-08-20], 5-15% → pareggio entry×1.01, >15% → protegge metà gain) |
| 2 | TP fisso di famiglia | Prezzo ≥ TP suggerito (`calculate_tp_suggerito_l0`, **nuovo 2026-08-05** — target fisso `l0_take_profit_pct` per famiglia, vedi tabella sotto) |

> **Fix 2026-08-05 — stessa contraddizione già risolta su L1**: `check_l0_exit()` chiudeva
> automaticamente le posizioni reali su kill switch, RSI<25, prezzo<minimo 30gg o timeout
> 45gg — in contrasto con "nessun automatismo, l'unica uscita reale è il tocco manuale di
> SL o TP". Verificato sul DB di produzione: 4 delle 5 posizioni L1 storiche risultavano
> chiuse con `exit_rule='B_trailing'` (regola dashboard-only), non da un vero tocco di
> SL/TP. `check_l0_exit()` rimossa (dead code). Ora l'uscita reale dipende solo da
> `sl_hit`/`tp_hit`; la posizione non viene mai riclassificata a L1/L2, resta L0 finché
> non tocca uno dei due livelli.
>
> **Prima L0 non aveva alcun Take Profit** — solo SL. Aggiunto `l0_take_profit_pct` per
> le 13 famiglie con L0 attivo (target ~2-2.5x il drawdown minimo richiesto in ingresso:
> non basta recuperare il calo, serve un margine reale di nuovo trend). ⚠️ **Dal
> 2026-08-06** il whitelist gate (vedi "L0 — Come Si Entra" sopra) rende 12 di queste 13
> righe irraggiungibili in pratica — solo `equity_sviluppati` può ancora entrare in L0. La
> tabella resta valida come riferimento parametri (per quando/se la whitelist verrà
> riaperta), non come stato operativo attuale:

| Famiglia | l0_take_profit_pct | Famiglia | l0_take_profit_pct |
|----------|:---:|----------|:---:|
| equity_sviluppati | 16% | oro_metalli_preziosi | 16% |
| mercati_emergenti | 18% | metalli_industriali | 18% |
| settoriali_growth | 22% | real_estate_reit | 13% |
| settoriali_difensivi | 10% | crypto_digital_assets | 45% |
| bond_governativi | 6% | leva_single_stock | 30% |
| bond_corp_hy_em | 8% | private_equity_buffer | 12% |
| commodities | 20% | monetario_liquidita | n/a (L0 disabilitato) |

---

## Esecuzione ordini reali su Directa (2026-08-08)

> Sezione operativa, non un parametro del sistema — riguarda come tradurre gli SL/TP
> calcolati (email + dashboard) in ordini reali sul broker. Emersa da un caso reale
> (posizione L1 su Amundi MSCI Water, 70 quote) durante una sessione di gestione
> portafoglio, non da un'analisi preventiva.
>
> ⚠️ **Specifica di Directa, non universale (storico)**: il sistema ha operato per un periodo
> anche su **Webank** (es. la posizione DJIA, FR0007056841) — confermato che Webank supporta
> Stop Loss e Take Profit **contemporaneamente attivi** (verosimilmente un vero OCO), a
> differenza del vincolo Directa descritto sotto. `order_pricing.py` calcola gli stessi tre
> prezzi per ogni posizione indipendentemente dal broker — su Webank si possono piazzare
> `prezzo_stop`/`prezzo_limite_stop` E `prezzo_limite_tp` come due ordini separati fin da
> subito, senza la danza cancella-e-sostituisci richiesta da Directa. Il broker **è** tracciato
> per posizione (`etf_portfolio_entries.broker`, aggiunto durante la sessione dell'8/08) — email
> e dashboard applicano automaticamente la logica giusta in base al broker della posizione
> (`OCO_CAPABLE_BROKERS = {'Webank'}` in `order_pricing.py`).
>
> ✅ **Aggiornamento 2026-08-19 — policy Directa-only**: l'utente è passato a usare solo
> Directa per le nuove posizioni (sia L0 che L1) — non apre più posizioni su Webank. Le due
> posizioni Webank residue (Amundi DJ Industrial Average L1, iShares MSCI Canada L0) restano
> gestite manualmente dall'utente in dashboard. **Codice non modificato**: il default era
> già `'Directa'` ovunque (form dashboard, `add_portfolio_entry()`, tutte le letture in
> `app.py`) — la logica multi-broker/OCO resta nel codice ma inerte, tenuta per flessibilità
> futura, non rimossa. Vedi `memory/etf_broker_choice_l0_webank_l1_directa.md`.

**Directa non ha un ordine "Take Profit"**: lo Stop di vendita accetta solo un trigger
verso il basso (`Prezzo Stop ≤ X` → esegue un ordine Limite a un prezzo Y sotto il
trigger, per garantire il fill anche in caso di gap). Per catturare un target al rialzo
serve un ordine Limite separato, senza trigger.

**Scoperta critica, verificata in produzione**: su un conto cash Directa (nessun short
selling) **non è possibile tenere attivi Stop e Limite in parallelo sulle stesse quote**.
Un secondo ordine di vendita per l'intera posizione viene rifiutato con l'errore
`"Quantità titolo superiore alla disponibilità in portafoglio o titolo non vendibile allo
scoperto"` — lo Stop già impegna tutte le quote disponibili, un Limite per lo stesso
quantitativo supererebbe quanto realmente posseduto. Confermato piazzando lo Stop
aggiornato su Water (70/70 quote, Trigger 71,77€/Prezzo 71,05€, "Immesso") e poi provando
a piazzare in parallelo il Limite TP a 73,57€: rifiutato.

**Conseguenza pratica**: un solo ordine di vendita può essere attivo alla volta per
l'intera posizione.
- **Default**: tenere lo Stop attivo (protezione del capitale/guadagno accumulato — è
  la priorità, coerente con la filosofia "nessun automatismo, ma protezione sempre
  presente" del resto del sistema).
- **Quando il prezzo si avvicina al TP**: cancellare manualmente lo Stop e piazzare il
  Limite (o vendere) in quel momento — non è automatizzabile con due ordini paralleli.

**`order_pricing.py`** (`compute_order_prices()`) traduce gli SL/TP calcolati in tre
valori mostrati in email e dashboard:
- `prezzo_stop` / `prezzo_limite_stop` — la coppia per l'ordine Stop attivo (margine 1%
  tra i due, per garantire l'esecuzione anche in caso di gap)
- `prezzo_limite_tp` — **target di riferimento**, non un ordine piazzabile in parallelo
  (vedi sopra)

**Euristica di avvicinamento al TP** (decisa con l'utente 2026-08-08, non backtestata
come le formule SL/TP — riguarda solo come si formula l'ordine, mai quando uscire): lo
Stop si stringe automaticamente verso il prezzo corrente quando ci si avvicina al target,
segnalato con 🔶 in email/dashboard:
```
distanza_da_TP% = (TP − prezzo_attuale) / prezzo_attuale
se distanza_da_TP < 1.5%: Stop = prezzo_attuale × 0.99
se distanza_da_TP < 3.0%: Stop = prezzo_attuale × 0.985
altrimenti: Stop = sl_suggerito (valore "ufficiale", invariato)
```
Lo Stop stretto non scende mai sotto il valore già suggerito dalla formula ufficiale
(`max(sl_suggerito, tightened)`) — l'euristica stringe, non allarga mai la protezione.

**Non ancora fatto**: un alert email dedicato quando una posizione entra nella zona di
stringimento (oggi è solo un flag 🔶 nel resoconto quotidiano, facile da perdere con più
posizioni attive) — proposto, non richiesto esplicitamente.

---

## 🎯 Flusso Completo di Monitoraggio (End-to-End)

### Come il Sistema Decide il Livello di un ETF — Passo per Passo

Ogni giorno alle 17:00, il monitor esegue questa sequenza:

```
PASSO 1: Raccogliere dati
├─ Leggi lista ETF da Excel (ticker, categoria)
├─ Fetch prezzo + OHLCV da Yahoo Finance
├─ Salva in PostgreSQL (price_history)
└─ Leggi ultimi 200 giorni di storico

PASSO 2: Calcolare indicatori tecnici
├─ EMA20 (prezzo recente)
├─ SMA50 (trend medio)
├─ SMA200 (regime lungo)
├─ RSI14 (momentum)
├─ ADX14 (forza trend)
├─ MACD (accelerazione)
└─ Tutti i calcoli usano i parametri da etf_families.yaml

PASSO 3: Determinare il livello GLOBALE (L0/L1/L2/L3) — suggest_level()
├─ Leggi parametri della famiglia ETF (es. equity_sviluppati) da etf_families.yaml
├─ Verifica le 7 condizioni (vedi sezione "L1 — Come Si Entra" sotto)
├─ Conta quante sono TRUE (buy_count)
│  └─ Serve buy_count >= min_buy_count (= 7 per TUTTE le famiglie oggi, zero tolleranza)
├─ Se 7/7: verifica le fondamenta (regime BULL, prezzo > SMA50, no kill switch)
│  ├─ Tutte vere → L1
│  └─ Una fallisce → resta L2
└─ Se < 7/7 → L2 (se sopra EMA20 abbastanza gg) o L3 (universe)

  NOTA: esiste in parallelo un secondo motore, la "Gerarchia 2+2"
  (check_l1_entry_accelerated(), Gate A+M + Velocity P/R/D/X, sizing 60-100%)
  e un motore "tiered" (check_l1_entry_tiered(), quality score 0-4). Entrambi
  vengono CALCOLATI e loggati/salvati come metadata (l1_accelerated_entry,
  l1_tiered_entry nel dashboard_data.json) ma NON decidono il livello — è
  informativo/sperimentale, non collegato a suggest_level(). Non farsi
  guidare da questi campi per capire perché un ETF è o non è in L1.

PASSO 4: Verificare uscite L1 — DUE MOTORI DISTINTI, non intercambiabili
├─ Dashboard (classificazione L1↔L2/L3 nell'universo monitorato):
│  suggest_level() con current_level=1, regole F→A→B→C→E
│  + downgrade automatico se buy_count scende sotto 7 o il regime lascia BULL
│  Non sono vendite reali: un ETF che esce da L1 qui significa solo
│  "non è più un candidato per un NUOVO acquisto"
└─ Portafoglio reale (posizioni in etf_portfolio_entries, quelle comprate
   davvero): NESSUN AUTOMATISMO. Ogni giorno il monitor ricalcola SL
   (calculate_sl_suggerito_l1) e TP (calculate_sg_suggerito_l1) e li
   manda via email. L'utente li imposta/aggiorna manualmente su Directa.
   La posizione esce solo quando il prezzo tocca uno dei due a mercato —
   è questa l'unica regola che conta per sapere quanto tieni davvero
   una posizione e per calcolare rendimenti reali (vedi sezione dedicata sotto).

PASSO 5: Valutare L0 (se prezzo è in crollo)
├─ Drawdown? Prezzo ≤ picco × (1 - dd_threshold)?
├─ RSI ipervenduto? RSI < rsi_max?
├─ Divergenza rialzista? Prezzo minimo ↓, RSI minimo ↑?
├─ Segnale recupero? RSI > 40 O breakout ≥ 1%?
└─ Se tutte 4 → INGRESSO L0, attesa recupero

PASSO 6: Aggiornare output
├─ Salva livello in PostgreSQL (l1_tracking, l0_tracking)
├─ Aggiorna Excel (colonna "Livello")
├─ Salva data/dashboard_data.json (letto da browser)
└─ Genera email con segnali L1 e L0

PASSO 7: PDF Automatico
├─ Leggi config/etf_families.yaml
├─ pdf_generator.py genera tabelle parametri
├─ Salva PDF in data/ETF_Monitor_Parametri_Riferimento.pdf
└─ Browser scarica automaticamente
```

### Implementazione Tecnica della Sincronizzazione PDF (100% Automatica)

Affinché il PDF sia **sempre** sincronizzato, usa questa pipeline:

**File: `pdf_generator.py`**
```python
def generate_parameters_pdf(output_path):
    """Genera PDF DIRETTAMENTE dal YAML — nessun hardcoding."""
    
    # Step 1: Leggi il YAML
    with open('config/etf_families.yaml') as f:
        families = yaml.safe_load(f)['families']
    
    # Step 2: Per ogni famiglia, estrai i parametri
    for fam_name, fam_params in families.items():
        # Extract: rsi_entry_low, rsi_entry_high, adx_entry, ecc.
        # Genera righe di tabella nel PDF
    
    # Step 3: Crea documento ReportLab
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    story = []
    
    # Step 4: Aggiungi titolo + paragrafo di sincronizzazione
    story.append(Paragraph("ETF Monitor — Parametri di Riferimento", styles['Title']))
    story.append(Paragraph(
        f"Documento auto-generato {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        styles['Normal']
    ))
    
    # Step 5: Aggiungi tabelle (dinamiche dal YAML)
    for fam_name, params in families.items():
        table_data = [
            ['Famiglia', fam_name],
            ['RSI Range', f"{params['rsi_entry_low']}–{params['rsi_entry_high']}"],
            ['ADX Entry', params['adx_entry']],
            # ... altri parametri
        ]
        story.append(Table(table_data))
    
    # Step 6: Genera PDF
    doc.build(story)
```

**File: `app.py` (all'avvio)**
```python
from pdf_generator import generate_parameters_pdf

@app.before_request
def generate_pdf_on_startup():
    """Al startup, genera il PDF da YAML."""
    generate_parameters_pdf('data/ETF_Monitor_Parametri_Riferimento.pdf')
```

**File: `monitor.py` (dopo ogni ciclo)**
```python
def run_monitor():
    """Monitor principale — esecuzione 17:00 + 09:00."""
    
    # ... fetch, calcoli, salvataggi ...
    
    # STEP FINALE: Rigenera PDF
    generate_parameters_pdf('data/ETF_Monitor_Parametri_Riferimento.pdf')
    add_log("✅ PDF parametri rigenerato e sincronizzato con YAML")
```

**File: `app.py` (endpoint download)**
```python
@app.route('/api/download-parameters-pdf')
def download_pdf():
    """Scarica il PDF parametri — garantito sincronizzato."""
    return send_file(
        'data/ETF_Monitor_Parametri_Riferimento.pdf',
        as_attachment=True,
        download_name='ETF_Monitor_Parametri.pdf'
    )
```

**File: `dashboard.html` (bottone scaricamento)**
```html
<button onclick="downloadPDF()">📥 Scarica Parametri PDF</button>

<script>
function downloadPDF() {
    fetch('/api/download-parameters-pdf')
        .then(r => r.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `ETF_Monitor_Parametri_${new Date().toISOString().split('T')[0]}.pdf`;
            a.click();
        });
}
</script>
```

**Risultato finale:**
- ✅ Modifica YAML → monitoraggio rilegge automaticamente
- ✅ Prossimo ciclo monitor → PDF rigenerato automaticamente
- ✅ Utente scarica PDF → riceve i parametri attuali, SEMPRE sincronizzati

---

## 📊 Interazione tra Parametri — Come Lavorano Insieme

Nessun parametro agisce da solo. Ecco come si combinano:

### Scenario 1: Ingresso L1 Accelerato (Gerarchia 2+2) — motore parallelo, NON autoritativo

> ⚠️ Questo scenario descrive `check_l1_entry_accelerated()`, un motore calcolato in
> parallelo (STEP 12) e salvato come metadata (`l1_accelerated_entry`, `l1_velocity_count`)
> ma che **non decide il livello reale**. Il gate che conta oggi è quello a 7 condizioni
> descritto in "L1 — Come Si Entra" sopra (`min_buy_count: 7`, zero tolleranza). Questo
> esempio resta utile per capire l'idea di sizing per confidenza, ma con questi numeri
> (Gate 2/2 + Velocity 2/4) l'ETF **non** entrerebbe in L1 nel sistema live.

```
Giorno 1, ore 17:00 — Monitor esegue

┌─ GATE STRUTTURALE (OBBLIGATORIO) ─────────────────
│ A: prezzo = €102, EMA20 = €100 → 102 > 100 ✓
│ M: MACD histogram = +0.5 → positivo ✓
│ Risultato: GATE PASSATO, procedi a VELOCITÀ
│
├─ VELOCITÀ FLESSIBILE (ALMENO 2 SU 4) ─────────────
│ P: prezzo = €102, SMA50 = €101 → 102 > 101 ✓
│ R: RSI = 48, range = 45-55 → DENTRO ✓
│ D: ADX = 20, soglia = 22 → SOTTO ✗
│ X: EMA20 = €100, SMA50 = €101 → 100 < 101 ✗
│ Risultato: 2 su 4 VERE → INGRESSO AUTORIZZATO
│
└─ DECISION: L1 con 60% allocation
  Motivo: Gate 2/2 + Velocity 2/4 = confidenza 60%
```

### Scenario 2: Protezione con Stop Loss Dinamico

```
Entry L1 su €100
Parametri equity_sviluppati:
  - sl_initial_pct = 0.05 (protezione iniziale 5%)
  - trailing_base_pct = 0.08 (base trailing 8%)
  - trailing_sensitivity = 0.005
  - trailing_min_pct = 0.94 (floor 94%)

Giorno 1 (prezzo = €100, gain = 0%):
  SL = 100 × (1 - 0.05) = €95
  → Se scende a €95, uscita totale

Giorno 5 (prezzo = €108, gain = +8%):
  excess_gain = 8% - 3% (threshold) = 5%
  distance = 8% - (5% × 0.005) = 7.75%
  SL = 108 × (1 - 0.0775) = €99.57
  → Stop loss SALITO automaticamente, protegge i profitti

Giorno 10 (prezzo = €120, gain = +20%):
  excess_gain = 20% - 3% = 17%
  distance = 8% - (17% × 0.005) = 7.15% → ma è < 94% floor
  distance = 94% (FLOOR ATTIVATO)
  SL = 120 × 0.94 = €112.80
  → Protezione minima garantita, non scende più
```

### Scenario 3: Uscita L1 per Stanchezza (Regola C)

```
Entry L1 a €100 (RSI = 50)

Giorni passati:
  Giorno 1: prezzo = €102, RSI = 52
  Giorno 2: prezzo = €105, RSI = 65
  Giorno 3: prezzo = €108, RSI = 76 (IPERCOMPRATO)
    → Log: "RSI_prev = 76 >= 70, monitora"
  Giorno 4: prezzo = €107, RSI = 68 (SCESO SOTTO 70)
    → TRIGGER REGOLA C: "era ≥70, ora <70"
    → USCITA TOTALE
    → Email: "ETF USCITO per stanchezza RSI (C)"
```

### Scenario 4: L0 Entry Deep Recovery

```
ETF equity, picco = €100
Parametri L0:
  - dd_threshold = 0.065 (calo 6.5%)
  - rsi_max = 45
  - lookback_high_days = 3
  - recovery_min_pct = 0.015

Crollo di mercato:
  Giorno 1: prezzo €98, RSI = 42 → ancora non pronto
  Giorno 2: prezzo €96, RSI = 38 → drawdown 4%, RSI < 45 ✓
  Giorno 3: prezzo €94, RSI = 35 → drawdown 6% ✓, RSI < 45 ✓
    Verifica divergenza: minimo prezzo ↓ ma RSI minimo ↑
    → Divergenza CONFERMATA ✓

Recupero:
  Giorno 4: prezzo €95, RSI = 37 → nessun segnale ancora
  Giorno 5: prezzo €96.50, RSI = 42 → +1.6% su 5gg ✓
    → INGRESSO L0 CONFERMATO
    → Salva: entry_price = €94, entry_date = day5
    → Attesa: prezzo > EMA20 (promozione a L2)

Dopo 15 giorni:
  Prezzo risale a €99 (+5.3% da entry L0)
  Prezzo > EMA20 (€97) ✓
    → USCITA L0, PROMOZIONE A L2
    → Email: "ETF ripreso da L0 → L2"
```

---

## 🎓 Esempio Completo: ETF SWDA.L (MSCI World)

> ⚠️ Esempio narrativo tenuto per didattica sul funzionamento generale degli indicatori,
> ma con due parti superate: (1) usa la logica Gate+Velocity ("Gerarchia 2+2"), sostituita
> dal gate rigido a 7 condizioni; (2) i valori YAML sotto sono quelli precedenti allo
> Step 4 del 2026-08-04 — `equity_sviluppati` oggi ha `rsi_entry_high: 58`,
> `days_above_ema: 3`. Valori aggiornati nella tabella famiglie in fondo al documento.

Fingiamo di seguire SWDA.L per una settimana intera. SWDA.L è **equity_sviluppati**, quindi usa questi parametri dal YAML (valori storici, vedi nota sopra):

```yaml
rsi_entry_low: 45
rsi_entry_high: 55
adx_entry: 22
ema_dist_max: 4.0
days_above_ema: 5
dd_threshold: 0.065
sl_initial_pct: 0.05
trailing_base_pct: 0.08
```

**LUNEDÌ**
```
Prezzo: €82
EMA20: €80.50
SMA50: €80.00
SMA200: €79.00
RSI: 52
ADX: 18
MACD histogram: -0.3

Analisi:
  GATE A: 82 > 80.50 ✓
  GATE M: MACD -0.3 (negativo) ✗
  → BLOCCO: almeno uno dei gate è FALSE
  → Livello attuale: L3 (universe)

Azione: NESSUNA
```

**MARTEDÌ**
```
Prezzo: €84
EMA20: €81.20
SMA50: €80.30
SMA200: €79.10
RSI: 54
ADX: 20
MACD histogram: +0.1

Analisi:
  GATE A: 84 > 81.20 ✓
  GATE M: +0.1 (positivo) ✓
  → GATE PASSATO
  
  VELOCITÀ:
    P: 84 > 80.30 ✓ (sì, sopra SMA50)
    R: RSI 54, range 45-55 ✓ (dentro range)
    D: ADX 20, soglia 22 ✗ (sotto soglia)
    X: EMA20 81.20 < SMA50 80.30 ✗ (non soddisfatto)
  → Conta: 2 su 4 vere ✓
  
  Livello: L1 (INGRESSO AUTORIZZATO)
  Confidence: 60% (Gate 2/2 + Velocity 2/4)
  Stop Loss: €84 × (1 - 0.05) = €79.80
  
Azione: EMAIL ALERT - "SWDA.L pronto per ingresso L1"
```

**MERCOLEDÌ**
```
Prezzo: €86 (+2%)
EMA20: €82.30
RSI: 56
ADX: 23
MACD histogram: +0.4

Azione: MANTIENI L1 (tutte le 6 condizioni di uscita sono FALSE)
Dashboard: mostra SWDA.L in L1 con €86 (entry day martedì)
```

**GIOVEDÌ**
```
Prezzo: €88 (+4%)
Gain: +4.65% da entry
EMA20: €83.50
RSI: 68
ADX: 25
MACD histogram: +0.6

Trailing Stop Update:
  excess_gain = 4.65% - 3% = 1.65%
  distance = 8% - (1.65% × 0.005) = 7.99%
  SL = 88 × (1 - 0.0799) = €80.98
  → Stop loss salito da €79.80 a €80.98

Azione: MANTIENI L1 (SL protegge i profitti)
```

**VENERDÌ**
```
Prezzo: €91 (+7.5% da entry)
EMA20: €85.00
RSI: 76 (IPERCOMPRATO, ma < 70 ancora no)
MACD histogram: +0.8

Azione: MANTIENI L1

Fine settimana:
  Posizione: L1 attiva
  Entry: €84, Current: €91
  Gain: +7.5%
  Stop Loss: €81 (trailing dinamico)
  
Email di riepilogo:
  SWDA.L — L1 attiva — Gain +7.5% — SL €81
```

Se il LUNEDÌ DOPO:
```
Prezzo: €88 (-3.3% da €91)
RSI: 68 → 64 (era sopra 70, ora scende)
  → REGOLA C TRIGGERED: uscita totale

Azione: USCITA L1 (regola C stanchezza)
Email: "SWDA.L USCITO da L1 per stanchezza (Regola C)"
Trade chiuso: Entry €84, Exit €88, Gain +4.76%
Storico: salvato in l1_exit_history
```

---

## Stato Attuale & Roadmap L1 (dal 2026-08-05)

> Sezione viva — aggiornarla quando arrivano nuovi dati (es. dal backtest esteso a 3 anni) o quando si prende una decisione. Non è uno storico di modifiche già fatte (quello è più sotto, "Note Operative") ma il punto di riferimento su cosa è deciso, cosa è in osservazione, e quando si riapre la discussione.

### Cosa sappiamo — AGGIORNATO dopo il backtest a 3 anni (2026-08-05, stesso modello: entrata 7/7+fondamenta, uscita solo SL/TP giornalieri via `calculate_sl_suggerito_l1`/`calculate_stop_gain_dynamic`, costi Directa 5+5€, tasse 26% — nota: senza compensazione minus/plus, quindi il netto reale è probabilmente migliore di quello simulato)

**12 mesi (2025-08→2026-08) vs 3 anni (2023-08→2026-08):**

| | `min_buy_count=7` | `min_buy_count=6` (12 mesi) | `min_buy_count=6` (3 anni) |
|---|:---:|:---:|:---:|
| Trade | 3 (identici su 1 e 3 anni) | 234 | 469 |
| Win rate | 100% | 52.9% | **46.1-46.3%** |
| P&L netto 10.000€/trade | +1.572€ | +14.451€ | **+1.489€** |
| P&L netto 5.000€/trade | +775€ | +6.264€ | **-1.280€** |

- **`min_buy_count=7` è stabile su qualunque finestra temporale**: stessi identici 3 trade sia a 1 che a 3 anni — nessun nuovo ingresso nei 2 anni aggiuntivi. Segnale raro ma affidabile, non un artefatto di un periodo favorevole.
- **`min_buy_count=6` si è ridimensionato parecchio sui 3 anni**: da nettamente profittevole a marginale (10k€) o in perdita netta (5k€). Causa identificata: il **2024** (143 trade, quasi 1/3 del totale) ha avuto win rate 37.1% e rendimento medio -0.84% — un anno chiaramente negativo per la strategia che il test a 12 mesi non catturava (quella finestra prendeva soprattutto il 2025, l'anno migliore).
- **`leva_single_stock` è confermata, non più solo sospettata**: su 3 anni sono 12 trade (non più 4), tutti nel pattern negativo (-5.10% medio, -61,24% totale) — la famiglia peggiore in assoluto.
- **`mercati_emergenti` è passata da "motore" (+28.72% sui 12 mesi) a leggermente negativa (-10.39% sui 3 anni)** — il suo contributo positivo recente non è una caratteristica strutturale.
- `equity_sviluppati` resta l'unico driver stabile e positivo su entrambe le finestre.

### Decisioni prese

1. **`min_buy_count` resta a 7 in produzione.** Nessuna modifica a YAML o alla logica L1 per un periodo di validazione live. **Rinforzato dai dati a 3 anni**: 7/7 è ora la scelta più solida delle due, non più solo quella "attuale in attesa di conferma".
2. **Periodo di validazione live: 3-4 settimane dal 2026-08-05** — resta valido.
3. **`leva_single_stock` esclusa dal gate L1 — FATTO (2026-08-05)**: `min_buy_count: 8` in `config/etf_families.yaml` (irraggiungibile su 7 condizioni). Non è una rimozione dall'Excel/monitor: la famiglia resta tracciata in L0/L2/L3 come tutte le altre, blocca solo la promozione a L1. Impatto verificato: 10 perdenti su 12 trade nel backtest a 3 anni, +6.124€ di miglioramento sul P&L netto 3 anni (10.000€/trade) rimuovendola dal calcolo (da +1.489€ a +7.613€).
   > ⚠️ **Gap noto**: questo blocco vale solo per `suggest_level()` (il gate principale). `check_l1_entry_tiered()`/`check_l1_entry_accelerated()` (i motori paralleli della Fase 3 "sistema tiered") **non leggono `min_buy_count`** — se/quando si collegano quei motori, l'esclusione di `leva_single_stock` va applicata esplicitamente anche lì, altrimenti la famiglia può rientrare da quella porta.
4. **`mercati_emergenti` declassata da "motore" a "da monitorare"** — non trattarla più come un contributo affidabile per default.
5. **`check_l1_exit()` e `calculate_sg_suggerito_l1()` rimosse** (erano dead code, mai più chiamate).
6. **`alerts.py` non toccato** — revisione rimandata al prossimo sprint.
7. **`min_buy_count=6` NON è più raccomandato come "alternativa validata pronta all'uso"** — i dati a 3 anni mostrano che l'edge è fragile/regime-dipendente (positivo nel 2025, negativo nel 2024). Prima di riconsiderarlo servono o (a) un modello fiscale con compensazione minus/plus per capire il vero netto, o (b) un filtro che escluda selettivamente i trade deboli (vedi sistema tiered sotto).

### ⚠️ Aggiornamento 2026-08-23 — da scadenza fissa (06/09/2026) a checkpoint ricorrente

**La data fissa "lockdown fino al 06/09/2026" citata più sotto in questo documento (per
`CANDIDATE_MODEL_B_20260807`, `CANDIDATE_MODEL_L0_20260808`, Market Breadth) è superata come
unico momento di decisione.** Non viene cancellata perché è il motivo per cui il lockdown è
iniziato ed è tuttora valida come primo checkpoint — ma non è più l'unica occasione per
guardare i dati né il presupposto per continuare a tracciare gli Shadow Monitor.

**Cosa cambia:**
- Gli Shadow Monitor (`shadow_monitor.py`, `shadow_monitor_l0.py`,
  `shadow_monitor_breadth.py`) **restano accesi indefinitamente** in background, sempre
  agganciati al ciclo giornaliero del monitor (STEP 8/8b/8c) — non c'è una data in cui si
  "spengono" o "scadono". Continuano a loggare su `etf_shadow_positions` a prescindere da
  qualunque scadenza.
- Al posto di una singola data fissa, il punto di riferimento diventa un **checkpoint
  ricorrente** (indicativamente mensile, o comunque non prima del 06/09/2026 per il primo
  giro): si estrae lo stato di `etf_shadow_positions` per ciascun `model_name`, si confronta
  con i nuovi ingressi reali `native_7` nello stesso periodo (query in
  `memory/etf_post_lockdown_todo_20260906.md`), e si riporta lo stato — senza che il
  raggiungimento di una data o di un numero di trade inneschi automaticamente una modifica.
- **Soglia di fiducia per qualunque promozione a produzione: N≥30 trade chiusi**, coerente
  con la soglia già usata in ogni sweep/backtest di questo documento (non 15-20 come
  ipotizzato in una discussione con un'altra AI il 2026-08-23) — sotto quella soglia il
  progetto ha già visto più volte pattern belli in-sample che si sono rivelati overfitting
  (es. `mm200_delta=-1` su L1, la zona "85% enter" sul breadth). Un candidato con N ancora
  piccolo a un checkpoint resta "in osservazione", non promosso né scartato.
- **Nessuna promozione automatica**: anche quando un candidato raggiunge N≥30 con metriche
  favorevoli, la modifica allo YAML resta una decisione esplicita dell'utente al momento del
  checkpoint — stessa filosofia "nessun automatismo" già applicata al trading reale (SL/TP
  toccati manualmente, non auto-vendita, vedi [[etf_no_auto_exit_real_positions]]). L'unica
  eccezione concessa finora è stata `CANDIDATE_MODEL_L0_SL_20260820`, promossa in produzione
  su richiesta esplicita e immediata dell'utente lo stesso giorno del backtest — resta un
  caso singolo, non un precedente per abbassare la soglia N≥30.

**Perché**: la finestra 2026-08-05→2026-09-06 si è rivelata talmente povera di segnali per
il gate nativo 7/7 (0 nuovi ingressi L1, 0 nuovi ingressi L0 in 18 giorni, verificato
2026-08-23) che aspettare una singola data per decidere avrebbe quasi certamente prodotto
"ancora troppo pochi dati" di nuovo — il problema non è la durata della finestra, è la rarità
strutturale del segnale 7/7. Un checkpoint ricorrente lascia raccogliere evidenza più a
lungo senza dover rifissare una nuova scadenza ogni volta che quella attuale scade a vuoto.

### Survey completo 14 famiglie (2026-08-24) + blocco L1 su 5 famiglie difensive

Su richiesta dell'utente ("quali altre famiglie non entrano mai, e come li gestiamo"),
survey di tutte le 14 famiglie su `native_7`/`smart_6_macd` (Golden Dataset, 3 anni) via
`optimize_hyperparameters.py`. Risultato completo in
`memory/etf_family_viability_survey_2026_08_24.md`. Sintesi:

| Gruppo | Famiglie | Trade 3yr | Esito |
|---|---|---:|---|
| Motore attivo | equity_sviluppati, settoriali_growth | 38+10 | Unici driver reali |
| In prova (L0, non L1) | oro_metalli_preziosi, metalli_industriali | 0 su L1 | Vedi sezione L0 sotto |
| **Bloccate 2026-08-24** | bond_governativi, bond_corp_hy_em, settoriali_difensivi, real_estate_reit, private_equity_buffer | 4 (tutte perdite) | `min_buy_count: 8` |
| Già escluse | leva_single_stock, commodities, crypto_digital_assets | 0-12 | Zero segnali o track record negativo |
| Diverso by design | monetario_liquidita | n/a | Non trend-following |

**Blocco applicato oggi**: le 5 famiglie difensive/bond avevano acceso il gate `native_7`
solo 4 volte in 3 anni — **tutte e 4 in perdita** (0% win rate: `bond_governativi` 2/2 perse,
`bond_corp_hy_em` 1/1, `private_equity_buffer` 1/1; `settoriali_difensivi` e
`real_estate_reit` già a 0 trade). Stesso trattamento già dato a `leva_single_stock`
(commit storico): `min_buy_count: 7` → **`8`** in `config/etf_families.yaml` per tutte e 5
— irraggiungibile su un gate a 7 condizioni, blocca solo la promozione a L1 (restano
tracciate normalmente in L0/L2/L3/dashboard, nessuna rimozione). Non serve un fix
parametrico: la diagnosi (vedi memory) è che l'impianto trend-following (EMA/SMA allineate +
persistenza + MACD in salita) non si adatta a strumenti a bassa volatilità come i bond — non
è un problema di soglie sbagliate.

⚠️ **Legenda tabella famiglie più sotto in questo documento va aggiornata di conseguenza**:
`min_buy_count` non è più "7 per tutte le 14 famiglie" — oggi è **8 per 6 famiglie**
(`leva_single_stock` + le 5 appena bloccate) e **7 per le restanti 8**. Stesso discorso per
il CLAUDE.md di root (`../CLAUDE.md`, tabella "Profili parametri FAMIGLIE ETF").

**Roadmap L0 sulle famiglie "morte" per L1 — decisa 2026-08-24**: la stessa disattivazione
per L1 non significa "chiuso per sempre" — per `oro_metalli_preziosi`/`metalli_industriali`
un meccanismo diverso (L0 mean-reversion, whitelist bypassata solo in memoria per il test)
ha già dato un segnale promettente (vedi sezione dedicata "Grid Search L0" più sotto e
`shadow_monitor_l0_oro.py`/`shadow_monitor_l0_metalli.py`, live dal 2026-08-24). **Estensione
decisa oggi**: testare lo stesso approccio (`backtest_l0_v2.py::simulate_l0()`, whitelist
bypassata solo nello script, nessun impatto produzione) sulle **restanti 8 famiglie mai
provate su L0** (i 5 bond/difensivi appena bloccati + i 3 speculativi
`commodities`/`leva_single_stock`/`crypto_digital_assets`) — L0 è un meccanismo
strutturalmente diverso (mean-reversion su drawdown, non momentum), quindi il fatto che L1
non si adatti a questi asset non implica automaticamente che L0 fallisca allo stesso modo;
va verificato con lo stesso metodo, non assunto. Vedi risultato del test in
`memory/etf_family_viability_survey_2026_08_24.md` (aggiornato dopo l'esecuzione) —
qualunque famiglia con segnale incoraggiante segue lo stesso percorso di oro/metalli
(Shadow Monitor dedicato, non promozione diretta).

**Aggiornamento stesso giorno — L0 testato su tutte e 8, poi CORRETTO poche ore dopo**: il
primo test L0 sulle 8 famiglie bloccate (whitelist bypassata solo in memoria, script one-off
mai committato) aveva dato **0 trade su tutte e 8** — risultato poi scoperto **falso, causato
da un bug**: lo script bypassava solo `l0_whitelist` ma non `l0_blacklist`, e tutte e 8 le
famiglie sono ANCHE in blacklist (`suggest_level_0()` controlla entrambe indipendentemente,
technical_analysis.py:927-933 — stesso identico bug trovato poco dopo negli Shadow Monitor
L0-oro/metalli già live, vedi sezione dedicata più sotto). Con **entrambe** le liste
bypassate correttamente, il risultato vero è l'opposto: **5 famiglie su 8 mostrano un
segnale L0 potenzialmente positivo** (bond_governativi, bond_corp_hy_em, real_estate_reit,
commodities, crypto_digital_assets), 3 negative (settoriali_difensivi, private_equity_buffer,
leva_single_stock). Dettagli, dato corrotto trovato in `3LAM.MI` (falsava la media di
`leva_single_stock` a +101,9%/trade — escluso), e test IN/OUT-of-sample di conferma in
`memory/etf_family_viability_survey_2026_08_24.md`.

Per il gap di diversificazione (portafoglio reale 75%/25% azionario/bond, con la quota bond
senza alcun meccanismo attivo), l'utente ha chiesto esplicitamente di procedere con un terzo
meccanismo — **fatto lo stesso giorno**, vedi sezione dedicata sotto.

### CANDIDATE_BOND_TREND_20260824 — terzo meccanismo per le 5 famiglie bond/difensive

Diagnosticato PRIMA di progettare (`diagnose_bond_conditions.py`, scratch, walk giorno-per-
giorno delle 7 condizioni `native_7` su 40.711 ticker-giorni, 61 ticker del cluster
difensivo, Golden Dataset 3 anni): **7/7 non accade MAI** (0.00%), **6/7 solo 85 giorni su
40.711 (0.21%)**. Frequenza TRUE per condizione: `allineamento_ok` 19.1% (EMA20>SMA50 —
il blocco dominante), `rsi_ok` 24.8%, `macd_ok` 27.2%, `space_residuo_ok` 25.0%,
`persistenza_ok` 51.5%, `distance_ok` 60.6%, `adx_ok` 78.7%. Nei rari giorni a 6/7, il
blocco è quasi sempre `allineamento_ok` (43.5%) o `rsi_ok` (40.0%) insieme — i filtri di
momentum equity (RSI/ADX/MACD/incrocio EMA20-SMA50) semplicemente non si adattano a
strumenti che oscillano in bande strette guidate dai tassi, non da trend equity-style.

**Meccanismo progettato**: `ETFTechnicalAnalyzer.suggest_bond_trend_entry()`
(`technical_analysis.py`) — 4 condizioni, niente RSI/ADX/MACD/SMA50:
1. price > EMA20
2. giorni_sopra_EMA20 ≥ `persistence_days` E slope(EMA20, finestra 10gg) > 0
3. 0% ≤ distanza da EMA20 ≤ `dist_max_pct` (ingresso non esteso)
4. no kill switch (calo giornaliero ≤ −3%)

Uscita: **riusa le funzioni reali di L1 senza modifiche** — `calculate_sl_suggerito_l1`
(trailing EMA20-based) e `calculate_stop_gain_dynamic` (target dinamico, ma con
`target_max_pct` molto più piccolo del 15% equity — l'upside realistico di un bond è
ordini di grandezza inferiore).

**Grid search iniziale (pooled)** (`backtest_bond_trend.py`, scratch, stesso Golden
Dataset, split IN 2023-08-05→2025-08-05 / OUT 2025-08-05→2026-08-05, stesso modello
costi/tasse di `backtest_l1.py`): testate combinazioni di persistenza (5/8/12/15/20gg) ×
distanza max (0.3/0.5/1.0/1.5%) × target TP (3%/5%) sulle 5 famiglie MESCOLATE (61 ticker).
Risultato pooled: IN N=191 WR=60.8% PF=1.71 | OUT N=76 WR=45.2% PF=1.68 con
persistence=20/dist_max=0.5%/target=3%.

⚠️ **Corretto poche ore dopo lo stesso giorno — il risultato pooled nascondeva un problema
serio**: su richiesta dell'utente ("non dovrebbero avere parametri diversi rispetto agli
azionari?"), grid search RIPETUTO segmentato PER FAMIGLIA (non più mescolate) con
`backtest_bond_trend_perfamily.py` (scratch). Risultato:

| Famiglia | IN: WR/PF | OUT: WR/PF | Verdetto |
|---|---|---|---|
| **bond_corp_hy_em** | 70-76% / 2,65-3,67 | 67-80% / **4,22-6,24** | Solido su ogni combinazione — PF out-of-sample sistematicamente MIGLIORE dell'in-sample |
| bond_governativi | 54-60% / 1,54-2,19 | **7-13% / 0,01-0,18** | Crolla quasi a zero fuori campione |
| settoriali_difensivi | 25-46% / 0,27-0,73 | misto, N=4 ticker | Troppo piccolo per essere significativo |
| real_estate_reit | 40-55% / 0,54-0,93 | misto, N=3 ticker | Troppo piccolo per essere significativo |
| private_equity_buffer | 20-33% / 0,21-0,5 | 25-33% / 0,31-0,41 | Perde sempre, entrambe le finestre |

Il pooled sembrava a posto solo perché l'ottima performance di `bond_corp_hy_em`
compensava nella media il crollo di `bond_governativi` — mescolarle nascondeva un rischio
reale (posizioni ombra su governativi sarebbero state fuorvianti). **Modello ristretto a
`bond_corp_hy_em` soltanto**, unica famiglia con edge forte, coerente su ogni combinazione
testata, e col pattern anti-overfitting più pulito visto in questo progetto (OOS > IN).

**Parametri finali** (ottimizzati per `bond_corp_hy_em` specificamente, non più pooled):

| Parametro | Valore |
|---|---|
| `families` | **solo `bond_corp_hy_em`** |
| `persistence_days` | 12 (era 20 nel pooled) |
| `dist_max_pct` | 0.3% (era 0.5%) |
| `target_max_pct` (TP dinamico) | 3% (invariato) |
| `target_floor_pct` | 2% (invariato) |
| `slope_window` / `slope_sensitivity` (decadimento TP) | 3 / 0.15 (stessa convenzione delle famiglie equity, non sweepato) |

**Metriche finali** (Golden Dataset, batch `2026-08-07`, 26 ticker `bond_corp_hy_em`):

| | In-Sample | Out-of-Sample |
|---|---|---|
| N trade | 83 | 45 |
| Win rate netto | 72.6% | 77.3% |
| Profit Factor | 3.43 | **5.89** |
| P&L netto (10k€/trade) | +7.306€ | +5.147€ |

Riserva che resta valida anche ristretto a una famiglia sola: **molti trade aprono sugli
stessi giorni su ticker diversi** (i bond corporate/HY della stessa asset class si muovono
insieme sulle notizie di credito/tassi) — il campione indipendente reale è più vicino a
~15-20 "eventi di mercato" che a 83+45 scommesse scorrelate. Il PF resta comunque solido e
coerente IN→OUT.

⚠️ **NON promosso in produzione** — stessa disciplina di ogni altro candidato: Shadow
Monitor prima, promozione solo dopo N≥30 su dati forward reali e decisione esplicita
dell'utente. **Shadow Monitor implementato e live lo stesso giorno**:
`shadow_monitor_bond_trend.py`, STEP 8f in `monitor.py::run()`, `model_name` =
`candidate_bond_trend_20260824`, parametri letti da
`global_params.bond_trend_model` in `config/etf_families.yaml` (mai una modifica a
`min_buy_count`/`native_7` — meccanismo completamente separato). Email sui nuovi ingressi
via `alerts.py::send_shadow_entries(variant='BOND_TREND')`, stesso meccanismo già attivo per
gli altri 4 candidati. Verificato: import puliti, smoke test su `_get_params()` OK, deploy
via `./deploy.sh`. Le 4 posizioni ombra aperte al primo ciclo (AFRN.PA, EFRN.DE, ECR3.DE,
AFLT.PA) erano già tutte `bond_corp_hy_em` — nessuna posizione su famiglie escluse da
ripulire dopo la restrizione.

**Estrazione risultati al prossimo checkpoint** (stesso pattern degli altri candidati):
```sql
SELECT ticker, entry_date, exit_date, exit_reason, gross_pct_gain, status
FROM etf_shadow_positions WHERE model_name = 'candidate_bond_trend_20260824'
ORDER BY entry_date;
```

### 🔴 Bug reale trovato e corretto 2026-08-24 — bypass whitelist L0 senza bypass blacklist

Investigando perché `shadow_monitor_l0_oro.py`/`shadow_monitor_l0_metalli.py` (live dal
giorno prima) non avessero mai aperto una posizione, e perché il test "L0 su 8 famiglie
morte" desse 0 trade ovunque: `suggest_level_0()` controlla whitelist e blacklist **in modo
indipendente** (technical_analysis.py:927-933) — se la famiglia è ANCHE in blacklist, resta
bloccata anche se aggiunta alla whitelist. Sia i due Shadow Monitor live sia lo script di
test delle 8 famiglie bypassavano solo `l0_whitelist`, mai `l0_blacklist` — ma
`oro_metalli_preziosi`, `metalli_industriali` e tutte le altre 8 famiglie testate sono
**tutte** in `l0_blacklist` nello YAML attuale. Risultato: bloccate comunque, sempre,
indipendentemente da quanto tempo passa.

**Impatto**: i due Shadow Monitor oro/metalli, deployati la sera prima, non avrebbero MAI
potuto aprire una posizione — bug silenzioso, stesso pattern del bug whitelist-mai-attiva
scoperto il 2026-08-07 (`self.p` vs `self._FAMILIES_CONFIG`), ma su un meccanismo diverso.
Fix: entrambe le funzioni di bypass ora svuotano anche la blacklist per la famiglia
interessata, oltre ad aggiungerla alla whitelist. Deployato in hot-fix nel container prima
ancora del prossimo `./deploy.sh` pianificato, poi committato normalmente.

**Con il bug corretto, tutti i numeri "L0 negativo/zero" riportati in precedenza lo stesso
giorno erano sbagliati.** Rifatti tutti i test:

**Oro/metalli — numeri veri, molto meglio dei 3/13 riportati inizialmente**: stessa finestra
2023-08-05→oggi, whitelist E blacklist bypassate: **oro N=12** (non 3), **metalli N=23**
(non 13). Estendendo la finestra al massimo storico disponibile nel batch congelato
(dati fino al 2022-02-15/03-08, mai usati da nessun backtest finora — tutti partivano da
2023-08-05) fino a 2023-02-01 (margine di sicurezza per i 220gg di warm-up SMA200):
**oro N=14, metalli N=31** su finestra unica continua.

⚠️ **Split IN/OUT-of-sample sulla finestra estesa fatto subito dopo, stesso giorno — indebolisce
il caso invece di rafforzarlo**: IN 2023-02-01→2025-08-05 / OUT 2025-08-05→2026-08-05.
- Oro: IN N=14 WR=38,5% | **OUT N=0** — tutta l'attività recente è rimasta come posizioni
  ancora aperte nella finestra IN, zero trade chiusi da validare fuori campione.
- Metalli: IN N=29 WR=**19,2%** avg=**-2,03%** (P&L -5.283€, negativo) | OUT N=4 WR=100%
  avg+14,15%. I 6 mesi aggiunti (feb-mag 2023) rivelano un cluster di 6 perdite consecutive
  che ribalta l'in-sample da positivo a negativo; il fuori-campione resta forte ma N=4 è
  troppo piccolo per contare da solo.

**Conclusione**: allargare lo storico non rafforza oro/metalli — se possibile aggiunge una
cautela reale (il quadro pluriennale di metalli include un tratto perdente che la finestra
più corta escludeva). Nessuna modifica ai parametri live degli Shadow Monitor (restano
quelli nativi YAML) — continuano a girare e accumulare dati forward reali, più affidabili
di ulteriori tagli di backtest su questi due asset rumorosi. Filone chiuso — non riaprire
senza nuovi dati o un approccio diverso.

**8 famiglie "morte" — 5 su 8 mostrano segnale positivo**, non zero:

| Famiglia | N (2023-08-05→oggi) | Win rate | Rend. medio | P&L (10k€/trade) |
|---|---:|---:|---:|---:|
| bond_corp_hy_em | 11 | 75,0% | +6,43% | +5.143€ |
| crypto_digital_assets | 26 | 32,0% | +7,41% | +18.531€ |
| commodities | 13 | 38,5% | +3,11% | +4.049€ |
| real_estate_reit | 10 | 50,0% | +2,61% | +2.612€ |
| bond_governativi | 11 | 71,4% | +2,28% | +1.597€ |
| private_equity_buffer | 9 | 25,0% | -1,27% | -1.020€ |
| settoriali_difensivi | 14 | 27,3% | -1,27% | -1.395€ |
| leva_single_stock | 124* | 22,1% | -0,61% | -7.410€ |

*Trovato e scartato un dato corrotto su `3LAM.MI` (entry 0,13€→exit 25,58€, +19.147% su un
singolo trade — chiaramente un errore di dati, non un movimento di mercato reale) che da
solo falsava la media dell'intera famiglia a +101,9%/trade e P&L a +1,4M€. Numero sopra già
pulito. `leva_single_stock` resta negativo anche corretto, coerente col suo track record
già noto altrove in questo documento.

✅ **Verifica IN/OUT-of-sample fatta subito dopo, stesso giorno — nessuna delle 5 regge**:

| Famiglia | IN: N/WR/avg | OUT: N/WR/avg | Verdetto |
|---|---|---|---|
| bond_governativi | 7/100%/+4,94% | 4/**0%**/-4,45% | Ribaltamento completo |
| bond_corp_hy_em | 4/33%/-0,91% | 7/100%/+12,08% | N troppo piccolo entrambi i lati |
| real_estate_reit | 9/29%/-0,43% | 2/100%/+9,71% | N=2 fuori campione, rumore |
| commodities | 11/**0%**/-4,65% | 3/100%/+15,75% | In-sample già a 0% WR su 11 trade |
| crypto_digital_assets | 21/47%/+13,56% | 7/**0%**/-5,06% | Firma classica di overfitting (bene dentro, crolla fuori) |

Il numero aggregato "5 famiglie positive" su finestra unica era statisticamente fragile —
bastava dividere in IN/OUT perché ogni singolo caso si ribaltasse o si rivelasse rumore puro
(N troppo piccolo). **Conclusione finale: nessuna delle 8 famiglie bloccate merita uno
Shadow Monitor L0** — non per il motivo sbagliato di prima (bug, 0 segnali), ma per il
motivo giusto ora verificato (segnale non riproducibile fuori campione). Per
`crypto_digital_assets`/`commodities` questo conferma retroattivamente perché la whitelist
originale li escludeva (fallimenti reali durante bear market, coerenti con l'OOS negativo
qui). `bond_corp_hy_em` resta comunque coperta — meglio, con N=83/45 solido IN/OUT — dal
modello Bond-Trend dedicato (vedi sopra), non serve un secondo meccanismo L0 per la stessa
famiglia. Nessun nuovo Shadow Monitor costruito. Vedi
`memory/etf_family_viability_survey_2026_08_24.md` per il dettaglio completo.

### Punto di decisione successivo — AGGIORNATO dopo il test reale "smart 6/7 MACD" (vedi sotto, 2026-08-05)

Il test reale (non solo statistico) della variante "MACD obbligatorio anche a 6/7"
cambia il quadro: non è più solo "restare a 7 o aprire al 6 rumoroso" — c'è una terza
opzione concretamente migliore di entrambe sui dati a 3 anni (vedi tabella sotto).
Prima di renderla operativa in produzione, valutare comunque:

- **Rendere `smart_6_macd` la soglia di produzione** (sostituendo `min_buy_count=7` con
  "buy_count≥6 E macd_ok sempre vero") — l'opzione oggi meglio supportata dai dati, ma
  non ancora validata live, solo su backtest
- **Collegare il sistema "tiered" già scritto ma inutilizzato** (`check_l1_entry_tiered()`/
  `check_l1_entry_accelerated()`, quality score 0-4, sizing 50-100%) — resta un'alternativa,
  ma `smart_6_macd` è più semplice da implementare (una riga di condizione in più) e ha
  già un numero concreto dietro
- **Raffinare il modello di backtest con compensazione fiscale minus/plus** — utile comunque,
  ma meno urgente ora che anche senza quella raffinatezza `smart_6_macd` è nettamente
  profittevole in entrambe le size testate

### Fase 2 — Ipotesi filtro ADX su `min_buy_count=6`: TESTATA E RESPINTA (2026-08-05)

Un'analisi esterna aveva ipotizzato che un filtro ADX aggiuntivo su `min_buy_count=6`
avrebbe eliminato una quota rilevante di segnali falsi, specialmente nel 2024 (l'anno
negativo). Invece di implementarlo sulla fiducia, `backtest_l1.py` è stato esteso per
registrare, su ogni trade entrato esattamente a 6/7 nei 3 anni (469 trade), **quale**
delle 7 condizioni mancava.

**Distribuzione condizione mancante (469 trade, 6/7)**:

| Condizione | Trade | % |
|---|:---:|:---:|
| `macd_ok` | 344 | 73.3% |
| `rsi_ok` | 90 | 19.2% |
| `adx_ok` | 34 | 7.2% |
| `space_residuo_ok` | 1 | 0.2% |

**Per anno**:

| Anno | Trade | macd_ok | rsi_ok | adx_ok |
|---|:---:|:---:|:---:|:---:|
| 2023 | 19 | 14 (73.7%) | 5 (26.3%) | — |
| **2024** | 143 | 106 (**74.1%**) | 28 (19.6%) | 9 (**6.3%**) |
| 2025 | 159 | 121 (76.1%) | 27 (17.0%) | 11 (6.9%) |
| 2026 | 148 | 103 (69.6%) | 30 (20.3%) | 14 (9.5%) |

**Conclusione: ipotesi respinta.** `adx_ok` non è affatto la condizione mancante
dominante (7.2% sul totale) e **non è nemmeno leggermente sovrarappresentata nel 2024**
(6.3%, il valore più basso tra i 4 anni) — un filtro ADX aggiuntivo su
`min_buy_count=6` avrebbe scartato solo ~7% dei trade in modo pressoché uniforme su
tutti gli anni, senza correggere selettivamente il 2024. La condizione dominante ovunque
è `macd_ok` (~70-76% in ogni singolo anno, inclusi quelli buoni) — quindi nemmeno un
filtro MACD spiegherebbe perché il 2024 specificamente è stato negativo: il profilo
delle condizioni mancanti nei trade 6/7 del 2024 è statisticamente indistinguibile da
quello degli altri anni. Questo rafforza la decisione #7 sopra (l'edge di
`min_buy_count=6` è fragile/regime-dipendente) con un dato in più: la causa non è "entra
con un requisito debole in particolare" — è che il 2024 è stato un anno strutturalmente
sfavorevole per il tipo di setup che 6/7 cattura, non isolabile con un filtro sulle
condizioni d'ingresso già misurate. Prossimo esperimento sensato, se si vuole
continuare su questa strada: un indicatore di **regime di mercato** (es. VIX, ampiezza
di mercato) come filtro esterno, non un'altra soglia sulle 7 condizioni esistenti.

**Follow-up 2026-08-05 — segmentazione win rate per condizione mancante** (test proposto
dopo che un'analisi esterna ipotizzava "il 73% dei fallimenti è causato dal MACD" —
un'affermazione che il dato sopra NON supporta di per sé, perché misura solo la
*frequenza* con cui una condizione manca, non se quei trade vanno peggio. Va misurato
separatamente, ed è quello che segue):

| Condizione mancante | Trade | Win rate netto | Rend. medio netto | P&L netto totale (10k€/trade) |
|---|:---:|:---:|:---:|:---:|
| `macd_ok` | 340 | 44.1% | -0.01% | -428€ |
| `rsi_ok` | 86 | 50.0% | +0.04% | +372€ |
| `adx_ok` | 33 | **57.6%** | **+0.33%** | **+1.099€** |

**C'è un effetto reale**: i trade dove manca il MACD sono i peggiori (44.1% win rate),
quelli dove manca l'ADX i migliori (57.6%) — l'ipotesi esterna "MACD obbligatorio anche
a 6/7" non è campata in aria, ha un fondamento nei dati.

**Ma non spiega il 2024 specificamente**: `macd_ok` mancante nel 2024 ha win rate 35.8%
(peggio della media 2024 di 37.1%, ma di poco) — e i trade 2024 dove mancava invece RSI
o ADX (37 trade, per differenza) sommano comunque **-3.559€ netti**, ancora chiaramente
in perdita. Un filtro "MACD obbligatorio" avrebbe tolto qualche trade cattivo ovunque
(migliora la qualità media in generale), ma il 2024 sarebbe rimasto un anno negativo
anche depurato dai trade con MACD mancante. Conferma quanto scritto sopra: la causa del
2024 è di regime di mercato, non isolabile scegliendo quale condizione rendere
obbligatoria.

**Nota laterale utile**: escludendo `leva_single_stock` (già fuori da L1 in produzione,
`min_buy_count=8`) il bucket `macd_ok` mancante passa da -428€ a **+4.804€** netti —
la famiglia leva pesava sproporzionatamente in quel gruppo. Conferma indiretta che
l'esclusione già fatta di `leva_single_stock` è stata la mossa con più impatto reale
finora, più della caccia a una condizione specifica da rendere obbligatoria.

**Conclusione**: rendere `macd_ok` obbligatorio anche a 6/7 è un filtro di qualità
generico ragionevole da testare con una simulazione vera (non solo questo replay
statistico) se si vuole aumentare il volume oltre il 7/7 rigido — ma va presentato come
tale, non come soluzione mirata al 2024. La "conferma 2gg consecutivi" e il "filtro di
regime macro" restano ipotesi non testate a questo punto.

### Fase 2 — Test REALE "smart 6/7 MACD obbligatorio": risultato forte (2026-08-05)

A differenza del replay statistico sopra (segmentazione post-hoc su trade già simulati),
questo è un backtest vero: nuova variante `smart_6_macd` in `backtest_l1.py`, stessa
soglia `min_buy_count=6` ma con vincolo aggiuntivo che `macd_ok` sia SEMPRE tra le
condizioni vere (la condizione che può mancare dev'essere un'altra). Stesso storico a
3 anni (2023-08→2026-08), stesso universo (236 ETF, 13 famiglie), stesso modello di
uscita (solo SL/TP giornalieri).

| | `native_7` | `override_6` (6/7 puro) | `smart_6_macd` |
|---|:---:|:---:|:---:|
| Trade totali | 3 | 469 | **151** |
| Win rate netto | 100% | 46.1-46.3% | **54.4%** |
| Rendimento medio netto/trade | +5.17/+5.24% | -0.06%/+0.03% | **+0.35%/+0.44%** |
| P&L netto 5.000€/trade | +775€ | **-1.304€** | **+2.599€** |
| P&L netto 10.000€/trade | +1.572€ | +1.442€ | **+6.460€** |

**Risultato netto**: `smart_6_macd` batte entrambe le alternative su tutti i fronti che
contano:
- **4-4.5x più P&L netto** di `native_7` (10k€: +6.460€ vs +1.572€) pur restando molto
  più selettivo di `override_6` puro (151 trade contro 469, il 32% del volume)
- **Ribalta il segno a 5.000€/trade**: `override_6` puro è in perdita netta (-1.304€),
  `smart_6_macd` è solidamente in profitto (+2.599€) — il filtro non solo migliora la
  media, cambia la conclusione operativa
- **Win rate +8 punti** sopra `override_6` puro (54.4% vs 46.1-46.3%), pur restando
  sotto il 100% (irripetibile) di `native_7`
- Il filtro rimuove esattamente 318 dei 469 trade 6/7 (quelli dove mancava il MACD,
  vedi segmentazione sopra) — coerente: elimina il gruppo peggiore, tiene quello buono

**Implicazione per la roadmap**: questo è il miglior candidato oggi per sostituire
`min_buy_count=7` in produzione — ma resta **solo backtest**, non ancora validato live.
Vedi "Punto di decisione successivo" sopra per i prossimi passi prima di renderlo
operativo.

---

## PAC — confronto con portafoglio attivo (2026-08-24)

Feature reale (non backtest) nata dallo stesso confronto PAC-vs-attivo che ha motivato la
promozione di `smart_6_macd` (vedi sopra). L'utente vuole verificare nella realtà, con
soldi veri, se un PAC passivo su un paniere diversificato batte il portafoglio attivo del
sistema — stessa domanda del backtest, ma tracciata live invece che simulata.

**Paniere scelto**: solo `VWCE.DE` (Vanguard FTSE All-World, ISIN `IE00BK5BQT80`) — un solo
ETF, deliberatamente, perché il punto del PAC è azzerare le decisioni. Era già
nell'universo monitorato (nessuna aggiunta necessaria).

**Disciplina di esecuzione — stessa filosofia "nessun automatismo" di tutto il resto**:
l'utente esegue davvero l'acquisto su Directa **lo stesso giorno fisso di ogni mese**
(mai "il minimo del mese" — non è conoscibile in anticipo, e cercarlo reintrodurrebbe
esattamente il market-timing che il PAC è pensato per eliminare), poi registra il
versamento a mano nella nuova pagina. Il sistema non piazza né simula alcun ordine.

**Implementazione**:
- `migrations/006_add_pac_contributions.sql` — tabella `etf_pac_contributions` (isin,
  ticker, data, importo, prezzo, quote, broker), `UNIQUE(isin, contribution_date)` evita
  doppioni sullo stesso mese.
- `database.py`: `add_pac_contribution()` / `get_pac_contributions()` /
  `remove_pac_contribution()`. `get_portfolio_entries()` ora seleziona anche la colonna
  `shares` (mancava — serviva per calcolare il capitale investito reale nel confronto,
  aggiunta additiva, nessun impatto sui chiamanti esistenti).
- `app.py`: `GET/POST /api/pac`, `DELETE /api/pac/<id>` — la GET calcola sia le posizioni
  PAC aggregate (quote totali, costo medio, valore attuale) sia il confronto diretto con
  il portafoglio attivo reale (`etf_portfolio_entries` status='active', capitale versato
  vs valore attuale, stesso principio del backtest ma su dati veri).
- `templates/pac.html` — nuova pagina `/pac`, link "💰 PAC" aggiunto alla nav bar di
  `dashboard.html`. Form di registrazione versamento, tabella posizioni, storico
  versamenti, due card affiancate PAC vs Attivo con il rendimento % a confronto.

Verificato end-to-end (POST/GET/DELETE) con un versamento di prova, poi rimosso (non era
un acquisto reale). Deployato via `./deploy.sh`.

**Aggiornamento stesso giorno — confronto a tre vie con frecce**: su richiesta, il
confronto non è più "PAC vs Attivo" unico ma **tre sleeve separate** (PAC, L1, L0), lette
da `portfolio_type` in `etf_portfolio_entries`. Ogni card mostra una freccia (🔼 dove
pesare di più, 🔽 dove pesare di meno, ➡️ differenza minima o campione troppo piccolo) —
la freccia scatta solo se lo scarto tra la migliore e la peggiore è ≥3 punti percentuali
**e** tutte le sleeve coinvolte hanno almeno 3 posizioni/versamenti, altrimenti resta
neutra di proposito (stessa cautela già discussa sul non reagire a un campione piccolo
tipo "6 mesi, 2 trade").

**Prima esecuzione reale (2026-08-24) — commissione reale ≠ commissione da backtest**: il
primo versamento PAC vero (6 quote `VWCE.DE` su Xetra, ordine a mercato piazzato su
Directa) ha mostrato una commissione di **9,50€**, quasi doppia dei 5€ assunti in tutti i
backtest del sistema (verosimilmente un sovrapprezzo per mercato estero rispetto alla
Borsa Italiana, dove sono MEU/PHAG). Senza tenerne conto, il PAC sarebbe risultato
otticamente migliore di quanto sia davvero nel confronto con L1/L0 — l'errore opposto a
quello già corretto nei backtest (che includono sempre i costi).

- `migrations/007_add_pac_fee_column.sql` — colonna `fee_eur NUMERIC(8,2) DEFAULT 0` su
  `etf_pac_contributions`.
- `database.py::add_pac_contribution()` — nuovo parametro `fee_eur: float = 0.0`.
- `app.py`: `total_amount` (capitale investito PAC) ora = controvalore quote + commissioni
  pagate; nuovo campo `total_fees` per posizione; validazione `fee_eur >= 0` in POST.
- `templates/pac.html` — campo "Commissione (€)" nel form (default 9,50, il valore reale
  osservato), colonna commissione in tabella posizioni e storico versamenti.

**Bug reale trovato e corretto lo stesso giorno — confronto ignorava le posizioni chiuse**:
il confronto L1/L0 leggeva solo `etf_portfolio_entries` con `status='active'`
(`get_portfolio_entries()`, filtro SQL). Quando una posizione L1/L0 usciva (vendita reale
registrata in dashboard Portafoglio con "Esci"), spariva del tutto dal confronto PAC — il
guadagno/perdita realizzato non veniva mai conteggiato. Nel tempo questo avrebbe reso il
confronto sempre più ingannevole: solo le posizioni aperte in quel preciso momento
avrebbero contato, perdendo tutta la storia dei trade già chiusi (effetto survivorship).
Fix: `database.py::get_exited_portfolio_entries()` (nuovo, legge `status='exited' AND
exit_price IS NOT NULL`) + `app.py::get_pac()` somma alle sleeve `shares × entry_price`
(investito) e `shares × exit_price` (valore) anche per le posizioni chiuse, con lo stesso
peso delle posizioni aperte (`shares × prezzo attuale`). Nessuna azione utente nuova
richiesta: le uscite si registrano esattamente come prima (pagina Portafoglio → "Esci"),
il confronto le include automaticamente da ora in poi.

---

## Infrastruttura Tecnica

### VPS & Percorsi
- **Provider:** Hostinger Ubuntu 24.04 LTS
- **IP:** `76.13.37.133` | **SSH:** `ssh root@76.13.37.133`
- **Dashboards:** https://etf.andreapavan.tech
- **Container:** `etf_monitor_system-app-1` → porta 5001
- **Git remote:** `git@github-pimpy67:pimpy67/etf-monitor-system.git`

### Database PostgreSQL
- **Container:** `etf_monitor_system-postgres-1`
- **Credenziali:** user `etfmonitor`, db `etfs`
- **Tabelle:** price_history, l1_tracking, l0_tracking, l1_exit_history, portfolio_entries

### File Principali
| File | Ruolo |
|------|-------|
| `app.py` | Flask API + dashboard |
| `monitor.py` | Fetch prezzi, calcolo L0/L1/L2/L3, aggiorna Excel |
| `technical_analysis.py` | Indicatori (EMA, RSI, ADX, MACD), logiche L0/L1 |
| `pdf_generator.py` | **Genera PDF parametri automaticamente dal YAML** |
| `config/etf_families.yaml` | **FONTE DI VERITÀ** — contiene tutti i parametri |
| `etf_monitoraggio.xlsx` | Lista ETF — fonte di verità ticker/categoria |
| `dashboard.html` | Frontend con tab "Parametri di Riferimento" |

### Monitor Quotidiano
```
scheduler.py (17:00 + 09:00 lun-ven)
  ├─ monitor.py
  ├─ Fetch prezzi Yahoo Finance
  ├─ Calcola indicatori
  ├─ Determina L0/L1/L2/L3
  ├─ Aggiorna Excel
  ├─ pdf_generator.py → PDF sincronizzato
  ├─ alerts.py → email
  └─ log in data/dashboard_data.json
```

### Comandi Rapidi VPS

```bash
# Log live
ssh root@76.13.37.133 "docker logs etf_monitor_system-app-1 --tail=30 -f"

# Trigger monitor manuale
ssh root@76.13.37.133 "curl -X POST http://localhost:5001/api/trigger-update"

# Query DB
ssh root@76.13.37.133 "docker exec etf_monitor_system-postgres-1 psql -U etfmonitor -d etfs -c 'SELECT * FROM etf_l1_tracking;'"
```

### Deploy
```bash
./deploy.sh
```
Fa: git push → git reset VPS → docker build → docker up

---

## Note Operative

- **Dopo `docker cp` su file `.py`: sempre `docker restart etf_monitor_system-app-1`**
- Il monitor modifica `etf_monitoraggio.xlsx` in-place — `deploy.sh` lo salva prima di `git reset --hard`
- Ticker Yahoo Finance: formato `SWDA.L`, `ENRJ.PA`, `XEON.DE`
- **240 ETF monitorati** (aggiornato 2026-07-22)
- Email resend: `onboarding@resend.dev` → `andreapavan67@gmail.com`
- **Backtest storici**: usare `backtest_l1.py` (nel repo) come base — fetcha da Yahoo Finance
  direttamente (non dal DB, il cui storico pre-fix ha ancora righe Open/High/Low NULL) e usa
  `calculate_sl_suggerito_l1`/`calculate_stop_gain_dynamic` per le uscite (le uniche due
  funzioni reali, `check_l1_exit()` è stata rimossa il 2026-08-05 perché dead code), non la
  logica di `suggest_level()` (vedi sopra perché sono diverse). Fetch fresco è necessario
  anche perché il DB storico va "auto-risanandosi" solo giorno per giorno da oggi in poi.

### Sessione fix 2026-08-04 (riassunto)
- Fix bug `suggested` non assegnato quando un ETF raggiungeva 7/7 (mai accaduto prima, quindi
  mai emerso) + disaccoppiamento regime da `allineamento_ok`
- Step 4: persistenza 5→3 (equity_sviluppati, settoriali_growth, settoriali_difensivi), tetto
  RSI alzato (equity_sviluppati 55→58, mercati_emergenti 52→58, settoriali_growth 58→60),
  spazio residuo →2.5% su 6 famiglie
- Fix DB: `save_close_bulk()`/`get_close_by_isin()` scartavano Open/High/Low/Volume per gli
  ETF con ISIN dal secondo run del giorno in poi → nuovo `get_ohlc_by_isin()` usato dal
  fast-path del monitor; `save_ohlcv_bulk()` usato anche per gli ETF con ISIN
- Fix Regola E (ADX debole) mai attiva + Regola C sempre attiva sui bond in dashboard +
  Stop Gain dinamico di fatto statico (vedi sezione "L1 — Come Si Esce" sopra)

### Sessione fix 2026-08-05 (riassunto) — L0 + email + bug portafoglio

**L0 (stessa filosofia già applicata a L1)**:
- FAST/SLOW ora richiedono conferma di recupero prima di entrare (vedi "L0 — Come Si Entra")
- Rimossa la promozione automatica L0→L2 su prezzo>EMA20 (γ) — resta L0 finché non perde i
  requisiti (vedi "L0 — Come Si Esce")
- Aggiunto Take Profit per L0 (`l0_take_profit_pct`, mancava — c'era solo SL)
- Portafoglio reale L0: uscita ora solo SL/TP (rimossa `check_l0_exit()`, stessa
  contraddizione già risolta su L1 — kill switch/bear trap/stop assoluto/timeout non sono
  vendite reali)

**Bug portafoglio reale (trovati indagando "perché non arrivano le email")**:
- `etf_portfolio_entries` aveva **due colonne** per L0/L1 (`portafoglio` letta dal monitor,
  `portfolio_type` scritta da dashboard) mai sincronizzate — un ETF aggiunto come L0 da
  dashboard veniva elaborato dal monitor con la logica SL/TP di L1. Fix: `add_portfolio_entry()`
  scrive entrambe; riga esistente corretta con UPDATE una tantum su produzione.
- `get_portfolio_entries()` non filtrava per `status` — la dashboard mostrava posizioni
  chiuse da settimane come se fossero ancora attive (da qui la convinzione errata che il
  portafoglio non fosse vuoto). Fix: filtro `WHERE status='active'`.
- Verificato che 4 delle 5 posizioni L1 storiche erano state chiuse con `exit_rule='B_trailing'`
  (regola dashboard-only, non un vero tocco di SL/TP) — uscite premature dal bug pre-fix.

**Email**:
- Il resoconto portafoglio veniva inviato PRIMA del ricalcolo giornaliero di SL/TP (mostrava
  sempre i valori di ieri) — spostato dopo gli STEP 4/7 in `monitor.py::run()`
- Rimosso il secondo invio duplicato alle 17:30 UTC (era un workaround per il bug sopra,
  ora inutile — resta solo l'invio delle 17:00 UTC / 19:00 CEST)

### Sessione fix 2026-08-06 (riassunto) — mm200 filter, L0 safety gates, sync doc

**L1**:
- `mm200_distance_max` aggiunto alla condizione 1 (Allineamento) — vedi "L1 — Come Si
  Entra" sopra. Motivato da Feature Extraction (gap −3.38pp tra vincenti/perdenti sulla
  distanza da SMA200) e confermato da A/B test reale (+€327 P&L, +2pp WR su 3 anni).
  Valore per famiglia: 0.4% (monetario) → 4.8% (crypto). Commit `2deb026`.
- Fix bug inizializzazione `smart_6_7_macd_enabled`/`smart_6_7_triggered` (usate prima di
  essere definite, `UnboundLocalError`) — commit `b7bf282`. Riguarda solo la variante
  sperimentale `smart_6_7_macd` (oggi `use_smart_6_7_macd: false` su tutte le 14 famiglie
  nel YAML, quindi non attiva in produzione), non il gate nativo a 7 condizioni.
- `sync_l1_portfolio.py` (nuovo): sincronizza automaticamente dashboard→portafoglio per le
  posizioni L1 che raggiungono 7/7+fondamenta. Commit `a10a59e`.

**L0**:
- Whitelist ristretta a `equity_sviluppati` soltanto + gate di regime BULL su tutti e 3 i
  percorsi d'ingresso — vedi "L0 — Come Si Entra" sopra per dettagli e numeri di
  validazione. Commit `e81ae75`.
- Fix `send_portfolio_report()` in `alerts.py`: un blocco `except` orfano impediva l'invio,
  email portafoglio silenziosamente non partivano.
- Cleanup DB: rimosse 24 entry `l0_tracking` legacy precedenti al regime filter
  (2026-07-30), non più coerenti con le regole attuali. Commit `b215639`.

**Documentazione**: ampia batch di file `.md` aggiunti in root e `memory/` (deployment
report, roadmap, guida investimento, session log) — non tutti riconciliati fra loro, vedi
nota sotto.

> ⚠️ **Discrepanza aperta — spiegazione "bug" verificata e ESCLUSA (2026-08-06)**:
> `memory/SESSION_2026_08_06_AB_TEST_DEPLOYMENT.md` e `DEPLOYMENT_REPORT_20260806_FINAL.md`
> riportano un backtest nativo 7/7 a 3 anni con **80 trade, 60% win rate, €7.177 netto**
> (usato come baseline per giustificare `mm200_distance_max`) — un risultato radicalmente
> diverso dai **3 trade, 100% win rate** documentati il giorno prima (2026-08-05, sezione
> "Stato Attuale & Roadmap L1" sotto), stesso identico gate (`min_buy_count=7`, stesso
> storico 3 anni, stesso `backtest_l1.py` che chiama `analyzer.suggest_level()` — non è un
> motore di backtest separato).
>
> `SESSION_2026_08_06_AB_TEST_DEPLOYMENT.md` attribuisce il vecchio risultato (3 trade) a un
> "bug che bloccava il 98% dei segnali" (Fase 1 → "FAKE"), riferendosi al fix
> `b7bf282` (`UnboundLocalError` su `smart_6_7_macd_enabled`/`smart_6_7_triggered`,
> referenziate nel dict `conditions` prima di essere assegnate). **Cronologia verificata,
> spiegazione incompatibile:**
> - Il risultato "3 trade" è documentato nel commit `3bdb52e` delle **04:07** del 06/08,
>   relativo a un backtest eseguito il **05/08** — un giorno intero prima.
> - Il codice `smart_6_7_macd` (le variabili che causano il bug) è stato introdotto solo
>   con `59db2d2` delle **09:55** del 06/08 — quel codice, e quindi il bug, **non esisteva
>   ancora** quando il risultato "3 trade" è stato calcolato. Non può averlo causato.
> - Anche ignorando i tempi: `backtest_l1.py:113-114` chiama `analyzer.suggest_level()`
>   **senza alcun try/except**. Le due variabili vengono referenziate nel dict `conditions`
>   ad ogni chiamata, indipendentemente dal flag `use_smart_6_7_macd` — quindi se il bug
>   fosse stato davvero attivo durante un run, lo script sarebbe **crashato immediatamente
>   al primo ETF processato**, non avrebbe prodotto un esito pulito di 3 trade completi con
>   100% win rate. Un bug che "blocca il 98% dei segnali" lasciandone passare 3 puliti non è
>   il comportamento di un'eccezione non gestita.
>
> **Conclusione (2026-08-06)**: la spiegazione data per gli 80 trade non regge. Da dove venga
> quel numero resta ignoto — possibile un run con parametri, universo o storico diversi mai
> documentati, o un valore non derivato da un'esecuzione reale dello script.

> ✅ **RISOLTO — causa reale identificata (2026-08-07)**: rilanciato `backtest_l1.py` sul
> commit esatto `3bdb52e` (stesso codice, stessi parametri `--start 2023-08-05`, stesso
> universo di 236 ETF del run del 05/08 che aveva prodotto i 3 trade), in un worktree git
> isolato copiato dentro il container per non toccare `/app` in produzione. **Risultato: 1
> trade solo** (`WLDC.PA`, +5.19% lordo/+3.77% netto, 54gg) — `CEC.PA` e `LGQM.DE` (gli altri
> due trade del 05/08) risultano oggi entrambi `native_7: 0 trade`, senza alcun errore di
> fetch: vengono scaricati e analizzati normalmente, semplicemente non soddisfano più le 7
> condizioni sui dati odierni.
>
> **Causa**: `backtest_l1.py` non legge da uno storico congelato — ad ogni esecuzione
> riscarica OHLCV **live da Yahoo Finance** via `yfinance`. Yahoo rivede retroattivamente gli
> adjusted close (dividendi, split, ricalcoli), e la finestra "fino a oggi" si sposta di
> qualche giorno a ogni run: bastano micro-variazioni su un valore storico borderline (es.
> ADX a 22.01 che diventa 21.98) per far scattare o non scattare una condizione delle 7, e
> quindi l'intero trade, da un giorno all'altro. **Stesso identico codice + stessi parametri
> + 2 soli giorni di differenza tra i due run → 3 trade vs 1 trade.** Questo conferma che
> `backtest_l1.py` **non è riproducibile run-to-run** con lo stato attuale (fetch live), a
> prescindere dal codice — quindi confrontare conteggi di trade fatti in giorni diversi (3 vs
> 80 vs 1) non è mai stato un confronto valido like-for-like. Non prova che 80 fosse
> "corretto", ma esclude definitivamente sia il bug `regime_ok`/`smart_6_7_macd` (già escluso
> il 06/08 per cronologia) sia qualunque altra spiegazione basata sul codice: il rumore viene
> dai dati sorgente, non dalla logica.
>
> **Implicazione pratica**: nessun numero di trade/P&L da un singolo run di `backtest_l1.py`
> va più trattato come definitivo finché lo script continua a rifetchare dati live — vale per
> tutti i risultati storici citati in questo documento (3, 469, 151, 80, 1...), non solo per
> l'80. Per backtest scientificamente ripetibili servirebbe uno storico OHLCV congelato
> (snapshot fisso, es. su tabella Postgres o file locale) da cui il backtest legge sempre gli
> stessi dati, lasciando il fetch live solo al monitor giornaliero (che necessita solo
> dell'ultima candela).
>
> ✅ **IMPLEMENTATO (2026-08-07)**: `etf_price_history_frozen` (migration `002`), popolata da
> `freeze_historical_dataset.py` (229/236 ticker, 219.268 righe, 2022-02-15→2026-08-07, batch
> `'2026-08-07'`). `backtest_l1.py` ora legge da lì **di default** (`FrozenDataFetcher`), con
> `--live` per il vecchio comportamento fetch-live quando serve. `database.py`:
> `save_frozen_ohlcv_bulk()` / `get_frozen_ohlcv()`.
>
> **BASELINE_OFFICIAL_20260807** (native_7, `--start 2023-08-05`, batch congelato
> `2026-08-07`, codice HEAD di oggi = con fix `regime_ok` + filtro `mm200_distance_max`):
> **1 trade** — `WLDC.PA` (equity_sviluppati), entry 2025-08-15 @15.606, exit TP 2025-10-08
> @16.416, 54gg, +5.19% lordo. Netto: 5.000€/trade → +3.69% (+184,64€); 10.000€/trade →
> +3.77% (+376,68€). Win rate 100% (su 1 trade — non conclusivo, resta il problema di sempre:
> il gate 7/7 nativo è estremamente selettivo). Questo è ora il numero di riferimento per
> qualunque confronto futuro sullo stesso codice — riproducibile all'infinito finché si usa
> lo stesso `--frozen-batch`. Non è direttamente confrontabile con i 3 trade del 05/08 o gli
> 80 mai spiegati: quelli usavano codice precedente (senza `mm200_distance_max`) e dati non
> congelati.
>
> **Gap noto**: questo run ha usato l'universo Excel di **prima** degli ultimi 3 fix ticker
> (`USHYC`→`USHYC.MI`, `PHAU.MI`→`PHAU.L`, `3LMS.MI`→`3LMS.L`, vedi sotto) — quei 3 ticker
> compaiono ancora come "storico insufficiente" nel run. Impatto atteso trascurabile (erano
> già a 0 trade in ogni versione precedente), ma non riverificato. Un rerun con l'universo
> pienamente aggiornato non è ancora stato fatto.

### 🔴 FIX CRITICO 2026-08-07 — whitelist/blacklist L0 non è mai stata attiva

**Scoperto indagando un'anomalia nel nuovo progetto L0** (vedi sezione sotto), non durante
un controllo di sicurezza dedicato — buona ragione per prendere sul serio le anomalie anche
quando sembrano solo un dettaglio del backtest.

`global_params` è una chiave YAML di **primo livello** (sorella di `families:`, non annidata
dentro nessuna famiglia). Ma `self.p` (riga ~105 di `technical_analysis.py`, in `__init__`)
viene assegnato **solo** al sotto-dizionario della singola famiglia
(`_FAMILIES_CONFIG['families'][famiglia]`) — non contiene mai `global_params`. Di
conseguenza `self.p.get('global_params', {})` dentro `suggest_level_0()` ha **sempre**
restituito `{}` per qualunque famiglia, quindi `l0_whitelist`/`l0_blacklist` erano **sempre**
liste vuote, e il controllo whitelist introdotto dal commit `e81ae75` (06/08) per
restringere L0 a `equity_sviluppati` (vedi sopra "L0 — Come Si Entra") **non ha mai
funzionato realmente**, nonostante fosse documentato in questo stesso file come attivo dal
06/08.

**Confermato con dati di produzione al momento della scoperta**: dashboard con **6 ETF
classificati L0, zero `equity_sviluppati`** — `IUSB.DE` (leva_single_stock), `COMH.MI`
(commodities), `LHKG.DE`/`ASI.PA`/`INDO.PA` (mercati_emergenti), `PHAU.L`
(oro_metalli_preziosi). Esattamente il tipo di ingresso speculativo che la whitelist doveva
prevenire (motivazione originale del 06/08: fallimenti L0 su INRG/BATE/BTCN durante bear
market strutturali) — probabilmente accaduto in silenzio per tutto il mese. Nessuna
posizione reale del portafoglio coinvolta (verificato contro `etf_portfolio_entries`).

**Fix**: legge `global_params` da `self._FAMILIES_CONFIG` (config di classe, condivisa) invece
che da `self.p`. Verificato: `mercati_emergenti` ora blocca correttamente
(`L0_DISABLED_NOT_IN_WHITELIST`), `equity_sviluppati` valuta le condizioni normalmente. Dopo
il deploy: L0 sceso da 6 a **0** (nessun `equity_sviluppati` soddisfa le condizioni in
questo momento — corretto, non un effetto collaterale). Commit `600f51b`.

### Bug minori di classificazione trovati nello stesso giro (`family_detection`)

- `'Obbligazionari Governo'`/`'Obbligazionari Corporate'` (categorie Excel reali, **senza
  trattino**) non matchavano i pattern esistenti (`'obbligazionari - governativi'`/
  `'- corporate'`, **con trattino**) → 2 ETF governativi + 1 corporate cadevano nel default
  `equity_sviluppati`, con soglie RSI/ADX/`mm200_distance_max` sbagliate per un bond.
- `'Liquidità'` (con accento) non matchava `'liquidita'` (senza accento) come substring →
  stesso problema per 1 ETF di liquidità. Fix: aggiunto pattern `'liquidit'` (sicuro in
  entrambi i casi).
- `'Azionari Alternativi'` (**`LVO.MI`**, *Amundi S&P 500 VIX Futures Enhanced Roll UCITS
  ETF*) cadeva nello stesso default. Non è un ETF azionario normale: un prodotto sui futures
  VIX decade strutturalmente per contango (-82% in 4 anni nello storico, giornate di ±15-17%)
  e non risponde a mean-reversion/trend-following classico — generava 25 trade spuri nel
  backtest L0 di oggi contro 0-8 di ogni altro ticker. Riclassificato `leva_single_stock`:
  automaticamente escluso da L0 (blacklist, ora davvero attiva — vedi sopra) e soglie L1 più
  adatte all'alta volatilità. Commit `564de92`.

### Grid Search `smart_6_macd` — pilota 2026-08-07 (`optimize_hyperparameters.py`)

**Obiettivo**: trovare parametri ottimali per L1 su `smart_6_macd` (non `native_7`, troppo
raro — vedi baseline sopra) via sensitivity analysis, con split In-Sample/Out-of-Sample per
evitare overfitting temporale, su 3 cluster raggruppati per `sl_initial_pct` reale (non nomi
di famiglia arbitrari — vedi tabella sotto) per portare N a livelli statisticamente utili.

**Infrastruttura costruita** (tutta committata, `202db3f`/`509b4d3`):
- `technical_analysis.py::suggest_level()` — nuovo parametro opzionale `precomputed` per
  ricevere EMA/SMA/RSI/ADX/MACD/ATR già calcolati invece di ricalcolarli da zero a ogni
  giorno del walk-forward (era il costo O(n²) per ticker dominante). Stesso comportamento
  identico quando `precomputed=None` (default), zero rischio per i chiamanti esistenti.
- `backtest_l1.py::simulate()` — `precomputed_full` (taglia le serie precalcolate giorno per
  giorno) + `macd_skip_mask` (skip certo, non euristico: quando `require_macd=True`, `macd_ok`
  è obbligatorio, quindi nei giorni in cui è già falso l'ingresso è impossibile a prescindere
  dalle altre 6 condizioni — salta la chiamata a `suggest_level()` invece di scartarne il
  risultato dopo). `redirect_stdout` aperto una volta sola fuori dal loop invece che a ogni
  giorno.
- **Validazione incrociata obbligatoria PRIMA di fidarsi dei numeri** (`--validate`): (1) motore
  veloce vs originale, 480 check, 0 discrepanze; (2) `simulate()` con vs senza `macd_skip_mask`,
  liste di trade identiche. Entrambe PASS.
- **Multiprocessing scartato**: la VPS ha **1 solo vCPU** (verificato con `nproc`), quindi
  parallelizzare per core non dà alcun guadagno qui — anzi rischierebbe di far competere per
  RAM (3.8GB totali, spesso <200MB liberi con Postgres+Flask già attivi) con la produzione
  live sulla stessa macchina. L'unica leva reale su singolo core è ridurre il lavoro totale
  (skip-mask), non distribuirlo.

**Cluster per volatilità reale** (criterio: `sl_initial_pct` dallo YAML, non nomi):

| Cluster | Famiglie | sl_initial_pct | N ticker |
|---|---|---|---|
| difensivo | bond_governativi, bond_corp_hy_em, settoriali_difensivi, real_estate_reit, private_equity_buffer | 2.5–4.0% | 58 |
| core | equity_sviluppati, oro_metalli_preziosi, mercati_emergenti, settoriali_growth, metalli_industriali | 5.0–6.0% | 153 |
| speculativo | commodities, leva_single_stock, crypto_digital_assets | 7.0–12.0% | 16 |

**Griglia pilota**: `mm200_delta` ∈ {-1.0, 0.0, +1.0} × `adx_delta` ∈ {-4, 0, +4} = 9 combinazioni
per cluster (27 totali), applicate come **delta sulla baseline di ciascuna famiglia**, non
come valore assoluto condiviso. Split: In-Sample 2023-08-05→2025-08-05, Out-of-Sample
2025-08-05→2026-08-05. **Tempo reale: 90.5 minuti** (core ~400s/combo, difensivo ~155s/combo,
speculativo ~45s/combo — proporzionale al numero di ticker, non c'è overhead nascosto).

**Risultato — nessuna combinazione ha raggiunto N≥30 in-sample, in nessun cluster:**

| Cluster | N in-sample (range sulle 9 combo) | Note |
|---|---|---|
| core | 6–22 | Unico cluster con segnale, ma sotto soglia |
| speculativo | **0 su tutte e 9 le combinazioni** | Nessun trade `smart_6_macd`, mai |
| difensivo | 2–3 | **Win rate in-sample 0% su ogni singola combinazione** — ogni trade perdente |

✅ **Discrepanza 26 vs 151 RISOLTA (2026-08-07, stessa sera)**: sommando tutti i cluster alla
combinazione base si ottengono ~26 trade totali contro i 151 del run 05/08 — diff-debug
mirato su `CHIP.MI` (4 trade `smart_6_macd` nel run originale) isola la causa in modo netto:
`backtest_l1.py` originale invariato e il motore ottimizzato di `optimize_hyperparameters.py`
danno **entrambi 0 trade** su CHIP.MI con il codice di oggi (confermando che il motore dello
sweep è corretto, nessun bug) — ma **disattivando `mm200_distance_max`** (settato a 999)
tornano **esattamente i 4 trade originali**, stesse date. Causa: `mm200_distance_max`
(aggiunto il 06/08, commit `2deb026`, **dopo** il run da 151 trade) taglia sistematicamente
gli ingressi troppo estesi sopra SMA200 — per `equity_sviluppati` la soglia e' 3.0%, e
TUTTI e 4 i trade storici di CHIP.MI la superavano. Stessa dinamica già vista su `native_7`
(3→1 trade), qui semplicemente più marcata. Non un bug: codice cambiato tra le due misure.
**Implicazione per la griglia**: `mm200_distance_max` è la leva dominante dello sweep, non
una minore — il pilota lo faceva variare solo di ±1pp attorno alla baseline (troppo stretto
quando la baseline stessa può azzerare tutti i trade). Un prossimo pilota deve usare un range
molto più ampio su questo parametro specifico (es. 3–10%, non baseline±1).

### Grid Search `smart_6_macd` — sweep ampio 2026-08-07 (`--wide`), risultati

Rilanciato con `mm200_distance_max` **assoluto** ∈ {3%, 5%, 7%, 9%, OFF} (non più delta ±1pp
sulla baseline) × `adx_entry` delta ∈ {-4, 0, +4} — 15 combinazioni/cluster, 45 totali,
**44.9 minuti** (motore con skip-mask MACD attivo, ~3.3x più veloce del pilota precedente,
confermato: `speculativo` 44s→13s/combo).

**Core (153 ticker) — unico cluster con segnale utilizzabile**, 5 combinazioni superano N≥30
in-sample:

| mm200 | adxΔ | IN: N / PF / WR | OUT: N / PF / WR | Nota |
|---|---|---|---|---|
| **7.0%** | **-4** | 33 / 1.18 / 57.6% | 25 / **1.65** / **68.0%** | Out-of-sample **migliora** l'in-sample — opposto dell'overfitting, il candidato migliore |
| OFF | +4 | 39 / 1.25 / 56.4% | 57 / 1.23 / 54.4% | PF quasi identico nei due periodi, molto stabile |
| 9.0% | -4 | 41 / 0.99 / 51.2% | 30 / 1.61 / 66.7% | In-sample sostanzialmente in pareggio (PF<1), il buon OOS è sospetto |
| OFF | -4 | 89 / 0.92 / 48.3% | 103 / 1.18 / 53.4% | N enorme ma PF appena sopra 1 in entrambi i periodi |
| OFF | +0 | 57 / 0.92 / 49.1% | 76 / 1.45 / 59.2% | Simile al precedente |

**Candidate Entry Zone per `core`**: `mm200_distance_max=7.0%, adx_entry` baseline-4 —
migliore combinazione rischio/robustezza (l'unica dove l'anno nascosto è andato meglio
dell'in-sample, non peggio), anche se N=25 out-of-sample resta appena sotto la soglia di
30 presa come riferimento. `mm200=OFF, adxΔ=+4` è l'alternativa più prudente (N più alto,
comportamento quasi identico nei due periodi). **Non ancora promosso in produzione** —
resta un candidato da backtest, il sistema live è in lockdown parametri fino al 06/09/2026.

**Difensivo (58 ticker)**: anche con `mm200_distance_max` completamente disattivato, N
massimo resta 9 e il win rate in-sample è 0–33% su quasi tutte le combinazioni. Non è un
problema di `mm200_distance_max` per questo cluster — bond/settoriali difensivi/REIT/PE si
muovono troppo poco perché `macd_ok` (histogram positivo E in accelerazione) scatti spesso.
`smart_6_macd` semplicemente non è adatto a questo cluster, a prescindere dai parametri
d'ingresso sweepati qui.

**Speculativo (16 ticker)**: 0 trade su tutte le 12 combinazioni con `mm200_distance_max`
attivo (3–9%), 1 trade solo disattivandolo del tutto. Stesso verdetto: il collo di bottiglia
non è `mm200_distance_max` per questo cluster, è altrove (probabilmente `macd_ok` o la
finestra RSI/ADX, non ancora isolato).

**Prossimo passo naturale (Fase 2, non ancora fatto)**: fissata la Candidate Entry Zone di
`core`, sweep dei parametri di **uscita** (`sl_buffer_wide` per lo Stop Loss,
`l1_stop_gain_dynamic.{target_max_pct,target_floor_pct,slope_sensitivity}` per il Take
Profit dinamico) attorno a quella configurazione d'ingresso — deliberatamente escluso da
questo primo giro per tenere gestibile la validazione. Stesso pattern di override sicuro già
usato per `mm200_distance_max`/`adx_entry`, nessun lavoro di validazione aggiuntivo previsto
oltre a confermare che l'override di `analyzer.p['l1_stop_gain_dynamic']` (dict annidato,
non uno scalare) si propaga correttamente.

### Fase 2 + micro-sweep TP (2026-08-07) — CANDIDATE_MODEL_B_20260807

**Fase 2** (`--phase2`, 36 combinazioni, 69 min, solo cluster `core`, Candidate Entry Zone
fissa mm200=7.0%/adxΔ=-4): sweep di `sl_buffer_wide` (moltiplicatore 1.0–1.8x) ×
`l1_stop_gain_dynamic.target_max_pct` (10–15%) × `target_floor_pct` (3–5%, mai il vincolo
attivo — dimensione senza effetto misurabile, i tre valori danno risultati identici a parità
degli altri due parametri).

**Risultato più importante: allargare lo Stop Loss peggiora tutto.** Profit Factor
in-sample migliore per moltiplicatore: 1.0x→**1.45**, 1.2x→1.32, 1.5x→1.07, 1.8x→0.96 — e il
Max Drawdown esplode in parallelo: 32.5% → 34.5% → 57–65% → 59–66%. Allargare lo SL non
riduce le uscite premature, lascia solo correre più a lungo le perdite. **SL alla baseline di
famiglia (moltiplicatore 1.0x) è l'unica scelta sostenibile** in questo range.

**Micro-sweep TP** (`--tp-micro`, 5 combinazioni, 9.9 min, SL fisso a baseline): esteso il
target fino al 25% per vedere se il trend crescente della Fase 2 (10%→1.27, 12%→1.32,
15%→1.45) continuava. **Non continua**: 18%→1.30 (cala), 20%→1.33, 22%→1.36, 25%→1.36 — zona
piatta/rumorosa tra 15% e 25%, non un massimo più alto. N e win rate restano identici (31
trade, 54.8%) su tutto il range: il TP non cambia mai quali trade avvengono, solo dove
escono. **15% resta il miglior punto trovato**, non l'inizio di una salita — bene non essere
andati oltre a inseguire rumore statistico.

**CANDIDATE_MODEL_B_20260807** (solo cluster `core`: `equity_sviluppati`,
`oro_metalli_preziosi`, `mercati_emergenti`, `settoriali_growth`, `metalli_industriali`;
`smart_6_macd`, non `native_7`):

| Parametro | Valore |
|---|---|
| `mm200_distance_max` | 7.0% (assoluto, sostituisce il valore per-famiglia) |
| `adx_entry` | baseline di famiglia − 4 |
| `sl_buffer_wide` | invariato (baseline di famiglia) |
| `l1_stop_gain_dynamic.target_max_pct` | 15% (0.15) |
| `l1_stop_gain_dynamic.target_floor_pct` | irrilevante, mai il vincolo attivo |
| min_buy_count | 6 (con `macd_ok` sempre obbligatorio) |

**Metriche certificate** (Golden Dataset, batch `2026-08-07`, split
2023-08-05→2025-08-05 / 2025-08-05→2026-08-05):

| | In-Sample | Out-of-Sample |
|---|---|---|
| N trade | 31 | 18 |
| Profit Factor | 1.45 | 1.62 |
| Win Rate | 54.8% | 55.6% |
| Max Drawdown | 32.5% | 19.1% |

**Cluster `difensivo` e `speculativo`: esclusi da questo candidato** — non è un problema dei
parametri sweepati, è mancanza strutturale di segnale `smart_6_macd` a monte (vedi sopra).

> ⚠️ **NON promosso in produzione.** Tre motivi, non uno: (1) il sistema è in lockdown
> parametri fino al 06/09/2026, deciso esplicitamente in questa sessione; (2) `smart_6_macd`
> non è mai stato attivo in produzione (`use_smart_6_7_macd: false` su tutte le famiglie) —
> promuovere questi parametri significherebbe anche decidere di attivarlo, una scelta
> distinta mai presa esplicitamente; (3) N=31/18 resta un campione modesto, appena sopra la
> soglia di significatività scelta (30) in-sample e sotto in out-of-sample. Resta un
> **candidato backtestato**, non una modifica pronta per lo YAML.
>
> ✅ **Shadow Monitor IMPLEMENTATO E LIVE (2026-08-07, stessa sessione)**: `shadow_monitor.py`
> (nuovo modulo) + `etf_shadow_positions` (migration `003`) + `database.py`
> (`open_shadow_position`/`close_shadow_position`/`get_open_shadow_position`/
> `get_shadow_positions`). Chiamato da `monitor.py::run()` come **STEP 8**, avvolto in
> try/except (mai blocca il ciclo reale) — stesso pattern già usato per
> `l1_seven_conditions`/`l1_tiered_entry`/`l1_accelerated_entry` (motori paralleli
> informativi, non decisionali). Riusa la logica reale (`suggest_level()`,
> `calculate_sl_suggerito_l1`, `calculate_stop_gain_dynamic`) con i soli parametri di
> CANDIDATE_MODEL_B sovrascritti — nessuna duplicazione. **Solo le 5 famiglie di `core`**.
> Log sempre su `etf_shadow_positions`, da estrarre manualmente al 06/09/2026 per il
> confronto native_7 vs candidato su dati forward reali. Verificato end-to-end su tutti i
> 155 ticker di `core` senza errori (0 ingressi il primo giorno, coerente con la bassa
> frequenza attesa del candidato — ~31 trade/2 anni sull'intero cluster). Commit `0be6673`.
>
> ✅ **Aggiornamento 2026-08-19 — email attivata**: la scelta "nessuna email" (2026-08-07)
> è stata superata su richiesta esplicita dell'utente. `alerts.py::send_shadow_entries()`
> (esisteva già, mai collegata) ora viene chiamata da `monitor.py` STEP 8/8b quando
> `run_shadow_monitor()`/`run_shadow_monitor_l0()` aprono una nuova posizione ombra —
> una mail per L1 (`variant='L1'`) e una per L0 (`variant='L0'`), solo sui nuovi ingressi
> (non sulle uscite), solo quando `send_daily_report=True` (non sul run silenzioso delle
> 09:00). Zero impatto sulle decisioni reali, resta puramente informativo.
>
> **Estrazione risultati a fine lockdown**:
> ```sql
> SELECT ticker, entry_date, exit_date, exit_reason, gross_pct_gain
> FROM etf_shadow_positions WHERE model_name = 'candidate_model_b_20260807'
> ORDER BY entry_date;
> ```

> ✅ **PROMOSSO IN PRODUZIONE 2026-08-24** — deroga esplicita al lockdown, su richiesta
> diretta dell'utente, con Shadow Monitor ancora a N=1 (ben sotto la soglia N≥30 — stesso
> tipo di eccezione già concessa una volta per `CANDIDATE_MODEL_L0_SL_20260820`, non un
> nuovo precedente generale). Contesto della decisione: nella stessa sessione è stato
> costruito un confronto diretto "PAC passivo su VWCE.DE vs sistema attivo" con la stessa
> cassa mensile simulata (€1.000/mese, 3 anni) — `native_7` (1 solo trade nel periodo)
> rendeva +1,03% contro il +23,34% del PAC; `smart_6_macd` (13 trade presi) rendeva +7,02%,
> ancora sotto il PAC ma molto più vicino — motivando la richiesta di attivarlo subito
> invece di aspettare il 06/09.
>
> **Applicato esattamente il bundle certificato**, su tutte e 5 le famiglie `core`
> (scelta esplicita dell'utente tra due alternative proposte — solo `equity_sviluppati` era
> l'opzione più prudente, scartata):
> ```yaml
> # per ciascuna delle 5 famiglie core (equity_sviluppati, mercati_emergenti,
> # settoriali_growth, oro_metalli_preziosi, metalli_industriali):
> use_smart_6_7_macd: true
> mm200_distance_max: 7.0        # assoluto, sostituisce il valore per-famiglia precedente
> adx_entry: <baseline famiglia> - 4   # es. equity_sviluppati 22->18, settoriali_growth 25->21
> l1_stop_gain_dynamic.target_max_pct: 0.15   # sostituisce il valore per-famiglia precedente
> ```
> ⚠️ **Rischio noto, accettato esplicitamente**: il sondaggio delle 14 famiglie (stesso
> giorno) aveva già declassato `oro_metalli_preziosi` (0 giorni raggiunge mai smart_6_macd
> nel suo storico) e `mercati_emergenti` ("da motore a monitorare, edge fragile/regime-
> dipendente") — il bundle certificato N=151/31/18 le include comunque perché il backtest
> originale del 07/08 era sull'intero cluster insieme, non segmentato per famiglia (lo
> stesso tipo di rischio "pooled" isolato due volte in questa sessione — Bond-Trend e L0 sulle
> 8 famiglie morte). Non risegmentato prima della promozione — deciso di procedere comunque
> su richiesta esplicita, monitorare i risultati reali family-by-family al prossimo
> checkpoint invece di ritardare l'attivazione.
>
> **Cleanup eseguito lo stesso giorno** (produzione e candidato ora coincidono, stesso schema
> di `CANDIDATE_MODEL_L0_SL_20260820`): `shadow_monitor.py` rimosso dal repo e dalla chiamata
> STEP 8 in `monitor.py::run()`; variante `'L1'` rimossa da
> `alerts.py::_SHADOW_VARIANTS` (default di fallback spostato su `'L0'`). L'unica posizione
> ombra esistente (`LGQM.DE`, aperta 2026-08-22) chiusa amministrativamente nel DB
> (`exit_reason='PROMOTED'`, non un vero tocco di SL/TP). Deployato via `./deploy.sh`.
>
> **Da fare al prossimo checkpoint**: monitorare gli ingressi reali family-by-family (via
> `etf_l1_tracking`) per verificare se `oro_metalli_preziosi`/`mercati_emergenti` si
> comportano come temuto (segnali rari o di bassa qualità) — se confermato, valutare di
> restringere `use_smart_6_7_macd` alle sole famiglie che si dimostrano valide, stessa
> disciplina già applicata a Bond-Trend lo stesso giorno.

### Sessione fix 2026-08-07 (riassunto) — bug regime_ok, 10 ticker delistati, chiusura discrepanza 80 vs 3

- **Fix `UnboundLocalError: regime_ok`** in `suggest_level_0()`: la variabile veniva letta ai
  percorsi FAST/SLOW (righe 948/968 dell'epoca) prima di essere calcolata (riga 1005) —
  introdotto dal gate regime BULL del 06/08 (`e81ae75`), mai emerso prima perché nessun run
  precedente aveva loggato l'errore come tale. Impatto reale: **48 ETF su 240 (20%
  dell'universo)**, tutti gli `equity_sviluppati` che superano il whitelist gate L0, venivano
  scartati a ogni run con `data_status='no_data'` — sembravano "senza dati" ma avevano
  storico regolare in DB (verificato: 638-640gg per un campione). Fix: spostato il calcolo di
  `regime_ok` subito dopo `global_params`, prima di qualunque uso. Commit `988a5bd`.
- **10 ticker Yahoo Finance delistati** (`WSML.DE`, `IWMO.DE`, `IWQU.DE`, `MVOL.DE`,
  `IGLN.MI`, `BITC.MI`, `ETHE.MI`, `SLNC.MI`, `BTCE.MI`, `BDAS.MI`) — genuinamente "0 giorni
  per sempre", non nuovi ETF in accumulo. Rimappati per ISIN (non per nome, per evitare falsi
  positivi su varianti hedged/Advanced) a ticker vivi verificati via `yfinance`:
  `WSML.L`/`IWMO.L`/`IWQU.L`/`MVOL.L`/`IGLN.L` (Londra, USD), `BITC.SW`/`ETHE.SW`/`SLNC.SW`
  (Swiss SIX, CHF), `BTCE.DE` (Xetra, EUR), `DA21.DE` (Xetra, USD — unico caso di cambio
  ticker root, non solo suffisso: `BDAS` non esiste più su nessuna borsa). Commit `1ea0771`.
  Dopo entrambi i fix: `no_data` sceso da 58 a 0 su 240 ETF.
- **Chiusa l'indagine sulla discrepanza 80 vs 3 trade nativi 7/7** aperta il 06/08 — non con
  la conferma sperata ("3 è giusto, 80 è sbagliato"), ma con l'identificazione della causa
  reale: `backtest_l1.py` non è riproducibile run-to-run perché rifetcha OHLCV live da Yahoo
  a ogni esecuzione. Vedi nota sopra in "L1 — Come Si Esce" per il dettaglio completo
  (rerun a codice identico, 2 giorni dopo → 3 trade diventano 1).
- **Golden Dataset**: implementato lo storico OHLCV congelato (`etf_price_history_frozen`)
  per rendere i backtest riproducibili — vedi nota sopra in "L1 — Come Si Esce" per schema,
  script di backfill e la prima **BASELINE_OFFICIAL_20260807** (1 trade, `WLDC.PA`).
- **7 ticker aggiuntivi corretti/rimossi** durante il backfill del Golden Dataset (emersi
  come "0 righe" nel fetch storico completo, non nel semplice check giornaliero del
  monitor): `USHYC`→`USHYC.MI` (mancava il suffisso borsa), `PHAU.MI`→`PHAU.L` (WisdomTree
  Physical Gold, migrato a Londra), `3LMS.MI`→`3LMS.L` (GraniteShares 3x Long Microsoft,
  migrato a Londra). Rimossi invece 4 ticker senza soluzione: `NDXH2.PA` (duplicato — stesso
  ISIN `LU1954152853` di `UST.PA`, già tracciato), `3LIS.MI`/`3LUC.MI`/`3MBS.MI`
  (GraniteShares 3x Intesa/UniCredit/-3x FTSE MIB — nessun listing vivo trovato su Yahoo
  sotto nessun suffisso borsa comune). Universo sceso da 240 a 236 righe in Excel.
- **Grid search `smart_6_macd` (`optimize_hyperparameters.py`)**: infrastruttura completa
  (motore vettorizzato validato a 0 discrepanze, cluster per `sl_initial_pct`, split
  in/out-of-sample) — vedi sezioni dedicate sopra. Percorso completo in un solo giorno:
  pilota (27 combo, N<30 ovunque) → discrepanza 26 vs 151 trade risolta (causa
  `mm200_distance_max`, non un bug) → sweep ampio (45 combo, Candidate Entry Zone trovata
  per `core`: mm200=7.0%/adxΔ=-4) → Fase 2 uscite (36 combo: allargare lo SL peggiora tutto,
  SL alla baseline è l'unica scelta sostenibile) → micro-sweep TP (5 combo: 15% resta il
  miglior target, oltre è rumore) → **CANDIDATE_MODEL_B_20260807** documentato e certificato
  (IN N=31 PF=1.45 WR=54.8%, OUT N=18 PF=1.62 WR=55.6%). **Non promosso in produzione** —
  lockdown fino al 06/09/2026, `smart_6_macd` mai attivato live, N ancora modesto. Prossimo
  Shadow Monitor **implementato e live** (`shadow_monitor.py`, STEP 8 in `monitor.py`,
  tabella `etf_shadow_positions`) — traccia ogni giorno cosa avrebbe fatto il candidato
  sulle 5 famiglie di `core`, zero email, zero impatto sulle decisioni reali. Verificato
  end-to-end senza errori. Estrazione risultati al 06/09/2026.
- **Nota**: `/root/etf_monitor_system/etf_monitoraggio.xlsx` è un **bind mount** diretto in
  `/app/etf_monitoraggio.xlsx` (non `COPY` in build) — modifiche al file sull'host sono
  visibili nel container **senza restart**. Utile per fix rapidi ai dati (ticker, borsa,
  valuta) senza rischiare di uccidere processi in background nel container (es. un backtest
  lungo lanciato con `docker exec -d`, che un `docker compose up -d --force-recreate`
  ucciderebbe).

### Grid Search L0 — `optimize_l0.py` + `optimize_l0_regime.py` (2026-08-07/08) — CANDIDATE_MODEL_L0_20260808

Stesso approccio già usato per `smart_6_macd` su L1 (Golden Dataset congelato, split
in/out-of-sample, motore vettorizzato con `precomputed`), applicato per la prima volta a L0.

**Infrastruttura**: `backtest_l0_v2.py` (commit `72d4c04`) — motore pulito che riusa le
funzioni di produzione reali (`suggest_level_0()`, `calculate_sl_suggerito_l0()`,
`calculate_tp_suggerito_l0()`). Non riusa `backtest_l0.py`/`backtest_l0_full.py`/
`backtest_l0_rigorous.py` preesistenti: quelli avevano una copia manuale della formula SL con
soglie sbagliate (2%/5% invece di 5%/15% reali) e saltavano whitelist/regime/divergenza —
**non fidarsi di quei file**. `suggest_level_0()` ha guadagnato un parametro opzionale
`precomputed` (RSI/EMA20/SMA50), stesso pattern di `suggest_level()`, validato a 0
discrepanze (320 check).

**Due bug di produzione reali trovati per caso investigando un'anomalia nei dati** (non
un audit dedicato — vedi sopra "FIX CRITICO 2026-08-07" per il dettaglio completo): whitelist
L0 mai davvero attiva (`600f51b`) e un ETF VIX futures mal classificato che generava 25 trade
spuri (`564de92`, `LVO.MI`→`leva_single_stock`). Correggere `564de92` ha cambiato la baseline
a 3 anni (equity_sviluppati, parametri nativi) da 216 a 184 trade e il rendimento medio/trade
da un +17.4% palesemente gonfiato a un +3.04% credibile — quest'ultimo è il numero da citare.

**Sweep 1 — `optimize_l0.py --sweep` (PRAGMATIC, 108 combo, 179.7 min, 2026-08-07/08)**:
`dd_threshold`/`rsi_max`/`recovery_min_pct` risultano **completamente non discriminanti** —
N identico (146 IN / 44 OUT) su ogni combinazione dd/rsi/recovery testata. Causa (non un bug,
verificato leggendo `technical_analysis.py:972-1041`): `suggest_level_0()` prova prima FAST e
SLOW, che non leggono affatto questi 3 parametri — solo se entrambi falliscono si arriva a
PRAGMATIC. Su `equity_sviluppati`, che ha `l0_regime` configurato, il 100% dei trade entra via
FAST/SLOW, PRAGMATIC non viene mai raggiunto. L'unico parametro che conta in questo sweep è
`l0_take_profit_pct`: PF 2.11→3.18 IN e 3.97→4.51 OUT man mano che tp va da 10% a 16%,
monotono, nessun segno di picco prima del 16% (grid non testata oltre). **TP=16% confermato
come miglior valore trovato** — è già il valore in produzione per `equity_sviluppati` (vedi
tabella `l0_take_profit_pct` sopra), quindi questo sweep conferma il default, non lo cambia.

**Sweep 2 — `optimize_l0_regime.py` (FAST/SLOW, 28 combo, ~2h totali, 2026-08-08)**: sweep
mirato ai soli 4 parametri che davvero governano l'ingresso FAST/SLOW (verificato leggendo
`_analyze_l0_fast_path`/`_analyze_l0_slow_path`): `flash_crash_window_days` +
`flash_crash_zscore_threshold` (FAST), `regime_min_days_below_sma200` + `dd_min_duration_days`
(SLOW). `capitulation_volume_multiplier`/`reclaim_ema_fast_period`/`reclaim_ema_slow_period`
sono morti nel codice (periodi EMA-reclaim sono hardcoded 20/50, non letti dal YAML);
`dd_threshold_atr_multiple` è letto ma solo per un campo diagnostico, non gating.

- **FAST (12 combo, 54.9 min)**: non discriminante — la FAST path contribuisce solo 0-2 trade
  su ~146-148 totali in ogni combinazione, dominata quasi totalmente da SLOW. PF migliore
  resta 3.18 (tp=0.16), stesso tetto dello Sweep 1. Nessun parametro FAST vale la pena di
  toccare.
- **SLOW (16 combo, 73.3 min)**: qui c'è segnale reale. Baseline YAML `equity_sviluppati`
  (`regime_min_days_below_sma200=10, dd_min_duration_days=4`, confermato in
  `config/etf_families.yaml:70-78`) → IN N=146 PF=3.18 WR=42.5% | OUT N=44 PF=4.51 WR=50.0%
  (stessi identici trade dello Sweep 1, come atteso). Migliore combinazione trovata, stessa
  disciplina di sempre (preferire OOS che tiene/migliora rispetto a IN, non solo IN alto):
  **`regime_min_days_below_sma200=5, dd_min_duration_days=4`** → IN N=152 PF=**3.38** WR=44.1%
  | OUT N=62 PF=**4.84** WR=51.6% — batte il baseline su IN *e* OUT, con N più alto in
  entrambi i periodi, non un episodio isolato. Runner-up con N ancora più ampio:
  `min_days=5, dd_min=3` → IN N=169 PF=3.38 WR=43.8% | OUT N=72 PF=4.42 WR=48.6%. **Scartata**
  la combinazione con il PF in-sample più alto in assoluto della griglia (`min_days=15,
  dd_min=2`, IN PF=3.7): OOS crolla a PF=2.88 WR=37.5% — stessa firma di overfitting già vista
  e scartata nello sweep L1 (caso `mm200_delta=-1`).

**CANDIDATE_MODEL_L0_20260808** (solo `equity_sviluppati` — unica famiglia raggiungibile per
L0, vedi whitelist gate sopra):

| Parametro | Valore |
|---|---|
| `regime_min_days_below_sma200` | 5 (baseline YAML: 10) |
| `dd_min_duration_days` | 4 = 4% (invariato — nome fuorviante, è una soglia di drawdown /100, non un conteggio di giorni) |
| `l0_take_profit_pct` | 16% (invariato, già il valore in produzione) |
| `flash_crash_window_days` / `flash_crash_zscore_threshold` | invariati (non discriminanti) |
| `dd_threshold` / `rsi_max` / `recovery_min_pct` (PRAGMATIC) | invariati (mai raggiunti in pratica) |
| Stop Loss | invariato rispetto al candidato — formula dinamica a scaglioni esistente (`calculate_sl_suggerito_l0`: <5% profitto → entry×0.96, 5–15% → pareggio entry×1.01, >15% → protegge metà gain). Non sweepata in questo candidato del 08/08, vedi nota sotto — il primo scaglione (2%→4%) è stato poi sweepato e promosso in produzione separatamente il 2026-08-20, vedi CANDIDATE_MODEL_L0_SL_20260820 più sotto |

**Metriche certificate** (Golden Dataset, batch `2026-08-07`, stesso split di
`CANDIDATE_MODEL_B_20260807`):

| | In-Sample | Out-of-Sample |
|---|---|---|
| N trade | 152 | 62 |
| Profit Factor | 3.38 | 4.84 |
| Win Rate | 44.1% | 51.6% |

> ⚠️ **NON promosso in produzione** — stesso motivo del candidato L1: lockdown parametri fino
> al 06/09/2026. A differenza di `CANDIDATE_MODEL_B_20260807` questo è un ritocco di un solo
> parametro già attivo in produzione (non richiede attivare un motore sperimentale spento),
> quindi il rischio di deploy è più basso — ma resta comunque **solo backtest**, non ancora
> validato live, e va comunque attraverso l'attesa del lockdown.
>
> ✅ **Aggiornamento 2026-08-20**: il primo scaglione della formula SL (`calculate_sl_suggerito_l0`,
> profitto<5%) è stato sweepato e **promosso in produzione** — vedi
> "CANDIDATE_MODEL_L0_SL_20260820" più sotto.
>
> ✅ **Gap chiuso 2026-08-24**: `calculate_sl_suggerito_l0` ora legge tutti e 3 gli scaglioni
> dallo YAML per famiglia (`l0_sl_tier1_threshold_pct`/`l0_sl_tier1_buffer_pct`/
> `l0_sl_tier2_threshold_pct`/`l0_sl_tier2_markup_pct`/`l0_sl_tier3_giveback_pct`), con
> default via `self.p.get(...)` = ai valori hardcoded precedenti (5%/4%/15%/1%/8%) — zero
> cambio di comportamento verificato (stessi identici SL su 3 casi di test). Valori espliciti
> aggiunti nello YAML per `equity_sviluppati`/`oro_metalli_preziosi`/`metalli_industriali`
> (le uniche famiglie con attività L0 reale o Shadow); le altre 11 restano sul default
> implicito, invariato. Rilevante ora per gli Shadow Monitor L0 su oro/metalli (bypassano la
> whitelist per il test ma prima usavano comunque questi parametri "a taglia unica").
>
> ✅ **Correzione 2026-08-19 — lo Shadow Monitor L0 esiste già ed è live**: la frase sopra era
> superata. `shadow_monitor_l0.py` è stato aggiunto l'08/08 (stessa sessione di questo
> candidato, poco dopo) — STEP 8b in `monitor.py::run()`, stesso pattern del sperimentale L1
> (log sempre su `etf_shadow_positions` con `model_name='candidate_model_l0_20260808'`,
> avvolto in try/except non bloccante — email sui nuovi ingressi attivata il 2026-08-19,
> vedi sezione CANDIDATE_MODEL_B_20260807 sopra). Logga una riga di riepilogo solo quando succede
> qualcosa (apertura/chiusura) — per questo è passato inosservato per giorni, non perché non
> stesse girando. Estrazione manuale al 06/09/2026, stessa data del candidato L1:
> ```sql
> SELECT ticker, entry_date, exit_date, exit_reason, gross_pct_gain, status
> FROM etf_shadow_positions WHERE model_name = 'candidate_model_l0_20260808'
> ORDER BY entry_date;
> ```
> Stato al 2026-08-19 (12 giorni di osservazione): 5 posizioni tracciate, tutte su
> `equity_sviluppati` (unica famiglia raggiungibile) — 1 chiusa via SL (-2.42%), 4 aperte
> (ENRG.PA, INCI.MI, WATC.SW, LBRE.DE — quest'ultimo un rientro dopo lo stop dell'08/08).
> Campione ancora troppo piccolo per qualunque conclusione. Nello stesso periodo lo Shadow
> Monitor L1 (`candidate_model_b_20260807`) non ha aperto nessuna posizione ombra: in 12 giorni
> nessuno dei due gate (nativo 7/7 o candidato 6/7+MACD) ha trovato un ingresso valido sulle
> famiglie core — non è che il gate 7/7 sia più selettivo del candidato in questo periodo,
> è che il mercato non ha offerto setup validi per nessuno dei due.

### CANDIDATE_MODEL_L0_SL_20260820 — PROMOSSO IN PRODUZIONE lo stesso giorno (deroga esplicita al lockdown)

**Origine**: whipsaw reale su BRES/Amundi STOXX Europe 600 Basic Res. (LU1834983550,
`equity_sviluppati`) — posizione L0 reale, 71 quote, uscita il 2026-08-20 mattina via lo
stop reale (allora al 2%, `calculate_sl_suggerito_l0` primo scaglione) a -2,35% netto;
il prezzo è poi rimbalzato quasi a pareggio (140,18€ vs 140,58€ di carico) lo stesso
pomeriggio. L'utente ha notato il whipsaw e chiesto se il 2% fosse troppo stretto — gap
genuinamente mai testato prima (diverso dal test del 19/08 sui tier 2/3, quello sì
respinto, vedi sopra "Evaluated and REJECTED").

**Backtest one-shot** (Golden Dataset congelato batch `2026-08-07`, 106 ETF
`equity_sviluppati`, stesso split IN/OUT di CANDIDATE_MODEL_L0_20260808, ingressi di
baseline invariati — solo il primo scaglione della formula SL variato, tiers 2/3 e TP
invariati). Ogni buffer testato migliora **monotonicamente** WR/PF/rendimento medio/P&L
netto, sia IN che OUT-of-sample — segnale molto più pulito del test del 19/08:

| Buffer | IN: N / WR / PF / P&L 10k€ | OUT: N / WR / PF / P&L 10k€ |
|---|---|---|
| 2% (vecchia produzione) | 146 / 42.5% / 3.18 / +53.602€ | 44 / 50.0% / 4.51 / +22.032€ |
| 3% | 143 / 57.3% / 4.43 / +80.930€ | 40 / 60.0% / 5.31 / +24.901€ |
| **4% (scelto)** | **142 / 64.8% / 4.68 / +91.715€** | **37 / 70.3% / 6.18 / +27.819€** |
| 5% | 140 / 70.0% / 4.86 / +98.423€ | 35 / 77.1% / 7.61 / +29.884€ |
| 6% | 139 / 72.7% / 4.57 / +99.705€ | 33 / 81.8% / 8.65 / +30.425€ |

4% scelto come ginocchio della curva (cattura la maggior parte del guadagno senza
spingere il rischio per trade al livello del 6%). Script di sweep scratch-only
(`optimize_l0_sl_tier1.py`, docker cp'd, eseguito, cancellato — mai entrato nel repo).

**Trade-off consapevole, non gratis**: la perdita massima teorica per singolo trade
raddoppia (2%→4%) — non catturato dalle metriche aggregate sopra, che misurano solo
l'effetto medio su tutti i trade.

**Deviazione esplicita dal processo standard**: ogni altro candidato di questo mese
(`CANDIDATE_MODEL_B_20260807`, `CANDIDATE_MODEL_L0_20260808`, Market Breadth) segue
backtest → Shadow Monitor live → decisione solo a fine lockdown (06/09/2026). Per
questo, su richiesta esplicita dell'utente dopo essere stato avvisato del trade-off e
della rottura di processo, si è promosso **direttamente in produzione lo stesso giorno**
del backtest — **non ripetere questa scorciatoia per altri candidati senza una richiesta
altrettanto esplicita**, il lockdown resta la regola per tutto il resto.

**Implementazione**: `technical_analysis.py::calculate_sl_suggerito_l0()`, primo
scaglione `entry_price * 0.98` → `entry_price * 0.96`. Nessun cambio YAML (la formula è
hardcoded, non parametrizzata per famiglia — irrilevante oggi dato che solo
`equity_sviluppati` è raggiungibile via whitelist L0). Lo Shadow Monitor dedicato
(`shadow_monitor_l0_sl.py`, STEP 8d in `monitor.py`, vissuto meno di un'ora) è stato
**rimosso lo stesso giorno**: una volta promosso, produzione e candidato coincidono,
non c'è più una baseline distinta da tracciare in parallelo. Le 2 posizioni ombra che
aveva aperto al suo unico ciclo (`LBRE.DE` @140,18, `DEFS.PA` @6,36) sono state chiuse
amministrativamente nel DB (`exit_reason='PROMOTED'`), non per un vero
tocco di SL/TP. Deploy via `./deploy.sh`. Vedi memory/etf_post_lockdown_todo_20260906.md
sezione 3 per il dettaglio completo.

---

## Variabili d'Ambiente `.env`
```
DB_PASSWORD=FundMonitor2026!
RESEND_API_KEY=...
EMAIL_SENDER=onboarding@resend.dev
MONITOR_HOUR=17
MONITOR_MINUTE=0
MONITOR_DAYS=1-5
RUN_ON_START=false
```
