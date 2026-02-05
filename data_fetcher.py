"""
data_fetcher.py - Recupero dati OHLCV per ETF via yfinance
===========================================================
Usa yfinance per ottenere dati Open/High/Low/Close/Volume.
Vantaggio: 6 mesi di storico disponibili immediatamente.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
import time
import logging


class ETFDataFetcher:
    """Recupera dati OHLCV per ETF tramite yfinance"""

    def __init__(self):
        self.cache = {}
        self.cache_duration = 3600  # 1 ora

    def get_etf_data(self, ticker: str) -> dict:
        """
        Recupera dati correnti per un ETF

        Args:
            ticker: Ticker dell'ETF (es. SWDA.MI, VWCE.DE, QQQ)

        Returns:
            Dizionario con dati OHLCV correnti, o None se errore
        """
        # Controlla cache
        cache_key = f"{ticker}_{datetime.now().strftime('%Y%m%d')}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            etf = yf.Ticker(ticker)
            hist = etf.history(period="5d")

            if hist.empty:
                print(f"  Nessun dato per {ticker}")
                return None

            # Ultimo giorno disponibile
            last = hist.iloc[-1]
            last_date = hist.index[-1]

            result = {
                'close': float(last['Close']),
                'open': float(last['Open']),
                'high': float(last['High']),
                'low': float(last['Low']),
                'volume': int(last['Volume']),
                'date': last_date.strftime('%Y-%m-%d'),
                'source': 'yfinance'
            }

            self.cache[cache_key] = result
            return result

        except Exception as e:
            print(f"  Errore recupero dati {ticker}: {e}")
            return None

    def get_historical_data(self, ticker: str, period: str = '6mo') -> pd.DataFrame:
        """
        Recupera storico OHLCV per un ETF

        Args:
            ticker: Ticker dell'ETF
            period: Periodo storico (1mo, 3mo, 6mo, 1y, 2y, 5y, max)

        Returns:
            DataFrame con colonne Open, High, Low, Close, Volume e index=Date
        """
        try:
            etf = yf.Ticker(ticker)
            hist = etf.history(period=period)

            if hist.empty:
                print(f"  Nessun storico per {ticker}")
                return pd.DataFrame()

            # Mantieni solo le colonne OHLCV
            df = hist[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
            print(f"  Scaricati {len(df)} giorni di storico per {ticker}")
            return df

        except Exception as e:
            print(f"  Errore storico {ticker}: {e}")
            return pd.DataFrame()

    def validate_ticker(self, ticker: str) -> bool:
        """
        Verifica che un ticker sia valido

        Args:
            ticker: Ticker da validare

        Returns:
            True se il ticker restituisce dati
        """
        try:
            etf = yf.Ticker(ticker)
            hist = etf.history(period="5d")
            return not hist.empty
        except Exception:
            return False


def test_fetcher():
    """Test del data fetcher ETF"""
    fetcher = ETFDataFetcher()

    test_tickers = [
        ("SWDA.MI", "iShares Core MSCI World"),
        ("VWCE.DE", "Vanguard FTSE All-World"),
        ("QQQ", "Invesco QQQ Trust"),
    ]

    print("=" * 60)
    print("TEST ETF DATA FETCHER")
    print("=" * 60)

    successi = 0
    for ticker, nome in test_tickers:
        print(f"\n{nome} ({ticker}):")

        # Test dati correnti
        data = fetcher.get_etf_data(ticker)
        if data:
            print(f"  Prezzo: {data['close']:.2f} (Volume: {data['volume']:,})")
            successi += 1
        else:
            print(f"  Dati non disponibili")

        # Test storico
        hist = fetcher.get_historical_data(ticker, period='1mo')
        if not hist.empty:
            print(f"  Storico: {len(hist)} giorni")

        time.sleep(1)

    print(f"\nRISULTATO: {successi}/{len(test_tickers)} ETF trovati")


if __name__ == "__main__":
    test_fetcher()
