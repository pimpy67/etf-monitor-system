---
name: alignment_matrix_canonical
description: Mappa di sincronizzazione — Cosa deve stare in CLAUDE.md vs HTML vs PDF
metadata: 
  node_type: memory
  type: project
  date: 2026-07-22
  originSessionId: 2f9d89cf-c8ec-4cb5-8314-7d617accdaa5
  modified: 2026-07-22T20:51:54.672Z
---

# Alignment Matrix — Canonical Documentation Map

**Scopo**: Definire ESATTAMENTE cosa deve stare in ogni fonte e come sincronizzarsi.

---

## Principio: Una Sola Fonte per Ogni Concetto

```
CLAUDE.md = Spiegazione Concettuale + Link a valori live
dashboard.html = Visualizzazione UI + Parametri live da API
PDF = Snapshot congelato (scaricabile)
YAML = Dati grezzi (master)
```

---

## Tabella: Cosa va Dove

| Argomento | CLAUDE.md | dashboard.html | PDF | YAML | Note |
|-----------|-----------|---|---|---|---|
| **Cos'è L1?** | ✅ Spiegazione completa | ❌ (link a CLAUDE.md) | ✅ Estratto | ❌ | Testo unico in CLAUDE.md |
| **7 Condizioni L1** | ✅ Descrizione razionale | ✅ Visualizzazione dinamica | ✅ Tabella auto-gen | ✅ Metadati | Parametri da YAML via API |
| **RSI Entry Range (equity)** | ❌ (link a "vedi parametri") | ✅ 45-55 (da API) | ✅ 45-55 (da YAML) | ✅ 45, 55 | YAML è master |
| **ADX Entry (equity)** | ❌ (link a "vedi parametri") | ✅ ≥22 (da API) | ✅ ≥22 (da YAML) | ✅ 22 | YAML è master |
| **Regola D Uscita (Piede Dentro)** | ✅ Spiegazione | ✅ Descrizione | ✅ Descrizione | ❌ | Se ancora implementata |
| **Stop Loss Iniziale** | ✅ Razionale (esempio €100→€95) | ✅ Formula dinamica | ✅ Tabella | ✅ sl_initial_pct | YAML è master |
| **L0 4 Condizioni** | ✅ Spiegazione | ✅ Visualizzazione | ✅ Elenco | ✅ Metadati | Parametri da YAML |
| **L2 Readiness Score** | ✅ Spiegazione anti-flickering | ✅ Slider/gauge | ✅ Descrizione | ✅ Pesi | YAML è master |
| **Kill Switch (-3%)** | ✅ Spiegazione | ✅ Info | ✅ Info | ❌ (hardcoded) | Costante globale |
| **Regime (Bull/Laterale/Bear)** | ✅ Spiegazione | ✅ Visualizzazione | ✅ Formula | ⚠️ Parametri parziali | Da completare in YAML |
| **Famiglia ETF (es. equity_sviluppati)** | ❌ (link a dashboard) | ✅ Tab con dettagli | ✅ Pagina dedicata | ✅ Full config | YAML è master |
| **Backtest Results** | ❌ | ✅ Storico performance | ❌ | ⚠️ Da aggiungere | Non nel primo rollout |

---

## Sezione per Sezione: Che Cosa Deve Essere Scritto Dove

### Sezione 1: Infrastruttura VPS

**CLAUDE.md**:
```markdown
## Infrastruttura VPS

- **Provider**: Hostinger VPS — Ubuntu 24.04 LTS
- **IP / hostname**: 76.13.37.133 / srv1407758.hstgr.cloud
- ... (statico, no parametri)
```

**dashboard.html**:
```html
<!-- Non va in dashboard (info di sistema, non pertinente UI) -->
```

**PDF**:
```
Appendice A: Infrastruttura
- Provider: Hostinger VPS ...
(statico, riportato da CLAUDE.md)
```

✅ **Sincronizzazione**: Manuale (aggiorna CLAUDE.md, PDF si rigenera)

---

### Sezione 2: Profili Parametri per Famiglia

#### IN CLAUDE.md

```markdown
## Profili Parametri per Famiglia ETF (Riferimento Concettuale)

Cada famiglia ETF ha **parametri specifici** calibrati per il suo profilo di rischio.

### Equity Sviluppati
- **Profilo**: Large cap stabili (ACWI, Developed Markets)
- **Rischio**: Moderato
- **Caratteristiche**: Trend persistenti, bassa volatilità
- **Parametri specifici**: [vedi Dashboard Parametri](link)

Per i valori attuali di RSI Entry, ADX, Stop Loss, ecc., 
consulta la [Dashboard Dinamica](https://etf.andreapavan.tech) 
o scarica il [PDF Ufficiale](link).

### Mercati Emergenti
- ...
```

