"""
justetf_fetcher.py - Recupero dati ETF da JustETF
===================================================
Sostituisce yfinance come fonte dati principale.
Usa la libreria justetf-scraping per ottenere:
- Prezzi storici (Close) tramite load_chart()
- Quote real-time tramite API JustETF
- Metadati ETF (TER, AUM, holdings)
"""

import logging
import time
import pandas as pd
from datetime import datetime

import justetf_scraping as jes

logger = logging.getLogger(__name__)


class JustETFDataFetcher:
    """Recupera dati ETF da JustETF usando ISIN come identificatore"""

    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit  # secondi tra richieste
        self.cache = {}
        self.cache_duration = 3600  # 1 ora
        self._last_request_time = 0

    def _wait_rate_limit(self):
        """Rispetta il rate limit tra richieste"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    def get_historical_data(self, isin: str, days: int = 200) -> pd.DataFrame:
        """
        Recupera storico prezzi Close da JustETF.

        Args:
            isin: Codice ISIN dell'ETF (es. IE00B4L5Y983)
            days: Numero di giorni di storico richiesti

        Returns:
            DataFrame con colonna 'Close' e index=Date.
            Vuoto se errore.
        """
        cache_key = f"hist_{isin}_{datetime.now().strftime('%Y%m%d')}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            self._wait_rate_limit()
            logger.info(f"  Scaricamento storico JustETF per {isin}...")
            df = jes.load_chart(isin)

            if df.empty:
                logger.warning(f"  Nessun dato storico per {isin}")
                return pd.DataFrame()

            # Prendi solo gli ultimi N giorni
            result = pd.DataFrame({'Close': df['quote']})
            result.index.name = 'Date'

            if len(result) > days:
                result = result.tail(days)

            logger.info(f"  Scaricati {len(result)} giorni per {isin}")
            self.cache[cache_key] = result
            return result

        except Exception as e:
            logger.error(f"  Errore storico JustETF {isin}: {e}")
            return pd.DataFrame()

    def get_current_price(self, isin: str) -> dict:
        """
        Recupera prezzo corrente da JustETF.

        Returns:
            Dict con 'close', 'date', 'source' oppure None
        """
        cache_key = f"price_{isin}_{datetime.now().strftime('%Y%m%d_%H')}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            self._wait_rate_limit()

            # Usa chart data per ottenere ultimo prezzo
            df = jes.load_chart(isin)
            if df.empty:
                return None

            last_row = df.iloc[-1]
            last_date = df.index[-1]

            result = {
                'close': float(last_row['quote']),
                'date': str(last_date),
                'source': 'justetf'
            }

            self.cache[cache_key] = result
            return result

        except Exception as e:
            logger.error(f"  Errore prezzo JustETF {isin}: {e}")
            return None

    def get_etf_metadata(self, isin: str) -> dict:
        """
        Recupera metadati ETF: TER, AUM, inception date, ecc.

        Returns:
            Dict con metadati oppure None
        """
        try:
            self._wait_rate_limit()
            overview = jes.get_etf_overview(isin)

            return {
                'isin': isin,
                'name': overview.get('name'),
                'ter': overview.get('ter'),
                'fund_size': overview.get('fund_size'),
                'countries': overview.get('countries', []),
                'sectors': overview.get('sectors', []),
                'holdings': overview.get('holdings', []),
                'source': 'justetf'
            }

        except Exception as e:
            logger.error(f"  Errore metadati JustETF {isin}: {e}")
            return None

    def validate_isin(self, isin: str) -> bool:
        """Verifica che un ISIN restituisca dati su JustETF"""
        try:
            self._wait_rate_limit()
            df = jes.load_chart(isin)
            return not df.empty
        except Exception:
            return False


def test_fetcher():
    """Test del JustETF data fetcher"""
    fetcher = JustETFDataFetcher(rate_limit=1.5)

    test_etfs = [
        ("IE00B4L5Y983", "iShares Core MSCI World"),
        ("LU1681043599", "Amundi MSCI World"),
        ("FR0010315770", "Amundi MSCI World Swap II"),
    ]

    print("=" * 60)
    print("TEST JUSTETF DATA FETCHER")
    print("=" * 60)

    successi = 0
    for isin, nome in test_etfs:
        print(f"\n{nome} ({isin}):")

        # Test storico
        hist = fetcher.get_historical_data(isin, days=60)
        if not hist.empty:
            print(f"  Storico: {len(hist)} giorni")
            print(f"  Ultimo prezzo: {hist['Close'].iloc[-1]:.2f}")
            successi += 1
        else:
            print(f"  Storico non disponibile")

    print(f"\nRISULTATO: {successi}/{len(test_etfs)} ETF trovati")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_fetcher()
