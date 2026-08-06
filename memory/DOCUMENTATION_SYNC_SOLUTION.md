---
name: documentation_sync_solution
description: Piano di implementazione — Una sola fonte di verità (YAML) per parametri
metadata: 
  node_type: memory
  type: project
  date: 2026-07-22
  originSessionId: 2f9d89cf-c8ec-4cb5-8314-7d617accdaa5
  modified: 2026-07-22T20:44:37.284Z
---

# Soluzione di Sincronizzazione Documentale — Una Sola Fonte di Verità

## Problema Attuale

Hai **3 fonti separate e disallineate**:

```
1. CLAUDE.md (repo)
   ├─ Contiene parametri hardcoded
   ├─ Aggiornato manualmente
   └─ Sempre stale rispetto al codice
   
2. dashboard.html (browser)
   ├─ Tabelle di parametri hardcoded
   ├─ Descrizioni copiate da CLAUDE.md
   └─ Ultimo aggiornamento: 22/07 (ma cambia ogni settimana)
   
3. PDF generato (app.py)
   ├─ Generato da pdf_generator.py
   ├─ Legge parzialmente il YAML
   └─ Non contiene tutte le descrizioni / razionale
```

**Conseguenza**: Quando cambi un parametro nel YAML, devi aggiornare manualmente CLAUDE.md + dashboard.html + rigenerare PDF. Nessuno dei tre resta sincronizzato.

---

## Soluzione: YAML Come Fonte Unica

```
┌─────────────────────────────────┐
│  config/etf_families.yaml       │
│  (FONTE DI VERITÀ UNICA)        │
│                                 │
│  - Tutti i parametri            │
│  - Tutte le descrizioni         │
│  - Tutte le note di razionale   │
└────────────┬────────────────────┘
             │
    ┌────────┴────────┬────────────┬──────────────┐
    ↓                 ↓            ↓              ↓
[app.py]         [pdf_gen.py]  [CLI doc]   [dashboard.html]
/api/params      PDF generato   markdown   carica live da API
(JSON)           automaticamente             via AJAX
```

---

## Implementazione Fase 1: Estendere YAML (1 ora)

### Struttura Attuale del YAML

```yaml
families:
  equity_sviluppati:
    description: "Equity sviluppati — Large cap, ACWI, All-World"
    rsi_entry_low: 45
    rsi_entry_high: 55
    adx_entry: 22
    ...
```

### Struttura Nuova (Aggiunta Metadati)

```yaml
families:
  equity_sviluppati:
    # --- METADATA ---
    description: "Equity sviluppati — Large cap, ACWI, All-World"
    family_order: 1
    icon: "📈"
    risk_level: "moderato"  # basso, moderato, alto, molto_alto
    
    # --- PARAMETERS CON DESCRIZIONE ---
    parameters:
      rsi_entry_low:
        value: 45
        description: "RSI minimo per ingresso L1 (non troppo debole)"
        rationale: "Equity sviluppate accettano RSI > 45 per evitare rimbalzi da ipervenduto"
        range: [30, 70]
        
      rsi_entry_high:
        value: 55
        description: "RSI massimo per ingresso L1 (non troppo caldo)"
        rationale: "Limite superiore a 55 evita ipercomprato iniziale"
        range: [30, 70]
        
      adx_entry:
        value: 22
        description: "Soglia ADX minima per confermare trend"
        rationale: "ADX ≥ 22 richiede trend FORTE, non laterale"
        range: [10, 40]
        
      # ... altri parametri seguono lo stesso formato
    
    # --- L1 ENTRY LOGIC ---
    l1_conditions:
      - name: "Allineamento"
        rule: "price > EMA20 > SMA50 > SMA200 (se mm200_filter=True)"
        description: "Posizionamento prezzo nelle tre medie"
        
      - name: "Persistenza"
        rule: "days_above_EMA20 ≥ N + slope(EMA20) > 0"
        description: "Movimento confermato, non one-off"
        
      # ... tutte e 7 le condizioni documentate
    
    # --- L1 EXIT LOGIC ---
    l1_exits:
      - priority: 1
        rule: "F — Kill Switch"
        trigger: "Calo giornaliero ≤ −3%"
        action: "USCITA totale"
        active_for: ["equity_sviluppati", "emergenti", "growth", ...]
        
      # ... tutte e 6 le regole
    
    # --- L0 ENTRY LOGIC ---
    l0_conditions:
      - name: "Drawdown"
        rule: "price ≥ L0_DRAWDOWN% sotto il picco (ultimi 90gg)"
        description: "Calo rilevante, non puntuale"
        
      # ... tutte e 4 le condizioni
    
    # --- STOP LOSS & TRAILING ---
    stop_loss:
      sl_initial_pct:
        value: 0.05
        description: "Protezione iniziale 5%"
        rationale: "Equity sviluppate tollerano max 5% di drawdown da entry"
        
      trailing_levels:
        - gain_threshold_pct: 0
          distance_pct: 0.08
          description: "Inizio: 8% di distanza dal prezzo"
          
        - gain_threshold_pct: 5
          distance_pct: 0.075
          description: "Dopo +5% di guadagno: stringe a 7.5%"
          
        # ... altri tier
```

