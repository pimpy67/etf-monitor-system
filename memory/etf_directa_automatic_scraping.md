---
name: etf_directa_automatic_scraping
description: Piano per scaricare automaticamente i prezzi degli ETF Directa
metadata: 
  node_type: memory
  type: project
  status: IN PROGRESS
  date: 2026-07-07
  originSessionId: c74b19e0-7264-4b9a-a514-edc7242ac1fd
---

# Piano Aggiornamento Automatico ETF Directa

## Problema
- USHYC (LU1435356065) non è su Yahoo Finance (ticker locale MTA)
- Non è su nessuna API free (testato: Finnhub, Alpha Vantage, Twelve Data, Polygon)
- Devo trovare un sistema automatico per aggiornare i prezzi

## Soluzione Scelta: Scraping da Investing.com

### Fase 1: Implementazione Scraper Selenium ⏳ IN PROGRESS
**File**: `data_fetcher.py` → funzione `get_price_from_investing(isin)`

Requisiti:
- Selenium + Chrome/Firefox driver
- Retry logic (max 3 tentativi)
- Timeout: 10 secondi
- User-Agent rotation

```python
def get_price_from_investing(isin: str) -> dict:
    """
    Scrapa prezzo da Investing.com usando ISIN
    Returns: {'price': 10.502, 'date': '2026-07-07', 'source': 'investing.com'}
    """
    # TODO: implementare
```

### Fase 2: Integrazione nel Monitor
**File**: `monitor.py` → `fetch_price()`

Fallback chain:
```
1. Prova Yahoo Finance
2. Se fallisce → Prova Investing.com (scraping)
3. Se fallisce → Usa prezzo precedente dal DB
```

### Fase 3: Scheduling
Aggiungi nel cron/scheduler:
```
Ogni giorno ore 16:00 CEST: update_etf_prices() con scraping Investing
```

## ETF da Monitorare

| Ticker | ISIN | Sorgente | Stato |
|--------|------|----------|-------|
| USHYC | LU1435356065 | Investing.com | ⏳ Scraper |
| WAT.PA | FR0010527275 | Yahoo Finance | ✅ OK |

## Alternative Considerate

| Soluzione | Costo | Complessità | Affidabilità | Note |
|-----------|-------|------------|--------------|------|
| API a pagamento (Alpha Vantage Pro) | $$ | Bassa | Alta | ✅ Migliore, ma costo |
| Scraping Investing.com (Selenium) | FREE | Media | Media | ⏳ In sviluppo |
| Scraping Directa stessa | FREE | Alta | Bassa | Richiede login |
| Yahoo Finance fallback | FREE | Bassa | Alta | ✅ Per WAT.PA |

## Next Steps

1. **Oggi**: Implementare scraper base Investing.com
2. **Domani**: Testare su USHYC in produzione
3. **Prossima settimana**: Valutare upgrade API a pagamento se scraping è unreliable
4. **Lungo termine**: Se budget permette, usare API affidabile

## Note Importanti

⚠️ **Scraping da Investing.com è resistente anti-bot**
- Possibili blocchi di IP
- Soluzione: rotation user-agent, delay tra richieste
- Contingency: mantenere fallback al prezzo Excel

💡 **Se consideriamo API a pagamento**:
- Alpha Vantage: $20/mese per tier plus
- Finnhub Pro: €100+/mese
- Polygon Pro: €200+/mese

Conviene se: >5 ETF locali da tracciare
