"""
data_fetcher.py - Recupero dati ETF da Yahoo Finance
======================================================
Usa yfinance per OHLCV completo (Open, High, Low, Close, Volume).
Ticker nel formato Yahoo Finance (es. SWDA.L, CSPX.L, EIMI.L).
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time


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