### Struttura YAML Risultante

**File**: `config/etf_families_extended.yaml`
- ~800 righe (esteso dal YAML attuale di ~300)
- Machine-readable: parsa in Python
- Human-readable: commenti chiari
- Versionabile: git history

---

## Implementazione Fase 2: API Endpoint (30 min)

### `/api/parameters` — Nuovo Endpoint in app.py

```python
@app.route('/api/parameters', methods=['GET'])
def get_parameters():
    """
    Legge config/etf_families_extended.yaml
    Ritorna JSON con TUTTI i parametri + descrizioni
    """
    with open('config/etf_families_extended.yaml', 'r') as f:
        families = yaml.safe_load(f)['families']
    
    result = {}
    for family_name, family_data in families.items():
        result[family_name] = {
            'description': family_data.get('description'),
            'icon': family_data.get('icon'),
            'risk_level': family_data.get('risk_level'),
            'parameters': family_data.get('parameters', {}),
            'l1_conditions': family_data.get('l1_conditions', []),
            'l1_exits': family_data.get('l1_exits', []),
            'l0_conditions': family_data.get('l0_conditions', []),
            'stop_loss': family_data.get('stop_loss', {}),
        }
    
    return jsonify(result)

@app.route('/api/parameters/<family_name>', methods=['GET'])
def get_parameters_by_family(family_name):
    """Parametri di una sola famiglia"""
    with open('config/etf_families_extended.yaml', 'r') as f:
        families = yaml.safe_load(f)['families']
    
    if family_name not in families:
        return jsonify({'error': f'Family {family_name} not found'}), 404
    
    return jsonify(families[family_name])
```

### Test dell'API

```bash
# Tutti i parametri
curl https://etf.andreapavan.tech/api/parameters | jq .

# Solo equity_sviluppati
curl https://etf.andreapavan.tech/api/parameters/equity_sviluppati | jq .
```

---

## Implementazione Fase 3: Dashboard HTML Dinamico (1 ora)

### dashboard.html — Nuova Sezione "Parametri di Riferimento"

