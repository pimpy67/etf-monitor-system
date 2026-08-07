"""
freeze_historical_dataset.py — Congela UNA VOLTA lo storico OHLCV di tutto l'universo
ETF in etf_price_history_frozen, per rendere i backtest riproducibili al 100%.

Da lanciare manualmente quando serve un nuovo snapshot (es. dopo un lungo periodo, o se
si vuole includere ETF nuovi). NON viene mai chiamato dal monitor live — quello continua
a usare dati freschi via data_fetcher.py/get_ohlc_by_isin per i segnali reali.

Uso:
    python3 freeze_historical_dataset.py [--batch YYYY-MM-DD] [--days 1120]
"""

import argparse
import time
from datetime import datetime

import pandas as pd

from data_fetcher import ETFDataFetcher
from database import Database
from technical_analysis import ETFTechnicalAnalyzer

TARGET_FAMILIES = {
    'equity_sviluppati', 'mercati_emergenti', 'settoriali_growth', 'settoriali_difensivi',
    'bond_governativi', 'bond_corp_hy_em', 'commodities', 'oro_metalli_preziosi',
    'metalli_industriali', 'real_estate_reit', 'crypto_digital_assets',
    'leva_single_stock', 'private_equity_buffer',
}


def load_universe(excel_path='etf_monitoraggio.xlsx'):
    df = pd.read_excel(excel_path, sheet_name='ETF')
    rows = []
    for _, row in df.iterrows():
        ticker = str(row.get('Ticker', '')).strip()
        isin = str(row.get('ISIN', '')).strip()
        categoria = str(row.get('Categoria', ''))
        if not ticker or ticker.lower() == 'nan':
            continue
        famiglia = ETFTechnicalAnalyzer.detect_family(categoria)
        if famiglia in TARGET_FAMILIES:
            rows.append({'ticker': ticker, 'isin': isin if isin.lower() != 'nan' else '',
                         'famiglia': famiglia})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', default=datetime.now().strftime('%Y-%m-%d'),
                         help='Etichetta dello snapshot (default: data odierna)')
    parser.add_argument('--days', type=int, default=1120,
                         help='Giorni di storico da scaricare per ticker (default ~3 anni + buffer)')
    args = parser.parse_args()

    universe = load_universe()
    print(f"Golden Dataset — batch '{args.batch}' — {len(universe)} ETF, {args.days} giorni ciascuno")
    print("=" * 78)

    fetcher = ETFDataFetcher()
    db = Database()

    ok, empty, err = 0, 0, 0
    for i, item in enumerate(universe, 1):
        ticker = item['ticker']
        isin = item['isin']
        try:
            df = fetcher.get_historical_data(ticker, days=args.days)
            if df.empty:
                print(f"[{i}/{len(universe)}] {ticker:12s} VUOTO (0 righe)")
                empty += 1
                continue
            saved = db.save_frozen_ohlcv_bulk(ticker, isin, df, args.batch)
            print(f"[{i}/{len(universe)}] {ticker:12s} OK — {saved} righe "
                  f"({df.index[0].date()} -> {df.index[-1].date()})")
            ok += 1
        except Exception as e:
            print(f"[{i}/{len(universe)}] {ticker:12s} ERRORE: {e}")
            err += 1
        time.sleep(fetcher.rate_limit)

    print("=" * 78)
    print(f"Completato: {ok} OK, {empty} vuoti, {err} errori su {len(universe)} ticker")
    print(f"Batch salvato: '{args.batch}'")


if __name__ == '__main__':
    main()
