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

**Esempio (equity_sviluppati):**
```
rsi_entry_low: 45
rsi_entry_high: 55

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
days_above_ema = 5

Giorno 1: prezzo > EMA20 ✓
Giorno 2: prezzo > EMA20 ✓
Giorno 3: prezzo > EMA20 ✓
Giorno 4: prezzo > EMA20 ✓
Giorno 5: prezzo > EMA20 ✓
→ OK, INGRESSO CONFERMATO

Se Giorno 2: prezzo scende sotto EMA20
→ Falso segnale, counter riazzera, aspetta di nuovo 5 giorni
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

### L1 — Come Si Entra (Gerarchia 2+2)

Il sistema usa una **gerarchia intelligente**:

**GATE STRUTTURALE (obbligatorio):**
- A: Prezzo > EMA20 (il prezzo deve stare sopra la media veloce)
- M: MACD > 0 (il momentum deve spingere al rialzo)

Se ENTRAMBI sono FALSE → **BLOCCO TOTALE**, nessun ingresso possibile.

**VELOCITÀ FLESSIBILE (almeno 2 su 4):**
- P: Prezzo > SMA50 (allineamento con media media)
- R: RSI in range ottimale (46-55 per equity)
- D: ADX > soglia (forza trend confermata)
- X: EMA20 > SMA50 (doppio allineamento)

Se **almeno 2 tra P, R, D, X sono TRUE** → **INGRESSO AUTORIZZATO**.

---

### L1 — Come Si Esce (6 Regole di Uscita)

| Priorità | Regola | Trigger | Azione |
|:---:|--------|---------|--------|
| 1 | **F — Kill Switch** | Calo giornaliero ≤ −3% | USCITA totale |
| 2 | **A — Stop Loss** | Prezzo < EMA20 per 3 giorni | USCITA totale |
| 3 | **B — Trailing Stop** | EMA10 < EMA20 | USCITA totale |
| 4 | **C — Stanchezza** | RSI era ≥ 70, scende sotto | USCITA totale |
| 5 | **E — ADX Debole** | ADX < 18 + prezzo < EMA20 | USCITA totale |
| 6 | **D — Piede Dentro** | RSI > 78 | USCITA 90%, mantieni 10% + monetario |

**Uscita Parziale (Piede Dentro):**
Se attiva la regola D:
- Vendi 90% della posizione
- Compra ETF monetario (XEON — pagherà ~3-4% annuo)
- Mantieni 10% dell'ETF: rimane in L1 come "sensore"
- Al prossimo segnale di ingresso, rientra con il 100%

---

### L0 — Come Si Entra (Deep Recovery)

**Tutte 4 condizioni sono obbligatorie:**

1. **Drawdown:** Prezzo almeno X% sotto il picco storico (dd_threshold dal YAML)
2. **RSI Ipervenduto:** RSI < rsi_max (es. 45 per equity)
3. **Divergenza Rialzista:** Il prezzo fa un minimo più basso, ma RSI fa un minimo più alto
4. **Segnale di Recupero:** RSI risorge > 40, OPPURE prezzo sale ≥ 1% su 5 giorni

**Esempio:**
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

### L0 — Come Si Esce

| Simbolo | Regola | Trigger | Azione |
|:---:|--------|---------|--------|
| γ | Promozione | Prezzo > EMA20 | Esce da L0, va a L2 |
| β | Trappola | RSI < 25 dopo entry | USCITA, era una trappola |
| α | Stop Assoluto | Prezzo < panic_low | USCITA urgente |
| ε | Tempo Scaduto | 30 giorni senza recupero | USCITA in monitor.py |

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

PASSO 3: Determinare il livello GLOBALE (L0/L1/L2/L3)
├─ Leggi parametri della famiglia ETF (es. equity_sviluppati)
├─ Esegui le 4 verifiche di ingresso L1 (gerarchia 2+2)
│  ├─ GATE A: prezzo > EMA20?
│  ├─ GATE M: MACD histogram > 0?
│  ├─ Se entrambi FALSE → L2 max
│  └─ Se almeno 1 TRUE → valuta VELOCITÀ
├─ Conta quante tra P, R, D, X sono TRUE
│  ├─ 0-1 vere: L2
│  ├─ 2-3 vere: L1 (ingresso autorizzato)
│  └─ 4 vere: L1 (ingresso massimamente confermato)
└─ Se nessun ingresso → rimane L3 (universe)

PASSO 4: Verificare uscite L1 (se già in posizione)
├─ Regola F: calo giornaliero ≤ -3%? → USCITA totale
├─ Regola A: prezzo < EMA20 da 3+ giorni? → USCITA totale
├─ Regola B: EMA10 < EMA20? → USCITA totale
├─ Regola C: RSI era ≥70, ora <70? → USCITA totale
├─ Regola E: ADX < 18 E prezzo < EMA20? → USCITA totale
├─ Regola D: RSI > 78? → USCITA 90% (piede dentro)
└─ Calcola stop loss dinamico con trailing

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

### Scenario 1: Ingresso L1 Accelerato (Gerarchia 2+2)

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

Fingiamo di seguire SWDA.L per una settimana intera. SWDA.L è **equity_sviluppati**, quindi usa questi parametri dal YAML:

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
