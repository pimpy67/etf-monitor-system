"""
monitor.py - Monitoraggio ETF
==============================
Orchestrazione del sistema:
1. Legge file Excel con lista ETF (ticker Yahoo Finance + ISIN)
2. Recupera dati OHLCV via Yahoo Finance
3. Calcola indicatori tecnici (EMA20, SMA50, SMA200, ADX, RSI)
4. Gestisce livelli L0/L1/L2/L3
5. Invia alert giornalieri
6. Genera dashboard JSON
"""

import os
import sys
from datetime import datetime, timedelta, date as date_type
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill
import json
import time
import numpy as np
from decimal import Decimal
from pathlib import Path
import traceback

from data_fetcher import ETFDataFetcher
from technical_analysis import ETFTechnicalAnalyzer
from alerts import AlertSystem
from database import PriceDatabase


monitor_log = []


def add_log(message: str):
    entry = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
    monitor_log.append(entry)
    if len(monitor_log) > 200:
        monitor_log.pop(0)
    print(entry)


class ETFMonitor:
    """Sistema principale di monitoraggio ETF"""

    def __init__(self, excel_path: str = 'etf_monitoraggio.xlsx'):
        self.excel_path   = excel_path
        self.data_fetcher = ETFDataFetcher(rate_limit=1.0)
        self.alert_system = AlertSystem()
        self.db           = PriceDatabase()

    def load_etfs(self) -> pd.DataFrame:
        """Carica lista ETF dal file Excel."""
        try:
            df = pd.read_excel(self.excel_path, sheet_name='ETF')
            add_log(f"Caricati {len(df)} ETF dal file Excel")
            return df
        except Exception as e:
            add_log(f"ERRORE caricamento Excel: {e}")
            return pd.DataFrame()

    def get_etf_history(self, ticker: str, isin: str = '') -> pd.DataFrame:
        """
        Recupera storico OHLCV per un ETF.
        Prima prova il DB; se i dati sono datati (> 5gg) rifresca da Yahoo Finance.
        """
        import pandas as _pd

        # 1. Database
        db_df = _pd.DataFrame()
        if isin:
            db_df = self.db.get_close_by_isin(isin, days=260)

        # Usa il DB solo se ha già i dati di oggi (last_date == today)
        if not db_df.empty and len(db_df) >= 55:
            today     = _pd.Timestamp.today().normalize()
            last_date = db_df.index[-1] if hasattr(db_df.index[-1], 'date') else _pd.Timestamp(db_df.index[-1])
            if (today - last_date).days <= 0:
                return db_df  # dati già aggiornati a oggi → no fetch Yahoo Finance

        # 2. Yahoo Finance (OHLCV completo) — DB assente o datato
        df = self.data_fetcher.get_historical_data(ticker, days=260)
        if not df.empty:
            if isin:
                self.db.save_close_bulk(isin, df, source='yfinance')
            else:
                self.db.save_ohlcv_bulk(ticker, df, source='yfinance')
            return df

        # 3. DB come fallback anche se datato
        if not db_df.empty:
            return db_df

        return _pd.DataFrame()

    def analyze_etf(self, row: pd.Series) -> dict:
        """Analizza un singolo ETF dalla riga Excel."""
        ticker   = str(row.get('Ticker', '')).strip()
        isin     = str(row.get('ISIN', '')).strip()
        nome     = str(row.get('Nome ETF', ticker))
        categoria = str(row.get('Categoria', ''))
        borsa    = str(row.get('Borsa', ''))
        level    = int(row.get('Livello', 3))

        # Nuovi sistema: usa famiglia da config YAML
        famiglia = ETFTechnicalAnalyzer.detect_family(categoria)
        analyzer = ETFTechnicalAnalyzer(famiglia=famiglia)

        # Mantieni etf_type per backward compatibility
        etf_type = famiglia

        identifier = ticker if ticker else isin
        if not identifier:
            add_log(f"  SKIP: nessun ticker per {nome}")
            return self._empty_result(ticker, isin, nome, categoria, borsa, level,
                                      'Ticker mancante')

        add_log(f"  Analisi {nome[:40]} ({identifier})...")

        hist = self.get_etf_history(ticker, isin)

        if hist.empty or len(hist) < 20:
            add_log(f"    Storico insufficiente: {len(hist)} giorni")
            return self._empty_result(ticker, isin, nome, categoria, borsa, level,
                                      f'Dati insufficienti: {len(hist)} giorni')

        analysis = analyzer.analyze_etf(hist, current_level=level)

        return {
            'ticker':    ticker,
            'isin':      isin,
            'nome':      nome,
            'categoria': categoria,
            'borsa':     borsa,
            'livello':   level,
            'etf_type':  etf_type,
            'analysis':  analysis,
        }

    def _empty_result(self, ticker, isin, nome, categoria, borsa, level, reason):
        famiglia = ETFTechnicalAnalyzer.detect_family(categoria)
        return {
            'ticker': ticker, 'isin': isin, 'nome': nome,
            'categoria': categoria, 'borsa': borsa, 'livello': level,
            'etf_type': famiglia,  # backward compatibility
            'analysis': {
                'current_price': None,
                'ema20': None, 'sma50': None, 'sma200': None,
                'rsi': None, 'adx': None, 'macd_histogram': None,
                'suggested_level': level, 'level_change': False,
                'level_reason': reason, 'conditions': {}, 'buy_count': 0,
                'l0_entry': False, 'l0_exit_rule': None,
                'pct_change_1d': None, 'pct_change_1w': None, 'pct_change_1m': None,
                'data_status': 'no_data',
            }
        }

    def update_excel(self, results: list):
        """Aggiorna il file Excel con i risultati."""
        try:
            wb = load_workbook(self.excel_path)
            ws = wb['ETF']

            COL_LIVELLO         = 1
            COL_TICKER          = 2
            COL_PREZZO          = 7
            COL_EMA20           = 8
            COL_SMA50           = 9
            COL_RSI             = 10
            COL_ADX             = 11
            COL_MACD            = 12
            COL_SEGNALE         = 13
            COL_ULTIMA_MODIFICA = 14

            excel_row_map = {row_idx - 2: row_idx for row_idx in range(2, ws.max_row + 1)}
            level_changes = []

            for i, result in enumerate(results):
                a = result['analysis']
                row = excel_row_map.get(i)
                if row is None:
                    continue

                current_level  = result['livello']
                suggested      = a.get('suggested_level', current_level)
                level_reason   = a.get('level_reason', '')

                if suggested != current_level:
                    ws.cell(row=row, column=COL_LIVELLO, value=suggested)
                    level_changes.append({
                        'nome': result['nome'], 'ticker': result['ticker'],
                        'isin': result.get('isin', ''),
                        'from': current_level, 'to': suggested,
                        'reason': level_reason,
                    })
                    cell = ws.cell(row=row, column=COL_LIVELLO)
                    if suggested < current_level:
                        cell.fill = PatternFill("solid", fgColor="00B050")
                        cell.font = Font(bold=True, color="FFFFFF")
                    else:
                        cell.fill = PatternFill("solid", fgColor="FF6600")
                        cell.font = Font(bold=True, color="FFFFFF")

                ws.cell(row=row, column=COL_PREZZO, value=a.get('current_price'))
                ws.cell(row=row, column=COL_EMA20,  value=a.get('ema20'))
                ws.cell(row=row, column=COL_SMA50,  value=a.get('sma50'))
                ws.cell(row=row, column=COL_RSI,    value=a.get('rsi'))
                ws.cell(row=row, column=COL_ADX,    value=a.get('adx'))
                ws.cell(row=row, column=COL_MACD,   value=a.get('macd_histogram'))

                # Segnale testuale
                if suggested == 0:
                    signal_txt = 'L0 RECOVERY'
                    color = 'FF6600'
                elif suggested == 1:
                    conds = a.get('buy_count', 0)
                    signal_txt = f'L1 BUY ({conds}/6)'
                    color = '00B050'
                elif suggested == 2:
                    signal_txt = 'L2 WATCH'
                    color = 'FFC000'
                else:
                    signal_txt = 'L3'
                    color = 'D9D9D9'

                cell = ws.cell(row=row, column=COL_SEGNALE, value=signal_txt)
                cell.fill = PatternFill("solid", fgColor=color)
                cell.font = Font(bold=True, color="000000" if color in ('FFC000', 'D9D9D9') else "FFFFFF")

                ws.cell(row=row, column=COL_ULTIMA_MODIFICA,
                        value=datetime.now().strftime('%Y-%m-%d %H:%M'))

            wb.save(self.excel_path)
            add_log(f"File Excel aggiornato")

            if level_changes:
                add_log(f"CAMBI DI LIVELLO: {len(level_changes)}")
                for c in level_changes:
                    dir_ = "UP" if c['to'] < c['from'] else "DOWN"
                    add_log(f"  {dir_} {c['nome'][:40]}: L{c['from']} → L{c['to']}")

            return level_changes

        except Exception as e:
            add_log(f"Errore aggiornamento Excel: {e}")
            add_log(traceback.format_exc())
            return []

    def generate_dashboard_data(self, results: list, send_daily_report: bool = True, errors: list = None) -> dict:
        """Genera dati JSON per la dashboard HTML."""
        if errors is None:
            errors = []
        l1_tracking = self.db.get_all_l1_entries()
        dashboard = {
            'last_update': datetime.now().isoformat(),
            'data_source': 'Yahoo Finance',
            'summary': {
                'total_etfs': len(results),
                'l0_count': 0, 'l1_count': 0, 'l2_count': 0, 'l3_count': 0,
                'alerts_sent': send_daily_report,
            },
            'levels': {0: [], 1: [], 2: [], 3: []},
            'categories': {},
        }

        for r in results:
            a         = r['analysis']
            suggested = a.get('suggested_level', r['livello'])
            category  = r['categoria']

            level_key = f'l{suggested}_count'
            if level_key in dashboard['summary']:
                dashboard['summary'][level_key] += 1

            price = a.get('current_price')
            etf_data = {
                'ticker':            r['ticker'],
                'isin':              r.get('isin', ''),
                'nome':              r['nome'],
                'categoria':         category,
                'borsa':             r.get('borsa', ''),
                'etf_type':          r.get('etf_type', 'equity_developed'),
                'price':             float(price) if price is not None else None,
                'ema20':             a.get('ema20'),
                'sma50':             a.get('sma50'),
                'sma200':            a.get('sma200'),
                'rsi':               a.get('rsi'),
                'adx':               a.get('adx'),
                'macd_histogram':    a.get('macd_histogram'),
                'dist_ema20':        a.get('dist_ema20'),
                'days_above_ema20':  a.get('days_above_ema20', 0),
                'buy_count':         a.get('buy_count', 0),
                'level_reason':      a.get('level_reason', ''),
                'conditions':        a.get('conditions', {}),
                'pct_1d':            a.get('pct_change_1d'),
                'pct_1w':            a.get('pct_change_1w'),
                'pct_1m':            a.get('pct_change_1m'),
                'peak_price':        a.get('peak_price'),
                'drawdown_from_peak': a.get('drawdown_from_peak', 0.0),
                'l0_entry':          a.get('l0_entry', False),
                'data_status':       a.get('data_status', 'ok'),
            }

            # entry_date e entry_price per ETF in L1 (serve per linea verticale grafico)
            if suggested == 1:
                isin_key = r.get('isin', '') or r['ticker']
                tracking = l1_tracking.get(isin_key, {})
                etf_data['entry_date']  = str(tracking.get('entry_date', '')) if tracking else ''
                etf_data['entry_price'] = float(tracking.get('entry_price', 0)) if tracking else None

            level_int = max(0, min(3, int(suggested)))
            dashboard['levels'][level_int].append(etf_data)

            if category not in dashboard['categories']:
                dashboard['categories'][category] = []
            dashboard['categories'][category].append(etf_data)

        class SafeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                if isinstance(obj, np.integer):
                    return int(obj)
                if isinstance(obj, np.floating):
                    return float(obj)
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                if isinstance(obj, (date_type, datetime)):
                    return str(obj)
                return super().default(obj)

        # Data freshness: data più recente nel DB
        try:
            stats = self.db.get_stats()
            dashboard['summary']['data_as_of'] = stats.get('last_date')
        except Exception:
            dashboard['summary']['data_as_of'] = None

        # Health report per /api/health
        dashboard['health'] = {
            'timestamp': datetime.now().isoformat(),
            'total_etfs': len(results),
            'etfs_ok': len(results),
            'etfs_error': len(errors),
            'errors': [{'ticker': e.get('ticker', '?'), 'error': e.get('error', '')} for e in errors],
            'etfs_with_price': sum(1 for r in results if r['analysis'].get('current_price') is not None),
            'etfs_no_price': sum(1 for r in results if r['analysis'].get('current_price') is None),
        }

        os.makedirs('data', exist_ok=True)
        with open('data/dashboard_data.json', 'w') as f:
            json.dump(dashboard, f, indent=2, cls=SafeEncoder)

        return dashboard

    def send_alerts(self, results: list):
        """
        Invia alert giornalieri:
        - send_new_entries: solo nuovi ingressi in L1 (+ nuovi L0)
        - send_l1_exit: ogni uscita da L1
        - send_portfolio_signals: RSI > 72 o condizioni in deterioramento
        """
        today     = datetime.now().date()
        today_str = today.strftime('%Y-%m-%d')

        existing_l1 = self.db.get_all_l1_entries()
        existing_l0 = self.db.get_all_l0_entries()

        current_l1_isins  = set()
        current_l0_isins  = set()
        new_l1_entries    = []
        new_l0_entries    = []
        portfolio_signals = []

        for r in results:
            a         = r['analysis']
            suggested = a.get('suggested_level', r['livello'])
            isin      = r.get('isin', '') or r['ticker']
            price     = a.get('current_price')

            # ── L0 tracking ──────────────────────────────────────────────────
            if suggested == 0:
                current_l0_isins.add(isin)
                if isin not in existing_l0:
                    if price:
                        panic_low = a.get('l0_data', {}).get('panic_low')
                        self.db.set_l0_entry(isin, today_str, price, panic_low)
                    add_log(f"  NUOVO L0: {r['nome'][:40]}")
                    new_l0_entries.append({
                        'isin':              isin,
                        'ticker':            r['ticker'],
                        'nome':              r['nome'],
                        'price':             float(price) if price else None,
                        'panic_low':         a.get('l0_data', {}).get('panic_low'),
                        'rsi':               a.get('rsi'),
                        'distance_from_peak': a.get('l0_data', {}).get('distance_from_peak'),
                    })

            # ── L1 tracking ──────────────────────────────────────────────────
            if suggested == 1:
                current_l1_isins.add(isin)
                if isin not in existing_l1:
                    if price:
                        self.db.set_l1_entry(isin, today_str, price)
                    entry_date  = today
                    entry_price = float(price) if price else None
                    add_log(f"  NUOVO L1: {r['nome'][:40]}" +
                            (f" — entrato a {entry_price:.4f}" if entry_price else ''))
                    new_l1_entries.append({
                        'isin':      isin,
                        'ticker':    r['ticker'],
                        'nome':      r['nome'],
                        'categoria': r['categoria'],
                        'price':     float(price) if price else None,
                        'rsi':       a.get('rsi'),
                        'adx':       a.get('adx'),
                        'sma200':    a.get('sma200'),
                        'buy_count': a.get('buy_count', 0),
                    })
                else:
                    entry       = existing_l1[isin]
                    entry_date  = entry['entry_date']
                    entry_price = entry['entry_price']

                    try:
                        ed = entry_date if isinstance(entry_date, date_type) \
                            else datetime.fromisoformat(str(entry_date)).date()
                        days_in_l1 = max(1, int(np.busday_count(ed, today)) + 1)
                    except Exception:
                        days_in_l1 = 1

                    pct_gain = None
                    if price and entry_price:
                        pct_gain = round((float(price) - float(entry_price)) / float(entry_price) * 100, 2)

                    rsi = a.get('rsi') or 0
                    bc  = a.get('buy_count', 6)

                    signal_type   = None
                    signal_detail = None
                    if rsi >= 78:
                        signal_type   = 'piede_dentro'
                        signal_detail = f'RSI attuale: {rsi:.1f} (soglia Piede Dentro: 78). Valuta XEON.'
                    elif rsi >= 72:
                        signal_type   = 'stanchezza'
                        signal_detail = f'RSI attuale: {rsi:.1f} — zona di stanchezza in arrivo'
                    elif bc <= 4 and days_in_l1 > 5:
                        signal_type   = 'attenzione'
                        signal_detail = f'Condizioni soddisfatte: {bc}/6'

                    if signal_type:
                        portfolio_signals.append({
                            'isin':          isin,
                            'ticker':        r['ticker'],
                            'nome':          r['nome'],
                            'categoria':     r['categoria'],
                            'entry_date':    entry_date,
                            'days_in_l1':    days_in_l1,
                            'pct_gain':      pct_gain,
                            'rsi':           rsi,
                            'adx':           a.get('adx'),
                            'signal_type':   signal_type,
                            'signal_detail': signal_detail,
                        })

        # ── Uscite da L1 ──────────────────────────────────────────────────────
        for isin, entry in existing_l1.items():
            if isin in current_l1_isins:
                continue
            fr = next((r for r in results if (r.get('isin') or r['ticker']) == isin), None)
            if not fr:
                self.db.remove_l1_entry(isin)
                continue
            a          = fr['analysis']
            exit_price = a.get('current_price')
            ep         = entry['entry_price']
            ed_raw     = entry['entry_date']
            try:
                ed = ed_raw if isinstance(ed_raw, date_type) \
                    else datetime.fromisoformat(str(ed_raw)).date()
                days = max(1, int(np.busday_count(ed, today)) + 1)
            except Exception:
                days = 1
            pct = round((float(exit_price) - float(ep)) / float(ep) * 100, 2) \
                if exit_price and ep else None
            pct_str = f'{pct:+.2f}%' if pct is not None else 'N/D'
            add_log(f"  USCITA L1: {fr['nome'][:40]} — {pct_str}")
            self.alert_system.send_l1_exit({
                'isin': isin, 'ticker': fr['ticker'], 'nome': fr['nome'],
                'categoria': fr['categoria'],
                'entry_date': ed_raw, 'entry_price': ep,
                'exit_price': float(exit_price) if exit_price else None,
                'days_in_l1': days, 'pct_gain': pct,
                'analysis': a,
            })
            self.db.remove_l1_entry(isin)

        # ── Uscite da L0 ──────────────────────────────────────────────────────
        for isin in list(existing_l0.keys()):
            if isin not in current_l0_isins:
                add_log(f"  USCITA L0: {isin}")
                self.db.remove_l0_entry(isin)

        # ── Invio email ────────────────────────────────────────────────────────
        if new_l1_entries or new_l0_entries:
            add_log(f"  Email nuovi ingressi: L1={len(new_l1_entries)} L0={len(new_l0_entries)}")
            self.alert_system.send_new_entries(new_l1_entries, new_l0_entries)
        else:
            add_log("  Nessun nuovo ingresso oggi")

        if portfolio_signals:
            add_log(f"  Email segnali portafoglio: {len(portfolio_signals)}")
            self.alert_system.send_portfolio_signals(portfolio_signals)
        else:
            add_log("  Nessun segnale portafoglio oggi")

    def run(self, send_daily_report: bool = True):
        """Esegue il ciclo completo di monitoraggio.

        Args:
            send_daily_report: Se True invia alert email (run principale).
                               Se False aggiorna solo dashboard (run silenzioso mattutino).
        """
        add_log("=" * 50)
        label = "completo" if send_daily_report else "silenzioso"
        add_log(f"ETF MONITOR [{label}] — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        add_log(f"Fonte dati: Yahoo Finance | Schema: EMA20+SMA50+SMA200+ADX+RSI")

        # 1. Carica ETF
        df_etfs = self.load_etfs()
        if df_etfs.empty:
            add_log("ERRORE: Nessun ETF da monitorare")
            return

        # 2. Analizza ogni ETF
        add_log(f"Analisi di {len(df_etfs)} ETF...")
        results = []
        errors  = []

        for idx, row in df_etfs.iterrows():
            try:
                result = self.analyze_etf(row)
                results.append(result)
                a = result['analysis']
                lvl = a.get('suggested_level', result['livello'])
                add_log(f"  OK L{lvl} | {row.get('Ticker','?'):12s} {row.get('Nome ETF','')[:28]}")
            except Exception as e:
                tb = traceback.format_exc()
                errors.append({'ticker': row.get('Ticker','?'), 'error': str(e)})
                add_log(f"  ERR {row.get('Ticker','?')}: {e}")
                add_log(f"  {tb}")
            time.sleep(self.data_fetcher.rate_limit)

        add_log(f"Analisi: {len(results)} OK, {len(errors)} errori")

        # 3. Aggiorna Excel
        try:
            add_log("Aggiornamento Excel...")
            self.update_excel(results)
        except Exception as e:
            add_log(f"ERRORE Excel: {e}")

        # 4. Genera dashboard
        try:
            add_log("Generazione dashboard...")
            dashboard = self.generate_dashboard_data(results, send_daily_report=send_daily_report, errors=errors)
            add_log(f"Dashboard: L0={dashboard['summary']['l0_count']} "
                    f"L1={dashboard['summary']['l1_count']} "
                    f"L2={dashboard['summary']['l2_count']} "
                    f"L3={dashboard['summary']['l3_count']}")
        except Exception as e:
            add_log(f"ERRORE Dashboard: {e}")
            add_log(traceback.format_exc())
            dashboard = {
                'last_update': datetime.now().isoformat() + 'Z',
                'data_source': 'Yahoo Finance',
                'summary': {'total_etfs': len(results),
                            'l0_count': 0, 'l1_count': 0, 'l2_count': 0, 'l3_count': 0},
                'levels': {0: [], 1: [], 2: [], 3: []},
                'categories': {}
            }
            for r in results:
                try:
                    lvl = r['analysis'].get('suggested_level', r['livello'])
                    dashboard['levels'][max(0, min(3, int(lvl)))].append({
                        'ticker': r['ticker'], 'nome': r['nome'],
                        'price':  r['analysis'].get('current_price'),
                    })
                except Exception:
                    pass
            with open('data/dashboard_data.json', 'w') as f:
                json.dump(dashboard, f, indent=2)

        # 5. Invia alert (solo se run principale)
        if send_daily_report:
            try:
                add_log("Invio alert...")
                self.send_alerts(results)
            except Exception as e:
                add_log(f"ERRORE Alert: {e}")
        else:
            add_log("Alert saltati (refresh silenzioso)")

        add_log(f"Completato — {datetime.now().strftime('%H:%M')}")
        add_log("=" * 50)


def main():
    monitor = ETFMonitor()
    monitor.run()


if __name__ == '__main__':
    main()
