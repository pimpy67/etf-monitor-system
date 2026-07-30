"""
app.py - Web server dashboard ETF
===================================
Serve la dashboard HTML e le API JSON.
Auto-recovery: lancia il monitoraggio se non ha girato oggi.
"""

from flask import Flask, send_file, send_from_directory, jsonify, request
import os
import json
import threading
from datetime import datetime

from database import PriceDatabase
import monitor_lock
from pdf_generator import generate_parameters_pdf
from pdf_generator_complete import generate_complete_pdf
from technical_analysis import ETFTechnicalAnalyzer

app = Flask(__name__)
db  = PriceDatabase()


@app.route('/')
def index():
    return send_file('dashboard.html')

@app.route('/portfolio')
def portfolio():
    return send_file('templates/portfolio.html')

@app.route('/data/<path:filename>')
def serve_data(filename):
    return send_from_directory('data', filename)


def _get_dashboard_data():
    try:
        with open('data/dashboard_data.json', 'r') as f:
            return json.load(f)
    except Exception:
        return None


def _should_run_today():
    now          = datetime.now()
    monitor_hour = int(os.environ.get('MONITOR_HOUR', 18))

    # Controlla se oggi è un giorno previsto da MONITOR_DAYS (default lun-ven)
    monitor_days_str = os.environ.get('MONITOR_DAYS', '1-5')
    today_isoweekday = now.isoweekday()  # 1=lun, 7=dom
    try:
        if '-' in monitor_days_str:
            start, end = monitor_days_str.split('-')
            is_work_day = int(start) <= today_isoweekday <= int(end)
        else:
            is_work_day = today_isoweekday in [int(d) for d in monitor_days_str.split(',')]
    except Exception:
        is_work_day = today_isoweekday <= 5
    if not is_work_day:
        return False

    try:
        data         = _get_dashboard_data()
        if not data:
            return True
        total = data.get('summary', {}).get('total_etfs', 0)
        if total == 0:
            return True
        last_update = data.get('last_update')
        if not last_update:
            return True
        last_dt = datetime.fromisoformat(last_update.replace('Z', '').split('+')[0])
        return last_dt.date() < now.date() and now.hour >= monitor_hour
    except Exception:
        return True


def _trigger_auto_monitor():
    if not monitor_lock.try_acquire():
        return False

    def run():
        try:
            print(f"\nAUTO-RECOVERY: Avvio — {datetime.now()}")
            from monitor import ETFMonitor
            ETFMonitor().run(send_daily_report=True)
            print(f"AUTO-RECOVERY: Completato — {datetime.now()}")
        except Exception as e:
            print(f"AUTO-RECOVERY: Errore — {e}")
        finally:
            monitor_lock.release()

    threading.Thread(target=run, daemon=True).start()
    return True


@app.route('/api/status')
def status():
    data     = _get_dashboard_data()
    db_stats = db.get_stats()

    auto_triggered = False
    if _should_run_today() and not monitor_lock.is_running():
        auto_triggered = _trigger_auto_monitor()

    return jsonify({
        'status':                  'ok',
        'last_update':             data.get('last_update') if data else None,
        'total_etfs':              data.get('summary', {}).get('total_etfs', 0) if data else 0,
        'database':                db_stats,
        'monitor_running':         monitor_lock.is_running(),
        'auto_recovery_triggered': auto_triggered,
    })


@app.route('/api/etfs')
def get_etfs():
    try:
        with open('data/dashboard_data.json', 'r') as f:
            return jsonify(json.load(f))
    except Exception:
        return jsonify({'error': 'Data not available'}), 404


