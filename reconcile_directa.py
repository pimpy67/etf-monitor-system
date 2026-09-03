"""
reconcile_directa.py — Riconciliazione portafoglio ETF: estratto Directa vs monitor
==================================================================================

Confronta l'export Directa "P_TOTALE_*.xlsx" (le quote realmente possedute) con le
posizioni attive in `etf_portfolio_entries` (quelle registrate nel monitor).

La verità è **Directa**: il monitor sa solo cosa gli è stato detto e può divergere
se si dimentica di registrare un acquisto/una vendita. Questo modulo non modifica
nulla — produce solo un report di differenze.

Uso da CLI:
    python reconcile_directa.py /percorso/P_TOTALE-directa.xlsx
"""

from __future__ import annotations

import io
import re
import sys
from typing import Any

import openpyxl


# Intestazioni della tabella posizioni nell'export Directa (riga ~8).
_DIRECTA_HEADERS = ("Strumento", "Ticker", "Isin", "Quantita",
                    "Valore di carico", "Valore attuale", "Prezzo", "Prezzo medio", "Divisa")

# Tolleranza sul confronto quote (ETF a quote intere, ma frazioni possibili da PAC).
_QTY_EPS = 0.01


def _to_float(v: Any) -> float:
    """Converte un valore di cella Directa in float. Gestisce numeri già float,
    stringhe con virgola decimale, simbolo € e separatori di migliaia."""
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("€", "").replace(" ", "")
    if "," in s and "." in s:            # 1.234,56 -> 1234.56
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:                        # 1234,56 -> 1234.56
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_directa_export(source) -> dict:
    """Legge un P_TOTALE Directa (path, bytes o file-like) e restituisce:
        {
          "meta": {"conto": str, "data_estrazione": str, "valore_portafoglio": str},
          "positions": [
             {"isin","ticker","name","quantita","prezzo_medio",
              "valore_carico","valore_attuale","prezzo","divisa"}, ...
          ],
          "warnings": [str, ...]
        }
    """
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
    ws = wb.active

    rows = [[c.value for c in r] for r in ws.iter_rows()]
    wb.close()

    meta: dict[str, str] = {}
    warnings: list[str] = []

    # Metadata: righe "Chiave : Valore" prima della tabella.
    for r in rows[:8]:
        joined = " ".join(str(c) for c in r if c is not None)
        m = re.match(r"\s*(Conto|Data estrazione|Valore portafoglio)\s*:\s*(.+)", joined)
        if m:
            key = {"Conto": "conto", "Data estrazione": "data_estrazione",
                   "Valore portafoglio": "valore_portafoglio"}[m.group(1)]
            meta[key] = m.group(2).strip()

    # Trova la riga di intestazione della tabella posizioni.
    header_idx = -1
    for i, r in enumerate(rows):
        cells = [str(c).strip() if c is not None else "" for c in r]
        if "Strumento" in cells and "Isin" in cells:
            header_idx = i
            break
    if header_idx == -1:
        raise ValueError("Formato non riconosciuto: nessuna riga con colonne "
                         "'Strumento' e 'Isin'. È davvero un export P_TOTALE Directa?")

    headers = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
    col = {h: idx for idx, h in enumerate(headers)}

    def cell(r, name):
        idx = col.get(name)
        return r[idx] if idx is not None and idx < len(r) else None

    positions = []
    for r in rows[header_idx + 1:]:
        strumento = cell(r, "Strumento")
        isin = cell(r, "Isin")
        if not strumento or not isin:        # riga vuota o riga "Totale"
            continue
        isin = str(isin).strip().upper()
        if len(isin) != 12:
            warnings.append(f"Riga '{strumento}': ISIN '{isin}' non valido, ignorata.")
            continue
        positions.append({
            "isin": isin,
            "ticker": str(cell(r, "Ticker") or "").strip(),
            "name": str(strumento).strip(),
            "quantita": _to_float(cell(r, "Quantita")),
            "prezzo_medio": _to_float(cell(r, "Prezzo medio")),
            "valore_carico": _to_float(cell(r, "Valore di carico")),
            "valore_attuale": _to_float(cell(r, "Valore attuale")),
            "prezzo": _to_float(cell(r, "Prezzo")),
            "divisa": str(cell(r, "Divisa") or "").strip(),
        })

    if not positions:
        warnings.append("Nessuna posizione trovata nella tabella.")

    return {"meta": meta, "positions": positions, "warnings": warnings}


