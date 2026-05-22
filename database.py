"""
database.py - Gestione database PostgreSQL per storico prezzi ETF
=================================================================
Salva e recupera lo storico prezzi degli ETF su PostgreSQL (Railway).
Supporta sia identificazione per ticker che per ISIN.
Fonte dati: JustETF (solo Close) e yfinance (OHLCV legacy).
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

                # === MIGRAZIONE ISIN ===
                # Aggiungi colonna isin se non esiste
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'etf_price_history' AND column_name = 'isin'
                        ) THEN
                            ALTER TABLE etf_price_history ADD COLUMN isin VARCHAR(20);
                        END IF;
                    END $$;
                """)
                # Indice per query per ISIN
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_etf_price_isin_date
                    ON etf_price_history(isin, date DESC)
                    WHERE isin IS NOT NULL
                """)

                # Tabella per tracciare l'ingresso degli ETF in Livello 1
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS etf_l1_tracking (
                        isin VARCHAR(20) PRIMARY KEY,
                        entry_date DATE NOT NULL,
                        entry_price DECIMAL(12, 4) NOT NULL
                    )
                """)

                # Tabella per tracciare l'ingresso degli ETF in Livello 0 (Deep Recovery)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS etf_l0_tracking (
                        isin VARCHAR(20) PRIMARY KEY,
                        entry_date DATE NOT NULL,
                        entry_price DECIMAL(12, 4) NOT NULL,
                        panic_low DECIMAL(12, 4)
                    )
                """)

                # Storico uscite da L1
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS etf_l1_exit_history (
                        id SERIAL PRIMARY KEY,
                        isin VARCHAR(20) NOT NULL,
                        fund_name VARCHAR(200),
                        exit_date DATE NOT NULL,
                        exit_price DECIMAL(12, 4),
                        exit_rule INTEGER,
                        exit_trigger TEXT,
                        entry_date DATE,
                        entry_price DECIMAL(12, 4),
                        days_in_l1 INTEGER,
                        pct_gain DECIMAL(8, 4),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_etf_l1_exit_date
                    ON etf_l1_exit_history(exit_date DESC)
                """)

                # Portafoglio personale ETF
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS etf_portfolio_entries (
                        id SERIAL PRIMARY KEY,
                        isin VARCHAR(20) NOT NULL UNIQUE,
                        fund_name VARCHAR(200),
                        entry_date DATE NOT NULL,
                        entry_price DECIMAL(12, 4) NOT NULL,
                        exit_date DATE,
                        exit_price DECIMAL(12, 4),
                        status VARCHAR(20) DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)

                # Eventi portafoglio ETF (uscite, modifiche)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS etf_portfolio_events (
                        id SERIAL PRIMARY KEY,
                        isin VARCHAR(20) NOT NULL,
                        event_type VARCHAR(20) NOT NULL,
                        event_date DATE NOT NULL,
                        event_price DECIMAL(12, 4),
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)

                # Colonne piede dentro (idempotente — ADD COLUMN IF NOT EXISTS)
                for col_sql in [
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS is_partial BOOLEAN DEFAULT FALSE",
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS partial_exit_date DATE",
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS partial_exit_price DECIMAL(12,4)",
                ]:
                    cur.execute(col_sql)

                conn.commit()
                print("Tabelle ETF pronte (price_history, l1_tracking, l0_tracking, l1_exit_history, portfolio)")
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

    def save_close_bulk(self, isin: str, df: pd.DataFrame, source: str = 'justetf') -> int:
        """
        Salva dati Close in blocco da JustETF (solo prezzo chiusura).

        Args:
            isin: Codice ISIN dell'ETF
            df: DataFrame con colonna 'Close' e index=Date
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
                    close_val = float(row['Close'])
                    try:
                        cur.execute("""
                            INSERT INTO etf_price_history (ticker, isin, date, close, source)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (ticker, date)
                            DO UPDATE SET close = EXCLUDED.close, source = EXCLUDED.source,
                                          isin = EXCLUDED.isin
                        """, (isin, isin, date_str, close_val, source))
                        saved += 1
                    except Exception:
                        continue
                conn.commit()
        except Exception as e:
            print(f"Errore salvataggio bulk {isin}: {e}")
        finally:
            conn.close()

        return saved

    def get_close_by_isin(self, isin: str, days: int = 200) -> pd.DataFrame:
        """
        Recupera lo storico Close per un ETF tramite ISIN.

        Args:
            isin: Codice ISIN dell'ETF
            days: Numero di giorni da recuperare

        Returns:
            DataFrame con colonne ['date', 'close'] o con colonna 'Close' e index=Date
        """
        conn = self._get_connection()
        if not conn:
            return pd.DataFrame()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Cerca per ISIN (campo isin) o per ticker (che ora puo' contenere ISIN)
                cur.execute("""
                    SELECT date, close
                    FROM etf_price_history
                    WHERE isin = %s OR ticker = %s
                    ORDER BY date DESC
                    LIMIT %s
                """, (isin, isin, days))
                rows = cur.fetchall()

                if rows:
                    df = pd.DataFrame(rows)
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date').reset_index(drop=True)
                    df['close'] = df['close'].astype(float)
                    # Restituisci in formato compatibile con analisi tecnica
                    result = pd.DataFrame({
                        'Close': df['close'].values
                    }, index=df['date'])
                    result.index.name = 'Date'
                    return result
                return pd.DataFrame()
        except Exception as e:
            logging.error(f"Errore recupero Close {isin}: {e}")
            return pd.DataFrame()
        finally:
            conn.close()

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


    # ── L1 Tracking ──────────────────────────────────────────────────────────

    def get_all_l1_entries(self) -> Dict[str, Dict]:
        """
        Restituisce tutti gli ETF attualmente tracciati in L1.

        Returns:
            Dict {isin: {entry_date: date, entry_price: float}}
        """
        conn = self._get_connection()
        if not conn:
            return {}
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT isin, entry_date, entry_price FROM etf_l1_tracking")
                rows = cur.fetchall()
                return {
                    r['isin']: {
                        'entry_date': r['entry_date'],
                        'entry_price': float(r['entry_price'])
                    }
                    for r in rows
                }
        except Exception as e:
            logging.error(f"Errore get_all_l1_entries: {e}")
            return {}
        finally:
            conn.close()

    def set_l1_entry(self, isin: str, entry_date: str, entry_price: float) -> bool:
        """
        Registra l'ingresso di un ETF in L1 (INSERT, non sovrascrive se già presente).

        Args:
            isin: Codice ISIN
            entry_date: Data ingresso 'YYYY-MM-DD'
            entry_price: Prezzo al momento dell'ingresso
        """
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO etf_l1_tracking (isin, entry_date, entry_price)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (isin) DO NOTHING
                """, (isin, entry_date, float(entry_price)))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore set_l1_entry {isin}: {e}")
            return False
        finally:
            conn.close()

    def remove_l1_entry(self, isin: str) -> bool:
        """Rimuove un ETF dal tracking L1 (uscita da L1)."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM etf_l1_tracking WHERE isin = %s", (isin,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore remove_l1_entry {isin}: {e}")
            return False
        finally:
            conn.close()

    # ── L0 Tracking ──────────────────────────────────────────────────────────

    def get_all_l0_entries(self) -> Dict[str, Dict]:
        """Restituisce tutti gli ETF attualmente in L0."""
        conn = self._get_connection()
        if not conn:
            return {}
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT isin, entry_date, entry_price, panic_low FROM etf_l0_tracking")
                rows = cur.fetchall()
                return {
                    r['isin']: {
                        'entry_date':  r['entry_date'],
                        'entry_price': float(r['entry_price']),
                        'panic_low':   float(r['panic_low']) if r['panic_low'] else None,
                    }
                    for r in rows
                }
        except Exception as e:
            logging.error(f"Errore get_all_l0_entries: {e}")
            return {}
        finally:
            conn.close()

    def set_l0_entry(self, isin: str, entry_date: str, entry_price: float,
                     panic_low: float = None) -> bool:
        """Registra l'ingresso di un ETF in L0 (INSERT, non sovrascrive se presente)."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO etf_l0_tracking (isin, entry_date, entry_price, panic_low)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (isin) DO NOTHING
                """, (isin, entry_date, float(entry_price),
                      float(panic_low) if panic_low else None))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore set_l0_entry {isin}: {e}")
            return False
        finally:
            conn.close()

    def remove_l0_entry(self, isin: str) -> bool:
        """Rimuove un ETF dal tracking L0."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM etf_l0_tracking WHERE isin = %s", (isin,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore remove_l0_entry {isin}: {e}")
            return False
        finally:
            conn.close()

    def is_available(self) -> bool:
        """Verifica se il database è raggiungibile."""
        conn = self._get_connection()
        if not conn:
            return False
        conn.close()
        return True

    # ── L1 Exit History ──────────────────────────────────────────────────────

    def save_l1_exit(self, isin: str, fund_name: str, exit_date: str,
                     exit_price: float, exit_rule: int, exit_trigger: str,
                     entry_date: str, entry_price: float,
                     days_in_l1: int, pct_gain: float) -> bool:
        """Salva un'uscita da L1 nello storico."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO etf_l1_exit_history
                        (isin, fund_name, exit_date, exit_price, exit_rule, exit_trigger,
                         entry_date, entry_price, days_in_l1, pct_gain)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (isin, fund_name, exit_date, exit_price, exit_rule, exit_trigger,
                      entry_date, entry_price, days_in_l1, pct_gain))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore save_l1_exit {isin}: {e}")
            return False
        finally:
            conn.close()

    def get_l1_exits(self, days: int = 30) -> List[Dict]:
        """Restituisce le uscite da L1 degli ultimi N giorni."""
        conn = self._get_connection()
        if not conn:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT isin, fund_name, exit_date, exit_price, exit_rule, exit_trigger,
                           entry_date, entry_price, days_in_l1, pct_gain
                    FROM etf_l1_exit_history
                    WHERE exit_date >= CURRENT_DATE - INTERVAL '%s days'
                    ORDER BY exit_date DESC
                """, (days,))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logging.error(f"Errore get_l1_exits: {e}")
            return []
        finally:
            conn.close()

    # ── Portfolio ─────────────────────────────────────────────────────────────

    def get_portfolio_entries(self) -> List[Dict]:
        """Restituisce tutti gli ETF nel portafoglio."""
        conn = self._get_connection()
        if not conn:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT isin, fund_name, entry_date, entry_price,
                           exit_date, exit_price, status,
                           is_partial, partial_exit_date, partial_exit_price
                    FROM etf_portfolio_entries
                    ORDER BY entry_date DESC
                """)
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logging.error(f"Errore get_portfolio_entries: {e}")
            return []
        finally:
            conn.close()

    def add_portfolio_entry(self, isin: str, entry_date: str,
                            entry_price: float, fund_name: str = '') -> bool:
        """Aggiunge un ETF al portafoglio (o riattiva se già presente)."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO etf_portfolio_entries (isin, fund_name, entry_date, entry_price, status)
                    VALUES (%s, %s, %s, %s, 'active')
                    ON CONFLICT (isin) DO UPDATE
                        SET entry_date = EXCLUDED.entry_date,
                            entry_price = EXCLUDED.entry_price,
                            fund_name = EXCLUDED.fund_name,
                            status = 'active',
                            exit_date = NULL,
                            exit_price = NULL
                """, (isin, fund_name, entry_date, entry_price))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore add_portfolio_entry {isin}: {e}")
            return False
        finally:
            conn.close()

    def remove_portfolio_entry(self, isin: str) -> bool:
        """Rimuove definitivamente un ETF dal portafoglio."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM etf_portfolio_entries WHERE isin = %s", (isin,))
                cur.execute("DELETE FROM etf_portfolio_events WHERE isin = %s", (isin,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore remove_portfolio_entry {isin}: {e}")
            return False
        finally:
            conn.close()

    def update_portfolio_entry(self, isin: str, entry_date: str,
                               entry_price: float, fund_name: str = None) -> bool:
        """Modifica data/prezzo di entrata di un ETF."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                if fund_name is not None:
                    cur.execute("""
                        UPDATE etf_portfolio_entries
                        SET entry_date=%s, entry_price=%s, fund_name=%s
                        WHERE isin=%s
                    """, (entry_date, entry_price, fund_name, isin))
                else:
                    cur.execute("""
                        UPDATE etf_portfolio_entries
                        SET entry_date=%s, entry_price=%s
                        WHERE isin=%s
                    """, (entry_date, entry_price, isin))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore update_portfolio_entry {isin}: {e}")
            return False
        finally:
            conn.close()

    def exit_portfolio_entry(self, isin: str, exit_date: str, exit_price: float) -> bool:
        """Registra l'uscita da un ETF del portafoglio."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE etf_portfolio_entries
                    SET exit_date=%s, exit_price=%s, status='exited'
                    WHERE isin=%s
                """, (exit_date, exit_price, isin))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore exit_portfolio_entry {isin}: {e}")
            return False
        finally:
            conn.close()

    def partial_exit_portfolio_entry(self, isin: str, exit_date: str, exit_price: float) -> bool:
        """Segna il 90% come venduto — l'ETF rimane active con is_partial=True."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE etf_portfolio_entries
                    SET is_partial=TRUE, partial_exit_date=%s, partial_exit_price=%s
                    WHERE isin=%s
                """, (exit_date, exit_price, isin))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore partial_exit_portfolio_entry {isin}: {e}")
            return False
        finally:
            conn.close()

    def reactivate_portfolio_entry(self, isin: str) -> bool:
        """Annulla l'uscita e riporta un ETF a status active."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE etf_portfolio_entries
                    SET exit_date=NULL, exit_price=NULL, status='active'
                    WHERE isin=%s
                """, (isin,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore reactivate_portfolio_entry {isin}: {e}")
            return False
        finally:
            conn.close()

    def add_portfolio_event(self, isin: str, event_type: str, event_date: str,
                            event_price: float = None, notes: str = None) -> int:
        """Aggiunge un evento al portafoglio (exit, modifica). Ritorna l'id o -1."""
        conn = self._get_connection()
        if not conn:
            return -1
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO etf_portfolio_events (isin, event_type, event_date, event_price, notes)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (isin, event_type, event_date, event_price, notes))
                row = cur.fetchone()
                conn.commit()
                return row[0] if row else -1
        except Exception as e:
            logging.error(f"Errore add_portfolio_event {isin}: {e}")
            return -1
        finally:
            conn.close()

    def get_portfolio_events(self, isin: str) -> List[Dict]:
        """Restituisce tutti gli eventi registrati per un ETF."""
        conn = self._get_connection()
        if not conn:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, isin, event_type, event_date, event_price, notes
                    FROM etf_portfolio_events
                    WHERE isin = %s
                    ORDER BY event_date DESC
                """, (isin,))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logging.error(f"Errore get_portfolio_events {isin}: {e}")
            return []
        finally:
            conn.close()

    def update_portfolio_event(self, event_id: int, event_date: str,
                               event_price: float = None, notes: str = None) -> bool:
        """Modifica un evento portafoglio."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE etf_portfolio_events
                    SET event_date=%s, event_price=%s, notes=%s
                    WHERE id=%s
                """, (event_date, event_price, notes, event_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore update_portfolio_event {event_id}: {e}")
            return False
        finally:
            conn.close()

    def delete_portfolio_event(self, event_id: int) -> bool:
        """Elimina un evento portafoglio."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM etf_portfolio_events WHERE id=%s", (event_id,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore delete_portfolio_event {event_id}: {e}")
            return False
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
