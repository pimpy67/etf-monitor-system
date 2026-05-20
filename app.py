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

        # Recupera storico prezzi dal DB per il grafico
        identifier  = isin or ticker
        price_hist  = []
        df = db.get_close_by_isin(identifier, days=90)
        if df.empty and ticker:
            df = db.get_ohlcv(ticker, days=90)
            if not df.empty:
                for _, row in df.iterrows():
                    price_hist.append({'date': str(row['date']), 'close': float(row['close'])})
        else:
            for date_idx, row in df.iterrows():
                price_hist.append({'date': str(date_idx.date()), 'close': float(row['Close'])})

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
