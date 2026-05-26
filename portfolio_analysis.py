#!/usr/bin/env python3
"""
portfolio_analysis.py — Analisi giornaliera portafoglio reale
Legge il file XLS della banca, incrocia con ETF monitor, genera report HTML.

Uso:
  python portfolio_analysis.py
  oppure doppio click su analisi_portafoglio.bat
"""

import os
import sys
import json
import webbrowser
from datetime import datetime
from pathlib import Path
import urllib.request
import urllib.error

# Fix encoding console Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent
PORTAFOGLI_DIR = BASE_DIR / "portafogli"
REPORTS_DIR    = PORTAFOGLI_DIR / "reports"
ETF_API_BASE   = "https://etf.andreapavan.tech"

# Indici colonne nel file XLS della banca (riga header = riga 2, indice 0-based)
COL_TITOLO    = 1
COL_MERCATO   = 2
COL_QTY       = 3
COL_PMC       = 5
COL_LAST      = 6
COL_PL_EUR    = 7
COL_PL_PCT    = 8
COL_MKT_VAL  = 9
COL_ISIN      = 11
COL_VAR_PCT   = 15
COL_SCADENZA  = 27
COL_ACQUISTO  = 35

HEADER_ROW = 2  # riga 0-based con le intestazioni


def find_latest_xls():
    files = sorted(
        list(PORTAFOGLI_DIR.glob("Portafoglio-*.xls")) +
        list(PORTAFOGLI_DIR.glob("Portafoglio-*.xlsx")),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )
    if not files:
        print("ERRORE: nessun file Portafoglio-*.xls trovato in:", PORTAFOGLI_DIR)
        sys.exit(1)
    print(f"File: {files[0].name}")
    return files[0]


def safe_float(val, default=0.0):
    try:
        return float(val) if val not in ('', '-', None) else default
    except (ValueError, TypeError):
        return default


def parse_portfolio(xls_path):
    try:
        import xlrd
    except ImportError:
        print("Installa xlrd: python -m pip install xlrd")
        sys.exit(1)

    wb = xlrd.open_workbook(str(xls_path))
    sh = wb.sheet_by_index(0)
    positions = []

    for r in range(HEADER_ROW + 1, sh.nrows):
        row = sh.row_values(r)
        if len(row) <= COL_ISIN:
            continue

        isin = str(row[COL_ISIN]).strip()
        if len(isin) != 12:
            continue  # salta righe non-titolo (totali, vuote)

        titolo   = str(row[COL_TITOLO]).strip()
        mercato  = str(row[COL_MERCATO]).strip()
        qty      = safe_float(row[COL_QTY])
        pmc      = safe_float(row[COL_PMC])
        last     = safe_float(row[COL_LAST])
        pl_eur   = safe_float(row[COL_PL_EUR])
        pl_pct   = safe_float(row[COL_PL_PCT])
        mkt_val  = safe_float(row[COL_MKT_VAL])
        acquisto = safe_float(row[COL_ACQUISTO])
        var_pct  = safe_float(row[COL_VAR_PCT])
        scad_raw = str(row[COL_SCADENZA]).strip()
        scadenza = scad_raw if scad_raw not in ('31/12/2100', '', 'n.d.') else None

        is_btp = isin.startswith('IT')

        positions.append({
            'titolo':    titolo,
            'isin':      isin,
            'mercato':   mercato,
            'qty':       qty,
            'pmc':       pmc,
            'last':      last,
            'pl_eur':    pl_eur,
            'pl_pct':    pl_pct,
            'mkt_val':   mkt_val,
            'acquisto':  acquisto,
            'var_pct':   var_pct,
            'scadenza':  scadenza,
            'is_btp':    is_btp,
            'is_etf':    not is_btp,
        })

    return positions


def fetch_etf_data(isin):
    url = f"{ETF_API_BASE}/api/etf-detail?isin={isin}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'PortfolioAnalyzer/1.0'})
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"  API HTTP {e.code} per {isin}")
        return None
    except Exception as e:
        print(f"  Errore fetch {isin}: {e}")
        return None


