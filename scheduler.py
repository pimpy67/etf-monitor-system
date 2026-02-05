"""
scheduler.py - Scheduler per monitoraggio automatico ETF
=========================================================
Esegue il monitoraggio ogni giorno alle 18:00
"""

import schedule
import time
import os
from datetime import datetime
import threading

from monitor import ETFMonitor


def run_monitor():
    """Esegue il monitoraggio"""
    print(f"\nScheduler: avvio monitoraggio programmato - {datetime.now()}")
    try:
        monitor = ETFMonitor()
        monitor.run(send_daily_report=True)
    except Exception as e:
        print(f"Errore durante monitoraggio: {e}")


def run_scheduler():
    """Avvia lo scheduler"""
    hour = int(os.environ.get('MONITOR_HOUR', 18))
    minute = int(os.environ.get('MONITOR_MINUTE', 0))

    schedule_time = f"{hour:02d}:{minute:02d}"

    print(f"Scheduler configurato per le {schedule_time} ogni giorno")

    schedule.every().day.at(schedule_time).do(run_monitor)

    while True:
        schedule.run_pending()
        time.sleep(60)


def start_scheduler_thread():
    """Avvia scheduler in un thread separato (per uso con Flask)"""
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    return scheduler_thread


if __name__ == "__main__":
    print("=" * 50)
    print("ETF MONITOR SCHEDULER")
    print("=" * 50)

    if os.environ.get('RUN_ON_START', 'false').lower() == 'true':
        print("\nEsecuzione monitoraggio iniziale...")
        run_monitor()

    run_scheduler()
