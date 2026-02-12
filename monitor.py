"""
monitor.py - Script principale di monitoraggio ETF
====================================================
Orchestrazione del sistema:
1. Legge file Excel con lista ETF + mapping ISIN
2. Recupera dati prezzi Close via JustETF (per ISIN)
3. Calcola indicatori tecnici (EMA13, SMA50, RSI, MACD, Bollinger)
4. Genera segnali BUY/SELL/HOLD
5. Invia alert
6. Aggiorna Excel e dashboard
"""

import os
import sys
from datetime import datetime, timedelta
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
import json
import time
import numpy as np
from decimal import Decimal
from pathlib import Path

# Import moduli locali
from justetf_fetcher import JustETFDataFetcher
from technical_analysis import ETFTechnicalAnalyzer
from alerts import AlertSystem
from database import PriceDatabase


# Log globale degli errori consultabile via /api/monitor-log
monitor_log = []


def add_log(message: str):
    """Aggiunge un messaggio al log globale"""
    entry = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
    monitor_log.append(entry)
    # Tieni solo gli ultimi 200 messaggi
    if len(monitor_log) > 200:
        monitor_log.pop(0)
    print(entry)


class ETFMonitor:
    """Sistema principale di monitoraggio ETF"""

    def __init__(self, excel_path: str = 'etf_monitoraggio.xlsx'):
        self.excel_path = excel_path
        self.data_fetcher = JustETFDataFetcher(rate_limit=1.0)
        self.analyzer = ETFTechnicalAnalyzer()
        self.alert_system = AlertSystem()
        self.db = PriceDatabase()
        self.isin_mapping = self._load_isin_mapping()

        # Carica configurazione
        self.config = self._load_config()

    def _load_isin_mapping(self) -> dict:
        """Carica il mapping ISIN da file JSON"""
        mapping_path = 'data/isin_mapping.json'
        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                mapping_list = json.load(f)
            # Crea dict per indice Excel -> ISIN
            mapping = {}
            for entry in mapping_list:
                idx = entry.get('excel_index')
                isin = entry.get('isin', '')
                if idx is not None and isin:
                    mapping[idx] = entry
            add_log(f"Mapping ISIN caricato: {len(mapping)} ETF con ISIN")
            return mapping
        except FileNotFoundError:
            add_log("WARNING: File data/isin_mapping.json non trovato. Esegui isin_resolver.py prima.")
            return {}

    def _load_config(self) -> dict:
        """Carica configurazione dal file Excel"""
        try:
            df_config = pd.read_excel(self.excel_path, sheet_name='CONFIG', header=None)
            config = {}
            for _, row in df_config.iterrows():
                if pd.notna(row[0]) and pd.notna(row[1]):
                    key = str(row[0]).strip()
                    value = row[1]
                    config[key] = value
            return config
        except Exception as e:
            print(f"Configurazione default (CONFIG sheet non trovato: {e})")
            return {
                'EMA Fast Period': 13,
                'SMA Slow Period': 50,
                'RSI Period': 14,
                'RSI Buy Low': 55,
                'RSI Buy High': 65,
            }

    def load_etfs(self) -> pd.DataFrame:
        """Carica lista ETF dal file Excel, arricchita con ISIN"""
        try:
            df = pd.read_excel(self.excel_path, sheet_name='ETF')
            print(f"Caricati {len(df)} ETF dal file Excel")

            # Aggiungi ISIN dal mapping
            if 'ISIN' not in df.columns:
                df['ISIN'] = ''
                for idx in df.index:
                    if idx in self.isin_mapping:
                        df.at[idx, 'ISIN'] = self.isin_mapping[idx].get('isin', '')

            # Filtra ETF senza ISIN (non analizzabili)
            with_isin = df[df['ISIN'] != '']
            without_isin = df[df['ISIN'] == '']
            if len(without_isin) > 0:
                add_log(f"WARNING: {len(without_isin)} ETF senza ISIN (saranno saltati)")

            return df
        except Exception as e:
            print(f"Errore caricamento ETF: {e}")
            return pd.DataFrame()

    def get_etf_history(self, isin: str) -> pd.DataFrame:
        """
        Recupera storico prezzi Close per un ETF via JustETF.
        Prima prova il database, poi scarica da JustETF se necessario.
        """
        # 1. Prova a recuperare dal database
        db_df = self.db.get_close_by_isin(isin, days=200)

        if not db_df.empty and len(db_df) >= 55:
            return db_df

        # 2. Scarica da JustETF
        hist_df = self.data_fetcher.get_historical_data(isin, days=200)

        if not hist_df.empty:
            # Salva nel database
            saved = self.db.save_close_bulk(isin, hist_df, source='justetf')
            if saved > 0:
                print(f"    Salvati {saved} record in DB per {isin}")
            return hist_df

        # 3. Usa i dati dal database anche se insufficienti
        if not db_df.empty:
            return db_df

        return pd.DataFrame()

    def analyze_etf(self, row: pd.Series) -> dict:
        """Analizza un singolo ETF"""
        ticker = row['Ticker']
        isin = row.get('ISIN', '')
        level = int(row['Livello'])

        print(f"  Analisi {row['Nome ETF'][:40]}...")

        if not isin:
            print(f"    ISIN mancante per {ticker} - skip")
            return {
                'ticker': ticker,
                'isin': '',
                'nome': row['Nome ETF'],
                'categoria': row['Categoria'],
                'borsa': row.get('Borsa', ''),
                'livello': level,
                'analysis': {
                    'current_price': None,
                    'ema13': None, 'sma50': None, 'rsi': None,
                    'macd': None, 'macd_histogram': None,
                    'bb_width': None, 'bb_pct_b': None,
                    'final_signal': 'HOLD', 'signal_strength': 0,
                    'suggested_level': level, 'level_change': False,
                    'level_reason': 'ISIN mancante',
                    'data_status': 'no_isin'
                }
            }

        # Recupera storico Close
        close_df = self.get_etf_history(isin)

        if close_df.empty or len(close_df) < 20:
            print(f"    Storico insufficiente per {isin} ({len(close_df)} giorni)")
            return {
                'ticker': ticker,
                'isin': isin,
                'nome': row['Nome ETF'],
                'categoria': row['Categoria'],
                'borsa': row.get('Borsa', ''),
                'livello': level,
                'analysis': {
                    'current_price': None,
                    'ema13': None, 'sma50': None, 'rsi': None,
                    'macd': None, 'macd_histogram': None,
                    'bb_width': None, 'bb_pct_b': None,
                    'final_signal': 'HOLD', 'signal_strength': 0,
                    'suggested_level': level, 'level_change': False,
                    'level_reason': f'Dati insufficienti: {len(close_df)} giorni',
                    'data_status': 'insufficient'
                }
            }

        # Esegui analisi tecnica (solo Close)
        analysis = self.analyzer.analyze_etf(close_df, level=level)

        return {
            'ticker': ticker,
            'isin': isin,
            'nome': row['Nome ETF'],
            'categoria': row['Categoria'],
            'borsa': row.get('Borsa', ''),
            'livello': level,
            'analysis': analysis
        }

    def update_excel(self, results: list):
        """Aggiorna il file Excel con i risultati dell'analisi"""
        try:
            wb = load_workbook(self.excel_path)
            ws = wb['ETF']

            COL_LIVELLO = 1
            COL_TICKER = 2
            COL_PREZZO = 7
            COL_EMA13 = 8
            COL_SMA50 = 9
            COL_RSI = 10
            COL_MACD = 11       # Era ADX, ora MACD
            COL_BB_WIDTH = 12   # Era Vol Ratio, ora BB Width
            COL_SEGNALE = 13
            COL_ULTIMA_MODIFICA = 14

            # Usa indice Excel per identificare univocamente le righe
            # (evita problemi con ticker duplicati)
            excel_row_map = {}
            for row_idx in range(2, ws.max_row + 1):
                # Mappa per indice (riga Excel - 2 = indice DataFrame)
                excel_row_map[row_idx - 2] = row_idx

            level_changes = []

            for i, result in enumerate(results):
                analysis = result['analysis']
                row = excel_row_map.get(i)

                if row is None:
                    continue

                current_level = result['livello']
                suggested_level = analysis.get('suggested_level', current_level)
                level_reason = analysis.get('level_reason', '')

                if suggested_level != current_level:
                    ws.cell(row=row, column=COL_LIVELLO, value=suggested_level)
                    level_changes.append({
                        'nome': result['nome'],
                        'ticker': result['ticker'],
                        'isin': result.get('isin', ''),
                        'from': current_level,
                        'to': suggested_level,
                        'reason': level_reason
                    })
                    level_cell = ws.cell(row=row, column=COL_LIVELLO)
                    if suggested_level < current_level:
                        level_cell.fill = PatternFill("solid", fgColor="00B050")
                        level_cell.font = Font(bold=True, color="FFFFFF")
                    else:
                        level_cell.fill = PatternFill("solid", fgColor="FF6600")
                        level_cell.font = Font(bold=True, color="FFFFFF")

                ws.cell(row=row, column=COL_PREZZO, value=analysis.get('current_price'))
                ws.cell(row=row, column=COL_EMA13, value=analysis.get('ema13'))
                ws.cell(row=row, column=COL_SMA50, value=analysis.get('sma50'))
                ws.cell(row=row, column=COL_RSI, value=analysis.get('rsi'))
                ws.cell(row=row, column=COL_MACD, value=analysis.get('macd_histogram'))
                ws.cell(row=row, column=COL_BB_WIDTH, value=analysis.get('bb_width'))

                signal = analysis.get('final_signal', 'HOLD')
                signal_cell = ws.cell(row=row, column=COL_SEGNALE, value=signal)
                if signal == 'BUY':
                    signal_cell.fill = PatternFill("solid", fgColor="00B050")
                    signal_cell.font = Font(bold=True, color="FFFFFF")
                elif signal == 'SELL':
                    signal_cell.fill = PatternFill("solid", fgColor="FF0000")
                    signal_cell.font = Font(bold=True, color="FFFFFF")
                else:
                    signal_cell.fill = PatternFill("solid", fgColor="FFC000")
                    signal_cell.font = Font(bold=True)

                ws.cell(row=row, column=COL_ULTIMA_MODIFICA,
                        value=datetime.now().strftime('%Y-%m-%d %H:%M'))

            wb.save(self.excel_path)
            add_log(f"File Excel aggiornato")

            if level_changes:
                add_log(f"CAMBI DI LIVELLO: {len(level_changes)}")
                for change in level_changes:
                    direction = "UP" if change['to'] < change['from'] else "DOWN"
                    add_log(f"  {direction} {change['nome'][:40]}: L{change['from']} -> L{change['to']}")

            return level_changes

        except Exception as e:
            add_log(f"Errore aggiornamento Excel: {e}")
            return []

    def generate_dashboard_data(self, results: list) -> dict:
        """Genera dati per la dashboard HTML"""
        dashboard_data = {
            'last_update': datetime.now().isoformat(),
            'data_source': 'JustETF',
            'summary': {
                'total_etfs': len(results),
                'buy_signals': 0,
                'pullback_signals': 0,
                'sell_signals': 0,
                'hold_signals': 0
            },
            'levels': {
                1: [],
                2: [],
                3: []
            },
            'categories': {}
        }

        for r in results:
            signal = r['analysis'].get('final_signal', 'HOLD')
            level = r['analysis'].get('suggested_level', r['livello'])
            category = r['categoria']

            if signal == 'BUY':
                dashboard_data['summary']['buy_signals'] += 1
            elif signal == 'PULLBACK':
                dashboard_data['summary']['pullback_signals'] += 1
            elif signal == 'SELL':
                dashboard_data['summary']['sell_signals'] += 1
            else:
                dashboard_data['summary']['hold_signals'] += 1

            # Converti Decimal in float per evitare errori di serializzazione
            price = r['analysis'].get('current_price')
            ema13 = r['analysis'].get('ema13')
            sma50 = r['analysis'].get('sma50')

            etf_data = {
                'ticker': r['ticker'],
                'isin': r.get('isin', ''),
                'nome': r['nome'],
                'categoria': category,
                'borsa': r.get('borsa', ''),
                'price': float(price) if price is not None else None,
                'ema13': float(ema13) if ema13 is not None else None,
                'sma50': float(sma50) if sma50 is not None else None,
                'rsi': r['analysis'].get('rsi'),
                'macd': r['analysis'].get('macd'),
                'macd_histogram': r['analysis'].get('macd_histogram'),
                'bb_width': r['analysis'].get('bb_width'),
                'bb_pct_b': r['analysis'].get('bb_pct_b'),
                'signal': signal,
                'signal_strength': r['analysis'].get('signal_strength', 0),
                'buy_count': r['analysis'].get('buy_count', 0),
                'crossover': r['analysis'].get('crossover', 'neutral'),
                'pct_1d': r['analysis'].get('pct_change_1d'),
                'pct_1w': r['analysis'].get('pct_change_1w'),
                'pct_1m': r['analysis'].get('pct_change_1m'),
                'distance_from_ema': r['analysis'].get('distance_from_ema'),
                'pullback_active': r['analysis'].get('pullback_active', False),
                'limit_order_price': r['analysis'].get('limit_order_price')
            }
            dashboard_data['levels'][level].append(etf_data)

            if category not in dashboard_data['categories']:
                dashboard_data['categories'][category] = []
            dashboard_data['categories'][category].append(etf_data)

        # Salva JSON (converte Decimal e tipi numpy in tipi Python nativi)
        class SafeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                if isinstance(obj, (np.integer,)):
                    return int(obj)
                if isinstance(obj, (np.floating,)):
                    return float(obj)
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                return super().default(obj)

        with open('data/dashboard_data.json', 'w') as f:
            json.dump(dashboard_data, f, indent=2, cls=SafeEncoder)

        return dashboard_data

    def send_alerts(self, results: list):
        """Invia alert per segnali significativi"""
        for r in results:
            signal = r['analysis'].get('final_signal', 'HOLD')
            strength = r['analysis'].get('signal_strength', 0)
            level = r['livello']

            etf_info = {
                'ticker': r['ticker'],
                'isin': r.get('isin', ''),
                'nome': r['nome'],
                'categoria': r['categoria'],
                'livello': level
            }

            if level == 1 and signal == 'SELL':
                add_log(f"  ALERT SELL per L1: {r['nome'][:40]}")
                self.alert_system.send_sell_alert(etf_info, r['analysis'])

            elif level == 2:
                if signal == 'BUY' and strength >= 4:
                    add_log(f"  ALERT BUY per L2: {r['nome'][:40]}")
                    self.alert_system.send_buy_alert(etf_info, r['analysis'])
                elif signal == 'SELL':
                    add_log(f"  ALERT SELL per L2: {r['nome'][:40]}")
                    self.alert_system.send_sell_alert(etf_info, r['analysis'])

            elif level == 3 and signal == 'BUY' and strength == 5:
                add_log(f"  ALERT BUY per L3: {r['nome'][:40]}")
                self.alert_system.send_buy_alert(etf_info, r['analysis'])

    def run(self, send_daily_report: bool = True):
        """Esegue ciclo completo di monitoraggio"""
        import traceback
        add_log("=" * 50)
        add_log(f"ETF MONITOR - Avvio monitoraggio {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        add_log(f"Fonte dati: JustETF (solo Close)")

        # 1. Carica ETF
        df_etfs = self.load_etfs()
        if df_etfs.empty:
            add_log("ERRORE: Nessun ETF da monitorare (DataFrame vuoto)")
            return

        add_log(f"Caricati {len(df_etfs)} ETF dal file Excel")

        # 2. Analizza ogni ETF
        add_log(f"Inizio analisi di {len(df_etfs)} ETF...")
        results = []
        errors = []

        for idx, row in df_etfs.iterrows():
            try:
                result = self.analyze_etf(row)
                results.append(result)
                isin_str = result.get('isin', '')[:14]
                add_log(f"  OK {isin_str} - {row['Nome ETF'][:30]}")
            except Exception as e:
                error_detail = traceback.format_exc()
                errors.append({'ticker': row['Ticker'], 'error': str(e), 'traceback': error_detail})
                add_log(f"  ERRORE {row['Ticker']}: {e}")
                add_log(f"  TRACEBACK: {error_detail}")

        add_log(f"Analisi completata: {len(results)} OK, {len(errors)} errori")

        # 3. Aggiorna Excel
        try:
            add_log("Step 3: Aggiornamento file Excel...")
            self.update_excel(results)
            add_log("Step 3: Excel aggiornato OK")
        except Exception as e:
            add_log(f"Step 3 ERRORE Excel: {e}")
            add_log(traceback.format_exc())

        # 4. Genera dati dashboard
        try:
            add_log(f"Step 4: Generazione dashboard con {len(results)} risultati...")
            os.makedirs('data', exist_ok=True)
            dashboard_data = self.generate_dashboard_data(results)
            total = dashboard_data.get('summary', {}).get('total_etfs', '?')
            add_log(f"Step 4: Dashboard generata OK - {total} ETF")
        except Exception as e:
            add_log(f"Step 4 ERRORE Dashboard: {e}")
            add_log(traceback.format_exc())
            # Dashboard fallback
            dashboard_data = {
                'last_update': datetime.now().isoformat(),
                'data_source': 'JustETF',
                'summary': {'total_etfs': len(results), 'buy_signals': 0, 'sell_signals': 0, 'hold_signals': 0},
                'levels': {1: [], 2: [], 3: []},
                'categories': {}
            }
            for r in results:
                try:
                    etf_data = {
                        'ticker': r['ticker'], 'isin': r.get('isin', ''),
                        'nome': r['nome'], 'categoria': r['categoria'],
                        'borsa': r.get('borsa', ''), 'price': r['analysis'].get('current_price'),
                        'signal': r['analysis'].get('final_signal', 'HOLD'),
                        'signal_strength': r['analysis'].get('signal_strength', 0)
                    }
                    dashboard_data['levels'][r['livello']].append(etf_data)
                except:
                    pass
            with open('data/dashboard_data.json', 'w') as f:
                json.dump(dashboard_data, f, indent=2)
            add_log(f"Step 4: Dashboard fallback salvata con {len(results)} ETF")

        # 5. Invia alert
        try:
            add_log("Step 5: Invio alert...")
            self.send_alerts(results)
            add_log("Step 5: Alert OK")
        except Exception as e:
            add_log(f"Step 5 ERRORE Alert: {e}")

        # 6. Report giornaliero
        if send_daily_report:
            try:
                add_log("Step 6: Invio report giornaliero...")
                summary = {
                    'buy_signals': dashboard_data['summary']['buy_signals'],
                    'sell_signals': dashboard_data['summary']['sell_signals'],
                    'hold_signals': dashboard_data['summary']['hold_signals'],
                    'level_1': dashboard_data['levels'].get(1, []),
                    'level_2': dashboard_data['levels'].get(2, []),
                    'level_3': dashboard_data['levels'].get(3, [])[:10]
                }
                self.alert_system.send_daily_report(summary)
                add_log("Step 6: Report OK")
            except Exception as e:
                add_log(f"Step 6 ERRORE Report: {e}")

        add_log(f"Monitoraggio completato - {datetime.now().strftime('%H:%M')}")
        add_log("=" * 50)


def main():
    """Entry point"""
    monitor = ETFMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
