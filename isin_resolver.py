"""
isin_resolver.py - Risoluzione ISIN per ETF via JustETF
========================================================
Usa la libreria justetf-scraping per mappare i 188 ETF
dal file Excel ai rispettivi codici ISIN univoci.

Strategie di matching:
1. Ticker esatto (per ticker non duplicati)
2. Ticker + similarità nome (per ticker duplicati)
3. Solo similarità nome (fallback)
"""

import json
import logging
import pandas as pd
from difflib import SequenceMatcher
from pathlib import Path

import justetf_scraping as jes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAPPING_PATH = 'data/isin_mapping.json'


class ISINResolver:
    """Risolve ISIN per ETF usando dati JustETF"""

    def __init__(self):
        self.justetf_df = None

    def load_justetf_universe(self) -> pd.DataFrame:
        """Carica tutti gli ETF da JustETF (circa 4000+)"""
        if self.justetf_df is not None:
            return self.justetf_df

        logger.info("Caricamento universo ETF da JustETF...")
        self.justetf_df = jes.load_overview()
        logger.info(f"Caricati {len(self.justetf_df)} ETF da JustETF")
        return self.justetf_df

    def _name_similarity(self, name1: str, name2: str) -> float:
        """Calcola similarità tra due nomi ETF (0.0 - 1.0)"""
        # Normalizza
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()
        return SequenceMatcher(None, n1, n2).ratio()

    def _find_by_ticker(self, ticker: str) -> pd.DataFrame:
        """Trova ETF su JustETF per ticker (senza suffisso borsa)"""
        df = self.justetf_df

        # Rimuovi suffisso borsa (.MI, .DE, ecc.)
        base_ticker = ticker.split('.')[0] if '.' in ticker else ticker

        # Cerca match esatto nel campo ticker
        matches = df[df['ticker'].str.upper() == base_ticker.upper()]
        return matches

    def resolve_single(self, ticker: str, name: str, borsa: str = '') -> dict:
        """
        Risolve ISIN per un singolo ETF.

        Returns:
            dict con: isin, justetf_name, confidence, method
        """
        df = self.justetf_df

        # Strategia 1: Match per ticker
        ticker_matches = self._find_by_ticker(ticker)

        if len(ticker_matches) == 1:
            match = ticker_matches.iloc[0]
            isin = ticker_matches.index[0]
            confidence = 0.95
            # Verifica anche che il nome sia ragionevolmente simile
            sim = self._name_similarity(name, match['name'])
            if sim < 0.3:
                confidence = 0.6  # Ticker giusto ma nome molto diverso
            return {
                'isin': isin,
                'justetf_name': match['name'],
                'justetf_ticker': match['ticker'],
                'ter': float(match['ter']) if pd.notna(match['ter']) else None,
                'fund_size': int(match['size']) if pd.notna(match['size']) else None,
                'confidence': confidence,
                'method': 'ticker_exact'
            }

        if len(ticker_matches) > 1:
            # Strategia 2: Ticker duplicato, disambigua per nome
            best_sim = 0
            best_match = None
            best_isin = None

            for isin, row in ticker_matches.iterrows():
                sim = self._name_similarity(name, row['name'])
                if sim > best_sim:
                    best_sim = sim
                    best_match = row
                    best_isin = isin

            if best_match is not None and best_sim > 0.4:
                return {
                    'isin': best_isin,
                    'justetf_name': best_match['name'],
                    'justetf_ticker': best_match['ticker'],
                    'ter': float(best_match['ter']) if pd.notna(best_match['ter']) else None,
                    'fund_size': int(best_match['size']) if pd.notna(best_match['size']) else None,
                    'confidence': round(best_sim, 2),
                    'method': 'ticker_name_match'
                }

        # Strategia 3: Fallback - cerca solo per nome nell'intero universo
        best_sim = 0
        best_match = None
        best_isin = None

        for isin, row in df.iterrows():
            sim = self._name_similarity(name, row['name'])
            if sim > best_sim:
                best_sim = sim
                best_match = row
                best_isin = isin

        if best_match is not None and best_sim > 0.5:
            return {
                'isin': best_isin,
                'justetf_name': best_match['name'],
                'justetf_ticker': best_match['ticker'],
                'ter': float(best_match['ter']) if pd.notna(best_match['ter']) else None,
                'fund_size': int(best_match['size']) if pd.notna(best_match['size']) else None,
                'confidence': round(best_sim, 2),
                'method': 'name_fuzzy'
            }

        return {
            'isin': '',
            'justetf_name': '',
            'justetf_ticker': '',
            'ter': None,
            'fund_size': None,
            'confidence': 0,
            'method': 'not_found'
        }

    def resolve_all(self, excel_path: str = 'etf_monitoraggio.xlsx') -> list:
        """
        Risolve ISIN per tutti gli ETF nel file Excel.

        Returns:
            Lista di dict con risultati per ogni ETF
        """
        self.load_justetf_universe()

        df = pd.read_excel(excel_path, sheet_name='ETF')
        logger.info(f"Risoluzione ISIN per {len(df)} ETF...")

        results = []
        for idx, row in df.iterrows():
            ticker = str(row['Ticker'])
            name = str(row['Nome ETF'])
            borsa = str(row.get('Borsa', ''))

            result = self.resolve_single(ticker, name, borsa)
            result['excel_index'] = int(idx)
            result['excel_ticker'] = ticker
            result['excel_name'] = name
            results.append(result)

            # Log del progresso
            status = 'OK' if result['confidence'] >= 0.7 else 'LOW' if result['confidence'] > 0 else 'FAIL'
            logger.info(
                f"  [{status}] {ticker:15s} -> {result['isin']:14s} "
                f"(conf={result['confidence']:.2f}, method={result['method']})"
            )

        # Statistiche
        total = len(results)
        high_conf = sum(1 for r in results if r['confidence'] >= 0.7)
        low_conf = sum(1 for r in results if 0 < r['confidence'] < 0.7)
        not_found = sum(1 for r in results if r['confidence'] == 0)

        logger.info(f"\n{'='*60}")
        logger.info(f"RISULTATI RISOLUZIONE ISIN:")
        logger.info(f"  Totale: {total}")
        logger.info(f"  Alta confidenza (>=0.7): {high_conf}")
        logger.info(f"  Bassa confidenza (<0.7): {low_conf}")
        logger.info(f"  Non trovati: {not_found}")
        logger.info(f"{'='*60}")

        return results

    def save_mapping(self, results: list, path: str = MAPPING_PATH):
        """Salva mapping ISIN in file JSON"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info(f"Mapping salvato in {path}")

    def load_mapping(self, path: str = MAPPING_PATH) -> list:
        """Carica mapping ISIN da file JSON"""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)


def main():
    """Esegui risoluzione ISIN e salva risultati"""
    resolver = ISINResolver()
    results = resolver.resolve_all()
    resolver.save_mapping(results)

    # Mostra risultati a bassa confidenza per review manuale
    low_conf = [r for r in results if r['confidence'] < 0.7]
    if low_conf:
        print(f"\n{'='*60}")
        print(f"RICHIEDE REVIEW MANUALE ({len(low_conf)} ETF):")
        print(f"{'='*60}")
        for r in low_conf:
            print(f"  Ticker: {r['excel_ticker']}")
            print(f"  Nome:   {r['excel_name']}")
            print(f"  ISIN:   {r['isin'] or 'NON TROVATO'}")
            print(f"  Match:  {r['justetf_name']}")
            print(f"  Conf:   {r['confidence']}")
            print(f"  Metodo: {r['method']}")
            print()


if __name__ == "__main__":
    main()