```html
<!-- PARAMETRI DI RIFERIMENTO — Caricati dinamicamente da API -->
<div id="param-section" class="section">
  <h2>📊 Parametri di Riferimento (LIVE dal YAML)</h2>
  
  <div id="family-tabs" style="display:flex;gap:10px;margin-bottom:20px;">
    <!-- I tab vengono generati via JavaScript -->
  </div>
  
  <div id="family-content"></div>
  
  <div id="last-update" style="font-size:0.8em;color:#888;margin-top:20px;">
    Ultimo aggiornamento: <span id="timestamp">--</span>
  </div>
</div>

<script>
async function loadParameters() {
  try {
    const response = await fetch('/api/parameters');
    const families = await response.json();
    
    // Crea i tab
    const tabsContainer = document.getElementById('family-tabs');
    Object.keys(families).forEach(familyName => {
      const tab = document.createElement('button');
      tab.textContent = families[familyName].icon + ' ' + familyName;
      tab.onclick = () => showFamily(familyName, families[familyName]);
      tabsContainer.appendChild(tab);
    });
    
    // Mostra il primo
    const firstFamily = Object.keys(families)[0];
    showFamily(firstFamily, families[firstFamily]);
    
    // Timestamp
    document.getElementById('timestamp').textContent = new Date().toLocaleString();
    
  } catch (error) {
    console.error('Errore caricamento parametri:', error);
    document.getElementById('family-content').innerHTML = 
      '<p style="color:red;">Errore: impossibile caricare parametri da /api/parameters</p>';
  }
}

function showFamily(familyName, familyData) {
  const content = document.getElementById('family-content');
  
  let html = `<h3>${familyData.icon || '📈'} ${familyName}</h3>`;
  html += `<p><strong>Rischio:</strong> ${familyData.risk_level}</p>`;
  html += `<p>${familyData.description}</p>`;
  
  // Tabella parametri
  html += '<h4>Parametri</h4><table class="param-table">';
  html += '<thead><tr><th>Parametro</th><th>Valore</th><th>Descrizione</th><th>Razionale</th></tr></thead><tbody>';
  
  Object.entries(familyData.parameters || {}).forEach(([paramName, paramData]) => {
    html += `
      <tr>
        <td><strong>${paramName}</strong></td>
        <td style="text-align:center;">${paramData.value}</td>
        <td>${paramData.description}</td>
        <td style="font-size:0.9em;color:#888;">${paramData.rationale || '--'}</td>
      </tr>
    `;
  });
  
  html += '</tbody></table>';
  
  // L1 Conditions
  if (familyData.l1_conditions && familyData.l1_conditions.length > 0) {
    html += '<h4>L1 Condizioni di Ingresso</h4><ul>';
    familyData.l1_conditions.forEach(cond => {
      html += `<li><strong>${cond.name}:</strong> ${cond.rule}<br/><em>${cond.description}</em></li>`;
    });
    html += '</ul>';
  }
  
  // L1 Exits
  if (familyData.l1_exits && familyData.l1_exits.length > 0) {
    html += '<h4>L1 Regole di Uscita</h4><table class="param-table">';
    html += '<thead><tr><th>Priorità</th><th>Regola</th><th>Trigger</th><th>Azione</th></tr></thead><tbody>';
    familyData.l1_exits.forEach(exit => {
      html += `
        <tr>
          <td>${exit.priority}</td>
          <td>${exit.rule}</td>
          <td>${exit.trigger}</td>
          <td>${exit.action}</td>
        </tr>
      `;
    });
    html += '</tbody></table>';
  }
  
  // L0 Conditions
  if (familyData.l0_conditions && familyData.l0_conditions.length > 0) {
    html += '<h4>L0 Condizioni di Ingresso</h4><ul>';
    familyData.l0_conditions.forEach(cond => {
      html += `<li><strong>${cond.name}:</strong> ${cond.rule}<br/><em>${cond.description}</em></li>`;
    });
    html += '</ul>';
  }
  
  content.innerHTML = html;
}

// Carica al load della pagina
document.addEventListener('DOMContentLoaded', loadParameters);

// Ricarica ogni 5 minuti (tiene sincronizzato se il YAML cambia)
setInterval(loadParameters, 5 * 60 * 1000);
</script>
```

---

## Implementazione Fase 4: PDF Automatico Aggiornato (45 min)

### pdf_generator.py — Legge YAML Esteso

```python
def generate_pdf_from_yaml(yaml_path, output_path):
    """Legge il YAML esteso, genera PDF completo"""
    
    with open(yaml_path, 'r') as f:
        families = yaml.safe_load(f)['families']
    
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    # Titolo
    story.append(Paragraph("ETF Monitor — Parametri Ufficiali", styles['Title']))
    story.append(Paragraph(
        f"Generato automaticamente da config/etf_families.yaml<br/>{datetime.now().strftime('%d/%m/%Y %H:%M')}",
        styles['Normal']
    ))
    story.append(PageBreak())
    
    # Per ogni famiglia
    for family_name, family_data in families.items():
        story.append(Paragraph(f"{family_data.get('icon', '')} {family_name}", styles['Heading2']))
        story.append(Paragraph(f"Rischio: {family_data.get('risk_level', '--')}", styles['Normal']))
        story.append(Paragraph(family_data.get('description', ''), styles['Normal']))
        
        # Tabella parametri
        params = family_data.get('parameters', {})
        if params:
            story.append(Paragraph("Parametri", styles['Heading3']))
            
            table_data = [['Nome', 'Valore', 'Descrizione']]
            for pname, pdata in params.items():
                table_data.append([
                    pname,
                    str(pdata.get('value')),
                    pdata.get('description', '')
                ])
            
            table = Table(table_data, colWidths=[100*mm, 40*mm, 80*mm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a5490')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ]))
            story.append(table)
        
        story.append(Spacer(1, 12))
        story.append(PageBreak())
    
    doc.build(story)
    print(f"✅ PDF generato: {output_path}")
```

