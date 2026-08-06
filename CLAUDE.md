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

### L1 — Come Si Entra (7 Condizioni TUTTE Obbligatorie)

**SPECIFICA CORRETTA** (dal Prompt di implementazione STEP 3 v4.0):

L1 richiede **TUTTE e 7** le seguenti condizioni:

| # | Condizione | Significato | Parametro |
|---|-----------|-------------|-----------|
| **1** | **Allineamento** | price > EMA20 > SMA50 (+ price > SMA200 se mm200_filter) | `allineamento_ok` |
| **2** | **Persistenza** | giorni_sopra_EMA20 ≥ N + slope(EMA20) > 0 | `persistenza_ok` |
| **3** | **RSI Ottimale** | rsi_entry_low ≤ RSI ≤ rsi_entry_high (per famiglia) | `rsi_ok` |
| **4** | **Distanza EMA20** | 0% ≤ dist_EMA20 ≤ ema_dist_max (non troppo staccato) | `distance_ok` |
| **5** | **ADX Forte** | ADX ≥ adx_entry (forza trend confermata) | `adx_ok` |
| **6** | **MACD Momentum** | histogram > 0 AND (rising OR dist_ema20 < 2%) | `macd_ok` |
| **7** | **Spazio Residuo** | Resistenza > min_reward_pct OR ATR×mult > min_reward_pct | `space_residuo_ok` |

**Regola**: Se **qualsiasi UNA è FALSE** → **INGRESSO BLOCCATO** (L2)

**Fondamenta Irrinunciabili** (no eccezioni, verificate *dopo* il 7/7):
- ✅ Regime BULL: `(EMA20 − SMA50) / SMA50 > lateral_band` (soglia per famiglia, calculate_regime()). Dal fix del 2026-08-04 è verificato **una sola volta qui** — prima era anche incorporato dentro la condizione 1 (Allineamento), rendendo la condizione 1 un doppio controllo mascherato; oggi la condizione 1 è puramente geometrica (price>EMA20>SMA50 [+SMA200]).
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

`suggest_level_0()` ha **tre percorsi di ingresso**, non uno solo. I primi due (FAST/SLOW)
hanno priorità; se nessuno scatta si valuta il terzo (PRAGMATIC_4CONDITIONS):

1. **FAST** (flash crash): crollo rapido rilevato via z-score ATR su pochi giorni
2. **SLOW** (bear sostenuto): giorni consecutivi sotto SMA200 + drawdown normalizzato
3. **PRAGMATIC_4CONDITIONS** — tutte e 4 obbligatorie:
   1. **Drawdown:** Prezzo almeno X% sotto il picco storico (dd_threshold dal YAML)
   2. **RSI Ipervenduto:** RSI < rsi_max (es. 45 per equity)
   3. **Divergenza Rialzista:** Il prezzo fa un minimo più basso, ma RSI fa un minimo più alto
   4. **Segnale di Recupero:** RSI risorge > 40, OPPURE prezzo sale ≥ 1% su 5 giorni

> **Fix 2026-08-05**: prima FAST e SLOW entravano in L0 al solo rilevamento del crollo,
> senza nessuna prova che l'inversione fosse davvero iniziata — a differenza del
> percorso pragmatico, che richiede sempre divergenza+recovery. Causa sospetta dei
> "falsi L0" che continuavano a scendere o lateralizzavano dopo l'ingresso. Ora
> entrambi richiedono `_get_l0_confirmation_signal()` (RSI risalito sopra soglia
> OPPURE prezzo che riconquista l'EMA20/50) prima di confermare l'ingresso; se non
> confermato, si prosegue al percorso successivo (FAST → SLOW → PRAGMATIC).

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
| 1 | SL trailing | Prezzo ≤ SL suggerito (`calculate_sl_suggerito_l0`: <5% profitto → entry×0.98, 5-15% → pareggio entry×1.01, >15% → protegge metà gain) |
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
> non basta recuperare il calo, serve un margine reale di nuovo trend):

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
