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

app = Flask(__name__)
db  = PriceDatabase()


@app.route('/')
def index():
    return send_file('dashboard.html')

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
        last_dt = datetime.fromisoformat(last_update)
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
        df = db.get_close_by_isin(identifier, days=120)

        price_hist = []
        if not df.empty:
            df = df.reset_index()
            df.columns = ['date', 'close']
            df = df.sort_values('date').reset_index(drop=True)
        elif ticker or etf_info.get('isin'):
            df_old = db.get_ohlcv(etf_info.get('isin') or ticker, days=120)
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

        return jsonify({
            **etf_info,
            'price_history': price_hist,
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
            last_dt = datetime.fromisoformat(last_update)
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
        message = f'Dati non aggiornati da {hours_since_update}h'
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

    entries = db.get_all_l1_entries()
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
    except Exception:
        pass

    result = []
    for isin, entry in entries.items():
        entry_date  = entry['entry_date']
        entry_price = entry['entry_price']
        ed = entry_date if isinstance(entry_date, date_type) else date_type.fromisoformat(str(entry_date))
        try:
            days_in_l1 = max(1, int(np.busday_count(ed, today)) + 1)
        except Exception:
            days_in_l1 = 1

        df_p = db.get_close_by_isin(isin, days=3)
        current_price = None
        if not df_p.empty:
            current_price = float(df_p.iloc[-1]['Close'])

        pct_gain = None
        if current_price and entry_price:
            pct_gain = round((current_price - float(entry_price)) / float(entry_price) * 100, 2)

        delta_calendar = (today - ed).days
        result.append({
            'isin':         isin,
            'fund_name':    fund_names.get(isin, isin),
            'entry_date':   ed.isoformat(),
            'entry_price':  float(entry_price),
            'current_price': current_price,
            'pct_gain':     pct_gain,
            'days_in_l1':   days_in_l1,
            'is_new':       delta_calendar <= 1,
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

        result.append({
            'isin':          isin,
            'fund_name':     entry['fund_name'],
            'entry_date':    str(entry['entry_date']) if entry['entry_date'] else None,
            'entry_price':   float(entry['entry_price']) if entry['entry_price'] else None,
            'current_price': current_price,
            'perf_pct':      perf_pct,
            'exit_date':     str(entry['exit_date']) if entry.get('exit_date') else None,
            'exit_price':    float(exit_price) if exit_price else None,
            'status':        status,
            'level':         analysis.get('level') or analysis.get('suggested_level'),
            'rsi':           analysis.get('rsi'),
            'adx':           analysis.get('adx'),
            'ema20':         analysis.get('ema20'),
            'dist_ema20':    analysis.get('dist_ema20'),
            'etf_type':      analysis.get('etf_type', ''),
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
    ok = db.add_portfolio_entry(isin, entry_date, entry_price, fund_name)
    if ok:
        return jsonify({'status': 'ok', 'isin': isin})
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


if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
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