@app.route('/api/etf-detail')
def etf_detail():
    """Dettaglio completo di un ETF (per modal dashboard)."""
    ticker = request.args.get('ticker', '')
    isin   = request.args.get('isin', '')

    try:
        data = _get_dashboard_data()
        if not data:
            return jsonify({'error': 'Dashboard data non disponibile'}), 404

        # Cerca nelle liste di tutti i livelli
        etf_info = None
        for level_list in data.get('levels', {}).values():
            for etf in level_list:
                if (ticker and etf.get('ticker') == ticker) or \
                   (isin and etf.get('isin') == isin):
                    etf_info = etf
                    break
            if etf_info:
                break

        if not etf_info:
            return jsonify({'error': 'ETF non trovato'}), 404

        # Recupera storico prezzi dal DB con indicatori per il grafico
        import math as _math

        identifier = etf_info.get('isin') or isin or ticker
        df = db.get_close_by_isin(identifier, days=260)

        price_hist = []
        if not df.empty:
            df = df.reset_index()
            df.columns = ['date', 'close']
            df = df.sort_values('date').reset_index(drop=True)
        elif ticker or etf_info.get('isin'):
            df_old = db.get_ohlcv(etf_info.get('isin') or ticker, days=260)
            if not df_old.empty:
                df = df_old[['date', 'close']].copy()
                df = df.sort_values('date').reset_index(drop=True)

        if not df.empty and 'close' in df.columns:
            prices = df['close'].astype(float)
            df['ema20']  = prices.ewm(span=20, adjust=False).mean()
            df['sma50']  = prices.rolling(window=50, min_periods=1).mean()
            df['sma200'] = prices.rolling(window=200, min_periods=1).mean()

            def _fmt(v, d=4):
                try:
                    f = float(v)
                    return None if _math.isnan(f) or _math.isinf(f) else round(f, d)
                except Exception:
                    return None

            for _, row in df.tail(90).iterrows():
                price_hist.append({
                    'date':  str(row['date'].date()) if hasattr(row['date'], 'date') else str(row['date'])[:10],
                    'close': _fmt(row['close']),
                    'ema20': _fmt(row['ema20']),
                    'sma50': _fmt(row['sma50']),
                    'sma200': _fmt(row['sma200']),
                })

        # Price date: data reale dell'ultimo prezzo disponibile
        price_date = price_hist[-1]['date'] if price_hist else None

        # L1 conditions con valori reali e soglie per tipo ETF
        cond     = etf_info.get('conditions', {})
        etf_type = etf_info.get('etf_type', 'equity_developed')
        from technical_analysis import ETFTechnicalAnalyzer
        analyzer = ETFTechnicalAnalyzer(etf_type)
        p = analyzer.p

        l1_conditions = {
            'allineamento_ok': bool(cond.get('allineamento_ok', False)),
            'persistenza_ok':  bool(cond.get('persistenza_ok', False)),
            'rsi_ok':          bool(cond.get('rsi_ok', False)),
            'distance_ok':     bool(cond.get('distance_ok', False)),
            'adx_ok':          bool(cond.get('adx_ok', False)),
            'macd_ok':         bool(cond.get('macd_ok', False)),
            'values': {
                'price':            etf_info.get('price'),
                'price_date':       price_date,
                'ema20':            cond.get('ema20_current'),
                'sma50':            cond.get('sma50_current'),
                'sma200':           cond.get('sma200_current'),
                'rsi':              cond.get('rsi'),
                'adx':              cond.get('adx'),
                'dist_ema20':       cond.get('dist_ema20'),
                'days_above_ema20': cond.get('days_above_ema20'),
                'ema20_slope':      cond.get('ema20_slope'),
                'regime_ok':        cond.get('regime_ok'),
                'macd_histogram':   cond.get('macd_histogram'),
            },
            'thresholds': {
                'rsi_min':        p['rsi_entry_low'],
                'rsi_max':        p['rsi_entry_high'],
                'max_dist_ema20': p['ema_dist_max'],
                'adx_threshold':  p['adx_entry'],
                'days_above_ema': p['days_above_ema'],
            },
            'buy_count': etf_info.get('buy_count', 0),
        }

        return jsonify({
            **etf_info,
            'price_history':  price_hist,
            'price_date':     price_date,
            'l1_conditions':  l1_conditions,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/prices')
def get_prices():
    """Storico prezzi per ticker o ISIN."""
    ticker = request.args.get('ticker')
    isin   = request.args.get('isin')
    days   = int(request.args.get('days', 30))

    identifier = isin or ticker
    if not identifier:
        return jsonify(db.get_stats())

    df = db.get_close_by_isin(identifier, days)
    if df.empty:
        df_old = db.get_ohlcv(identifier, days)
        if not df_old.empty:
            return jsonify({'identifier': identifier,
                            'prices': [{'date': str(r['date']), 'close': float(r['close'])}
                                       for _, r in df_old.iterrows()],
                            'count': len(df_old)})
        return jsonify({'identifier': identifier, 'prices': [], 'count': 0})

    return jsonify({'identifier': identifier,
                    'prices': [{'date': str(d.date()), 'close': float(r['Close'])}
                               for d, r in df.iterrows()],
                    'count': len(df)})


@app.route('/api/portfolio-sl')
def portfolio_sl():
    """Restituisce SL attuali per tutte le posizioni L1, opzionalmente filtrate per ISIN."""
    try:
        conn = db.get_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 500

        from psycopg2.extras import RealDictCursor
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Leggi posizioni L1 da portfolio_entries, opzionalmente filtrate per ISIN
            isin_filter = request.args.get('isin', '').strip()

            if isin_filter:
                cur.execute("""
                    SELECT pe.isin, pe.entry_price, pe.entry_date, pe.fund_name,
                           pe.stop_loss_inserted, pe.stop_loss_suggested, pe.stop_loss_updated_at, pe.shares,
                           pe.sl_suggerito, pe.sg_suggerito
                    FROM etf_portfolio_entries pe
                    WHERE pe.status = 'active' AND pe.isin = %s
                    ORDER BY pe.entry_date DESC
                """, (isin_filter,))
            else:
                cur.execute("""
                    SELECT pe.isin, pe.entry_price, pe.entry_date, pe.fund_name,
                           pe.stop_loss_inserted, pe.stop_loss_suggested, pe.stop_loss_updated_at, pe.shares,
                           pe.sl_suggerito, pe.sg_suggerito
                    FROM etf_portfolio_entries pe
                    WHERE pe.status = 'active'
                    ORDER BY pe.entry_date DESC
                """)
            positions = cur.fetchall()

            # Per ogni posizione, leggi prezzo corrente
            result = []
            for pos in positions:
                isin = pos['isin']
                cur.execute("""
                    SELECT close, date, ticker FROM etf_price_history
                    WHERE isin = %s ORDER BY date DESC LIMIT 1
                """, (isin,))
                price_row = cur.fetchone()

                if price_row:
                    current_price = float(price_row['close'])
                    price_date = price_row['date']
                    ticker = price_row.get('ticker', isin)
                    pct_change = ((current_price - float(pos['entry_price'])) /
                                 float(pos['entry_price']) * 100) if pos['entry_price'] > 0 else 0

                    # Usa SL suggerito da STEP 4 (formula ibrida) se disponibile, altrimenti fallback a vecchio
                    entry_price = float(pos['entry_price'])
                    sl_suggerito = float(pos['sl_suggerito']) if pos.get('sl_suggerito') else None
                    sg_suggerito = float(pos['sg_suggerito']) if pos.get('sg_suggerito') else None

                    # Fallback: calcola SL consigliato (logica a 2 fasi) solo se non ho SL suggerito
                    if not sl_suggerito:
                        if pct_change <= 0:
                            sl_suggerito = entry_price * 0.98
                        else:
                            sl_suggerito = max(entry_price * 0.98, current_price * 0.95)

                    result.append({
                        'isin': isin,
                        'ticker': ticker,
                        'fund_name': pos['fund_name'],
                        'entry_price': float(entry_price),
                        'entry_date': str(pos['entry_date']),
                        'current_price': current_price,
                        'price_date': str(price_date),
                        'pct_change': round(pct_change, 2),
                        'sl_inserted': float(pos['stop_loss_inserted']) if pos['stop_loss_inserted'] else None,
                        'sl_suggested': round(sl_suggerito, 4) if sl_suggerito else None,
                        'sg_suggested': round(sg_suggerito, 4) if sg_suggerito else None,
                        'sl_updated': str(pos['stop_loss_updated_at']) if pos['stop_loss_updated_at'] else None,
                        'shares': float(pos['shares']) if pos['shares'] else None,
                    })

        conn.close()
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'positions': result,
            'count': len(result)
        })

    except Exception as e:
        print(f"Errore portfolio-sl: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/accept-sl-suggestion', methods=['POST'])
def accept_sl_suggestion():
    """Salva lo SL personale e il numero di quote per un ETF nel portafoglio."""
    try:
        data = request.get_json()
        isin = data.get('isin')
        sl_value = data.get('sl_value')
        shares = data.get('shares')

        if not isin:
            return jsonify({'error': 'ISIN required'}), 400

        if sl_value is None or shares is None:
            return jsonify({'error': 'sl_value and shares required'}), 400

        # Salva SL personale e shares nel database
        conn = db.get_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 500

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE etf_portfolio_entries
                    SET stop_loss_inserted = %s, shares = %s, stop_loss_updated_at = NOW()
                    WHERE isin = %s AND status = 'active'
                """, (float(sl_value), float(shares), isin))
                conn.commit()

                if cur.rowcount > 0:
                    return jsonify({
                        'status': 'saved',
                        'isin': isin,
                        'sl_inserted': float(sl_value),
                        'shares': float(shares),
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    return jsonify({'error': 'Portfolio entry not found'}), 404
        finally:
            conn.close()

    except Exception as e:
        print(f"Errore accept_sl_suggestion: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/trigger-update', methods=['GET', 'POST'])
def trigger_update():
    started = _trigger_auto_monitor()
    if started:
        return jsonify({'status': 'started',
                        'message': 'Monitoraggio ETF avviato in background',
                        'timestamp': datetime.now().isoformat()})
    return jsonify({'status': 'already_running',
                    'message': 'Monitoraggio gia in esecuzione',
                    'timestamp': datetime.now().isoformat()})


@app.route('/api/monitor-log')
def get_monitor_log():
    from monitor import monitor_log
    return jsonify({
        'log':             monitor_log,
        'count':           len(monitor_log),
        'monitor_running': monitor_lock.is_running(),
        'timestamp':       datetime.now().isoformat(),
    })


@app.route('/api/health')
def health_check():
    """Health check completo del sistema."""
    now = datetime.now()
    health = {}
    last_update = None
    try:
        with open('data/dashboard_data.json', 'r') as f:
            data = json.load(f)
        health = data.get('health', {})
        last_update = data.get('last_update')
    except Exception:
        pass

    stale = True
    hours_since_update = None
    if last_update:
        try:
            lu = last_update.replace('Z', '').split('+')[0]
            last_dt = datetime.fromisoformat(lu)
            delta = now - last_dt
            hours_since_update = round(delta.total_seconds() / 3600, 1)
            stale = hours_since_update > 26
        except Exception:
            pass

    db_ok = db.is_available()

    auto_recovery_triggered = False
    if stale and _should_run_today() and not monitor_lock.is_running():
        auto_recovery_triggered = _trigger_auto_monitor()

    etfs_ok    = health.get('etfs_ok', 0)
    etfs_error = health.get('etfs_error', 0)
    total_etfs = health.get('total_etfs', 0)

    if not stale and etfs_error == 0 and db_ok:
        status = 'green'
        message = 'Sistema operativo'
    elif stale:
        status = 'red'
        hrs_str = f'{hours_since_update}h' if hours_since_update is not None else '?h'
        message = f'Dati non aggiornati da {hrs_str}'
    else:
        status = 'yellow'
        message = f'{etfs_error} ETF con errore' if etfs_error else 'Stato parziale'

    return jsonify({
        'status': status,
        'message': message,
        'last_update': last_update,
        'hours_since_update': hours_since_update,
        'stale': stale,
        'monitor_running': monitor_lock.is_running(),
        'database': {'connected': db_ok},
        'etfs': {
            'total': total_etfs,
            'analyzed_ok': etfs_ok,
            'errors': etfs_error,
            'error_details': health.get('errors', []),
        },
        'auto_recovery_triggered': auto_recovery_triggered,
        'checked_at': now.isoformat(),
    })


@app.route('/api/l1-tracking')
def l1_tracking_api():
    """ETF attualmente in L1 con dati di ingresso e performance."""
    import numpy as np
    from datetime import date as date_type

    today = date_type.today()

    fund_names = {}
    try:
        with open('data/dashboard_data.json', 'r') as f:
            dash = json.load(f)
        for lv_funds in dash.get('levels', {}).values():
            for etf in lv_funds:
                isin = etf.get('isin') or ''
                if isin:
                    fund_names[isin] = etf.get('nome', isin)
    except Exception:
        pass

    # Query batch: ottiene tracking + ultimo prezzo in un colpo solo
    result = []
    conn = db._get_connection()
    if not conn:
        return jsonify({'tracking': []})
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.isin, t.entry_date, t.entry_price,
                       p.close AS current_price, p.date AS price_date
                FROM etf_l1_tracking t
                LEFT JOIN LATERAL (
                    SELECT close, date FROM etf_price_history
                    WHERE isin = t.isin
                    ORDER BY date DESC LIMIT 1
                ) p ON true
            """)
            rows = cur.fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()

    for isin, entry_date, entry_price, current_price, price_date in rows:
        ed = entry_date if isinstance(entry_date, date_type) else date_type.fromisoformat(str(entry_date))
        last_price_date = price_date if price_date else today

        try:
            days_in_l1 = max(1, int(np.busday_count(ed, last_price_date)) + 1)
        except Exception:
            days_in_l1 = 1

        pct_gain = None
        if current_price and entry_price:
            pct_gain = round((float(current_price) - float(entry_price)) / float(entry_price) * 100, 2)

        result.append({
            'isin':          isin,
            'fund_name':     fund_names.get(isin, isin),
            'entry_date':    ed.isoformat(),
            'entry_price':   float(entry_price),
            'current_price': float(current_price) if current_price else None,
            'pct_gain':      pct_gain,
            'days_in_l1':    days_in_l1,
            'is_new':        days_in_l1 == 1,
        })

    return jsonify({'tracking': result})


