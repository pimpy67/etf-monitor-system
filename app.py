"""
app.py - Web server per la dashboard ETF
==========================================
Serve la dashboard HTML e i dati JSON.
Legge dati direttamente da PostgreSQL (persistente).
"""

from flask import Flask, send_file, send_from_directory, jsonify, request
import os
import json
import threading
from datetime import datetime

from database import PriceDatabase

app = Flask(__name__)

# Database instance globale
db = PriceDatabase()


@app.route('/')
def index():
    """Serve la dashboard principale"""
    return send_file('dashboard.html')

@app.route('/data/<path:filename>')
def serve_data(filename):
    """Serve i file dati JSON"""
    return send_from_directory('data', filename)

@app.route('/api/status')
def status():
    """Endpoint per verificare lo stato del sistema"""
    json_status = None
    try:
        with open('data/dashboard_data.json', 'r') as f:
            data = json.load(f)
        json_status = {
            'last_update': data.get('last_update'),
            'total_etfs': data.get('summary', {}).get('total_etfs', 0)
        }
    except:
        pass

    db_stats = db.get_stats()

    return jsonify({
        'status': 'ok',
        'json_data': json_status,
        'database': db_stats,
        'database_url_set': bool(os.environ.get('DATABASE_URL'))
    })

@app.route('/api/etfs')
def get_etfs():
    """API per ottenere tutti gli ETF"""
    try:
        with open('data/dashboard_data.json', 'r') as f:
            return jsonify(json.load(f))
    except:
        return jsonify({'error': 'Data not available'}), 404

@app.route('/api/db-status')
def db_status_endpoint():
    """Diagnostica connessione database PostgreSQL"""
    raw_url = os.environ.get('DATABASE_URL', '')

    safe_url = 'NOT SET'
    if raw_url:
        import re
        safe_url = re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', raw_url)

    result = {
        'database_url_safe': safe_url,
        'database_url_length': len(raw_url),
        'db_url_resolved': bool(db.database_url),
        'timestamp': datetime.now().isoformat()
    }

    try:
        import psycopg2
        try:
            conn = psycopg2.connect(raw_url, sslmode='require', connect_timeout=5)
            conn.close()
            result['connection'] = 'OK (SSL)'
        except Exception as ssl_err:
            result['ssl_error'] = str(ssl_err)
            try:
                conn = psycopg2.connect(raw_url, connect_timeout=5)
                conn.close()
                result['connection'] = 'OK (no SSL)'
            except Exception as no_ssl_err:
                result['connection'] = 'ERRORE'
                result['no_ssl_error'] = str(no_ssl_err)
    except Exception as e:
        result['connection'] = 'ERRORE'
        result['error'] = str(e)

    return jsonify(result)

@app.route('/api/prices')
def get_prices():
    """API per ottenere prezzi OHLCV dal database"""
    ticker = request.args.get('ticker')
    days = int(request.args.get('days', 30))

    if ticker:
        df = db.get_ohlcv(ticker, days)
        if not df.empty:
            prices = []
            for _, row in df.iterrows():
                prices.append({
                    'date': str(row['date']),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': int(row['volume'])
                })
            return jsonify({'ticker': ticker, 'prices': prices, 'count': len(prices)})
        return jsonify({'ticker': ticker, 'prices': [], 'count': 0})
    else:
        stats = db.get_stats()
        return jsonify(stats)

@app.route('/api/trigger-update', methods=['POST'])
def trigger_update():
    """Trigger manuale del monitoraggio"""
    def run_monitor_async():
        try:
            from monitor import ETFMonitor
            monitor = ETFMonitor()
            monitor.run(send_daily_report=False)
        except Exception as e:
            print(f"Errore monitoraggio manuale: {e}")

    thread = threading.Thread(target=run_monitor_async)
    thread.start()

    return jsonify({
        'status': 'started',
        'message': 'Monitoraggio ETF avviato in background',
        'timestamp': datetime.now().isoformat()
    })


if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)

    if not os.path.exists('data/dashboard_data.json'):
        initial_data = {
            'last_update': datetime.now().isoformat(),
            'summary': {'total_etfs': 0, 'buy_signals': 0, 'sell_signals': 0, 'hold_signals': 0},
            'levels': {'1': [], '2': [], '3': []},
            'categories': {}
        }
        with open('data/dashboard_data.json', 'w') as f:
            json.dump(initial_data, f)

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