**Struttura YAML**:
```yaml
families:
  equity_sviluppati:
    description: "Equity sviluppati — Large cap, ACWI, All-World"
    risk_level: "moderato"
    icon: "📈"
    parameters:
      rsi_entry_low:
        value: 45
        description: "RSI minimo per ingresso L1"
        rationale: "Equity sviluppate evitano rimbalzi da ipervenduto"
        range: [30, 70]
      rsi_entry_high:
        value: 55
        description: "RSI massimo per ingresso L1"
        rationale: "Limite superiore evita ipercomprato"
        range: [30, 70]
      adx_entry:
        value: 22
        description: "Soglia ADX minima per trend"
        rationale: "ADX ≥ 22 richiede trend forte"
        range: [10, 40]
      # ... altri parametri
```

#### IN dashboard.html

```html
<div id="param-section">
  <h2>📊 Parametri di Riferimento (LIVE dal YAML)</h2>
  
  <!-- Tab per scegliere famiglia -->
  <div id="family-tabs"></div>
  
  <!-- Contenuto dinamico caricato da /api/parameters -->
  <div id="family-content"></div>
  
  <script>
    fetch('/api/parameters')
      .then(r => r.json())
      .then(families => {
        // Renderizza tab + tabelle parametri dinamicamente
        // NON hardcoded!
      });
  </script>
</div>
```

#### IN PDF

```
Capitolo 3: Parametri per Famiglia

(Generato automaticamente da pdf_generator.py che legge YAML)

Sezione 3.1: Equity Sviluppati
  - Descrizione: Large cap stabili (ACWI, Developed Markets)
  - Rischio: Moderato
  
  Tabella 3.1a: Parametri L1 Entry
  | Parametro | Valore | Descrizione |
  | rsi_entry_low | 45 | RSI minimo per ingresso L1 |
  | rsi_entry_high | 55 | RSI massimo per ingresso L1 |
  | adx_entry | 22 | Soglia ADX minima |
  ...
```

✅ **Sincronizzazione**: 
- YAML è master
- API legge YAML e la espone come JSON
- dashboard.html carica via AJAX (sempre aggiornato)
- pdf_generator.py legge YAML e genera PDF (ogni monitor run)
- CLAUDE.md contiene solo link a dashboard/PDF (no hardcoding)

---

### Sezione 3: 7 Condizioni di Ingresso L1

#### IN CLAUDE.md

```markdown
## L1 — Ingresso (7 Condizioni TUTTE Obbligatorie)

L1 richiede che **TUTTE** le seguenti condizioni siano vere:

### 1. Allineamento
**Regola**: price > EMA20 > SMA50 > SMA200 (se mm200_filter=True)

**Razionale**: Posizionamento del prezzo nelle medie indica trend ordinato. 
Se il prezzo non è nella sequenza corretta, il trend non è confermato.

**Esempio**:
- ✅ price €105 > EMA20 €103 > SMA50 €100 → Allineato, vai avanti
- ❌ price €95 > EMA20 €105 → Disallineato, scarta

### 2. Persistenza
**Regola**: giorni_sopra_EMA20 ≥ N + slope(EMA20) > 0

**Razionale**: Non bastano pochi giorni sopra EMA20; il movimento deve 
dimostrare persistenza (N giorni). Inoltre, la pendenza della EMA20 deve 
essere positiva per confermarne la crescita.

### 3. RSI Ottimale
**Regola**: rsi_entry_low ≤ RSI ≤ rsi_entry_high (dipende dalla famiglia)

**Razionale**: RSI nel range ottimale indica momentum positivo ma non esaurito. 
Valori specifici per famiglia vedi [Parametri](link).

### 4. Distanza EMA20
**Regola**: 0% ≤ dist_EMA20 ≤ ema_dist_max

**Razionale**: Non troppo vicino (non c'è movimento), non troppo lontano 
(potrebbe essere esaurito). Massimo dipende da volatilità della famiglia.

### 5. ADX Forte
**Regola**: ADX ≥ adx_entry

**Razionale**: ADX misura la forza del trend. Soglia minima evita ingressi 
in movimenti laterali/fragili.

### 6. MACD Momentum
**Regola**: histogram > 0 AND (rising OR dist_ema20 < 2%)

**Razionale**: MACD histogram positivo indica momentum. 
Se rising: accelerazione confermata.
Se dist < 2%: anche se non rising, sei ancora molto vicino alla EMA20 (sicuro).

### 7. Spazio Residuo
**Regola**: Resistenza > min_reward_pct OR ATR×mult > min_reward_pct

**Razionale**: Prima di entrare, verificare che c'è spazio tra il prezzo attuale 
e la resistenza. Non entrare se il prezzo ha già fatto gran parte del movimento.

---

**Override Squeeze**: Se il prezzo è in compressione di volatilità E breakout 
è confermato (ADX in salita + volume in espansione), l'override dello squeeze 
bypassa il check dello spazio residuo. Consultare [Parametri Squeeze](link).

---

**Parametri per famiglia**: I valori di N (giorni), adx_entry, ema_dist_max, 
rsi_entry_low/high, min_reward_pct variano per famiglia. 
Vedi [Dashboard Parametri](link) oppure [PDF](link).
```

#### IN dashboard.html