@app.route('/api/l0-tracking')
def l0_tracking_api():
    """ETF attualmente in L0 (Deep Recovery) con dati di ingresso e performance."""
    from datetime import date as date_type
    import numpy as np

    entries = db.get_all_l0_entries()
    today   = date_type.today()

    fund_names = {}
    try:
        with open('data/dashboard_data.json', 'r') as f:
            dash = json.load(f)
        for lv_funds in dash.get('levels', {}).values():
            for etf in lv_funds:
                isin = etf.get('isin') or ''
                if isin:
                    fund_names[isin] = etf.get('nome', isin)
        for etf in dash.get('l0_funds', []):
            isin = etf.get('isin') or ''
            if isin:
                fund_names[isin] = etf.get('nome', isin)
    except Exception:
        pass

    result = []
    for isin, entry in entries.items():
        entry_date  = entry['entry_date']
        entry_price = entry['entry_price']
        panic_low   = entry.get('panic_low')
        ed = entry_date if isinstance(entry_date, date_type) else date_type.fromisoformat(str(entry_date))

        df_p = db.get_close_by_isin(isin, days=3)
        current_price = None
        if not df_p.empty:
            current_price = float(df_p.iloc[-1]['Close'])

        try:
            days_in_l0 = max(1, int(np.busday_count(ed, today)) + 1)
        except Exception:
            days_in_l0 = 1

        pct_gain = None
        if current_price and entry_price:
            pct_gain = round((current_price - float(entry_price)) / float(entry_price) * 100, 2)

        result.append({
            'isin':             isin,
            'fund_name':        fund_names.get(isin, isin),
            'entry_date':       ed.isoformat(),
            'entry_price':      float(entry_price),
            'panic_low':        float(panic_low) if panic_low else None,
            'current_price':    current_price,
            'pct_gain':         pct_gain,
            'days_in_l0':       days_in_l0,
            'livello_display':  entry.get('livello_display', 'L0'),
        })

    return jsonify({'tracking': result})


