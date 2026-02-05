"""
database.py - Gestione database PostgreSQL per storico prezzi ETF
=================================================================
Salva e recupera lo storico OHLCV degli ETF su PostgreSQL (Railway)
"""

import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging

# Usa psycopg2 per PostgreSQL
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logging.warning("psycopg2 non installato. Installa con: pip install psycopg2-binary")


class PriceDatabase:
    """Gestisce lo storico prezzi OHLCV su PostgreSQL"""

    def __init__(self, database_url: str = None):
        """
        Inizializza la connessione al database

        Args:
            database_url: URL di connessione PostgreSQL (default: da variabile ambiente)
        """
        self.database_url = database_url or self._detect_database_url()
        self.connection = None

        if not POSTGRES_AVAILABLE:
            print("psycopg2 non disponibile - installa con: pip install psycopg2-binary")
            return

        if not self.database_url:
            print("DATABASE_URL non trovato. Lo storico non verra' salvato su PostgreSQL.")
            return

        print(f"DATABASE_URL configurato: {self.database_url[:30]}...")

        # Inizializza la tabella se non esiste
        self._init_table()

    @staticmethod
    def _detect_database_url() -> Optional[str]:
        """
        Cerca l'URL del database in diversi modi:
        1. DATABASE_URL (standard)
        2. DATABASE_PUBLIC_URL (Railway public)
        3. Costruisce da PGHOST, PGUSER, PGPASSWORD, PGDATABASE, PGPORT
        """
        # 1. DATABASE_URL diretto
        url = os.environ.get('DATABASE_URL')
        if url:
            print("Trovato DATABASE_URL")
            return url

        # 2. DATABASE_PUBLIC_URL (Railway)
        url = os.environ.get('DATABASE_PUBLIC_URL')
        if url:
            print("Trovato DATABASE_PUBLIC_URL")
            return url

        # 3. Costruisci da variabili PG* individuali
        pghost = os.environ.get('PGHOST')
        pguser = os.environ.get('PGUSER', 'postgres')
        pgpassword = os.environ.get('PGPASSWORD')
        pgdatabase = os.environ.get('PGDATABASE', 'railway')
        pgport = os.environ.get('PGPORT', '5432')

        if pghost and pgpassword:
            url = f"postgresql://{pguser}:{pgpassword}@{pghost}:{pgport}/{pgdatabase}"
            print(f"DATABASE_URL costruito da variabili PG*: {pghost}:{pgport}")
            return url

        print("Nessuna variabile database trovata (DATABASE_URL, DATABASE_PUBLIC_URL, PGHOST)")
        return None

    def _get_connection(self):
        """Ottiene una connessione al database"""
        if not self.database_url or not POSTGRES_AVAILABLE:
            return None

        try:
            conn = psycopg2.connect(self.database_url, sslmode='require')
            return conn
        except Exception:
            # Prova senza SSL (per database locali)
            try:
                conn = psycopg2.connect(self.database_url)
                return conn
            except Exception as e2:
                print(f"Errore connessione database: {e2}")
                return None

    def _init_table(self):
        """Crea la tabella etf_price_history se non esiste"""
        conn = self._get_connection()
        if not conn:
            return

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS etf_price_history (
                        id SERIAL PRIMARY KEY,
                        ticker VARCHAR(20) NOT NULL,
                        date DATE NOT NULL,
                        open DECIMAL(12, 4),
                        high DECIMAL(12, 4),
                        low DECIMAL(12, 4),
                        close DECIMAL(12, 4) NOT NULL,
                        volume BIGINT,
                        source VARCHAR(50),
                        created_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(ticker, date)
                    )
                """)
                # Aggiungi vincolo UNIQUE se mancante (tabella gia' esistente)
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint
                            WHERE conname = 'etf_price_history_ticker_date_key'
                        ) THEN
                            ALTER TABLE etf_price_history ADD CONSTRAINT etf_price_history_ticker_date_key UNIQUE (ticker, date);
                        END IF;
                    END $$;
                """)
                # Crea indice per query veloci
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_etf_price_history_ticker_date
                    ON etf_price_history(ticker, date DESC)
                """)
                conn.commit()
                print("Tabella etf_price_history pronta (con vincolo UNIQUE)")
        except Exception as e:
            logging.error(f"Errore creazione tabella: {e}")
        finally:
            conn.close()

    def save_ohlcv(self, ticker: str, date: str, open_price: float, high: float,
                   low: float, close: float, volume: int, source: str = 'yfinance') -> bool:
        """
        Salva dati OHLCV nel database

        Args:
            ticker: Ticker dell'ETF (es. SWDA.MI)
            date: Data nel formato YYYY-MM-DD
            open_price: Prezzo apertura
            high: Prezzo massimo
            low: Prezzo minimo
            close: Prezzo chiusura
            volume: Volume scambi
            source: Fonte del dato

        Returns:
            True se salvato con successo
        """
        conn = self._get_connection()
        if not conn:
            return False

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO etf_price_history (ticker, date, open, high, low, close, volume, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ticker, date)
                    DO UPDATE SET open = EXCLUDED.open, high = EXCLUDED.high,
                                  low = EXCLUDED.low, close = EXCLUDED.close,
                                  volume = EXCLUDED.volume, source = EXCLUDED.source
                """, (ticker, date, open_price, high, low, close, volume, source))
                conn.commit()
                return True
        except Exception as e:
            print(f"Errore salvataggio OHLCV {ticker}: {e}")
            return False
        finally:
            conn.close()

    def save_ohlcv_bulk(self, ticker: str, df: pd.DataFrame, source: str = 'yfinance') -> int:
        """
        Salva dati OHLCV in blocco dal DataFrame yfinance

        Args:
            ticker: Ticker dell'ETF
            df: DataFrame con colonne Open, High, Low, Close, Volume e index=Date
            source: Fonte del dato

        Returns:
            Numero di record salvati
        """
        conn = self._get_connection()
        if not conn:
            return 0

        saved = 0
        try:
            with conn.cursor() as cur:
                for date_idx, row in df.iterrows():
                    date_str = date_idx.strftime('%Y-%m-%d') if hasattr(date_idx, 'strftime') else str(date_idx)
                    try:
                        cur.execute("""
                            INSERT INTO etf_price_history (ticker, date, open, high, low, close, volume, source)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (ticker, date)
                            DO UPDATE SET open = EXCLUDED.open, high = EXCLUDED.high,
                                          low = EXCLUDED.low, close = EXCLUDED.close,
                                          volume = EXCLUDED.volume, source = EXCLUDED.source
                        """, (ticker, date_str,
                              float(row.get('Open', 0)), float(row.get('High', 0)),
                              float(row.get('Low', 0)), float(row['Close']),
                              int(row.get('Volume', 0)), source))
                        saved += 1
                    except Exception:
                        continue
                conn.commit()
        except Exception as e:
            print(f"Errore salvataggio bulk {ticker}: {e}")
        finally:
            conn.close()

        return saved

    def get_ohlcv(self, ticker: str, days: int = 200) -> pd.DataFrame:
        """
        Recupera lo storico OHLCV per un ETF

        Args:
            ticker: Ticker dell'ETF
            days: Numero di giorni da recuperare

        Returns:
            DataFrame con colonne ['date', 'open', 'high', 'low', 'close', 'volume']
        """
        conn = self._get_connection()
        if not conn:
            return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT date, open, high, low, close, volume
                    FROM etf_price_history
                    WHERE ticker = %s
                    ORDER BY date DESC
                    LIMIT %s
                """, (ticker, days))
                rows = cur.fetchall()

                if rows:
                    df = pd.DataFrame(rows)
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date').reset_index(drop=True)
                    # Converti Decimal a float
                    for col in ['open', 'high', 'low', 'close']:
                        df[col] = df[col].astype(float)
                    df['volume'] = df['volume'].astype(int)
                    return df
                return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        except Exception as e:
            logging.error(f"Errore recupero OHLCV {ticker}: {e}")
            return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        finally:
            conn.close()

    def get_close_series(self, ticker: str, days: int = 200) -> pd.Series:
        """
        Recupera solo i prezzi di chiusura come Serie pandas

        Args:
            ticker: Ticker dell'ETF
            days: Numero di giorni

        Returns:
            Serie pandas con index=date e values=close
        """
        df = self.get_ohlcv(ticker, days)
        if df.empty:
            return pd.Series(dtype=float)
        return pd.Series(df['close'].values, index=df['date'])

    def get_stats(self) -> Dict:
        """
        Statistiche sul database

        Returns:
            Dizionario con statistiche
        """
        conn = self._get_connection()
        if not conn:
            return {'error': 'Database non disponibile'}

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT COUNT(*) as total FROM etf_price_history")
                total = cur.fetchone()['total']

                cur.execute("SELECT COUNT(DISTINCT ticker) as etfs FROM etf_price_history")
                etfs = cur.fetchone()['etfs']

                cur.execute("""
                    SELECT MIN(date) as first_date, MAX(date) as last_date
                    FROM etf_price_history
                """)
                dates = cur.fetchone()

                cur.execute("""
                    SELECT ticker, COUNT(*) as count
                    FROM etf_price_history
                    GROUP BY ticker
                    ORDER BY count DESC
                """)
                by_etf = cur.fetchall()

                return {
                    'total_records': total,
                    'unique_etfs': etfs,
                    'first_date': str(dates['first_date']) if dates['first_date'] else None,
                    'last_date': str(dates['last_date']) if dates['last_date'] else None,
                    'records_by_etf': {r['ticker']: r['count'] for r in by_etf}
                }
        except Exception as e:
            logging.error(f"Errore statistiche: {e}")
            return {'error': str(e)}
        finally:
            conn.close()

    def count_prices(self, ticker: str = None) -> int:
        """Conta i prezzi salvati"""
        conn = self._get_connection()
        if not conn:
            return 0

        try:
            with conn.cursor() as cur:
                if ticker:
                    cur.execute("SELECT COUNT(*) FROM etf_price_history WHERE ticker = %s", (ticker,))
                else:
                    cur.execute("SELECT COUNT(*) FROM etf_price_history")
                return cur.fetchone()[0]
        except Exception as e:
            logging.error(f"Errore conteggio prezzi: {e}")
            return 0
        finally:
            conn.close()


if __name__ == "__main__":
    print("=" * 50)
    print("TEST DATABASE ETF")
    print("=" * 50)

    db = PriceDatabase()

    today = datetime.now().strftime('%Y-%m-%d')
    print(f"\nSalvataggio OHLCV test...")
    success = db.save_ohlcv('TEST.MI', today, 100.0, 102.0, 99.0, 101.5, 50000, 'Test')
    print(f"  Risultato: {'OK' if success else 'ERRORE'}")

    print(f"\nRecupero OHLCV...")
    df = db.get_ohlcv('TEST.MI', 10)
    print(f"  Record trovati: {len(df)}")

    print(f"\nStatistiche database:")
    stats = db.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