def build_signal(pos, api_data):
    """Calcola segnale operativo + stop loss dinamici dagli indicatori."""
    if not api_data:
        return {
            'level':       '?',
            'signal_txt':  '❓ Non monitorato',
            'signal_cls':  'unknown',
            'ema20':       None,
            'rsi':         None,
            'adx':         None,
            'stop_loss':   None,
            'trailing':    None,
            'note':        'ISIN non presente nel monitor ETF',
            'buy_count':   0,
        }

    # Indicatori tecnici: sono alle chiavi top-level della risposta API
    ema20        = api_data.get('ema20')
    rsi          = api_data.get('rsi')
    adx          = api_data.get('adx')
    buy_count    = api_data.get('buy_count', 0)
    entry_date   = api_data.get('entry_date')
    l0_entry     = api_data.get('l0_entry', False)
    days_above   = api_data.get('days_above_ema20', 0)
    sma50        = api_data.get('sma50')

    # Determina livello
    if l0_entry:
        level = 0
    elif entry_date:
        level = 1
    elif days_above >= 3 or (ema20 and sma50 and ema20 > sma50):
        level = 2
    else:
        level = 3

    # Stop loss dinamico: EMA20 è il livello trigger; -1.5% come buffer pratico
    stop_loss = round(ema20 * 0.985, 3) if ema20 else None
    # Trailing stop: il livello EMA20 stesso (se price scende qui → attenzione)
    trailing  = round(ema20, 3) if ema20 else None

    # Segnale operativo
    if level == 1:
        if rsi and rsi > 72:
            signal_txt = '🟡 HOLD — RSI tirato'
            signal_cls = 'hold'
            note = f'RSI {rsi:.0f} > 72: non aggiungere ora. Trailing stop a {trailing}'
        elif buy_count >= 6:
            signal_txt = '🟢 BUY / HOLD'
            signal_cls = 'buy'
            note = f'Tutte {buy_count}/6 condizioni L1 soddisfatte — trend confermato'
        elif buy_count >= 4:
            signal_txt = '🟢 HOLD FORTE'
            signal_cls = 'buy'
            note = f'{buy_count}/6 condizioni L1 ok — mantieni, trend solido'
        else:
            signal_txt = '🟡 HOLD'
            signal_cls = 'hold'
            note = f'L1 attivo, {buy_count}/6 condizioni — monitoraggio'
    elif level == 2:
        if rsi and rsi > 60 and adx and adx > 20:
            signal_txt = '🟡 WATCH+'
            signal_cls = 'watch_plus'
            note = 'Prossimo a L1 — tieni d\'occhio, possibile upgrade'
        else:
            signal_txt = '🟡 WATCH'
            signal_cls = 'watch'
            note = 'Trend parziale (L2) — mantieni ma non aumentare la posizione'
    elif level == 0:
        signal_txt = '🔵 RECOVERY'
        signal_cls = 'recovery'
        note = 'In recupero da minimo (L0) — posizione speculativa, trailing stretto'
    else:
        signal_txt = '⚠️ DEBOLE'
        signal_cls = 'weak'
        note = 'Trend non confermato (L3) — valuta uscita se continua a peggiorare'

    return {
        'level':      f'L{level}',
        'signal_txt': signal_txt,
        'signal_cls': signal_cls,
        'ema20':      round(ema20, 3) if ema20 else None,
        'rsi':        round(rsi, 1)   if rsi   else None,
        'adx':        round(adx, 1)   if adx   else None,
        'stop_loss':  stop_loss,
        'trailing':   trailing,
        'note':       note,
        'buy_count':  buy_count,
    }


# ── HTML REPORT ────────────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
       background: #0f1117; color: #e0e0e0; padding: 20px; font-size: 14px; }