@app.route('/api/l1-exits')
def l1_exits_api():
    """Uscite da L1 degli ultimi 30 giorni."""
    days  = int(request.args.get('days', 30))
    exits = db.get_l1_exits(days=days)
    result = []
    for e in exits:
        result.append({
            'isin':         e['isin'],
            'fund_name':    e['fund_name'] or e['isin'],
            'exit_date':    str(e['exit_date']),
            'exit_price':   float(e['exit_price']) if e['exit_price'] else None,
            'exit_rule':    e['exit_rule'],
            'exit_trigger': e['exit_trigger'] or '',
            'entry_date':   str(e['entry_date']) if e['entry_date'] else None,
            'entry_price':  float(e['entry_price']) if e['entry_price'] else None,
            'days_in_l1':   e['days_in_l1'],
            'pct_gain':     float(e['pct_gain']) if e['pct_gain'] is not None else None,
        })
    return jsonify({'exits': result, 'count': len(result)})


@app.route('/api/l2-watchlist')
def get_l2_watchlist():
    """Ritorna lista ETF in L2 Readiness watchlist (in_watchlist=true)."""
    try:
        if not db or not db.connection:
            return jsonify([])
        watchlist = db.get_l2_watchlist_active()
        return jsonify(watchlist)
    except Exception as e:
        print(f"L2 watchlist error: {e}")
        return jsonify([])


@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    """Portafoglio personale ETF arricchito con dati attuali."""
    entries = db.get_portfolio_entries()

    etf_analysis = {}
    try:
        with open('data/dashboard_data.json', 'r') as f:
            dash = json.load(f)
        for level_key, level_etfs in dash.get('levels', {}).items():
            for etf in level_etfs:
                isin = etf.get('isin') or ''
                if isin:
                    etf_analysis[isin] = {**etf, 'level': int(level_key)}
        for etf in dash.get('l0_funds', []):
            isin = etf.get('isin') or ''
            if isin:
                etf_analysis[isin] = {**etf, 'level': 0}
    except Exception:
        pass

    result = []
    for entry in entries:
        isin     = entry['isin']
        analysis = etf_analysis.get(isin, {})

        df_p = db.get_close_by_isin(isin, days=5)
        current_price = None
        if not df_p.empty:
            current_price = float(df_p.iloc[-1]['Close'])

        status    = entry.get('status', 'active')
        exit_price = entry.get('exit_price')
        ref_price = exit_price if (status == 'exited' and exit_price) else current_price
        perf_pct = None
        if ref_price and entry['entry_price'] and float(entry['entry_price']) > 0:
            perf_pct = round((float(ref_price) - float(entry['entry_price'])) / float(entry['entry_price']) * 100, 2)

        sl_suggerito = entry.get('sl_suggerito')
        sg_suggerito = entry.get('sg_suggerito')
        entry_confidence = entry.get('entry_confidence', 1.0)
        accumulated_pcts_str = entry.get('accumulated_pcts', '[]')
        accumulated_dates_str = entry.get('accumulated_dates', '[]')

        # Parse JSON
        try:
            accumulated_pcts = json.loads(accumulated_pcts_str) if accumulated_pcts_str else []
            accumulated_dates = json.loads(accumulated_dates_str) if accumulated_dates_str else []
        except:
            accumulated_pcts = []
            accumulated_dates = []

        result.append({
            'isin':                isin,
            'fund_name':           entry['fund_name'],
            'entry_date':          str(entry['entry_date']) if entry['entry_date'] else None,
            'entry_price':         float(entry['entry_price']) if entry['entry_price'] else None,
            'current_price':       current_price,
            'perf_pct':            perf_pct,
            'exit_date':           str(entry['exit_date']) if entry.get('exit_date') else None,
            'exit_price':          float(exit_price) if exit_price else None,
            'status':              status,
            'is_partial':          bool(entry.get('is_partial', False)),
            'partial_exit_date':   str(entry['partial_exit_date']) if entry.get('partial_exit_date') else None,
            'partial_exit_price':  float(entry['partial_exit_price']) if entry.get('partial_exit_price') else None,
            'level':               analysis.get('level') or analysis.get('suggested_level'),
            'rsi':                 analysis.get('rsi'),
            'adx':                 analysis.get('adx'),
            'ema20':               analysis.get('ema20'),
            'dist_ema20':          analysis.get('dist_ema20'),
            'etf_type':            analysis.get('etf_type', ''),
            'sl_suggerito':        float(sl_suggerito) if sl_suggerito else None,
            'sg_suggerito':        float(sg_suggerito) if sg_suggerito else None,
            'entry_confidence':    float(entry_confidence) if entry_confidence else None,
            'entry_mode':          entry.get('entry_mode', 'STANDARD'),
            'portfolio_type':      entry.get('portfolio_type', 'L1'),
            'stop_loss_l0_suggested': float(entry.get('stop_loss_l0_suggested')) if entry.get('stop_loss_l0_suggested') else None,
            'accumulated_pcts':    accumulated_pcts,
            'accumulated_dates':   accumulated_dates,
        })

    return jsonify({'portfolio': result, 'count': len(result)})