```html
<section id="l1-conditions">
  <h3>L1 — 7 Condizioni di Ingresso</h3>
  
  <div id="conditions-list">
    <!-- Caricato dinamicamente da /api/l1-conditions -->
  </div>
  
  <script>
    fetch('/api/l1-conditions')
      .then(r => r.json())
      .then(conditions => {
        let html = '';
        conditions.forEach((cond, idx) => {
          html += `
            <div class="condition">
              <h4>${idx+1}. ${cond.name}</h4>
              <p><strong>Regola:</strong> ${cond.rule}</p>
              <p><strong>Razionale:</strong> ${cond.rationale}</p>
              <p style="font-size:0.9em;color:#888;">Parametri: <a href="#params/${cond.family_name}">vedi ${cond.family_name}</a></p>
            </div>
          `;
        });
        document.getElementById('conditions-list').innerHTML = html;
      });
  </script>
</section>
```

#### IN PDF

```
Capitolo 2: L1 Entry Conditions

2.1 Overview
L1 richiede TUTTE le 7 condizioni. Questa sezione descrive 
il razionale di ognuna.

2.2 Condizione 1: Allineamento
Regola: price > EMA20 > SMA50 > SMA200 (se mm200_filter=True)
Razionale: Posizionamento del prezzo nelle medie ...

[Generato da pdf_generator.py che legge da YAML]
```

✅ **Sincronizzazione**: 
- CLAUDE.md: Spiegazione + link
- dashboard.html: Carica da API
- PDF: Auto-generato da YAML
- YAML: Metadati e descrizioni

---

### Sezione 4: Regole di Uscita L1

Stessa struttura di Sezione 3.

#### IN CLAUDE.md

```markdown
## L1 — Uscita (6 Regole di Priorità)

| Priorità | Regola | Trigger | Azione |
|:---:|--------|---------|--------|
| 1 | F — Kill Switch | Calo giornaliero ≤ −3% | USCITA totale |
| 2 | A — Stop Loss | Prezzo < EMA20 da 3+ giorni | USCITA totale |
| 3 | B — Trailing Stop | EMA10 < EMA20 | USCITA totale |
| 4 | C — Stanchezza | RSI era ≥70, scende <70 | USCITA totale |
| 5 | E — ADX Debole | ADX < 18 + prezzo < EMA20 | USCITA totale |
| 6 | D — Piede Dentro 90% | RSI > 78 | USCITA 90%, mantieni 10% + XEON |

**Nota**: La Regola D è la sola che non chiude al 100%. 
Vedi [Logica Piede Dentro](link) per dettagli.

Per verificare quale regola è attiva per la tua famiglia, 
consulta [Parametri](link).
```

---

## Checklist di Sincronizzazione (Quando Modifichi)

### Se Modifichi un Parametro nel YAML

```bash
# 1. Edita YAML
vi config/etf_families.yaml
# es. adx_entry: 22 → 25

# 2. Committa
git add config/etf_families.yaml
git commit -m "Increase adx_entry for equity_sviluppati: 22 → 25"

# 3. Deploy
./deploy.sh

# 4. Verifica
# - Dashboard: ricarica → vedi 25 (via API live)
# - PDF: scarica → vedi 25 (auto-generato)
# - CLAUDE.md: NON modificare (solo link)
```

### Se Aggiungi una Nuova Condizione L1

```bash
# 1. CLAUDE.md: Scrivi spiegazione + razionale
# 2. YAML: Aggiungi metadati alla condizione
# 3. pdf_generator.py: Aggiorna template (se necessario)
# 4. API: Aggiorna /api/l1-conditions (se nuovo endpoint)
# 5. dashboard.html: Aggiorna visualizzazione (se nuovo campo)
# 6. Backtest: Testa la nuova condizione su 2+ anni di dati
# 7. ADR: Documenta la decisione (ADR-NNN)
# 8. Commit: Un'unica PR con tutte le modifiche
```

---

## Checklist di Allineamento Attuale (2026-07-22)

- [ ] CLAUDE.md contiene 7 condizioni L1? ✅
- [ ] dashboard.html mostra 7 condizioni? ❌ (mostra 6, da aggiornare)
- [ ] /api/parameters espone i parametri? ❌ (non implementato, pianificato)
- [ ] dashboard.html carica da API (non hardcoded)? ❌ (hardcoded attualmente)
- [ ] PDF è generato da YAML? ⚠️ (parziale, da completare)
- [ ] CLAUDE.md ha link a dashboard/PDF? ⚠️ (alcuni hardcoded, da rimuovere)
- [ ] YAML ha tutti i metadati (descrizione + razionale)? ⚠️ (da estendere)

---

## Piano di Implementazione

**Fase 1** (FATTO 22/07):
- ✅ CLAUDE.md aggiornato a 7 condizioni
- ✅ dashboard.html aggiornato a 7 condizioni (via script Python)

**Fase 2** (PIANIFICATO):
- [ ] Estendere YAML con metadati completi
- [ ] Implementare /api/parameters endpoint
- [ ] Dashboard carica da API (AJAX)
- [ ] PDF generato automaticamente

**Fase 3** (DOPO FASE 2):
- [ ] Pulire CLAUDE.md (rimuovere hardcoding, aggiungere link)
- [ ] Verificare sincronizzazione end-to-end
