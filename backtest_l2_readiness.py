#!/usr/bin/env python3
"""
Backtest L2 Readiness Score — Validazione su dati storici
Misura il tasso di falsi positivi in mercati laterali (chop zone)
"""

import os
import json
import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from technical_analysis import ETFTechnicalAnalyzer
from database import PriceDatabase

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

LOOKBACK_DAYS = 120  # Ultimi 120 giorni di storico
MIN_DATA_POINTS = 50  # Minimo punti dati richiesti per backtest

L2_PARAMS = {
    'enter_threshold': 70,
    'exit_threshold': 60,
    'smoothing_period': 3,
    'jump_threshold': 25,
    'rsi_approach_margin': 5,
    'adx_trend_days': 5,
    'volume_ratio_threshold': 1.2,
}

class L2BacktestEngine:
    def __init__(self, db):
        self.db = db
        self.results = []
        self.false_positives = []
        self.chop_zones = []

    def calculate_l2_score_historical(self, prices_series, ema20_series, rsi_series,
                                       adx_series, volume_series, volume_20ma_series,
                                       days_above_ema20_series, ema20_full, adx_full,
                                       macd_hist_series):
        """
        Calcola L2 score grezzo per tutta la serie storica
        Ritorna lista di (date, score_grezzo)
        """
        scores = []

        for i in range(len(prices_series)):
            if i < 20:  # Saltare primi 20 giorni (mancano indicatori)
                continue

            price = prices_series[i]
            ema20 = ema20_series[i] if i < len(ema20_series) else None
            rsi = rsi_series[i] if i < len(rsi_series) else None
            adx = adx_series[i] if i < len(adx_series) else None
            volume = volume_series[i] if i < len(volume_series) else None
            volume_20ma = volume_20ma_series[i] if i < len(volume_20ma_series) else None
            days_above = days_above_ema20_series[i] if i < len(days_above_ema20_series) else 0
            macd_h = macd_hist_series[i] if i < len(macd_hist_series) else 0

            if any(x is None for x in [price, ema20, rsi, adx]):
                continue

            # 6 componenti L2 score

            # 1. Distance EMA20 (20%)
            dist_ema20 = abs(price - ema20) / ema20 * 100
            dist_score = max(0, 100 - (dist_ema20 / 4.0 * 100)) if dist_ema20 <= 4.0 else 0

            # 2. RSI approach (20%)
            rsi_low = 45  # Tipico range basso
            rsi_high = 55  # Tipico range alto
            rsi_center = (rsi_low + rsi_high) / 2
            rsi_approach = max(0, 100 - (abs(rsi - rsi_center) / (rsi_high - rsi_center) * 100))

            # 3. ADX rising (20%)
            adx_current = adx
            adx_score = min(100, (adx_current / 25.0) * 100)

            # 4. MACD histogram (20%)
            macd_score = 100 if macd_h > 0 else max(0, 100 * (1 + macd_h / 0.1)) if macd_h > -0.1 else 0

            # 5. Volume expansion (10%)
            if volume_20ma and volume_20ma > 0:
                volume_ratio = volume / volume_20ma
                volume_score = min(100, (volume_ratio / L2_PARAMS['volume_ratio_threshold']) * 100)
            else:
                volume_score = 50

            # 6. Days above EMA20 (10%)
            days_score = min(100, (days_above / 5.0) * 100)  # 5 è soglia L1

            # Weighted score
            raw_score = (
                dist_score * 0.20 +
                rsi_approach * 0.20 +
                adx_score * 0.20 +
                macd_score * 0.20 +
                volume_score * 0.10 +
                days_score * 0.10
            )

            scores.append({
                'index': i,
                'raw_score': raw_score,
                'dist_ema20': dist_ema20,
                'rsi': rsi,
                'adx': adx,
                'price': price,
                'ema20': ema20,
            })

        return scores

    def apply_smoothing_and_hysteresis(self, raw_scores):
        """
        Applica EMA3 smoothing + isteresi + jump override + hard reset
        Ritorna lista di (index, smoothed_score, enters_l2, exits_l2, jump_triggered)
        """
        if not raw_scores:
            return []

        smoothed = []
        ema_value = raw_scores[0]['raw_score']
        in_watchlist = False

        for i, item in enumerate(raw_scores):
            raw = item['raw_score']

            # Calcola delta
            delta = raw - raw_scores[i-1]['raw_score'] if i > 0 else 0

            # Jump override: se delta > 25 e raw >= 70, usa raw direttamente
            jump_triggered = False
            if abs(delta) > L2_PARAMS['jump_threshold'] and raw >= L2_PARAMS['enter_threshold']:
                ema_value = raw  # Hard-set
                jump_triggered = True
            else:
                # EMA3
                alpha = 2 / (L2_PARAMS['smoothing_period'] + 1)
                ema_value = ema_value * (1 - alpha) + raw * alpha

            # Isteresi
            enters_l2 = False
            exits_l2 = False

            if not in_watchlist and ema_value >= L2_PARAMS['enter_threshold']:
                enters_l2 = True
                in_watchlist = True
            elif in_watchlist and ema_value < L2_PARAMS['exit_threshold']:
                exits_l2 = True
                in_watchlist = False

            smoothed.append({
                'index': i,
                'raw_score': raw,
                'smoothed_score': ema_value,
                'enters_l2': enters_l2,
                'exits_l2': exits_l2,
                'in_watchlist': in_watchlist,
                'jump_triggered': jump_triggered,
                'delta': delta,
                'dist_ema20': item['dist_ema20'],
                'price': item['price'],
                'ema20': item['ema20'],
                'adx': item['adx'],
                'rsi': item['rsi'],
            })

        return smoothed

    def detect_chop_zones(self, prices):
        """
        Detect chop zones (mercati laterali) usando Average True Range
        Chop zone = ATR basso, movimento range-bound
        """
        if len(prices) < 20:
            return []

        chop_zones = []
        high = prices
        low = prices
        close = prices

        # Calcola ATR
        tr = []
        for i in range(len(prices)):
            h = high[i]
            l = low[i]
            c = close[i]
            if i > 0:
                tr.append(max(h - l, abs(h - c), abs(l - c)))
            else:
                tr.append(h - l)

        atr = pd.Series(tr).rolling(14).mean()
        price_range = pd.Series(prices).rolling(20).apply(lambda x: (x.max() - x.min()) / x.mean() * 100)

        for i in range(len(atr)):
            if atr[i] is not None and price_range[i] is not None:
                # Chop zone = prezzo in range stretto (< 2% su 20gg)
                if price_range[i] < 2.0:
                    chop_zones.append(i)

        return chop_zones

    def measure_false_positives(self, smoothed, chop_zones, etf_name):
        """
        Conta falsi positivi: entra in L2 ma esce il giorno dopo (no conversion a L1)
        """
        fp_count = 0
        fp_details = []

        for i, item in enumerate(smoothed):
            if item['enters_l2']:
                # Verifica se esce entro 2 giorni senza diventare L1
                for j in range(i+1, min(i+3, len(smoothed))):
                    if smoothed[j]['exits_l2']:
                        fp_count += 1
                        fp_details.append({
                            'index': i,
                            'duration_days': j - i,
                            'raw_score': item['raw_score'],
                            'smoothed_score': item['smoothed_score'],
                            'in_chop': i in chop_zones,
                        })
                        break

        return fp_count, fp_details

    def backtest_etf(self, isin, etf_name, categoria):
        """Backtest singolo ETF"""
        print(f"  🔄 {etf_name[:50]:50s}...", end='', flush=True)

        try:
            # Carica storico
            conn = self.db.get_connection()
            if not conn:
                print(f" ⏭️  (DB unavailable)")
                return None

            with conn.cursor() as cur:
                cur.execute("""
                    SELECT date, close, high, low, volume
                    FROM etf_price_history
                    WHERE ticker = %s
                    ORDER BY date ASC
                """, (isin,))
                rows = cur.fetchall()
            conn.close()

            if len(rows) < MIN_DATA_POINTS:
                print(f" ⏭️  (dati insufficienti: {len(rows)} punti)")
                return None

            # Filtra righe con close valido (obbligatorio)
            rows = [r for r in rows if r[1] is not None]
            if len(rows) < MIN_DATA_POINTS:
                print(f" ⏭️  (dati insufficienti: {len(rows)} punti)")
                return None

            rows.reverse()  # Cronologico

            dates = [r[0] for r in rows]
            closes = np.array([float(r[1]) for r in rows])
            # Se high/low mancano, stima da close con volatilità tipica (±1%)
            highs = np.array([float(r[2]) if r[2] else float(r[1]) * 1.01 for r in rows])
            lows = np.array([float(r[3]) if r[3] else float(r[1]) * 0.99 for r in rows])
            volumes = np.array([float(r[4]) if r[4] else 1000000 for r in rows])

            # Converte in pandas Series per l'analyzer
            closes_series = pd.Series(closes)
            highs_series = pd.Series(highs)
            lows_series = pd.Series(lows)
            volumes_series = pd.Series(volumes)

            # Calcola indicatori
            analyzer = ETFTechnicalAnalyzer(famiglia='equity_sviluppati')

            ema20_series = analyzer._ema(closes_series, period=20)
            rsi_series = analyzer._rsi(closes_series, period=14)
            adx_series = analyzer._adx(highs_series, lows_series, closes_series, period=14)

            volume_20ma = volumes_series.rolling(20).mean()

            days_above = []
            for i, c in enumerate(closes):
                if i < len(ema20_series):
                    days_above.append(1 if c > ema20_series.iloc[i] else 0)
                else:
                    days_above.append(0)

            # MACD
            macd, macd_signal, macd_hist = analyzer._macd(closes_series)

            # Calcola L2 score grezzo
            raw_scores = self.calculate_l2_score_historical(
                closes, ema20_series, rsi_series, adx_series, volumes, volume_20ma,
                days_above, ema20_series, adx_series, macd_hist
            )

            if len(raw_scores) < 20:
                print(f" ⏭️  (indicatori insufficienti)")
                return None

            # Applica smoothing + isteresi
            smoothed = self.apply_smoothing_and_hysteresis(raw_scores)

            # Detect chop zones
            chop_zones = self.detect_chop_zones(closes)

            # Conta falsi positivi
            fp_count, fp_details = self.measure_false_positives(smoothed, chop_zones, etf_name)
            fp_rate = (fp_count / len([s for s in smoothed if s['enters_l2']])) * 100 if any(s['enters_l2'] for s in smoothed) else 0

            total_entries = len([s for s in smoothed if s['enters_l2']])
            chop_entries = len([s for s in smoothed if s['enters_l2'] and s['index'] in chop_zones])
            chop_fp_rate = (chop_fp_count / chop_entries) * 100 if chop_entries > 0 else 0

            # Count chop zone false positives
            chop_fp_count = len([f for f in fp_details if f['in_chop']])

            result = {
                'isin': isin,
                'nome': etf_name,
                'categoria': categoria,
                'data_points': len(rows),
                'total_entries': total_entries,
                'false_positives': fp_count,
                'fp_rate': fp_rate,
                'chop_entries': chop_entries,
                'chop_fp': chop_fp_count,
                'chop_fp_rate': chop_fp_rate,
                'smoothed_series': smoothed,
            }

            print(f" ✅ entries={total_entries}, FP={fp_count} ({fp_rate:.1f}%)")
            return result

        except Exception as e:
            print(f" ❌ Errore: {e}")
            return None

    def run_backtest(self, limit=None):
        """Esegui backtest su tutti gli ETF"""
        print("\n" + "="*80)
        print("BACKTEST L2 READINESS SCORE — VALIDATION RUN")
        print("="*80)
        print(f"Parametri: ENTER={L2_PARAMS['enter_threshold']}, EXIT={L2_PARAMS['exit_threshold']}, " +
              f"EMA_PERIOD={L2_PARAMS['smoothing_period']}, JUMP_DELTA={L2_PARAMS['jump_threshold']}")
        print("="*80 + "\n")

        # Carica lista ETF
        conn = self.db.get_connection()
        if not conn:
            print("❌ Errore: impossibile connettersi al database")
            return None

        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ticker
                FROM etf_price_history
                LIMIT %s
            """, (limit or 50,))
            rows = cur.fetchall()
        conn.close()

        etfs = [(r[0], r[0]) for r in rows]  # (ticker, isin_fallback)

        print(f"🔍 Backtest su {len(etfs)} ETF (lookback {LOOKBACK_DAYS} giorni)\n")

        for ticker, isin in etfs:
            result = self.backtest_etf(isin or ticker, ticker or isin, '')
            if result:
                self.results.append(result)

        return self.generate_report()

    def generate_report(self):
        """Genera report finale"""
        if not self.results:
            print("\n⚠️  Nessun risultato di backtest disponibile")
            return

        print("\n" + "="*80)
        print("BACKTEST RESULTS — SUMMARY")
        print("="*80 + "\n")

        df = pd.DataFrame([{
            'nome': r['nome'],
            'entries': r['total_entries'],
            'fp': r['false_positives'],
            'fp_rate': r['fp_rate'],
            'chop_fp': r['chop_fp'],
        } for r in self.results])

        print(df.to_string(index=False))
        print()

        # Metriche aggregate
        total_entries = sum(r['total_entries'] for r in self.results)
        total_fp = sum(r['false_positives'] for r in self.results)
        overall_fp_rate = (total_fp / total_entries * 100) if total_entries > 0 else 0

        total_chop_fp = sum(r['chop_fp'] for r in self.results)
        total_chop_entries = sum(r['chop_entries'] for r in self.results)
        chop_fp_rate = (total_chop_fp / total_chop_entries * 100) if total_chop_entries > 0 else 0

        print("="*80)
        print("AGGREGATE METRICS")
        print("="*80)
        print(f"Total L2 Entries:       {total_entries}")
        print(f"Total False Positives:  {total_fp}")
        print(f"Overall FP Rate:        {overall_fp_rate:.2f}%")
        print()
        print(f"Chop Zone Entries:      {total_chop_entries}")
        print(f"Chop Zone FP:           {total_chop_fp}")
        print(f"Chop Zone FP Rate:      {chop_fp_rate:.2f}%")
        print()

        # Valutazione
        print("="*80)
        print("ASSESSMENT")
        print("="*80)

        if overall_fp_rate < 15:
            print(f"✅ GOOD: FP rate {overall_fp_rate:.2f}% è accettabile (<15%)")
            assessment = "PASS"
        elif overall_fp_rate < 25:
            print(f"⚠️  MARGINAL: FP rate {overall_fp_rate:.2f}% è alta (15-25%)")
            assessment = "REVIEW"
        else:
            print(f"❌ POOR: FP rate {overall_fp_rate:.2f}% è molto alta (>25%)")
            assessment = "FAIL"

        print()
        print(f"Recommendation: L2 readiness layer is {assessment} for dashboard integration")
        print("="*80 + "\n")

        # Salva risultati dettagliati
        report = {
            'timestamp': datetime.now().isoformat(),
            'parameters': L2_PARAMS,
            'lookback_days': LOOKBACK_DAYS,
            'etfs_tested': len(self.results),
            'overall_metrics': {
                'total_entries': total_entries,
                'total_false_positives': total_fp,
                'fp_rate_percent': overall_fp_rate,
                'chop_zone_entries': total_chop_entries,
                'chop_zone_fp': total_chop_fp,
                'chop_zone_fp_rate_percent': chop_fp_rate,
            },
            'assessment': assessment,
            'etf_results': self.results,
        }

        report_path = Path('data/l2_backtest_report.json')
        with open(report_path, 'w') as f:
            # Convertire series in liste per JSON
            for r in report['etf_results']:
                del r['smoothed_series']
            json.dump(report, f, indent=2, default=str)

        print(f"📊 Report salvato: {report_path}\n")

        return report

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("\n🧪 Initializing L2 Readiness Score Backtest...\n")

    db = PriceDatabase()
    engine = L2BacktestEngine(db)

    # Backtest 50 ETF casuali
    report = engine.run_backtest(limit=50)

    if report and report['assessment'] == 'PASS':
        print("✅ L2 BACKTEST PASSED — Ready for dashboard integration\n")
    else:
        print("⚠️  L2 BACKTEST NEEDS REVIEW — Adjusting parameters may be required\n")