@app.route('/api/portfolio', methods=['POST'])
def add_to_portfolio():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dati mancanti'}), 400
    isin        = data.get('isin', '').strip().upper()
    entry_date  = data.get('entry_date', '')
    entry_price = data.get('entry_price')
    fund_name   = data.get('fund_name', '').strip()
    if not isin or not entry_date or entry_price is None:
        return jsonify({'error': 'isin, entry_date e entry_price obbligatori'}), 400
    try:
        entry_price = float(entry_price)
    except (ValueError, TypeError):
        return jsonify({'error': 'entry_price deve essere un numero'}), 400
    
    # Determina se L1 o L0: controlla se esiste in etf_l1_tracking
    is_l1 = db.is_etf_in_l1_tracking(isin)
    portfolio_type = 'L1' if is_l1 else 'L0'
    stop_loss_l0_suggested = None
    
    # Se L0, calcola stop loss dinamico dalla famiglia
    if portfolio_type == 'L0':
        categoria = data.get('categoria', '')
        famiglia = ETFTechnicalAnalyzer.detect_family(categoria)
        analyzer = ETFTechnicalAnalyzer(famiglia=famiglia)
        profilo = analyzer.p
        # Stop loss L0 suggerito: entry_price * (1 - sl_buffer_wide)
        sl_buffer = profilo.get('sl_buffer_wide', 0.02)
        stop_loss_l0_suggested = entry_price * (1 - sl_buffer)
    
    ok = db.add_portfolio_entry(isin, entry_date, entry_price, fund_name,
                                portfolio_type=portfolio_type,
                                stop_loss_l0_suggested=stop_loss_l0_suggested)
    if ok:
        return jsonify({'status': 'ok', 'isin': isin, 'portfolio_type': portfolio_type})
    return jsonify({'error': 'Errore salvataggio'}), 503


@app.route('/api/portfolio/<isin>', methods=['DELETE'])
def remove_from_portfolio(isin):
    isin = isin.strip().upper()
    ok = db.remove_portfolio_entry(isin)
    if ok:
        return jsonify({'status': 'ok', 'isin': isin})
    return jsonify({'error': 'Errore rimozione'}), 503


@app.route('/api/portfolio/<isin>', methods=['PUT'])
def update_portfolio_entry_route(isin):
    isin = isin.strip().upper()
    data = request.get_json() or {}
    entry_date  = data.get('entry_date', '')
    entry_price = data.get('entry_price')
    fund_name   = data.get('fund_name')
    if not entry_date or entry_price is None:
        return jsonify({'error': 'entry_date e entry_price obbligatori'}), 400
    try:
        entry_price = float(entry_price)
    except (ValueError, TypeError):
        return jsonify({'error': 'entry_price deve essere un numero'}), 400
    ok = db.update_portfolio_entry(isin, entry_date, entry_price, fund_name)
    if ok:
        return jsonify({'status': 'ok', 'isin': isin})
    return jsonify({'error': 'Errore aggiornamento'}), 503


@app.route('/api/portfolio/<isin>/exit', methods=['POST'])
def exit_portfolio_route(isin):
    isin = isin.strip().upper()
    data = request.get_json() or {}
    exit_date  = data.get('exit_date', '')
    exit_price = data.get('exit_price')
    if not exit_date or exit_price is None:
        return jsonify({'error': 'exit_date e exit_price obbligatori'}), 400
    try:
        exit_price = float(exit_price)
    except (ValueError, TypeError):
        return jsonify({'error': 'exit_price deve essere un numero'}), 400
    ok = db.exit_portfolio_entry(isin, exit_date, exit_price)
    if ok:
        db.add_portfolio_event(isin, 'exit', exit_date, exit_price)
        return jsonify({'status': 'ok', 'isin': isin})
    return jsonify({'error': 'Errore salvataggio'}), 503


@app.route('/api/portfolio/<isin>/partial-exit', methods=['POST'])
def partial_exit_portfolio_route(isin):
    """Registra vendita parziale 90% — Piede Dentro. L'ETF rimane active in portafoglio."""
    isin = isin.strip().upper()
    data = request.get_json() or {}
    exit_date  = data.get('exit_date', '')
    exit_price = data.get('exit_price')
    if not exit_date or exit_price is None:
        return jsonify({'error': 'exit_date e exit_price obbligatori'}), 400
    try:
        exit_price = float(exit_price)
    except (ValueError, TypeError):
        return jsonify({'error': 'exit_price deve essere un numero'}), 400
    ok = db.partial_exit_portfolio_entry(isin, exit_date, exit_price)
    if ok:
        db.add_portfolio_event(isin, 'partial_exit', exit_date, exit_price, notes='Piede Dentro 90%')
        return jsonify({'status': 'ok', 'isin': isin})
    return jsonify({'error': 'Errore salvataggio'}), 503


