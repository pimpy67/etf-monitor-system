#!/bin/bash
# Launcher Mac/Linux per analisi portafoglio
cd "$(dirname "$0")"

echo ""
echo "================================================"
echo "  ANALISI PORTAFOGLIO ETF e BTP"
echo "================================================"
echo ""

# Installa xlrd se mancante
python3 -c "import xlrd" 2>/dev/null || pip3 install xlrd -q

python3 portfolio_analysis.py
