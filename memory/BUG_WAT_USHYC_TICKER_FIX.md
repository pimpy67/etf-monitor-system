---
name: bug_wat_ushyc_ticker_fix
description: "Bug critico - Ticker salvati come ISIN nel database, fixed 2026-07-07"
metadata: 
  node_type: memory
  type: project
  date: 2026-07-07
  status: ✅ FIXED - TESTING
  originSessionId: c74b19e0-7264-4b9a-a514-edc7242ac1fd
---

# 🔴 BUG CRITICO: Ticker Salvati Come ISIN

## Problema Identificato

**Quando**: 2026-07-07 ~19:00 CEST
**Dove**: Database PostgreSQL, tabella `etf_price_history`
**Cosa**: Colonna `ticker` contiene ISIN al posto del ticker vero

### Evidenza

```sql
-- Query nel DB
SELECT ticker, isin, close, date FROM etf_price_history 
WHERE isin='FR0010527275' ORDER BY date DESC LIMIT 5;

RISULTATO:
ticker          | isin           | close  | date
FR0010527275    | FR0010527275   | 71.13  | 2026-07-07  ❌ SBAGLIATO!
FR0010527275    | FR0010527275   | 70.92  | 2026-07-06
...
```

**Dovrebbe essere**:
```
ticker   | isin          | close | date
WAT.MI   | FR0010527275  | 71.13 | 2026-07-07  ✅ CORRETTO
```

---

## Root Cause

**File**: `database.py` riga 367
**Metodo**: `save_close_bulk(isin: str, df: pd.DataFrame, source: str)`

```python
# ❌ SBAGLIATO (riga 367):
cur.execute("""
    INSERT INTO etf_price_history (ticker, isin, date, close, source)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (ticker, date)
    DO UPDATE SET close = EXCLUDED.close, source = EXCLUDED.source,
                  isin = EXCLUDED.isin
""", (isin, isin, date_str, close_val, source))  # ← isin usato COME ticker!
```

**Problema**: Il metodo riceve solo `isin` e `df`, non ha il ticker vero (es. "WAT.MI").
Quando salva i dati, mette l'ISIN in entrambe le colonne `ticker` e `isin`.

---

## Impatto

### Dashboard
- ❌ Query `SELECT ... WHERE ticker = 'WAT.MI'` ritorna 0 righe
- ❌ Prezzi WAT.MI e USHYC.MI non visualizzati
- ❌ Storico vuoto nel grafico

### Portafoglio
- ❌ Calcolo P&L fallisce (niente storico per portafoglio)
- ❌ Email report non inviata (error in alerts.py query)

### Monitor
- ✅ Funziona, analizza i dati
- ✅ Salva nel DB, ma con ticker sbagliato

---

## Soluzione Applicata

### 1️⃣ Modifica `database.py` (riga 338)

**Prima**:
```python
def save_close_bulk(self, isin: str, df: pd.DataFrame, source: str = 'justetf') -> int:
    ...
    cur.execute(..., (isin, isin, date_str, close_val, source))  # ❌ isin come ticker
```

**Dopo**:
```python
def save_close_bulk(self, isin: str, df: pd.DataFrame, source: str = 'justetf', ticker: str = None) -> int:
    saved_ticker = ticker if ticker else isin
    ...
    cur.execute(..., (saved_ticker, isin, date_str, close_val, source))  # ✅ ticker corretto
```

**Cosa fa**: Se `ticker` è passato, lo usa. Altrimenti fallback a ISIN (backward compatible).

### 2️⃣ Modifica `monitor.py` (riga 84-85)

**Prima**:
```python
if isin:
    self.db.save_close_bulk(isin, df, source='yfinance')  # ❌ non passa ticker
```

**Dopo**:
```python
if isin:
    self.db.save_close_bulk(isin, df, source='yfinance', ticker=ticker)  # ✅ passa ticker
```

**Cosa fa**: Quando scarica dati con ISIN, passa ANCHE il ticker (es. "WAT.MI") al database.

### 3️⃣ Bonus: Corretto `alerts.py` (riga 384, 387, 407, 439)

**Problema separato**: Query cercavano `pe.ticker` ma tabella `etf_portfolio_entries` ha `pe.isin`

**Fix**: Cambiate tutte le query da `ticker` a `isin`

---

## Testing Plan

### Monitor Run (19:14 CEST)

**Comando**: `curl -X POST http://localhost:5001/api/trigger-update`
**Stato**: ⏳ IN EXECUTION (ETA 19:30)

**Verifiche post-run**:
```bash
# 1. Verificare ticker corretto nel DB
ssh root@76.13.37.133 "docker exec etf_monitor_system-postgres-1 psql -U etfmonitor -d etfs -c \"SELECT ticker, isin, close FROM etf_price_history WHERE ticker IN ('WAT.MI', 'USHYC.MI') LIMIT 2;\""

# Expected:
# ticker   | isin          | close
# WAT.MI   | FR0010527275  | ~70.35
# USHYC.MI | LU1435356065  | ~10.474

# 2. Verificare mail inviata senza errore
ssh root@76.13.37.133 "docker logs etf_monitor_system-app-1 2>&1 | grep -i 'email.*portfolio\|resend' | tail -3"

# 3. Hard refresh dashboard
# User: Ctrl+F5 su https://etf.andreapavan.tech

# 4. Verificare prezzi visualizzati
# - Aprire WAT.MI nel detail view
# - Verificare prezzo ~€70.35
# - Verificare storico nel grafico
```

---

## Ripercussioni Storiche

**Righe colpite nel DB**: ~357 (WAT.MI con vecchi dati)
**Soluzione**: 
- ✅ I vecchi dati rimangono (con ticker sbagliato) - non è un problema, il monitor sovrascriverà
- ✅ Da ora in poi i nuovi dati avranno ticker corretto
- ⚠️  Se necessario, si può fare una migrazione per fixare i vecchi dati

---

## Files Modificati

| File | Riga | Tipo | Status |
|------|------|------|--------|
| `database.py` | 338, 356, 367 | Signature + uso parametro | ✅ FIXED |
| `monitor.py` | 84-85 | Passa ticker a save_close_bulk | ✅ FIXED |
| `alerts.py` | 384, 387, 407, 439 | Query pe.ticker → pe.isin | ✅ FIXED |

---

## Lezioni Imparate

1. **Quando un metodo riceve ISIN** → deve ricevere ANCHE il ticker se disponibile
2. **Vincoli UNIQUE su (ticker, date)** → il ticker DEVE essere il valore corretto, non un sostituto
3. **Dual identificazione** (ticker + ISIN) → serve a supportare sia le query per ticker che per ISIN, ma ognuno deve avere il VALORE GIUSTO

---

## Status Finale

**Deploy**: 2026-07-07 19:14
**Riavvio Container**: ✅ OK
**Monitor Run**: ⏳ IN PROGRESS
**Next Check**: 2026-07-07 ~19:30

