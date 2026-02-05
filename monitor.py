"""
monitor.py - Script principale di monitoraggio ETF
====================================================
Orchestrazione del sistema:
1. Legge file Excel con lista ETF
2. Recupera dati OHLCV via yfinance
3. Calcola indicatori tecnici (EMA13, SMA50, RSI, ADX, Volume)
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
from decimal import Decimal
from pathlib import Path

# Import moduli locali
from data_fetcher import ETFDataFetcher
from technical_analysis import ETFTechnicalAnalyzer
from alerts import AlertSystem
from database import PriceDatabase


class ETFMonitor:
    """Sistema principale di monitoraggio ETF"""

    def __init__(self, excel_path: str = 'etf_monitoraggio.xlsx'):
        self.excel_path = excel_path
        self.data_fetcher = ETFDataFetcher()
        self.analyzer = ETFTechnicalAnalyzer()
        self.alert_system = AlertSystem()
        self.db = PriceDatabase()

        # Carica configurazione
        self.config = self._load_config()

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
                'ADX Threshold': 25,
                'Volume Multiplier': 1.5,
            }

    def load_etfs(self) -> pd.DataFrame:
        """
        Carica lista ETF dal file Excel

        Returns:
            DataFrame con tutti gli ETF
        """
        try:
            df = pd.read_excel(self.excel_path, sheet_name='ETF')
            print(f"Caricati {len(df)} ETF dal file Excel")
            return df
        except Exception as e:
            print(f"Errore caricamento ETF: {e}")
            return pd.DataFrame()

    def get_etf_history(self, ticker: str) -> pd.DataFrame:
        """
        Recupera storico OHLCV per un ETF.
        Prima prova il database, poi scarica da yfinance se necessario.

        Args:
            ticker: Ticker dell'ETF

        Returns:
            DataFrame con colonne Open, High, Low, Close, Volume
        """
        # 1. Scarica storico da yfinance (6 mesi)
        hist_df = self.data_fetcher.get_historical_data(ticker, period='6mo')

        if not hist_df.empty:
            # Salva nel database
            saved = self.db.save_ohlcv_bulk(ticker, hist_df)
            if saved > 0:
                print(f"    Salvati {saved} record in DB per {ticker}")

        # 2. Recupera dal database (piu' affidabile, include storico)
        db_df = self.db.get_ohlcv(ticker, days=200)

        if not db_df.empty and len(db_df) >= 55:
            # Converti in formato con colonne maiuscole per compatibilita'
            result = pd.DataFrame({
                'Open': db_df['open'].values,
                'High': db_df['high'].values,
                'Low': db_df['low'].values,
                'Close': db_df['close'].values,
                'Volume': db_df['volume'].values
            }, index=db_df['date'])
            return result

        # 3. Usa direttamente i dati yfinance se DB non disponibile
        if not hist_df.empty:
            return hist_df

        return pd.DataFrame()

    def analyze_etf(self, row: pd.Series) -> dict:
        """
        Analizza un singolo ETF

        Args:
            row: Riga del DataFrame con dati ETF

        Returns:
            Dizionario con risultati analisi
        """
        ticker = row['Ticker']
        level = int(row['Livello'])

        print(f"  Analisi {row['Nome ETF'][:40]}...")

        # Recupera storico OHLCV
        ohlcv = self.get_etf_history(ticker)

        if ohlcv.empty or len(ohlcv) < 20:
            print(f"    Storico insufficiente per {ticker} ({len(ohlcv)} giorni)")
            return {
                'ticker': ticker,
                'nome': row['Nome ETF'],
                'categoria': row['Categoria'],
                'borsa': row.get('Borsa', ''),
                'livello': level,
                'analysis': {
                    'current_price': None,
                    'ema13': None,
                    'sma50': None,
                    'rsi': None,
                    'adx': None,
                    'volume_ratio': None,
                    'final_signal': 'HOLD',
                    'signal_strength': 0,
                    'suggested_level': level,
                    'level_change': False,
                    'level_reason': f'Dati insufficienti: {len(ohlcv)} giorni',
                    'data_status': 'insufficient'
                }
            }

        # Esegui analisi
        analysis = self.analyzer.analyze_etf(ohlcv, level=level)

        return {
            'ticker': ticker,
            'nome': row['Nome ETF'],
            'categoria': row['Categoria'],
            'borsa': row.get('Borsa', ''),
            'livello': level,
            'analysis': analysis
        }

    def update_excel(self, results: list):
        """
        Aggiorna il file Excel con i risultati dell'analisi

        Args:
            results: Lista di risultati analisi
        """
        try:
            wb = load_workbook(self.excel_path)
            ws = wb['ETF']

            # Mappa colonne Excel:
            # A(1)=Livello, B(2)=Ticker, C(3)=Nome, D(4)=Categoria, E(5)=Borsa,
            # F(6)=Valuta, G(7)=Prezzo, H(8)=EMA13, I(9)=SMA50, J(10)=RSI,
            # K(11)=ADX, L(12)=Vol Ratio, M(13)=Segnale, N(14)=Ultima Modifica
            COL_LIVELLO = 1
            COL_TICKER = 2
            COL_PREZZO = 7
            COL_EMA13 = 8
            COL_SMA50 = 9
            COL_RSI = 10
            COL_ADX = 11
            COL_VOL_RATIO = 12
            COL_SEGNALE = 13
            COL_ULTIMA_MODIFICA = 14

            # Mappa ticker -> riga
            ticker_to_row = {}
            for row in range(2, ws.max_row + 1):
                ticker = ws.cell(row=row, column=COL_TICKER).value
                if ticker:
                    ticker_to_row[ticker] = row

            level_changes = []

            for result in results:
                ticker = result['ticker']
                analysis = result['analysis']

                if ticker in ticker_to_row:
                    row = ticker_to_row[ticker]

                    # Livello - aggiornamento automatico
                    current_level = result['livello']
                    suggested_level = analysis.get('suggested_level', current_level)
                    level_reason = analysis.get('level_reason', '')

                    if suggested_level != current_level:
                        ws.cell(row=row, column=COL_LIVELLO, value=suggested_level)
                        level_changes.append({
                            'nome': result['nome'],
                            'ticker': ticker,
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

                    # Prezzo
                    ws.cell(row=row, column=COL_PREZZO, value=analysis.get('current_price'))

                    # EMA13
                    ws.cell(row=row, column=COL_EMA13, value=analysis.get('ema13'))

                    # SMA50
                    ws.cell(row=row, column=COL_SMA50, value=analysis.get('sma50'))

                    # RSI
                    ws.cell(row=row, column=COL_RSI, value=analysis.get('rsi'))

                    # ADX
                    ws.cell(row=row, column=COL_ADX, value=analysis.get('adx'))

                    # Volume Ratio
                    ws.cell(row=row, column=COL_VOL_RATIO, value=analysis.get('volume_ratio'))

                    # Segnale
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

                    # Ultima Modifica
                    ws.cell(row=row, column=COL_ULTIMA_MODIFICA,
                            value=datetime.now().strftime('%Y-%m-%d %H:%M'))

            wb.save(self.excel_path)
            print(f"File Excel aggiornato")

            if level_changes:
                print(f"\nCAMBI DI LIVELLO AUTOMATICI:")
                for change in level_changes:
                    direction = "UP" if change['to'] < change['from'] else "DOWN"
                    print(f"  {direction} {change['nome'][:40]}: L{change['from']} -> L{change['to']}")
                    print(f"     Motivo: {change['reason']}")

            return level_changes

        except Exception as e:
            print(f"Errore aggiornamento Excel: {e}")
            return []

    def generate_dashboard_data(self, results: list) -> dict:
        """
        Genera dati per la dashboard HTML

        Args:
            results: Lista risultati analisi

        Returns:
            Dizionario con dati dashboard
        """
        dashboard_data = {
            'last_update': datetime.now().isoformat(),
            'summary': {
                'total_etfs': len(results),
                'buy_signals': 0,
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
            level = r['livello']
            category = r['categoria']

            if signal == 'BUY':
                dashboard_data['summary']['buy_signals'] += 1
            elif signal == 'SELL':
                dashboard_data['summary']['sell_signals'] += 1
            else:
                dashboard_data['summary']['hold_signals'] += 1

            etf_data = {
                'ticker': r['ticker'],
                'nome': r['nome'],
                'categoria': category,
                'borsa': r.get('borsa', ''),
                'price': r['analysis'].get('current_price'),
                'ema13': r['analysis'].get('ema13'),
                'sma50': r['analysis'].get('sma50'),
                'rsi': r['analysis'].get('rsi'),
                'adx': r['analysis'].get('adx'),
                'volume_ratio': r['analysis'].get('volume_ratio'),
                'signal': signal,
                'signal_strength': r['analysis'].get('signal_strength', 0),
                'buy_count': r['analysis'].get('buy_count', 0),
                'crossover': r['analysis'].get('crossover', 'neutral')
            }
            dashboard_data['levels'][level].append(etf_data)

            if category not in dashboard_data['categories']:
                dashboard_data['categories'][category] = []
            dashboard_data['categories'][category].append(etf_data)

        # Salva JSON (converte Decimal dal DB in float)
        class DecimalEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                return super().default(obj)

        with open('data/dashboard_data.json', 'w') as f:
            json.dump(dashboard_data, f, indent=2, cls=DecimalEncoder)

        return dashboard_data

    def send_alerts(self, results: list):
        """Invia alert per segnali significativi"""
        for r in results:
            signal = r['analysis'].get('final_signal', 'HOLD')
            strength = r['analysis'].get('signal_strength', 0)
            level = r['livello']

            etf_info = {
                'ticker': r['ticker'],
                'nome': r['nome'],
                'categoria': r['categoria'],
                'livello': level
            }

            # L1: Alert sempre su SELL
            if level == 1 and signal == 'SELL':
                print(f"  ALERT SELL per L1: {r['nome'][:40]}")
                self.alert_system.send_sell_alert(etf_info, r['analysis'])

            # L2: Alert su BUY forte o SELL
            elif level == 2:
                if signal == 'BUY' and strength >= 4:
                    print(f"  ALERT BUY per L2: {r['nome'][:40]}")
                    self.alert_system.send_buy_alert(etf_info, r['analysis'])
                elif signal == 'SELL':
                    print(f"  ALERT SELL per L2: {r['nome'][:40]}")
                    self.alert_system.send_sell_alert(etf_info, r['analysis'])

            # L3: Alert solo se BUY con tutte le condizioni (5/5)
            elif level == 3 and signal == 'BUY' and strength == 5:
                print(f"  ALERT BUY per L3: {r['nome'][:40]}")
                self.alert_system.send_buy_alert(etf_info, r['analysis'])

    def run(self, send_daily_report: bool = True):
        """Esegue ciclo completo di monitoraggio"""
        print("\n" + "=" * 60)
        print(f"ETF MONITOR - Avvio monitoraggio {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)

        # 1. Carica ETF
        df_etfs = self.load_etfs()
        if df_etfs.empty:
            print("Nessun ETF da monitorare")
            return

        # 2. Analizza ogni ETF
        print(f"\nAnalisi di {len(df_etfs)} ETF...")
        results = []

        for idx, row in df_etfs.iterrows():
            try:
                result = self.analyze_etf(row)
                results.append(result)
                time.sleep(0.5)  # Rate limiting yfinance
            except Exception as e:
                print(f"  Errore analisi {row['Ticker']}: {e}")

        print(f"\nAnalisi completata: {len(results)} ETF processati")

        # 3. Aggiorna Excel
        print("\nAggiornamento file Excel...")
        self.update_excel(results)

        # 4. Genera dati dashboard
        print("\nGenerazione dati dashboard...")
        os.makedirs('data', exist_ok=True)
        dashboard_data = self.generate_dashboard_data(results)

        # 5. Invia alert
        print("\nVerifica e invio alert...")
        self.send_alerts(results)

        # 6. Report giornaliero
        if send_daily_report:
            print("\nInvio report giornaliero...")
            summary = {
                'buy_signals': dashboard_data['summary']['buy_signals'],
                'sell_signals': dashboard_data['summary']['sell_signals'],
                'hold_signals': dashboard_data['summary']['hold_signals'],
                'level_1': dashboard_data['levels'][1],
                'level_2': dashboard_data['levels'][2],
                'level_3': dashboard_data['levels'][3][:10]
            }
            self.alert_system.send_daily_report(summary)

        print("\n" + "=" * 60)
        print(f"Monitoraggio completato - {datetime.now().strftime('%H:%M')}")
        print("=" * 60 + "\n")


def main():
    """Entry point"""
    monitor = ETFMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