def reconcile(directa_positions: list[dict],
              monitor_entries: list[dict],
              monitored_isins: set[str] | None = None) -> dict:
    """Confronta le posizioni Directa con le entry attive del monitor.

    monitor_entries: righe di `database.get_portfolio_entries()` (già status='active').
                     Più righe con lo stesso ISIN vengono sommate (add-to-position).
    monitored_isins: opzionale, ISIN presenti nell'universo monitorato (etf_monitoraggio.xlsx)
                     — serve solo a segnalare "posseduto ma non monitorato".
    """
    # Aggrega il lato monitor per ISIN.
    mon: dict[str, dict] = {}
    for e in monitor_entries:
        isin = str(e.get("isin") or "").strip().upper()
        if not isin:
            continue
        agg = mon.setdefault(isin, {
            "isin": isin, "name": e.get("fund_name") or "",
            "shares": 0.0, "cost": 0.0, "layers": set(), "brokers": set(), "n_lots": 0,
        })
        sh = float(e.get("shares") or 0)
        px = float(e.get("entry_price") or 0)
        agg["shares"] += sh
        agg["cost"] += sh * px
        if e.get("portfolio_type"):
            agg["layers"].add(e["portfolio_type"])
        if e.get("broker"):
            agg["brokers"].add(e["broker"])
        agg["n_lots"] += 1

    dir_by_isin = {p["isin"]: p for p in directa_positions}

    matched, only_directa, only_monitor = [], [], []

    for isin, d in dir_by_isin.items():
        m = mon.get(isin)
        if not m:
            only_directa.append({
                **d,
                "monitored": (monitored_isins is None) or (isin in monitored_isins),
            })
            continue
        m_shares = round(m["shares"], 4)
        m_avg = (m["cost"] / m["shares"]) if m["shares"] else 0.0
        qty_ok = abs(d["quantita"] - m_shares) < _QTY_EPS
        matched.append({
            "isin": isin,
            "name": d["name"] or m["name"],
            "layers": sorted(m["layers"]),
            "brokers": sorted(m["brokers"]),
            "n_lots": m["n_lots"],
            "directa_qty": d["quantita"],
            "monitor_qty": m_shares,
            "qty_ok": qty_ok,
            "qty_delta": round(d["quantita"] - m_shares, 4),
            "directa_avg_cost": round(d["prezzo_medio"], 4),
            "monitor_avg_cost": round(m_avg, 4),
            "cost_delta_pct": (round((m_avg - d["prezzo_medio"]) / d["prezzo_medio"] * 100, 2)
                               if d["prezzo_medio"] and m_avg else None),
            "valore_attuale": d["valore_attuale"],
        })

    for isin, m in mon.items():
        if isin not in dir_by_isin:
            only_monitor.append({
                "isin": isin,
                "name": m["name"],
                "layers": sorted(m["layers"]),
                "brokers": sorted(m["brokers"]),
                "monitor_qty": round(m["shares"], 4),
                "monitor_avg_cost": round((m["cost"] / m["shares"]) if m["shares"] else 0.0, 4),
            })

    matched.sort(key=lambda x: (x["qty_ok"], x["name"].lower()))
    only_directa.sort(key=lambda x: x["name"].lower())
    only_monitor.sort(key=lambda x: x["name"].lower())

    n_mismatch = sum(1 for x in matched if not x["qty_ok"])
    return {
        "matched": matched,
        "only_directa": only_directa,
        "only_monitor": only_monitor,
        "summary": {
            "directa_total": len(dir_by_isin),
            "monitor_total": len(mon),
            "ok": len(matched) - n_mismatch,
            "qty_mismatch": n_mismatch,
            "only_directa": len(only_directa),
            "only_monitor": len(only_monitor),
            "aligned": n_mismatch == 0 and not only_directa and not only_monitor,
        },
    }


def _cli(path: str) -> int:
    from database import PriceDatabase
    parsed = parse_directa_export(path)
    db = PriceDatabase()
    result = reconcile(parsed["positions"], db.get_portfolio_entries())
    s = result["summary"]

    print(f"\nEstratto Directa: {parsed['meta'].get('conto', '?')} — "
          f"{parsed['meta'].get('data_estrazione', '?')}")
    for w in parsed["warnings"]:
        print(f"  ⚠️  {w}")
    print(f"\nDirecta: {s['directa_total']} ETF · Monitor: {s['monitor_total']} attivi\n")

    if s["aligned"]:
        print("✅ TUTTO ALLINEATO — Directa e monitor coincidono.\n")
        return 0

    if result["matched"]:
        print("── Posizioni in entrambi ─────────────────────────────")
        for x in result["matched"]:
            flag = "  " if x["qty_ok"] else "❌"
            print(f"{flag} {x['name'][:44]:44} {'/'.join(x['layers']) or '—':4} "
                  f"Directa {x['directa_qty']:>9.2f}  Monitor {x['monitor_qty']:>9.2f}"
                  + ("" if x["qty_ok"] else f"   Δ {x['qty_delta']:+.2f}"))
    if result["only_directa"]:
        print("\n── Su Directa, NON registrate nel monitor (acquisto non registrato?) ──")
        for x in result["only_directa"]:
            tag = "" if x["monitored"] else "  [non nell'universo monitorato]"
            print(f"   {x['name'][:50]:50} {x['isin']}  qty {x['quantita']:.2f}{tag}")
    if result["only_monitor"]:
        print("\n── Attive nel monitor, NON su Directa (vendita non registrata?) ──")
        for x in result["only_monitor"]:
            print(f"   {x['name'][:50]:50} {x['isin']}  {'/'.join(x['layers']) or '—'}  "
                  f"qty {x['monitor_qty']:.2f}")
    print()
    return 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python reconcile_directa.py /percorso/P_TOTALE-directa.xlsx")
        sys.exit(2)
    sys.exit(_cli(sys.argv[1]))
