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

    def get_connection(self):
        """Metodo pubblico per ottenere connessione al database"""
        return self._get_connection()

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
                        panic_low DECIMAL(12, 4),
                        confirmation_mode VARCHAR(10),
                        trigger_low_price DECIMAL(12, 4),
                        confirmation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                        portfolio_type VARCHAR(2) DEFAULT 'L1',
                        stop_loss_l0_suggested DECIMAL(12, 4),
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

                # Preferiti personali — ETF "da tenere d'occhio", diversi dal portafoglio
                # reale (nessun prezzo di carico, solo tracking di come evolvono le
                # condizioni) e dalla etf_l2_watchlist sotto (quella è lo stato interno
                # di anti-flickering del punteggio L2, non una lista curata dall'utente).
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS etf_favorites (
                        id SERIAL PRIMARY KEY,
                        isin VARCHAR(20) NOT NULL UNIQUE,
                        ticker VARCHAR(20),
                        nome VARCHAR(200),
                        note TEXT,
                        added_date DATE NOT NULL,
                        last_buy_count INTEGER,
                        last_level INTEGER,
                        last_regime VARCHAR(20),
                        last_checked_date DATE,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)

                # Colonne piede dentro (idempotente — ADD COLUMN IF NOT EXISTS)
                for col_sql in [
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS is_partial BOOLEAN DEFAULT FALSE",
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS partial_exit_date DATE",
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS partial_exit_price DECIMAL(12,4)",
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS stop_loss_inserted DECIMAL(12, 4)",
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS stop_loss_suggested DECIMAL(12, 4)",
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS stop_loss_updated_at TIMESTAMP",
                    # STEP 1 — Nuovi campi per sistema L0-L1 a due portafogli
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS portafoglio VARCHAR(3) DEFAULT 'L1'",
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS entry_confidence DECIMAL(3, 2) DEFAULT 1.00",
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS entry_quality INTEGER DEFAULT 0",
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS entry_layer VARCHAR(2) DEFAULT 'L1'",
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS capital_pct DECIMAL(5, 4) DEFAULT 1.0000",
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS stop_gain_target DECIMAL(12, 4)",
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS sg_suggerito DECIMAL(12, 4)",
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS sl_suggerito DECIMAL(12, 4)",
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS days_no_recovery INTEGER DEFAULT 0",
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS stallo_counter INTEGER DEFAULT 0",
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS add_history TEXT DEFAULT '[]'",
                    # Ratchet dello Stop tattico di avvicinamento al TP (order_pricing.py) —
                    # il massimo prezzo_stop già suggerito finché la posizione resta aperta,
                    # cosi' il tattico non torna mai indietro anche se il prezzo si allontana
                    # temporaneamente dal TP. Scritto solo dal monitor giornaliero.
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS tp_proximity_stop_max DECIMAL(12, 4)",
                    # Trigger personale inserito su Directa per l'ordine Stop reale (2026-08-19)
                    # — distinto da stop_loss_inserted (il Prezzo Limite personale, il prezzo di
                    # garanzia). Insieme replicano la coppia Trigger+Limite di un vero ordine Stop
                    # Directa. Sostituisce l'uso di stop_gain_target come "TP personale" nella riga
                    # portafoglio (poco utile: il TP è comunque un ordine Limite separato, non fa
                    # parte dell'ordine Stop) — stop_gain_target resta nello schema ma non più letto
                    # dalla UI della riga portafoglio.
                    "ALTER TABLE etf_portfolio_entries ADD COLUMN IF NOT EXISTS stop_trigger_inserted DECIMAL(12, 4)",
                    # PRIORITÀ 1 FASE 2 — L0 State Persistence (2026-07-21)
                    "ALTER TABLE etf_l0_tracking ADD COLUMN IF NOT EXISTS confirmation_mode VARCHAR(10)",
                    "ALTER TABLE etf_l0_tracking ADD COLUMN IF NOT EXISTS trigger_low_price DECIMAL(12, 4)",
                    "ALTER TABLE etf_l0_tracking ADD COLUMN IF NOT EXISTS confirmation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
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

    def save_ohlcv_bulk(self, ticker: str, df: pd.DataFrame, source: str = 'yfinance',
                         isin: Optional[str] = None) -> int:
        """
        Salva dati OHLCV in blocco dal DataFrame yfinance

        Args:
            ticker: Ticker dell'ETF (o l'ISIN stesso, se usato come identificatore stabile)
            df: DataFrame con colonne Open, High, Low, Close, Volume e index=Date
            source: Fonte del dato
            isin: Codice ISIN, se noto — popola la colonna isin (prima veniva lasciata NULL
                  per ogni riga nuova, affidandosi solo alla convenzione ticker=isin)

        Returns:
            Numero di record salvati
        """
        conn = self._get_connection()
        if not conn:
            return 0

        saved = 0
        skipped_outliers = 0
        try:
            with conn.cursor() as cur:
                # Guardia anti-corruzione: scarta prezzi implausibili rispetto allo storico
                # esistente per questo ticker (es. errori di scraping/provider dati — trovato
                # 2026-08-23 un valore di ~9x il normale reintrodotto ad ogni refetch storico)
                cur.execute(
                    "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY close) FROM etf_price_history WHERE ticker = %s",
                    (ticker,)
                )
                row0 = cur.fetchone()
                median_close = float(row0[0]) if row0 and row0[0] is not None else None

                for date_idx, row in df.iterrows():
                    date_str = date_idx.strftime('%Y-%m-%d') if hasattr(date_idx, 'strftime') else str(date_idx)
                    close_val = float(row['Close'])
                    if median_close and median_close > 0 and \
                       (close_val > median_close * 5 or close_val < median_close * 0.2):
                        skipped_outliers += 1
                        continue
                    try:
                        cur.execute("""
                            INSERT INTO etf_price_history (ticker, date, open, high, low, close, volume, source, isin)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (ticker, date)
                            DO UPDATE SET open = EXCLUDED.open, high = EXCLUDED.high,
                                          low = EXCLUDED.low, close = EXCLUDED.close,
                                          volume = EXCLUDED.volume, source = EXCLUDED.source,
                                          isin = COALESCE(EXCLUDED.isin, etf_price_history.isin)
                        """, (ticker, date_str,
                              float(row.get('Open', 0)), float(row.get('High', 0)),
                              float(row.get('Low', 0)), close_val,
                              int(row.get('Volume', 0)), source, isin))
                        saved += 1
                    except Exception:
                        continue
                conn.commit()
        except Exception as e:
            print(f"Errore salvataggio bulk {ticker}: {e}")
        finally:
            conn.close()

        if skipped_outliers:
            print(f"⚠️  {ticker}: {skipped_outliers} prezzi scartati (implausibili, oltre 5x/0.2x la mediana storica {median_close})")

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
        skipped_outliers = 0
        try:
            with conn.cursor() as cur:
                # Guardia anti-corruzione: vedi save_ohlcv_bulk (stesso problema, trovato 2026-08-23)
                cur.execute(
                    "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY close) FROM etf_price_history WHERE ticker = %s",
                    (isin,)
                )
                row0 = cur.fetchone()
                median_close = float(row0[0]) if row0 and row0[0] is not None else None

                for date_idx, row in df.iterrows():
                    date_str = date_idx.strftime('%Y-%m-%d') if hasattr(date_idx, 'strftime') else str(date_idx)
                    close_val = float(row['Close'])
                    if median_close and median_close > 0 and \
                       (close_val > median_close * 5 or close_val < median_close * 0.2):
                        skipped_outliers += 1
                        continue
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

        if skipped_outliers:
            print(f"⚠️  {isin}: {skipped_outliers} prezzi scartati (implausibili, oltre 5x/0.2x la mediana storica {median_close})")

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

    def get_ohlc_by_isin(self, isin: str, days: int = 200) -> pd.DataFrame:
        """
        Recupera lo storico OHLCV per un ETF tramite ISIN (o ticker=isin).

        A differenza di get_close_by_isin(), include Open/High/Low/Volume —
        usato dal fast-path DB del monitor per non perdere i dati necessari
        ad ADX e allo spazio residuo (condizione L1 #7).

        Returns:
            DataFrame con colonne ['Open','High','Low','Close','Volume'] e index=Date.
            Open/High/Low/Volume possono essere NaN per righe salvate prima del fix
            (venivano storicamente scartate da save_close_bulk).
        """
        conn = self._get_connection()
        if not conn:
            return pd.DataFrame()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT date, open, high, low, close, volume
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
                    for col in ['open', 'high', 'low', 'close']:
                        df[col] = df[col].astype(float)
                    result = pd.DataFrame({
                        'Open':   df['open'].values,
                        'High':   df['high'].values,
                        'Low':    df['low'].values,
                        'Close':  df['close'].values,
                        'Volume': df['volume'].values,
                    }, index=df['date'])
                    result.index.name = 'Date'
                    return result
                return pd.DataFrame()
        except Exception as e:
            logging.error(f"Errore recupero OHLC {isin}: {e}")
            return pd.DataFrame()
        finally:
            conn.close()

    def save_frozen_ohlcv_bulk(self, ticker: str, isin: str, df: pd.DataFrame,
                                freeze_batch: str) -> int:
        """
        Salva uno storico OHLCV nel Golden Dataset congelato (etf_price_history_frozen).

        A differenza di save_ohlcv_bulk(), scrive in una tabella separata e mai toccata
        dal monitor live — pensata per essere popolata UNA VOLTA da un backfill dedicato
        (freeze_historical_dataset.py) e poi letta sempre invariata dai backtest, per
        avere risultati riproducibili al 100% run dopo run. Vedi CLAUDE.md.

        Args:
            ticker: Ticker dell'ETF
            isin: ISIN dell'ETF (puo' essere vuoto)
            df: DataFrame con colonne Open, High, Low, Close, Volume e index=Date
            freeze_batch: etichetta dello snapshot (es. '2026-08-07')

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
                            INSERT INTO etf_price_history_frozen
                                (freeze_batch, ticker, isin, date, open, high, low, close, volume)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (freeze_batch, ticker, date)
                            DO UPDATE SET open = EXCLUDED.open, high = EXCLUDED.high,
                                          low = EXCLUDED.low, close = EXCLUDED.close,
                                          volume = EXCLUDED.volume, isin = EXCLUDED.isin
                        """, (freeze_batch, ticker, isin or None, date_str,
                              float(row.get('Open', 0)) if pd.notna(row.get('Open')) else None,
                              float(row.get('High', 0)) if pd.notna(row.get('High')) else None,
                              float(row.get('Low', 0)) if pd.notna(row.get('Low')) else None,
                              float(row['Close']),
                              int(row.get('Volume', 0)) if pd.notna(row.get('Volume')) else None))
                        saved += 1
                    except Exception:
                        continue
                conn.commit()
        except Exception as e:
            print(f"Errore salvataggio frozen bulk {ticker}: {e}")
        finally:
            conn.close()

        return saved

    def get_frozen_ohlcv(self, ticker: str, freeze_batch: str) -> pd.DataFrame:
        """
        Recupera lo storico OHLCV congelato per un ticker da uno specifico snapshot.

        Returns:
            DataFrame con colonne ['Open','High','Low','Close','Volume'] e index=Date,
            ordinato cronologicamente, oppure DataFrame vuoto se non presente nel batch.
        """
        conn = self._get_connection()
        if not conn:
            return pd.DataFrame()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT date, open, high, low, close, volume
                    FROM etf_price_history_frozen
                    WHERE ticker = %s AND freeze_batch = %s
                    ORDER BY date ASC
                """, (ticker, freeze_batch))
                rows = cur.fetchall()

                if rows:
                    df = pd.DataFrame(rows)
                    df['date'] = pd.to_datetime(df['date'])
                    for col in ['open', 'high', 'low', 'close']:
                        df[col] = df[col].astype(float)
                    result = pd.DataFrame({
                        'Open':   df['open'].values,
                        'High':   df['high'].values,
                        'Low':    df['low'].values,
                        'Close':  df['close'].values,
                        'Volume': df['volume'].values,
                    }, index=df['date'])
                    result.index.name = 'Date'
                    return result
                return pd.DataFrame()
        except Exception as e:
            logging.error(f"Errore recupero frozen OHLCV {ticker}/{freeze_batch}: {e}")
            return pd.DataFrame()
        finally:
            conn.close()

    def get_open_shadow_position(self, model_name: str, ticker: str) -> Optional[dict]:
        """Restituisce la posizione ombra aperta per questo ticker/modello, o None."""
        conn = self._get_connection()
        if not conn:
            return None
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, ticker, isin, famiglia, entry_date, entry_price
                    FROM etf_shadow_positions
                    WHERE model_name = %s AND ticker = %s AND status = 'open'
                """, (model_name, ticker))
                row = cur.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logging.error(f"Errore get_open_shadow_position {ticker}: {e}")
            return None
        finally:
            conn.close()

    def open_shadow_position(self, model_name: str, ticker: str, isin: str, famiglia: str,
                              entry_date, entry_price: float) -> bool:
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO etf_shadow_positions
                        (model_name, ticker, isin, famiglia, entry_date, entry_price, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'open')
                    ON CONFLICT (model_name, ticker, entry_date) DO NOTHING
                """, (model_name, ticker, isin, famiglia, entry_date, entry_price))
                conn.commit()
            return True
        except Exception as e:
            logging.error(f"Errore open_shadow_position {ticker}: {e}")
            return False
        finally:
            conn.close()

    def close_shadow_position(self, position_id: int, exit_date, exit_price: float,
                               exit_reason: str, gross_pct_gain: float) -> bool:
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE etf_shadow_positions
                    SET status = 'closed', exit_date = %s, exit_price = %s,
                        exit_reason = %s, gross_pct_gain = %s, updated_at = now()
                    WHERE id = %s
                """, (exit_date, exit_price, exit_reason, gross_pct_gain, position_id))
                conn.commit()
            return True
        except Exception as e:
            logging.error(f"Errore close_shadow_position {position_id}: {e}")
            return False
        finally:
            conn.close()

    def get_shadow_positions(self, model_name: str) -> list:
        conn = self._get_connection()
        if not conn:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT ticker, isin, famiglia, entry_date, entry_price,
                           exit_date, exit_price, exit_reason, status, gross_pct_gain
                    FROM etf_shadow_positions
                    WHERE model_name = %s
                    ORDER BY entry_date
                """, (model_name,))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logging.error(f"Errore get_shadow_positions: {e}")
            return []
        finally:
            conn.close()

    def get_breadth_regime_state(self, model_name: str) -> Optional[str]:
        """Stato di ieri (NORMAL/SUPER_BULL) per l'isteresi del Market Breadth Shadow
        Monitor — vedi migrations/005_add_breadth_regime_state.sql. None se mai
        inizializzato (primo giro)."""
        conn = self._get_connection()
        if not conn:
            return None
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT current_state FROM etf_breadth_regime_state WHERE model_name = %s
                """, (model_name,))
                row = cur.fetchone()
                return row[0] if row else None
        except Exception as e:
            logging.error(f"Errore get_breadth_regime_state: {e}")
            return None
        finally:
            conn.close()

    def set_breadth_regime_state(self, model_name: str, state: str, breadth_pct: float) -> bool:
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO etf_breadth_regime_state (model_name, current_state, breadth_pct, updated_at)
                    VALUES (%s, %s, %s, now())
                    ON CONFLICT (model_name) DO UPDATE
                        SET current_state = EXCLUDED.current_state,
                            breadth_pct = EXCLUDED.breadth_pct,
                            updated_at = now()
                """, (model_name, state, breadth_pct))
                conn.commit()
            return True
        except Exception as e:
            logging.error(f"Errore set_breadth_regime_state: {e}")
            return False
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

    def set_l1_entry(self, isin: str, entry_date: str, entry_price: float, stop_loss: float = None) -> bool:
        """
        Registra l'ingresso di un ETF in L1 (INSERT, non sovrascrive se già presente).

        Args:
            isin: Codice ISIN
            entry_date: Data ingresso 'YYYY-MM-DD'
            entry_price: Prezzo al momento dell'ingresso
            stop_loss: Stop loss iniziale calcolato dinamicamente
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

                # Se c'è uno stop loss, aggiorna la tabella portfolio_entries (per resoconto)
                if stop_loss is not None:
                    cur.execute("""
                        UPDATE etf_portfolio_entries
                        SET stop_loss = %s, stop_loss_updated_at = NOW()
                        WHERE isin = %s
                    """, (float(stop_loss), isin))

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

    def update_stop_loss_trailing(self, isin: str, new_stop_loss: float) -> bool:
        """
        Aggiorna lo SL suggerito (trailing stop).

        Args:
            isin: Codice ISIN
            new_stop_loss: Nuovo valore SL trailing calcolato

        Returns:
            True se aggiornato, False se errore
        """
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                # Aggiorna SL consigliato (non il SL inserito)
                cur.execute("""
                    UPDATE etf_portfolio_entries
                    SET stop_loss_suggested = %s, stop_loss_updated_at = NOW()
                    WHERE isin = %s
                """, (float(new_stop_loss), isin))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore update_stop_loss_trailing {isin}: {e}")
            return False
        finally:
            conn.close()

    def accept_stop_loss_suggestion(self, isin: str) -> bool:
        """
        Accetta il suggerimento SL: copia stop_loss_suggested in stop_loss_inserted.

        Args:
            isin: Codice ISIN

        Returns:
            True se accettato, False se errore
        """
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE etf_portfolio_entries
                    SET stop_loss_inserted = stop_loss_suggested, stop_loss_updated_at = NOW()
                    WHERE isin = %s AND stop_loss_suggested IS NOT NULL
                """, (isin,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore accept_stop_loss_suggestion {isin}: {e}")
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
                cur.execute("SELECT isin, entry_date, entry_price, panic_low, livello_display FROM etf_l0_tracking")
                rows = cur.fetchall()
                return {
                    r['isin']: {
                        'entry_date':  r['entry_date'],
                        'entry_price': float(r['entry_price']),
                        'panic_low':   float(r['panic_low']) if r['panic_low'] else None,
                        'livello_display': r.get('livello_display', 'L0'),
                    }
                    for r in rows
                }
        except Exception as e:
            logging.error(f"Errore get_all_l0_entries: {e}")
            return {}
        finally:
            conn.close()

    def set_l0_entry(self, isin: str, entry_date: str, entry_price: float,
                     panic_low: float = None, confirmation_mode: str = None,
                     trigger_low_price: float = None) -> bool:
        """
        Registra l'ingresso di un ETF in L0 con stato persistente.

        Args:
            isin: Codice ISIN
            entry_date: Data ingresso (YYYY-MM-DD)
            entry_price: Prezzo ingresso
            panic_low: Prezzo minimo per stop assoluto
            confirmation_mode: 'FAST' o 'SLOW' (percorso L0 attivato)
            trigger_low_price: Prezzo minimo che ha triggerato L0 (per invalidazione)
        """
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO etf_l0_tracking
                    (isin, entry_date, entry_price, panic_low, confirmation_mode, trigger_low_price)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (isin) DO NOTHING
                """, (isin, entry_date, float(entry_price),
                      float(panic_low) if panic_low else None,
                      confirmation_mode, float(trigger_low_price) if trigger_low_price else None))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore set_l0_entry {isin}: {e}")
            return False
        finally:
            conn.close()

    def get_l0_state(self, isin: str) -> dict:
        """
        Legge lo stato persistente di un ETF in L0.

        Returns:
            Dict con {confirmation_mode, trigger_low_price, entry_price, entry_date}
            oppure {} se non trovato
        """
        conn = self._get_connection()
        if not conn:
            return {}
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT confirmation_mode, trigger_low_price, entry_price, entry_date
                    FROM etf_l0_tracking
                    WHERE isin = %s
                """, (isin,))
                row = cur.fetchone()
                if row:
                    return {
                        'confirmation_mode': row[0],
                        'trigger_low_price': float(row[1]) if row[1] else None,
                        'entry_price': float(row[2]),
                        'entry_date': str(row[3])
                    }
                return {}
        except Exception as e:
            logging.error(f"Errore get_l0_state {isin}: {e}")
            return {}
        finally:
            conn.close()

    def update_l0_state(self, isin: str, confirmation_mode: str = None,
                        trigger_low_price: float = None) -> bool:
        """Aggiorna lo stato persistente di un ETF in L0."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                if confirmation_mode is not None:
                    cur.execute("""
                        UPDATE etf_l0_tracking
                        SET confirmation_mode = %s
                        WHERE isin = %s
                    """, (confirmation_mode, isin))
                if trigger_low_price is not None:
                    cur.execute("""
                        UPDATE etf_l0_tracking
                        SET trigger_low_price = %s
                        WHERE isin = %s
                    """, (float(trigger_low_price), isin))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore update_l0_state {isin}: {e}")
            return False
        finally:
            conn.close()

    def update_l0_livello_display(self, isin: str, livello_display: str) -> bool:
        """Aggiorna il livello tecnico display per una posizione L0."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE etf_l0_tracking
                    SET livello_display = %s
                    WHERE isin = %s
                """, (livello_display, isin))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore update_l0_livello_display {isin}: {e}")
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
        """Restituisce gli ETF ATTIVI nel portafoglio.

        Fix 2026-08-05: prima non filtrava per status, quindi la dashboard
        (Portafoglio Personale, tab L1/L0) mostrava anche le posizioni con
        status='exited' come se fossero ancora aperte — un ETF chiuso da
        settimane restava visibile in "L1 Portfolio (N)" senza nessuna
        indicazione che non era più una posizione reale.
        """
        conn = self._get_connection()
        if not conn:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT isin, fund_name, entry_date, entry_price, shares,
                           exit_date, exit_price, status,
                           is_partial, partial_exit_date, partial_exit_price,
                           portfolio_type, stop_loss_l0_suggested,
                           sl_suggerito, sg_suggerito, stop_loss_inserted, stop_gain_target,
                           broker, tp_proximity_stop_max, stop_trigger_inserted
                    FROM etf_portfolio_entries
                    WHERE status = 'active'
                    ORDER BY entry_date DESC
                """)
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logging.error(f"Errore get_portfolio_entries: {e}")
            return []
        finally:
            conn.close()

    def get_portfolio_entries_by_type(self, portfolio_type: str = 'L1') -> list:
        """Restituisce ETF del portafoglio filtrati per tipo (L1 o L0)."""
        conn = self._get_connection()
        if not conn:
            return []
        try:
            from psycopg2.extras import RealDictCursor
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT isin, fund_name, entry_date, entry_price,
                           exit_date, exit_price, status,
                           is_partial, partial_exit_date, partial_exit_price,
                           portfolio_type, stop_loss_l0_suggested,
                           sl_suggerito, sg_suggerito, stop_loss_inserted, stop_gain_target,
                           broker
                    FROM etf_portfolio_entries
                    WHERE portfolio_type = %s
                    ORDER BY entry_date DESC
                """, (portfolio_type,))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logging.error(f"Errore get_portfolio_entries_by_type {portfolio_type}: {e}")
            return []
        finally:
            conn.close()

    def is_etf_in_l1_tracking(self, isin: str) -> bool:
        """Verifica se un ETF è in L1 tracking."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM etf_l1_tracking WHERE isin = %s LIMIT 1", (isin,))
                return cur.fetchone() is not None
        except Exception as e:
            logging.error(f"Errore is_etf_in_l1_tracking {isin}: {e}")
            return False
        finally:
            conn.close()

    def add_portfolio_entry(self, isin: str, entry_date: str,
                            entry_price: float, fund_name: str = '',
                            portfolio_type: str = 'L1', stop_loss_l0_suggested: float = None,
                            broker: str = 'Directa') -> bool:
        """Aggiunge un ETF al portafoglio (L1 o L0) con opzionali stop loss L0.

        Fix 2026-08-05: la tabella ha DUE colonne per lo stesso concetto —
        'portafoglio' (letta da monitor.py per calcolare SL/TP giornalieri e
        da alerts.py per l'email) e 'portfolio_type' (scritta/letta qui e in
        dashboard.html). Questo metodo scriveva solo la seconda, lasciando
        'portafoglio' bloccata sul default 'L1' — un ETF aggiunto come L0 da
        dashboard veniva quindi elaborato con la logica SL/TP di L1 dal
        monitor, mai da quella L0. Ora scrive entrambe le colonne allineate.
        """
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO etf_portfolio_entries (isin, fund_name, entry_date, entry_price, status, portfolio_type, portafoglio, stop_loss_l0_suggested, broker)
                    VALUES (%s, %s, %s, %s, 'active', %s, %s, %s, %s)
                    ON CONFLICT (isin) DO UPDATE
                        SET entry_date = EXCLUDED.entry_date,
                            entry_price = EXCLUDED.entry_price,
                            fund_name = EXCLUDED.fund_name,
                            status = 'active',
                            portfolio_type = EXCLUDED.portfolio_type,
                            portafoglio = EXCLUDED.portafoglio,
                            stop_loss_l0_suggested = EXCLUDED.stop_loss_l0_suggested,
                            broker = EXCLUDED.broker,
                            exit_date = NULL,
                            exit_price = NULL
                """, (isin, fund_name, entry_date, entry_price, portfolio_type, portfolio_type, stop_loss_l0_suggested, broker))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore add_portfolio_entry {isin}: {e}")
            return False
        finally:
            conn.close()

    def update_portfolio_broker(self, isin: str, broker: str) -> bool:
        """Aggiorna il broker (Directa/Webank/...) di una posizione esistente —
        determina quale guida SL/TP mostrare in email/dashboard (vedi
        order_pricing.py e CLAUDE.md 'Esecuzione ordini reali su Directa')."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE etf_portfolio_entries SET broker = %s WHERE isin = %s",
                            (broker, isin))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore update_portfolio_broker {isin}: {e}")
            return False
        finally:
            conn.close()

    def add_pac_contribution(self, isin: str, ticker: str, contribution_date: str,
                              amount_eur: float, price: float, fund_name: str = '',
                              broker: str = 'Directa') -> bool:
        """Registra un versamento PAC reale — l'utente ha già eseguito l'acquisto su
        Directa il giorno fisso del mese e registra qui a mano quanto/a che prezzo.
        Nessun automatismo: stessa filosofia di add_portfolio_entry. UNIQUE(isin,
        contribution_date) evita doppioni se lo stesso mese viene inserito due volte."""
        conn = self._get_connection()
        if not conn:
            return False
        shares = amount_eur / price if price else 0
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO etf_pac_contributions
                        (isin, ticker, fund_name, contribution_date, amount_eur, price, shares, broker)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (isin, contribution_date) DO UPDATE
                        SET amount_eur = EXCLUDED.amount_eur,
                            price = EXCLUDED.price,
                            shares = EXCLUDED.shares,
                            fund_name = EXCLUDED.fund_name,
                            broker = EXCLUDED.broker
                """, (isin, ticker, fund_name, contribution_date, amount_eur, price, shares, broker))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore add_pac_contribution {isin}: {e}")
            return False
        finally:
            conn.close()

    def get_pac_contributions(self, isin: str = None) -> List[Dict]:
        """Tutti i versamenti PAC, opzionalmente filtrati per ISIN, ordinati per data."""
        conn = self._get_connection()
        if not conn:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if isin:
                    cur.execute("""
                        SELECT * FROM etf_pac_contributions
                        WHERE isin = %s ORDER BY contribution_date
                    """, (isin,))
                else:
                    cur.execute("SELECT * FROM etf_pac_contributions ORDER BY contribution_date")
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logging.error(f"Errore get_pac_contributions: {e}")
            return []
        finally:
            conn.close()

    def remove_pac_contribution(self, contribution_id: int) -> bool:
        """Rimuove un versamento PAC registrato per errore."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM etf_pac_contributions WHERE id = %s", (contribution_id,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore remove_pac_contribution {contribution_id}: {e}")
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

    # ── Preferiti (watchlist personale) ─────────────────────────────────────

    def get_favorites(self) -> List[Dict]:
        """Restituisce tutti gli ETF nei Preferiti, più recenti prima."""
        conn = self._get_connection()
        if not conn:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT isin, ticker, nome, note, added_date,
                           last_buy_count, last_level, last_regime, last_checked_date
                    FROM etf_favorites
                    ORDER BY added_date DESC
                """)
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logging.error(f"Errore get_favorites: {e}")
            return []
        finally:
            conn.close()

    def add_favorite(self, isin: str, ticker: str = '', nome: str = '', note: str = '') -> bool:
        """Aggiunge un ETF ai Preferiti (idempotente — nessun errore se già presente)."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO etf_favorites (isin, ticker, nome, note, added_date)
                    VALUES (%s, %s, %s, %s, CURRENT_DATE)
                    ON CONFLICT (isin) DO NOTHING
                """, (isin, ticker, nome, note))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore add_favorite {isin}: {e}")
            return False
        finally:
            conn.close()

    def remove_favorite(self, isin: str) -> bool:
        """Rimuove definitivamente un ETF dai Preferiti."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM etf_favorites WHERE isin = %s", (isin,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore remove_favorite {isin}: {e}")
            return False
        finally:
            conn.close()

    def update_favorite_snapshot(self, isin: str, buy_count: int, level: int,
                                  regime: str) -> bool:
        """Aggiorna lo stato 'ieri' di un preferito (chiamato dal monitor ogni
        ciclo) — serve al digest email per calcolare i delta giorno su giorno."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE etf_favorites
                    SET last_buy_count = %s, last_level = %s, last_regime = %s,
                        last_checked_date = CURRENT_DATE
                    WHERE isin = %s
                """, (buy_count, level, regime, isin))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore update_favorite_snapshot {isin}: {e}")
            return False
        finally:
            conn.close()

    # ── L0 State Management ───────────────────────────────────────────────

    def get_l0_state(self, isin: str) -> Optional[Dict]:
        """Recupera lo stato L0 persistente (confirmation mode + trigger price)."""
        conn = self._get_connection()
        if not conn:
            return None
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT l0_confirmation_mode, l0_trigger_low_price, l0_trigger_date
                    FROM etf_l0_tracking
                    WHERE isin = %s
                    LIMIT 1
                """, (isin,))
                row = cur.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logging.error(f"Errore get_l0_state {isin}: {e}")
            return None
        finally:
            conn.close()

    def update_l0_state(self, isin: str, confirmation_mode: str,
                        trigger_low_price: float, trigger_date: str = None) -> bool:
        """Salva lo stato L0 (percorso lento/rapido bloccato)."""
        if trigger_date is None:
            trigger_date = datetime.now().strftime('%Y-%m-%d')
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE etf_l0_tracking
                    SET l0_confirmation_mode=%s, l0_trigger_low_price=%s, l0_trigger_date=%s
                    WHERE isin = %s
                """, (confirmation_mode, trigger_low_price, trigger_date, isin))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore update_l0_state {isin}: {e}")
            return False
        finally:
            conn.close()

    def invalidate_l0_state(self, isin: str) -> bool:
        """Invalida lo stato L0 (reset completo)."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE etf_l0_tracking
                    SET l0_confirmation_mode=NULL, l0_trigger_low_price=NULL, l0_trigger_date=NULL
                    WHERE isin = %s
                """, (isin,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore invalidate_l0_state {isin}: {e}")
            return False
        finally:
            conn.close()

    # ── L2 Watchlist Management ───────────────────────────────────────────

    def get_l2_watchlist_state(self, isin: str) -> Optional[Dict]:
        """Recupera lo stato L2 (score, in_watchlist, ema_smoothed, etc.)."""
        conn = self._get_connection()
        if not conn:
            return None
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT isin, ticker, score, in_watchlist, entered_date, exited_date,
                           ema_smoothed_value, last_raw_score, updated_at
                    FROM etf_l2_watchlist
                    WHERE isin = %s
                    LIMIT 1
                """, (isin,))
                row = cur.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logging.error(f"Errore get_l2_watchlist_state {isin}: {e}")
            return None
        finally:
            conn.close()

    def update_l2_watchlist_state(self, isin: str, ticker: str, score: float,
                                   in_watchlist: bool, ema_smoothed_value: float,
                                   last_raw_score: float) -> bool:
        """Aggiorna lo stato L2 watchlist."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            entered_date = datetime.now().strftime('%Y-%m-%d') if in_watchlist else None
            exited_date = datetime.now().strftime('%Y-%m-%d') if not in_watchlist else None

            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO etf_l2_watchlist (isin, ticker, score, in_watchlist, entered_date, exited_date, ema_smoothed_value, last_raw_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (isin) DO UPDATE SET
                        score=%s, in_watchlist=%s, entered_date=%s, exited_date=%s,
                        ema_smoothed_value=%s, last_raw_score=%s, updated_at=CURRENT_TIMESTAMP
                """, (isin, ticker, score, in_watchlist, entered_date, exited_date,
                      ema_smoothed_value, last_raw_score,
                      score, in_watchlist, entered_date, exited_date,
                      ema_smoothed_value, last_raw_score))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Errore update_l2_watchlist_state {isin}: {e}")
            return False
        finally:
            conn.close()

    def get_l2_watchlist_active(self) -> List[Dict]:
        """Restituisce tutti gli ETF in L2 watchlist (in_watchlist=true)."""
        conn = self._get_connection()
        if not conn:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT isin, ticker, score, entered_date, ema_smoothed_value, updated_at
                    FROM etf_l2_watchlist
                    WHERE in_watchlist = TRUE
                    ORDER BY score DESC, updated_at DESC
                """)
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logging.error(f"Errore get_l2_watchlist_active: {e}")
            return []
        finally:
            conn.close()


# Istanza globale per import da altri moduli
db = PriceDatabase()


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
