---
name: etf_directa_management
description: Come gestire gli ETF Directa nel sistema di monitoraggio
metadata: 
  node_type: memory
  type: reference
  date: 2026-07-07
  originSessionId: c74b19e0-7264-4b9a-a514-edc7242ac1fd
---

# Gestione ETF Directa (MTA - Borsa Italiana)

## ✅ Procedura Corretta

Quando un ETF è su **Directa (MTA - Borsa Italiana)**, usare questo approccio:

### 1. Prezzo da Directa come Base
- Inserisci il prezzo reale da Directa nell'Excel (es. WAT: 70.98€)
- Questo diventa il prezzo di partenza nel sistema

### 2. Ticker Handling
- **Se esiste su Yahoo Finance**: usa il ticker Yahoo (es. WAT.PA)
  - Il monitor fetcherà i prezzi reali automaticamente
  - I dati si aggiornano quotidianamente
  
- **Se NON esiste su Yahoo Finance**: usa il ticker locale (es. USHYC)
  - Aggiungi fallback nel data_fetcher
  - Il sistema mantiene il prezzo dall'Excel come base
  - I prezzi storici rimangono nel database

### 3. Salvataggio in Memory
Quando scopri un nuovo ETF Directa, aggiorna MEMORY.md con:
```
- USHYC (LU1435356065): Directa/MTA, prezzo €10.502, NO su Yahoo Finance
- WAT.PA (FR0010527275): Directa/MTA, prezzo €70.98, SÌ su Yahoo Finance come WAT.PA
```

## ETF Directa Registrati

| ETF | Ticker | Prezzo | Directa | Yahoo | Note |
|-----|--------|--------|---------|-------|------|
| Amundi USD HY Corp Bond ESG | USHYC | €10.502 | ✅ | ❌ | Locale MTA |
| Amundi MSCI Water | WAT.PA | €70.98 | ✅ | ✅ | Parigi |

## Comando per Verificare Yahoo Finance
```bash
python3 -c "import yfinance as yf; print(yf.Ticker('TICKER').history(period='5d'))"
```

## Azione Futura
Se Yahoo Finance aggiunge USHYC in futuro, aggiornare semplicemente il ticker nell'Excel a "USHYC" e il sistema lo fetcherà automaticamente.