@app.route('/api/portfolio/<isin>/reactivate', methods=['POST'])
def reactivate_portfolio_route(isin):
    isin = isin.strip().upper()
    ok = db.reactivate_portfolio_entry(isin)
    if ok:
        return jsonify({'status': 'ok', 'isin': isin})
    return jsonify({'error': 'Errore'}), 503


@app.route('/api/portfolio/events/<isin>', methods=['GET'])
def get_portfolio_events_route(isin):
    isin   = isin.strip().upper()
    events = db.get_portfolio_events(isin)
    return jsonify({'isin': isin, 'events': events})


@app.route('/api/portfolio/events/<int:event_id>', methods=['PUT'])
def update_portfolio_event_route(event_id):
    data       = request.get_json() or {}
    event_date = data.get('event_date', '')
    event_price = data.get('event_price')
    notes      = data.get('notes')
    if not event_date:
        return jsonify({'error': 'event_date obbligatorio'}), 400
    try:
        event_price = float(event_price) if event_price is not None else None
    except (ValueError, TypeError):
        return jsonify({'error': 'event_price deve essere un numero'}), 400
    ok = db.update_portfolio_event(event_id, event_date, event_price, notes)
    if ok:
        return jsonify({'status': 'ok', 'id': event_id})
    return jsonify({'error': 'Errore aggiornamento'}), 503


@app.route('/api/portfolio/events/<int:event_id>', methods=['DELETE'])
def delete_portfolio_event_route(event_id):
    ok = db.delete_portfolio_event(event_id)
    if ok:
        return jsonify({'status': 'ok', 'id': event_id})
    return jsonify({'error': 'Errore eliminazione'}), 503


@app.route('/api/portfolio-history/<isin>')
def portfolio_history_route(isin):
    """Storico 30gg con indicatori ETF per un ETF del portafoglio."""
    import pandas as pd
    import math

    isin         = isin.strip().upper()
    days_history = int(request.args.get('days', 30))

    df = db.get_close_by_isin(isin, days=days_history + 60)
    if df.empty or len(df) < 2:
        return jsonify({'isin': isin, 'history': [], 'error': 'Dati storici insufficienti'})

    df = df.reset_index()
    df.columns = ['date', 'close']
    df = df.sort_values('date').reset_index(drop=True)
    prices = df['close'].astype(float)

    df['ema20'] = prices.ewm(span=20, adjust=False).mean()
    df['sma50'] = prices.rolling(window=50, min_periods=1).mean()
    df['dist_ema20'] = (prices - df['ema20']) / df['ema20'] * 100

    delta    = prices.diff()
    avg_gain = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
    avg_loss = (-delta).clip(lower=0).ewm(com=13, min_periods=14).mean()
    df['rsi14'] = 100 - (100 / (1 + avg_gain / avg_loss.replace(0, float('nan'))))

    df['pct_1g'] = prices.pct_change() * 100
    df['pct_1w'] = prices.pct_change(periods=5) * 100

    def fmt(v, d=2):
        try:
            f = float(v)
            return None if math.isnan(f) or math.isinf(f) else round(f, d)
        except Exception:
            return None

    history = []
    for _, row in df.tail(days_history).iterrows():
        history.append({
            'date':      str(row['date'].date()) if hasattr(row['date'], 'date') else str(row['date'])[:10],
            'price':     fmt(row['close'], 4),
            'pct_1g':    fmt(row['pct_1g']),
            'pct_1w':    fmt(row['pct_1w']),
            'ema20':     fmt(row['ema20'], 4),
            'sma50':     fmt(row['sma50'], 4),
            'dist_ema20': fmt(row['dist_ema20']),
            'rsi14':     fmt(row['rsi14'], 1),
        })

    return jsonify({'isin': isin, 'history': history, 'count': len(history)})


@app.route('/api/db-status')
def db_status_endpoint():
    raw_url  = os.environ.get('DATABASE_URL', '')
    import re
    safe_url = re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', raw_url) if raw_url else 'NOT SET'
    result   = {'database_url_safe': safe_url, 'timestamp': datetime.now().isoformat()}
    try:
        import psycopg2
        conn = psycopg2.connect(raw_url, sslmode='require', connect_timeout=5)
        conn.close()
        result['connection'] = 'OK'
    except Exception as e:
        result['connection'] = 'ERRORE'
        result['error']      = str(e)
    return jsonify(result)


@app.route('/api/market-regime')
def market_regime_api():
    """Market Regime Dashboard — Risk Score, correlazione, suggested allocation."""
    try:
        from risk import MarketRegimeAnalyzer
        from datetime import datetime

        # Leggi ultimo aggiornamento dashboard
        with open('data/dashboard_data.json', 'r') as f:
            dash = json.load(f)

        # Estrai dati equity e bond dal dashboard_data
        equity_etfs = dash.get('levels', {}).get('1', []) + \
                      dash.get('levels', {}).get('2', []) + \
                      dash.get('levels', {}).get('3', [])

        # Cerca i principali benchmark (equity globale e bond)
        equity_regime = 'LATERALE'
        equity_adx = 15
        equity_rsi = 55
        equity_score = 3

        bond_regime = 'LATERALE'
        bond_adx = 10

        # Ricerca semplice: identifica best proxy di equity e bond
        for etf in equity_etfs:
            nome = etf.get('nome', '').lower()
            if 'vwce' in nome or 'all-world' in nome or 'msci world' in nome:
                equity_regime = etf.get('regime', 'LATERALE')
                equity_adx = etf.get('adx') or 15
                equity_rsi = etf.get('rsi') or 55
                equity_score = etf.get('buy_count', 3)
                break

        for etf in equity_etfs:
            nome = etf.get('nome', '').lower()
            if 'gov' in nome or 'egov' in nome or 'btp' in nome or ('bond' in nome and 'high' not in nome):
                bond_regime = etf.get('regime', 'LATERALE')
                bond_adx = etf.get('adx') or 10
                break

        # TODO: Calcola correlazione rolling da price_history
        # Per ora, correlazione neutrale
        correlation_90 = 0.0

        # Analizza regime
        analyzer = MarketRegimeAnalyzer(
            equity_regime=equity_regime,
            equity_adx=equity_adx,
            equity_rsi=equity_rsi,
            equity_score=equity_score,
            bond_regime=bond_regime,
            bond_adx=bond_adx,
            corr_90=correlation_90
        )

        report = analyzer.generate_regime_report()

        return jsonify({
            'market_regime': report,
            'data_timestamp': dash.get('last_update'),
            'analyzed_at': datetime.now().isoformat()
        })

    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/parameters')