### Integrazione in monitor.py

```python
# Al termine di ogni ciclo di monitor:
from pdf_generator import generate_pdf_from_yaml

def run_monitor():
    # ... fetch, calcoli, salvataggi ...
    
    # STEP FINALE: Rigenera PDF
    generate_pdf_from_yaml(
        'config/etf_families_extended.yaml',
        'data/ETF_Monitor_Parametri_Ufficiali.pdf'
    )
    print("✅ PDF sincronizzato con YAML")
```

---

## Implementazione Fase 5: CLAUDE.md Come Riferimento Concettuale (30 min)

### Nuovo Ruolo di CLAUDE.md

**DA FARE**:
- ✅ Tenere la sezione teorica (spiegazione di L0/L1/L2, regole di uscita, ecc)
- ✅ Aggiungere link al PDF/Dashboard per i valori numerici: "Vedi [Parametri Ufficiali](link) per i valori attuali"
- ❌ RIMUOVERE tabelle hardcoded di parametri
- ❌ RIMUOVERE valori numerici (rsi_entry_low: 45, ecc)

**Esempio**:

```markdown
## L1 — Ingresso (7 Condizioni TUTTE Obbligatorie)

L1 richiede che TUTTE le seguenti condizioni siano vere:

1. **Allineamento**: Prezzo > EMA20 > SMA50 > SMA200*
2. **Persistenza**: Giorni sopra EMA20 ≥ N + slope(EMA20) > 0
3. **RSI Ottimale**: RSI entro il range della famiglia
4. **Distanza EMA20**: 0% ≤ dist_EMA20 ≤ max della famiglia
5. **ADX Forte**: ADX ≥ soglia della famiglia
6. **MACD Momentum**: histogram > 0 AND (rising OR dist < 2%)
7. **Spazio Residuo**: Resistenza > min oppure ATR×mult > min

**Parametri specifici per famiglia**: Vedi la [Dashboard Parametri](https://etf.andreapavan.tech) 
o scarica il [PDF Ufficiale](https://etf.andreapavan.tech/api/download-parameters-pdf)

* SMA200 richiesto solo se mm200_filter=True per la famiglia
```

---

## Timeline di Implementazione

| Fase | Task | Tempo | Dipendenze |
|------|------|-------|------------|
| **1** | Estendere YAML con metadati | 1h | -- |
| **2** | Implementare /api/parameters | 30m | Fase 1 |
| **3** | Dashboard HTML dinamico | 1h | Fase 2 |
| **4** | pdf_generator.py aggiornato | 45m | Fase 1 |
| **5** | Pulire CLAUDE.md | 30m | Fase 4 |
| **6** | Test end-to-end | 30m | Tutte |
| **7** | Deploy VPS | 30m | Fase 6 |

**Totale**: ~5 ore lavoro

---

## Verifica di Correttezza (Dopo Implementazione)

Checklist:
- [ ] Modifica parametro nel YAML (es. adx_entry: 22 → 23)
- [ ] Ricarica dashboard → vedi il nuovo valore (AJAX)
- [ ] Genera PDF → vedi il nuovo valore nel PDF
- [ ] Controlla CLAUDE.md → nessun valore hardcoded (link al dashboard)
- [ ] Committa YAML + app.py + pdf_generator.py
- [ ] Deploy VPS
- [ ] Verifica che `/api/parameters` ritorni JSON corretto

---

## Benefici Finali

✅ **Una sola fonte di verità** (YAML)
✅ **Dashboard sempre aggiornato** (AJAX live)
✅ **PDF rigenerato ogni ciclo** (automatico)
✅ **CLAUDE.md rimane pulito** (solo concetti, non numeri)
✅ **Git history coerente** (modifica unica nel YAML)
✅ **Nessun disallineamento futuro** (impossibile)

---

## Possibilità di Rollout

Questo cambio è **backward-compatible**:
- ✅ Mantiene tutti i parametri esistenti
- ✅ Aggiunge solo metadati non-invasivi
- ✅ API ritorna JSON (facile per altri consumatori)
- ✅ PDF rimane un PDF (leggibile)

Puoi implementarlo in una pull request senza impattare il resto del sistema.
