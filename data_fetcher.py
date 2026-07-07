"""
data_fetcher.py - Recupero dati ETF da Yahoo Finance + Investing.com
=====================================================================
Usa yfinance per OHLCV completo (Open, High, Low, Close, Volume).
Ticker nel formato Yahoo Finance (es. SWDA.L, CSPX.L, EIMI.L).
Fallback: scraping da Investing.com per ticker locali (es. USHYC).
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from typing import Optional


class ETFDataFetcher:
    """Recupera dati OHLCV degli ETF da Yahoo Finance."""

    def __init__(self, rate_limit: float = 0.5):
        self.rate_limit = rate_limit
        self.cache      = {}
        self.cache_ttl  = 3600  # 1 ora

    def _cached(self, key: str):
        entry = self.cache.get(key)
        if entry and (time.time() - entry['ts']) < self.cache_ttl:
            return entry['data']
        return None

    def _store(self, key: str, data):
        self.cache[key] = {'data': data, 'ts': time.time()}

    def get_historical_data(self, ticker: str, days: int = 250) -> pd.DataFrame:
        """
        Recupera storico OHLCV per un ETF.

        Args:
            ticker: Ticker Yahoo Finance (es. 'SWDA.L', 'CSPX.L')
            days:   Numero di giorni storici richiesti

        Returns:
            DataFrame con colonne Open, High, Low, Close, Volume (index=Date, tz-naive)
            oppure DataFrame vuoto se fallisce.
        """
        cache_key = f"{ticker}_{days}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        try:
            import yfinance as yf
            etf  = yf.Ticker(ticker)
            # Richiedi qualche giorno in piu' per compensare festivi
            hist = etf.history(period=f"{days + 20}d")

            if hist.empty or len(hist) < 5:
                print(f"  Yahoo Finance: storico vuoto per {ticker}")
                return pd.DataFrame()

            # Normalizza indice: rimuovi timezone
            hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
            hist = hist.sort_index()

            # Seleziona colonne OHLCV disponibili
            cols   = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in hist.columns]
            result = hist[cols].copy().dropna(subset=['Close'])
            result = result.tail(days)

            self._store(cache_key, result)
            return result

        except ImportError:
            print("yfinance non installato. Esegui: pip install yfinance")
            return pd.DataFrame()
        except Exception as e:
            print(f"  Errore Yahoo Finance per {ticker}: {e}")
            # Fallback: se Yahoo fallisce, cerca su altre fonti (es. Investing.com)
            # Per ora: ritorna vuoto e il monitor userà i dati dal DB/Excel
            if ticker.upper() in ['USHYC', 'WAT']:  # Ticker locali MTA
                print(f"  ⚠️  {ticker} non trovato su Yahoo Finance (ticker locale MTA)")
                print(f"     Usando prezzo dall'Excel/Database come fallback")
            return pd.DataFrame()

    def get_close_series(self, ticker: str, days: int = 250) -> pd.Series:
        """Recupera solo la serie Close."""
        df = self.get_historical_data(ticker, days)
        if df.empty or 'Close' not in df.columns:
            return pd.Series(dtype=float)
        return df['Close'].astype(float)

    def get_current_price(self, ticker: str) -> dict:
        """Recupera il prezzo corrente (ultimo close disponibile)."""
        try:
            df = self.get_historical_data(ticker, days=5)
            if not df.empty and 'Close' in df.columns:
                return {
                    'price':    float(df['Close'].iloc[-1]),
                    'date':     df.index[-1].strftime('%Y-%m-%d'),
                    'source':   'Yahoo Finance',
                }
        except Exception as e:
            print(f"  Errore prezzo {ticker}: {e}")
        return {'price': None, 'date': datetime.now().strftime('%Y-%m-%d'),
                'source': 'N/A', 'error': 'Prezzo non disponibile'}

    # compatibilità con il vecchio codice
    def get_etf_data(self, ticker: str) -> dict:
        """Alias per get_current_price (compatibilità)."""
        result = self.get_current_price(ticker)
        if result.get('price') is not None:
            df = self.get_historical_data(ticker, days=5)
            if not df.empty:
                last = df.iloc[-1]
                return {
                    'close':  float(last['Close']),
                    'open':   float(last.get('Open', last['Close'])),
                    'high':   float(last.get('High', last['Close'])),
                    'low':    float(last.get('Low',  last['Close'])),
                    'volume': int(last.get('Volume', 0)),
                    'date':   df.index[-1].strftime('%Y-%m-%d'),
                    'source': 'yfinance',
                }
        return None

    def validate_ticker(self, ticker: str) -> bool:
        """Verifica che un ticker restituisca dati."""
        return not self.get_historical_data(ticker, days=5).empty

    def test_connection(self, ticker: str = 'SWDA.L') -> bool:
        return self.validate_ticker(ticker)

    def get_price_from_investing(self, isin: str) -> Optional[dict]:
        """
        Scrapa prezzo da Investing.com usando ISIN (fallback per ticker locali).
        Usa Selenium per caricare JavaScript dinamico.

        Args:
            isin: ISIN del fondo (es. 'LU1435356065')

        Returns:
            {'price': float, 'date': str, 'source': 'investing.com'} o None
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.chrome.options import Options
        except ImportError:
            print(f"  ⚠️  Selenium non installato - impossibile scrapare {isin}")
            return None

        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        try:
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(10)

            # Ricerca per ISIN su Investing.com
            url = f'https://it.investing.com/search/?q={isin}'
            driver.get(url)

            # Aspetta che carichi i risultati
            WebDriverWait(driver, 5).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, 'searchResultsTable'))
            )

            # Trova il primo link ETF
            links = driver.find_elements(By.TAG_NAME, 'a')
            etf_link = None
            for link in links:
                href = link.get_attribute('href') or ''
                if 'etf' in href.lower():
                    etf_link = href
                    break

            if not etf_link:
                print(f"  ⚠️  ISIN {isin}: nessun ETF trovato su Investing.com")
                driver.quit()
                return None

            # Visita la pagina dell'ETF
            driver.get(etf_link)
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'lastPrice'))
            )

            # Estrai il prezzo
            price_elem = driver.find_element(By.CLASS_NAME, 'lastPrice')
            price_text = price_elem.text.strip().replace(',', '.')
            price = float(price_text)

            driver.quit()

            return {
                'price': price,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'source': 'investing.com'
            }

        except Exception as e:
            print(f"  ❌ Errore scraping Investing.com per {isin}: {e}")
            try:
                driver.quit()
            except:
                pass
            return None


def test_fetcher():
    """Test del fetcher"""
    fetcher = ETFDataFetcher()
    tickers = [
        ('SWDA.L',  'iShares MSCI World'),
        ('CSPX.L',  'iShares Core S&P 500'),
        ('EIMI.L',  'iShares MSCI EM IMI'),
        ('IGLN.L',  'iShares Physical Gold'),
        ('IDTL.L',  'iShares $ Treasury 20y'),
    ]
    print('=' * 60)
    print('TEST ETF DATA FETCHER (Yahoo Finance)')
    print('=' * 60)
    ok = 0
    for ticker, nome in tickers:
        df = fetcher.get_historical_data(ticker, days=60)
        if not df.empty:
            last_close = float(df['Close'].iloc[-1])
            print(f"  OK  {ticker:12s} {nome}: {len(df)}gg, close = {last_close:.4f}")
            ok += 1
        else:
            print(f"  ERR {ticker:12s} {nome}: nessun dato")
        time.sleep(0.5)
    print(f'\nRisultato: {ok}/{len(tickers)} ETF trovati')


if __name__ == '__main__':
    test_fetcher()