def get_parameters():
    """Serve i parametri ETF dal YAML — sempre sincronizzati con il codice."""
    try:
        import yaml
        with open('config/etf_families.yaml', 'r') as f:
            config = yaml.safe_load(f)

        families = config.get('families', {})
        result = {}

        for family_name, params in families.items():
            result[family_name] = {
                'description': params.get('description', ''),
                'rsi_entry_low': params.get('rsi_entry_low'),
                'rsi_entry_high': params.get('rsi_entry_high'),
                'rsi_exit_min': params.get('rsi_exit_min'),
                'rsi_overbought': params.get('rsi_overbought'),
                'adx_entry': params.get('adx_entry'),
                'ema_dist_max': params.get('ema_dist_max'),
                'lateral_band': params.get('lateral_band'),
                'atr_max': params.get('atr_max'),
                'aum_min': params.get('aum_min'),
                'days_above_ema': params.get('days_above_ema'),
                'mm200_filter': params.get('mm200_filter'),
                'l0_drawdown': params.get('l0_drawdown'),
                'l0_rsi_max': params.get('l0_rsi_max'),
                'min_buy_count': params.get('min_buy_count'),
                'ema20_slope_min': params.get('ema20_slope_min'),
                'hold_days_max': params.get('hold_days_max'),
                'sl_initial_pct': params.get('sl_initial_pct'),
                'sl_atr_multiplier': params.get('sl_atr_multiplier'),
                'sl_trailing_trigger': params.get('sl_trailing_trigger'),
                'sl_profit_trigger_pct': params.get('sl_profit_trigger_pct'),
                'sl_trailing_tight_pct': params.get('sl_trailing_tight_pct'),
                'sl_initial_pct_fallback': params.get('sl_initial_pct_fallback'),
                'trailing_gain_threshold': params.get('trailing_gain_threshold'),
                'trailing_base_pct': params.get('trailing_base_pct'),
                'trailing_sensitivity': params.get('trailing_sensitivity'),
                'trailing_min_pct': params.get('trailing_min_pct'),
                # STEP 2 — L1 Hybrid SL + Dynamic SG
                'sl_buffer_wide': params.get('sl_buffer_wide'),
                'sg_target_pct': params.get('sg_target_pct'),
                'sg_floor_pct': params.get('sg_floor_pct'),
                'sg_decay_day': params.get('sg_decay_day'),
                'sg_rsi_exit': params.get('sg_rsi_exit'),
                # L0 Deep Recovery
                'l0_entry': params.get('l0_entry', {}),
            }

        return jsonify({
            'families': result,
            'timestamp': datetime.now().isoformat(),
            'total_families': len(result)
        })

    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/download-parameters-pdf')
def download_parameters_pdf():
    """Scarica il PDF dei parametri — sempre sincronizzato con YAML."""
    try:
        pdf_path = 'data/ETF_Monitor_Parametri_Riferimento.pdf'
        if not os.path.exists(pdf_path):
            generate_parameters_pdf(pdf_path)
        return send_file(pdf_path, as_attachment=True, download_name='ETF_Monitor_Parametri_Riferimento.pdf')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download-complete-documentation')
def download_complete_documentation():
    """Scarica il PDF COMPLETO con documentazione + parametri."""
    try:
        pdf_path = 'data/ETF_Monitor_Documentazione_Completa.pdf'
        if not os.path.exists(pdf_path):
            generate_complete_pdf(pdf_path)
        return send_file(pdf_path, as_attachment=True, download_name='ETF_Monitor_Documentazione_Completa.pdf')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/get-claude-doc')
