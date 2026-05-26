#!/bin/bash
cd "$(dirname "$0")"
python3 -c "import xlrd" 2>/dev/null || pip3 install xlrd -q
python3 portfolio_analysis.py