a { color: #63b3ed; }
h1 { color: #fff; font-size: 1.5rem; margin-bottom: 4px; }
h2 { color: #90cdf4; font-size: 1rem; margin: 26px 0 10px;
     border-bottom: 1px solid #2d3748; padding-bottom: 6px; letter-spacing: .04em; }
.subtitle { color: #718096; font-size: 0.8rem; margin-bottom: 22px; }

/* Cards */
.cards { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }
.card { background: #1a2035; border: 1px solid #2d3748; border-radius: 8px;
        padding: 12px 16px; min-width: 140px; }
.card-label { font-size: 0.68rem; color: #718096; text-transform: uppercase;
              letter-spacing: .06em; }
.card-value { font-size: 1.35rem; font-weight: 700; color: #fff; margin-top: 4px; }
.card-value.pos { color: #68d391; }
.card-value.neg { color: #fc8181; }
.card-sub { font-size: 0.74rem; color: #718096; margin-top: 2px; }

/* Tables */
.tbl-wrap { overflow-x: auto; margin-bottom: 10px; }
table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
th { background: #1a2035; color: #90cdf4; padding: 7px 9px; font-weight: 600;
     white-space: nowrap; text-align: right; }
th.l { text-align: left; }
th.c { text-align: center; }
td { padding: 6px 9px; border-bottom: 1px solid #1a2230; vertical-align: middle; }
td.r { text-align: right; }
td.c { text-align: center; }
td.pos { color: #68d391; }
td.neg { color: #fc8181; }
td.stop-val { color: #fc8181; font-weight: 600; text-align: right; }
td.trail-val { color: #f6ad55; font-weight: 600; text-align: right; }
td.note { font-size: 0.72rem; color: #a0aec0; font-style: italic;
          padding: 2px 9px 7px; border-bottom: 1px solid #2d3748; }

/* Signal row borders */
.s-buy      { border-left: 3px solid #68d391; }
.s-hold     { border-left: 3px solid #ecc94b; }
.s-watch    { border-left: 3px solid #63b3ed; }
.s-watch_plus { border-left: 3px solid #4fd1c5; }
.s-weak     { border-left: 3px solid #fc8181; }
.s-recovery { border-left: 3px solid #9f7aea; }
.s-unknown  { border-left: 3px solid #4a5568; }
tr:hover:not(.nrow) { background: #1e2533; }

/* Ranking */
.rank-box { display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px; }
.rank-item { display: flex; align-items: center; gap: 12px;
             background: #1a2035; border: 1px solid #2d3748;
             border-radius: 6px; padding: 10px 14px; }
.rank-item.s-buy      { border-left: 3px solid #68d391; }
.rank-item.s-hold     { border-left: 3px solid #ecc94b; }
.rank-item.s-watch    { border-left: 3px solid #63b3ed; }
.rank-item.s-watch_plus { border-left: 3px solid #4fd1c5; }
.rank-item.s-weak     { border-left: 3px solid #fc8181; }
.rank-emoji { font-size: 1.3rem; min-width: 28px; }
.rank-name  { flex: 1; font-size: 0.84rem; }
.rank-lv    { background: #2d3748; padding: 2px 8px; border-radius: 10px;
              font-size: 0.72rem; font-weight: 700; }
.rank-sig   { font-size: 0.82rem; min-width: 180px; }
.rank-stop  { font-size: 0.78rem; color: #fc8181; min-width: 110px; text-align: right; }
.rank-pl    { font-weight: 700; font-size: 0.88rem; min-width: 55px; text-align: right; }
.rank-pl.pos { color: #68d391; }
.rank-pl.neg { color: #fc8181; }

/* Legend + footer */
.legend { display: flex; gap: 20px; flex-wrap: wrap; margin-top: 18px;
          font-size: 0.74rem; color: #718096; }
.leg { display: flex; align-items: center; gap: 6px; }
.dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.footer { margin-top: 24px; color: #4a5568; font-size: 0.72rem;
          border-top: 1px solid #2d3748; padding-top: 10px; }
"""


def fmt_eur(v, decimals=2):
    if v is None: return '—'
    return f"€{v:,.{decimals}f}"

def fmt_pct(v, plus=True):
    if v is None: return '—'
    sign = '+' if v >= 0 and plus else ''
    return f"{sign}{v:.2f}%"

def pclass(v):
    return 'pos' if v >= 0 else 'neg'


def generate_report(positions, signals, report_date):
    etfs = [p for p in positions if p['is_etf']]
    btps = [p for p in positions if p['is_btp']]

    tot_val  = sum(p['mkt_val'] for p in positions)
    tot_pl   = sum(p['pl_eur']  for p in positions)
    etf_val  = sum(p['mkt_val'] for p in etfs)
    btp_val  = sum(p['mkt_val'] for p in btps)
    etf_pct  = etf_val / tot_val * 100 if tot_val else 0
    btp_pct  = btp_val / tot_val * 100 if tot_val else 0

    # ── Summary cards ──────────────────────────────────────────────────────────
    cards_html = f"""
<div class="cards">
  <div class="card">
    <div class="card-label">Valore totale</div>
    <div class="card-value">€{tot_val:,.0f}</div>
    <div class="card-sub">{'🟢 Positivo' if tot_pl >= 0 else '🔴 Negativo'}</div>
  </div>
  <div class="card">
    <div class="card-label">P&amp;L totale</div>
    <div class="card-value {pclass(tot_pl)}">{'+' if tot_pl >= 0 else ''}€{tot_pl:,.2f}</div>
    <div class="card-sub">vs costo acquisto</div>
  </div>
  <div class="card">
    <div class="card-label">ETF ({etf_pct:.1f}%)</div>
    <div class="card-value">€{etf_val:,.0f}</div>
    <div class="card-sub">{len(etfs)} posizioni</div>
  </div>
  <div class="card">
    <div class="card-label">BTP ({btp_pct:.1f}%)</div>
    <div class="card-value">€{btp_val:,.0f}</div>
    <div class="card-sub">{len(btps)} titoli</div>
  </div>
</div>"""

    # ── ETF table ──────────────────────────────────────────────────────────────
    etf_rows = ''
    for p in etfs:
        s  = signals.get(p['isin'], {})
        sc = s.get('signal_cls', 'unknown')
        pl_c    = pclass(p['pl_eur'])
        var_c   = pclass(p['var_pct'])
        stop_s  = fmt_eur(s.get('stop_loss'), 3)
        trail_s = fmt_eur(s.get('trailing'), 3)
        ema20_s = fmt_eur(s.get('ema20'), 3)
        rsi_s   = f"{s['rsi']:.1f}" if s.get('rsi') else '—'
        adx_s   = f"{s['adx']:.1f}" if s.get('adx') else '—'
        bc      = s.get('buy_count', 0)
        bc_s    = f"{bc}/6" if isinstance(bc, int) else '—'
        short   = p['titolo'][:38] + ('…' if len(p['titolo']) > 38 else '')

        etf_rows += f"""
    <tr class="s-{sc}">
      <td title="{p['titolo']}">{short}</td>
      <td class="c">{s.get('level','?')}</td>
      <td class="c">{s.get('signal_txt','?')}</td>
      <td class="r">{int(p['qty'])}</td>
      <td class="r">{fmt_eur(p['pmc'],3)}</td>
      <td class="r">{fmt_eur(p['last'],3)}</td>
      <td class="r {var_c}">{fmt_pct(p['var_pct'])}</td>
      <td class="r {pl_c}">{'+' if p['pl_eur']>=0 else ''}{fmt_eur(p['pl_eur'])}</td>
      <td class="r {pl_c}">{fmt_pct(p['pl_pct'])}</td>
      <td class="r">{fmt_eur(p['mkt_val'])}</td>
      <td class="r">{ema20_s}</td>
      <td class="r">{rsi_s}</td>
      <td class="r">{adx_s}</td>
      <td class="c">{bc_s}</td>
      <td class="stop-val">{stop_s}</td>
      <td class="trail-val">{trail_s}</td>
    </tr>
    <tr class="nrow"><td colspan="16" class="note">{s.get('note','')}</td></tr>"""

    # ── Ranking ────────────────────────────────────────────────────────────────
    def rank_key(p):
        s  = signals.get(p['isin'], {})
        lv = {'L1': 4, 'L2': 3, 'L0': 2, 'L3': 1, '?': 0}.get(s.get('level', '?'), 0)
        sg = {'buy': 3, 'hold': 2, 'watch_plus': 2, 'watch': 1,
              'recovery': 1, 'weak': 0, 'unknown': -1}.get(s.get('signal_cls', ''), 0)
        return (lv * 10 + sg, p['pl_pct'])

    ranked   = sorted(etfs, key=rank_key, reverse=True)
    emojis   = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣']
    rank_html = ''
    for i, p in enumerate(ranked):
        s   = signals.get(p['isin'], {})
        sc  = s.get('signal_cls', 'unknown')
        em  = emojis[i] if i < len(emojis) else f'{i+1}.'
        plc = pclass(p['pl_pct'])
        stop_disp = f"Stop: {fmt_eur(s.get('stop_loss'),3)}" if s.get('stop_loss') else ''
        short = p['titolo'][:38] + ('…' if len(p['titolo']) > 38 else '')
        rank_html += f"""
  <div class="rank-item s-{sc}">
    <span class="rank-emoji">{em}</span>
    <span class="rank-name">{short}</span>
    <span class="rank-lv">{s.get('level','?')}</span>
    <span class="rank-sig">{s.get('signal_txt','?')}</span>
    <span class="rank-stop">{stop_disp}</span>
    <span class="rank-pl {plc}">{fmt_pct(p['pl_pct'])}</span>
  </div>"""

    # ── BTP table ──────────────────────────────────────────────────────────────
    btp_rows = ''
    for p in btps:
        pl_c = pclass(p['pl_eur'])
        nom  = f"{int(p['qty']/1000)}K" if p['qty'] >= 1000 else str(int(p['qty']))
        scad = p['scadenza'] or '—'
        btp_rows += f"""
    <tr>
      <td>{p['titolo'][:50]}</td>
      <td class="c">{nom}</td>
      <td class="r">{p['pmc']:.3f}</td>
      <td class="r">{p['last']:.3f}</td>
      <td class="r {pl_c}">{'+' if p['pl_eur']>=0 else ''}€{p['pl_eur']:,.2f}</td>
      <td class="r {pl_c}">{fmt_pct(p['pl_pct'])}</td>
      <td class="r">€{p['mkt_val']:,.2f}</td>
      <td class="c">{scad}</td>
    </tr>"""

    # ── Assemble HTML ──────────────────────────────────────────────────────────
    now_str = datetime.now().strftime('%d/%m/%Y %H:%M')
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Portafoglio — {report_date}</title>
<style>{CSS}</style>
</head>
<body>

<h1>📈 Portafoglio ETF &amp; BTP — Analisi Operativa</h1>
<div class="subtitle">
  {report_date} &nbsp;|&nbsp;
  Dati tecnici: <a href="{ETF_API_BASE}" target="_blank">etf.andreapavan.tech</a> &nbsp;|&nbsp;
  Generato: {now_str}
</div>

{cards_html}

<h2>📊 ETF — Segnali Operativi</h2>
<div class="tbl-wrap">
<table>
  <thead>
    <tr>
      <th class="l">ETF</th>
      <th class="c">Livello</th>
      <th class="c">Segnale</th>
      <th>Qtà</th>
      <th>PMC</th>
      <th>Prezzo</th>
      <th>Var.%</th>
      <th>P&amp;L €</th>
      <th>P&amp;L %</th>
      <th>Valore</th>
      <th>EMA20</th>
      <th>RSI</th>
      <th>ADX</th>
      <th class="c">Cond.</th>
      <th>Stop Loss</th>
      <th>Trailing</th>
    </tr>
  </thead>
  <tbody>{etf_rows}
  </tbody>
</table>
</div>

<h2>🏆 Ranking ETF</h2>
<div class="rank-box">{rank_html}
</div>

<h2>🏛️ BTP — Riepilogo</h2>
<div class="tbl-wrap">
<table>
  <thead>
    <tr>
      <th class="l">Titolo</th>
      <th class="c">Nominale</th>
      <th>PMC</th>
      <th>Quotazione</th>
      <th>P&amp;L €</th>
      <th>P&amp;L %</th>
      <th>Valore</th>
      <th class="c">Scadenza</th>
    </tr>
  </thead>
  <tbody>{btp_rows}
  </tbody>
</table>
</div>

<div class="legend">
  <strong>Legenda:</strong>
  <span class="leg"><span class="dot" style="background:#fc8181"></span>Stop Loss = EMA20 × 98.5% — livello di uscita tecnica (prezzo sotto EMA20 per ≥3 gg)</span>
  <span class="leg"><span class="dot" style="background:#f6ad55"></span>Trailing = EMA20 — livello da non violare per proteggere il guadagno</span>
  <span class="leg">Cond. = condizioni L1 soddisfatte su 6</span>
</div>

<div class="footer">
  Sorgente: estratto banca + API <a href="{ETF_API_BASE}">{ETF_API_BASE}</a> &nbsp;|&nbsp;
  I segnali sono informativi, non consulenza finanziaria.
</div>

</body>
</html>"""


# ── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  ANALISI PORTAFOGLIO ETF & BTP")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 55)

    xls_path  = find_latest_xls()
    positions = parse_portfolio(xls_path)

    etfs = [p for p in positions if p['is_etf']]
    btps = [p for p in positions if p['is_btp']]
    print(f"Posizioni: {len(etfs)} ETF + {len(btps)} BTP")

    print("\nFetch dati tecnici ETF...")
    signals = {}
    for p in etfs:
        short = p['titolo'][:32]
        print(f"  {p['isin']} — {short}...")
        api_data = fetch_etf_data(p['isin'])
        signals[p['isin']] = build_signal(p, api_data)
        s = signals[p['isin']]
        sig_txt = s['signal_txt'].encode('ascii', 'replace').decode('ascii')
        print(f"    {s['level']} | {sig_txt} | Stop: {s['stop_loss']}")

    report_date = datetime.now().strftime('%d/%m/%Y')
    html = generate_report(positions, signals, report_date)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    out   = REPORTS_DIR / fname

    out.write_text(html, encoding='utf-8')
    print(f"\nReport salvato: {out}")

    webbrowser.open(out.as_uri())
    print("Aperto nel browser.")
    print("=" * 55)


if __name__ == '__main__':
    main()