def get_claude_doc():
    """Carica il CLAUDE.md intero come HTML — visualizzabile nel browser."""
    try:
        # Leggi il CLAUDE.md completo
        with open('CLAUDE.md', 'r', encoding='utf-8') as f:
            content = f.read()

        # Converti Markdown → HTML (usando markdown library)
        try:
            import markdown
            html = markdown.markdown(content, extensions=['tables', 'fenced_code', 'codehilite'])
        except ImportError:
            # Fallback: markdown grezzo convertito a HTML
            import re
            html = content
            html = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
            html = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
            html = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
            html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html)
            html = re.sub(r'\*(.*?)\*(?!\*)', r'<i>\1</i>', html)
            html = '<pre>' + html + '</pre>'

        # Restituisci HTML con CSS minimo per la leggibilità
        html_page = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>CLAUDE.md — Documentazione Completa</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; background: #f5f5f5; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 20px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1, h2, h3 {{ color: #1a5490; border-bottom: 1px solid #e0e0e0; padding-bottom: 10px; }}
        h1 {{ font-size: 2em; margin-top: 40px; }}
        h2 {{ font-size: 1.5em; margin-top: 30px; }}
        h3 {{ font-size: 1.2em; margin-top: 20px; }}
        pre {{ background: #f0f4f8; padding: 15px; border-radius: 5px; overflow-x: auto; font-size: 0.9em; }}
        code {{ background: #f0f4f8; padding: 2px 6px; border-radius: 3px; font-family: 'Courier New', monospace; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        table th, table td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        table th {{ background: #e8eef7; color: #1a5490; font-weight: bold; }}
        table tr:nth-child(even) {{ background: #f9f9f9; }}
        blockquote {{ border-left: 4px solid #1a5490; padding-left: 20px; margin-left: 0; color: #666; }}
        .toc {{ background: #f0f4f8; padding: 20px; border-radius: 5px; margin: 20px 0; }}
        .toc a {{ color: #1a5490; text-decoration: none; }}
        .toc a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📖 CLAUDE.md — Documentazione Completa del Sistema</h1>
        <p><i>Generato il {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</i></p>
        <div class="toc">
            <p><b>Naviga il documento:</b></p>
            <ul>
                <li><a href="#regola">Regola Permanente di Sincronizzazione</a></li>
                <li><a href="#concetti">Concetti Fondamentali</a></li>
                <li><a href="#parametri">Parametri Spiegati</a></li>
                <li><a href="#livelli">Schema Livelli</a></li>
                <li><a href="#flusso">Flusso End-to-End</a></li>
                <li><a href="#interazione">Interazione Parametri</a></li>
                <li><a href="#esempio">Esempio SWDA.L</a></li>
                <li><a href="#infrastruttura">Infrastruttura Tecnica</a></li>
            </ul>
        </div>
        {html}
    </div>
</body>
</html>
        """
        return html_page, 200, {'Content-Type': 'text/html; charset=utf-8'}

    except Exception as e:
        return jsonify({'error': f'Errore caricamento CLAUDE.md: {str(e)}'}), 500


@app.route('/api/parameters-tables-html')
def get_parameters_tables_html():
    """Genera le tabelle HTML parametri dinamicamente da YAML — 100% sincronizzate."""
    try:
        import yaml
        with open('config/etf_families.yaml', 'r') as f:
            config = yaml.safe_load(f)

        families = config.get('families', {})

        # Organizza famiglie per categoria
        equity_commodity = ['equity_sviluppati', 'mercati_emergenti', 'settoriali_growth',
                            'settoriali_difensivi', 'commodities', 'metalli_industriali']
        bond_other = ['bond_governativi', 'bond_corp_hy_em', 'oro_metalli_preziosi',
                      'real_estate_reit', 'inflation_linked', 'monetario_liquidita']
        crypto_leva = ['crypto_digital_assets', 'leva_single_stock', 'private_equity_buffer']

        # Tabella 1: Equity & Commodity
        html_part1 = '<table class="param-table" style="font-size:0.75em;"><thead><tr><th style="width:16%">Parametro</th>'
        for fam in equity_commodity:
            if fam in families:
                html_part1 += f'<th style="width:12%">{families[fam].get("description", fam).split(" — ")[0]}</th>'
        html_part1 += '</tr></thead><tbody>'

        # Righe parametri
        for param_name, param_key in [
            ('RSI Entry Range', 'rsi_entry_low'), ('ADX Min', 'adx_entry'),
            ('Dist. EMA20 Max', 'ema_dist_max'), ('Giorni Sopra EMA20', 'days_above_ema'),
            ('EMA20 Slope Min', 'ema20_slope_min'), ('Min Buy Count', 'min_buy_count'),
            ('SMA200 Filter', 'mm200_filter'), ('L0 Drawdown', 'l0_drawdown'), ('L0 RSI Max', 'l0_rsi_max')
        ]:
            html_part1 += f'<tr><td class="param-name">{param_name}</td>'
            for fam in equity_commodity:
                if fam in families:
                    params = families[fam]
                    if param_key == 'rsi_entry_low':
                        val = f"{params.get('rsi_entry_low', '—')}–{params.get('rsi_entry_high', '—')}"
                    elif param_key == 'adx_entry':
                        val = f"&gt;{params.get('adx_entry', '—')}" if params.get('adx_entry') else '—'
                    elif param_key == 'ema_dist_max':
                        val = f"{params.get('ema_dist_max', '—')*100:.1f}%"
                    elif param_key == 'ema20_slope_min':
                        val = f"{params.get('ema20_slope_min', 1.5)*100:.1f}%"
                    elif param_key == 'min_buy_count':
                        val = f"{params.get('min_buy_count', 6)}/6"
                    elif param_key == 'mm200_filter':
                        val = '✓ Sì' if params.get('mm200_filter') else '✗ No'
                    elif param_key == 'l0_drawdown':
                        val = f"{params.get('l0_drawdown', '—')}%" if params.get('l0_drawdown') else '—'
                    elif param_key == 'l0_rsi_max':
                        val = f"{params.get('l0_rsi_max', '—')}"
                    else:
                        val = str(params.get(param_key, '—'))
                    html_part1 += f'<td>{val}</td>'
            html_part1 += '</tr>'
        html_part1 += '</tbody></table>'

        # Nota: Parte 2 e 3 analoghe (implementate sulla dashboard come fallback per ora)

        return jsonify({
            'tables_html': html_part1,
            'note': 'Tabelle generate dinamicamente da config/etf_families.yaml',
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)

    # Genera PDF all'avvio (sincronizzati con YAML)
    try:
        generate_parameters_pdf('data/ETF_Monitor_Parametri_Riferimento.pdf')
        generate_complete_pdf('data/ETF_Monitor_Documentazione_Completa.pdf')
        print("✅ PDF generati all'avvio (parametri + documentazione completa)")
    except Exception as e:
        print(f"⚠️ Errore generazione PDF: {e}")

    if not os.path.exists('data/dashboard_data.json'):
        with open('data/dashboard_data.json', 'w') as f:
            json.dump({
                'last_update': datetime.now().isoformat(),
                'summary': {'total_etfs': 0, 'l0_count': 0, 'l1_count': 0,
                            'l2_count': 0, 'l3_count': 0},
                'levels': {'0': [], '1': [], '2': [], '3': []},
                'categories': {}
            }, f)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
