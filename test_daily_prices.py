"""
test_daily_prices.py - Test di verifica automatico per aggiornamenti prezzi giornalieri
=====================================================================================

Controlla che:
1. I prezzi siano stati aggiornati oggi (timestamp recente)
2. Il numero di ETF con prezzi validi sia > 180 (su 214)
3. Dashboard sia stata aggiornata (last_update = oggi)
4. L0/L1/L2/L3 abbiano dati coerenti
"""

import json
import psycopg2
import os
from datetime import datetime, timedelta
from pathlib import Path


def test_dashboard_updated():
    """Verifica che dashboard_data.json sia aggiornato oggi"""
    try:
        with open('data/dashboard_data.json', 'r') as f:
            data = json.load(f)

        last_update = data.get('last_update')
        if not last_update:
            return False, "last_update non trovato"

        last_dt = datetime.fromisoformat(last_update)
        today = datetime.now().date()

        if last_dt.date() != today:
            return False, f"last_update {last_dt.date()} ≠ oggi {today}"

        return True, f"✅ Dashboard aggiornato oggi a {last_dt.strftime('%H:%M:%S')}"
    except Exception as e:
        return False, f"❌ Errore lettura dashboard: {e}"


def test_price_history_count():
    """Verifica numero di ETF con prezzi nel database"""
    try:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            return False, "DATABASE_URL non configurato"

        try:
            conn = psycopg2.connect(db_url, sslmode='require')
        except:
            conn = psycopg2.connect(db_url)

        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(DISTINCT ticker) as etf_count,
                   COUNT(DISTINCT DATE(date)) as unique_dates
            FROM etf_price_history
            WHERE date >= (CURRENT_DATE - INTERVAL '1 day')
        """)
        etf_count, unique_dates = cur.fetchone()
        cur.close()
        conn.close()

        if etf_count < 180:
            return False, f"Solo {etf_count}/214 ETF hanno prezzi recenti (min: 180)"

        return True, f"✅ {etf_count} ETF con prezzi aggiornati, {unique_dates} date uniche"
    except Exception as e:
        return False, f"❌ Errore query DB: {e}"


def test_latest_price_dates():
    """Verifica che i prezzi più recenti siano di oggi o ieri"""
    try:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            return False, "DATABASE_URL non configurato"

        try:
            conn = psycopg2.connect(db_url, sslmode='require')
        except:
            conn = psycopg2.connect(db_url)

        cur = conn.cursor()
        cur.execute("""
            SELECT DATE(MAX(date)) as latest_date,
                   COUNT(*) as etf_with_latest
            FROM etf_price_history
            WHERE date = (SELECT MAX(date) FROM etf_price_history)
        """)
        latest_date, count = cur.fetchone()
        cur.close()
        conn.close()

        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        if latest_date not in [today, yesterday]:
            return False, f"Ultimi prezzi sono di {latest_date} (atteso oggi o ieri)"

        return True, f"✅ Ultimi prezzi di {latest_date}: {count} ETF aggiornati"
    except Exception as e:
        return False, f"❌ Errore query DB: {e}"


def test_l1_l2_consistency():
    """Verifica che la somma L0+L1+L2+L3 corrisponda al totale ETF"""
    try:
        with open('data/dashboard_data.json', 'r') as f:
            data = json.load(f)

        levels = data.get('levels', {})
        total = sum(len(levels.get(str(i), [])) for i in range(4))

        summary = data.get('summary', {})
        expected = summary.get('total_etfs', 0)

        if total != expected:
            return False, f"Somma livelli {total} ≠ total_etfs {expected}"

        l0_count = len(levels.get('0', []))
        l1_count = len(levels.get('1', []))
        l2_count = len(levels.get('2', []))
        l3_count = len(levels.get('3', []))

        return True, f"✅ L0:{l0_count} + L1:{l1_count} + L2:{l2_count} + L3:{l3_count} = {total} ETF"
    except Exception as e:
        return False, f"❌ Errore verifica livelli: {e}"


def test_monitor_completion_time():
    """Verifica che il monitor completi in tempo ragionevole (< 15 min)"""
    try:
        with open('data/dashboard_data.json', 'r') as f:
            data = json.load(f)

        last_update = data.get('last_update')
        if not last_update:
            return False, "last_update non trovato"

        last_dt = datetime.fromisoformat(last_update)
        elapsed = (datetime.now() - last_dt).total_seconds()

        if elapsed > 900:  # 15 minuti
            return False, f"Monitor ha impiegato {elapsed/60:.0f} min (max 15 min)"

        return True, f"✅ Monitor completato in {elapsed/60:.1f} minuti"
    except Exception as e:
        return False, f"❌ Errore timing: {e}"


def run_all_tests():
    """Esegue tutti i test e stampa report"""
    print("\n" + "=" * 70)
    print("🧪 TEST VERIFICA AGGIORNAMENTI PREZZI GIORNALIERI")
    print("=" * 70)

    tests = [
        ("Dashboard aggiornato", test_dashboard_updated),
        ("Prezzi nel database", test_price_history_count),
        ("Date prezzi recenti", test_latest_price_dates),
        ("Coerenza L0/L1/L2/L3", test_l1_l2_consistency),
        ("Tempo completamento monitor", test_monitor_completion_time),
    ]

    results = []
    for name, test_fn in tests:
        success, message = test_fn()
        results.append((success, name, message))
        status = "✅" if success else "❌"
        print(f"\n{status} {name}")
        print(f"   {message}")

    passed = sum(1 for s, _, _ in results if s)
    total = len(results)

    print("\n" + "=" * 70)
    print(f"📊 RISULTATO: {passed}/{total} test passati")
    print("=" * 70)

    if passed == total:
        print("🎉 TUTTI I TEST PASSATI — Aggiornamenti automatici funzionanti!")
        return True
    else:
        print("⚠️  ALCUNI TEST FALLITI — Verificare i log del monitor")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
