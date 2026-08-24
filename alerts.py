"""
alerts.py - Notifiche email ETF Monitor
=========================================
3 email, inviate solo quando c'è qualcosa da dire:
  1. send_new_entries      → nuovi ingressi L1 (+ nuovi L0)
  2. send_l1_exit          → uscita da L1 con regola e risultato %
  3. send_portfolio_signals → segnali operativi (Piede Dentro, Attenzione)
  4. send_health_report    → solo se ci sono errori tecnici
"""
from datetime import datetime
import os

try:
    import resend as _resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False

REGOLE = {
    'A': ('A — Stop Loss',       '#6c757d', 'Prezzo sotto EMA20 per ≥3 giorni consecutivi'),
    'B': ('B — Trailing Stop',   '#fd7e14', 'EMA10 ha incrociato EMA20 al ribasso'),
    'C': ('C — Stanchezza RSI',  '#dc3545', 'RSI era ≥70, ora sceso sotto 70'),
    'D': ('D — Piede Dentro',    '#E65100', 'RSI > 78 — Uscita parziale 90%'),
    'E': ('E — ADX Debole',      '#6c757d', 'ADX < 18 con prezzo sotto EMA20'),
    'F': ('F — Kill Switch',     '#b71c1c', 'Calo giornaliero ≤ −3%'),
}

_BODY_STYLE = 'font-family:Arial,sans-serif;max-width:680px;margin:0 auto;background:#f0f2f5;'
_FOOTER = '<div style="padding:12px;background:#333;color:#999;text-align:center;font-size:12px">ETF Monitor · {ts}</div>'


class AlertSystem:

    def __init__(self, sender_email=None, sender_password=None, recipient_email=None):
        self.sender_email    = sender_email    or os.getenv('EMAIL_SENDER', 'onboarding@resend.dev')
        self.recipient_email = recipient_email or os.getenv('EMAIL_RECIPIENT', 'andreapavan67@gmail.com')
        self.resend_api_key  = os.getenv('RESEND_API_KEY', '')
        if RESEND_AVAILABLE and self.resend_api_key:
            _resend.api_key = self.resend_api_key

    def _send_email(self, subject: str, body_html: str) -> bool:
        if not RESEND_AVAILABLE:
            print(f'⚠️  Resend non disponibile — {subject}'); return False
        if not self.resend_api_key:
            print(f'⚠️  RESEND_API_KEY mancante — {subject}'); return False
        try:
            _resend.Emails.send({
                'from': f'ETF Monitor <{self.sender_email}>',
                'to':   [self.recipient_email],
                'subject': subject,
                'html': body_html,
            })
            print(f'✅ Email inviata: {subject}')
            return True
        except Exception as e:
            print(f'❌ Errore email: {e}'); return False

    # ── 1. Nuovi ingressi ─────────────────────────────────────────────────
    def send_new_entries(self, new_l1: list, new_l0: list = None) -> bool:
        """Una email con tutti i nuovi ingressi in L1 (e opzionalmente L0)."""
        today = datetime.now().strftime('%d/%m/%Y')
        n1, n0 = len(new_l1), len(new_l0 or [])
        parts = []
        if n1: parts.append(f'{n1} nuovo{"i" if n1 > 1 else ""} in L1')
        if n0: parts.append(f'{n0} in L0')
        subject = f'🟢 {" · ".join(parts)} — {today}'

        # ── Sezione L1 ────────────────────────────────────────────────────
        l1_rows = ''
        for i, f in enumerate(new_l1):
            rsi   = f.get('rsi')
            adx   = f.get('adx')
            bc    = f.get('buy_count', 6)
            price = f.get('price')
            sma200 = f.get('sma200')
            regime = '🟢 Rialzista' if (price and sma200 and price > sma200) else ('🔴 Ribassista' if sma200 else '—')
            bg    = '#f9f9f9' if i % 2 else 'white'
            _link = f'https://etf.andreapavan.tech/?isin={f.get("isin","")}&ticker={f.get("ticker","")}'
            l1_rows += (
                f'<tr style="background:{bg}">'
                f'<td style="padding:8px;border:1px solid #ddd">'
                f'<a href="{_link}" style="color:#00B050;text-decoration:none"><strong>{f["nome"][:45]}</strong></a><br>'
                f'<small style="color:#888">{f.get("ticker","")} · {f.get("isin","")}</small></td>'
                f'<td style="padding:8px;border:1px solid #ddd;font-size:11px;color:#666">{f.get("categoria","")[:28]}</td>'
                f'<td style="padding:8px;border:1px solid #ddd;text-align:right;font-weight:bold">'
                f'{"€{:.4f}".format(price) if price else "—"}</td>'
                f'<td style="padding:8px;border:1px solid #ddd;text-align:center">'
                f'{"{:.0f}".format(rsi) if rsi else "—"}</td>'
                f'<td style="padding:8px;border:1px solid #ddd;text-align:center">'
                f'{"{:.0f}".format(adx) if adx else "—"}</td>'
                f'<td style="padding:8px;border:1px solid #ddd;text-align:center;font-size:11px">{regime}</td>'
                f'<td style="padding:8px;border:1px solid #ddd;text-align:center;font-weight:bold;color:#00B050">'
                f'{bc}/6</td></tr>'
            )

        l1_section = (
            f'<h2 style="color:#00B050;margin:0 0 12px">🟢 Nuovi in L1 — {n1} ETF</h2>'
            f'<table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:24px">'
            f'<thead><tr style="background:#00B050;color:white">'
            f'<th style="padding:8px;border:1px solid #ddd;text-align:left">ETF</th>'
            f'<th style="padding:8px;border:1px solid #ddd">Categoria</th>'
            f'<th style="padding:8px;border:1px solid #ddd">Prezzo</th>'
            f'<th style="padding:8px;border:1px solid #ddd">RSI</th>'
            f'<th style="padding:8px;border:1px solid #ddd">ADX</th>'
            f'<th style="padding:8px;border:1px solid #ddd">Regime</th>'
            f'<th style="padding:8px;border:1px solid #ddd">Cond.</th>'
            f'</tr></thead><tbody>{l1_rows}</tbody></table>'
        ) if n1 else ''

        # ── Sezione L0 ────────────────────────────────────────────────────
        l0_section = ''
        if new_l0:
            l0_rows = ''
            for i, f in enumerate(new_l0):
                bg    = '#f9f9f9' if i % 2 else 'white'
                dist  = f.get('distance_from_peak')
                rsi   = f.get('rsi')
                price = f.get('price')
                pl    = f.get('panic_low')
                _link = f'https://etf.andreapavan.tech/?isin={f.get("isin","")}&ticker={f.get("ticker","")}'
                l0_rows += (
                    f'<tr style="background:{bg}">'
                    f'<td style="padding:8px;border:1px solid #ddd">'
                    f'<a href="{_link}" style="color:#E65100;text-decoration:none"><strong>{f["nome"][:45]}</strong></a><br>'
                    f'<small style="color:#888">{f.get("ticker","")} · {f.get("isin","")}</small></td>'
                    f'<td style="padding:8px;border:1px solid #ddd;text-align:right">'
                    f'{"€{:.4f}".format(price) if price else "—"}</td>'
                    f'<td style="padding:8px;border:1px solid #ddd;text-align:center;color:#DC3545;font-weight:bold">'
                    f'{"{:.1f}%".format(dist) if dist is not None else "—"}</td>'
                    f'<td style="padding:8px;border:1px solid #ddd;text-align:right;color:#DC3545">'
                    f'{"€{:.4f}".format(pl) if pl else "—"}</td>'
                    f'<td style="padding:8px;border:1px solid #ddd;text-align:center">'
                    f'{"{:.0f}".format(rsi) if rsi else "—"}</td>'
                    f'</tr>'
                )
            l0_section = (
                f'<h2 style="color:#E65100;margin:0 0 8px">🟠 Nuovi in L0 — Deep Recovery</h2>'
                f'<p style="color:#666;font-size:12px;margin:0 0 10px">ETF in forte calo con segnali di recupero. Stop loss = Panic Low.</p>'
                f'<table style="width:100%;border-collapse:collapse;font-size:13px">'
                f'<thead><tr style="background:#E65100;color:white">'
                f'<th style="padding:8px;border:1px solid #ddd;text-align:left">ETF</th>'
                f'<th style="padding:8px;border:1px solid #ddd">Prezzo</th>'
                f'<th style="padding:8px;border:1px solid #ddd">Dist. Picco</th>'
                f'<th style="padding:8px;border:1px solid #ddd">Panic Low</th>'
                f'<th style="padding:8px;border:1px solid #ddd">RSI</th>'
                f'</tr></thead><tbody>{l0_rows}</tbody></table>'
            )

        ts = datetime.now().strftime('%d/%m/%Y %H:%M')
        body_html = (
            f'<html><body style="{_BODY_STYLE}">'
            f'<div style="background:linear-gradient(135deg,#00B050,#007A36);color:white;padding:24px;text-align:center">'
            f'<h1 style="margin:0;font-size:20px">🟢 NUOVI INGRESSI ETF</h1>'
            f'<p style="margin:6px 0 0;opacity:.9;font-size:14px">{datetime.now().strftime("%A %d %B %Y")}</p>'
            f'</div>'
            f'<div style="padding:20px;background:white">{l1_section}{l0_section}</div>'
            f'{_FOOTER.format(ts=ts)}</body></html>'
        )
        return self._send_email(subject, body_html)

    _SHADOW_VARIANTS = {
        'L1': {
            'label': 'Candidate Model B',
            'params': 'mm200_distance_max=7.0%, adx-4, smart_6_macd, TP=15%',
            'color_main': '#8E44AD', 'color_dark': '#5B2C6F', 'tag': 'L1',
        },
        'L0': {
            'label': 'Candidate Model L0',
            'params': 'regime_min_days_below_sma200=5 (invece di 10), resto YAML nativo (SL, TP=16%)',
            'color_main': '#E67E22', 'color_dark': '#A04000', 'tag': 'L0',
        },
        'BREADTH': {
            'label': 'Candidate Breadth',
            'params': 'gate 6/7+MACD obbligatorio SOLO quando Market Breadth (EMA20>SMA50 su tutto l\'universo) >=80% (esce sotto 65%) — nessun altro override',
            'color_main': '#1ABC9C', 'color_dark': '#117A65', 'tag': 'Breadth',
        },
        'L0_ORO': {
            'label': 'Candidate L0 Oro',
            'params': 'L0 (mean-reversion) su oro_metalli_preziosi — whitelist bypassata solo per il test, nessun altro parametro cambiato (dd_threshold/rsi_max/TP nativi)',
            'color_main': '#D4AC0D', 'color_dark': '#7D6608', 'tag': 'L0-Oro',
        },
        'L0_METALLI': {
            'label': 'Candidate L0 Metalli Industriali',
            'params': 'L0 (mean-reversion) su metalli_industriali — whitelist bypassata solo per il test, nessun altro parametro cambiato (dd_threshold/rsi_max/TP nativi)',
            'color_main': '#935116', 'color_dark': '#5B2E0C', 'tag': 'L0-Metalli',
        },
        'BOND_TREND': {
            'label': 'Candidate Bond Trend',
            'params': 'Terzo meccanismo (no RSI/ADX/MACD) per bond_governativi/bond_corp_hy_em/settoriali_difensivi/real_estate_reit/private_equity_buffer — persistenza 20gg, dist_max 0.5%, TP dinamico target 3%',
            'color_main': '#2E86C1', 'color_dark': '#1B4F72', 'tag': 'Bond-Trend',
        },
    }

    def send_shadow_entries(self, new_entries: list, variant: str = 'L1') -> bool:
        """Email inviata SOLO quando uno Shadow Monitor apre una nuova posizione
        ipotetica — CANDIDATE_MODEL_B_20260807 (variant='L1', cluster core),
        CANDIDATE_MODEL_L0_20260808 (variant='L0', equity_sviluppati), o il candidato
        Market Breadth (variant='BREADTH', 2026-08-20, cluster core, solo i trade extra
        oltre a native_7 — vedi shadow_monitor_breadth.py). new_entries: lista di dict
        {ticker, isin, nome, famiglia, price}. Nessun impatto sulle decisioni reali —
        puramente informativa, per seguire i candidati durante il lockdown fino al
        06/09/2026. Vedi CLAUDE.md e memory/etf_post_lockdown_todo_20260906.md.

        Collegata il 2026-08-19 su richiesta esplicita — prima le funzioni
        run_shadow_monitor()/run_shadow_monitor_l0() la lasciavano inutilizzata
        (decisione "nessuna email" del 2026-08-07/08, superata)."""
        if not new_entries:
            return True

        v = self._SHADOW_VARIANTS.get(variant, self._SHADOW_VARIANTS['L1'])
        model_label = v['label']
        params_desc = v['params']
        color_main = v['color_main']
        color_dark = v['color_dark']

        today = datetime.now().strftime('%d/%m/%Y')
        n = len(new_entries)
        subject = f'🟣 Shadow Monitor {v["tag"]}: {n} nuovo{"i" if n > 1 else ""} ingresso {model_label} — {today}'

        rows = ''
        for i, f in enumerate(new_entries):
            bg = '#f9f9f9' if i % 2 else 'white'
            _link = f'https://etf.andreapavan.tech/?isin={f.get("isin","")}&ticker={f.get("ticker","")}'
            rows += (
                f'<tr style="background:{bg}">'
                f'<td style="padding:8px;border:1px solid #ddd">'
                f'<a href="{_link}" style="color:{color_main};text-decoration:none"><strong>{f.get("nome","")[:45]}</strong></a><br>'
                f'<small style="color:#888">{f.get("ticker","")} · {f.get("isin","")}</small></td>'
                f'<td style="padding:8px;border:1px solid #ddd;font-size:11px;color:#666">{f.get("famiglia","")}</td>'
                f'<td style="padding:8px;border:1px solid #ddd;text-align:right;font-weight:bold">'
                f'{"€{:.4f}".format(f["price"]) if f.get("price") else "—"}</td>'
                f'</tr>'
            )

        ts = datetime.now().strftime('%d/%m/%Y %H:%M')
        body_html = (
            f'<html><body style="{_BODY_STYLE}">'
            f'<div style="background:linear-gradient(135deg,{color_main},{color_dark});color:white;padding:24px;text-align:center">'
            f'<h1 style="margin:0;font-size:20px">🟣 SHADOW MONITOR — {model_label}</h1>'
            f'<p style="margin:6px 0 0;opacity:.9;font-size:14px">{datetime.now().strftime("%A %d %B %Y")}</p>'
            f'</div>'
            f'<div style="padding:20px;background:white">'
            f'<p style="color:#666;font-size:12px;margin:0 0 12px">'
            f'Ingresso IPOTETICO ({params_desc}) — '
            f'non è un acquisto reale, nessuna azione richiesta. Sistema live in lockdown '
            f'parametri fino al 06/09/2026, decide sempre e solo con i parametri nativi.</p>'
            f'<p style="color:#888;font-size:11px;margin:0 0 12px;padding:8px 10px;'
            f'background:#f5f5f5;border-left:3px solid {color_main}">'
            f'⚠️ Cliccando l\'ETF sotto si apre la scheda con le regole <strong>native</strong> '
            f'(7/7 condizioni, soglie di famiglia standard) — è normale che mostri un punteggio '
            f'diverso da quello che ha fatto scattare questo ingresso ombra, perché questo modello '
            f'usa parametri sperimentali più permissivi ({params_desc}), non quelli in produzione.</p>'
            f'<table style="width:100%;border-collapse:collapse;font-size:13px">'
            f'<thead><tr style="background:{color_main};color:white">'
            f'<th style="padding:8px;border:1px solid #ddd;text-align:left">ETF</th>'
            f'<th style="padding:8px;border:1px solid #ddd">Famiglia</th>'
            f'<th style="padding:8px;border:1px solid #ddd">Prezzo ingresso</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>'
            f'</div>'
            f'{_FOOTER.format(ts=ts)}</body></html>'
        )
        return self._send_email(subject, body_html)

    def send_tp_proximity_alert(self, events: list) -> bool:
        """
        Email dedicata, inviata SUBITO quando una posizione reale (L0 o L1)
        entra o avanza nella fascia di stringimento tattico dello Stop verso
        il TP (order_pricing.py, <3%/<1.5% dal target) — 2026-08-20, su
        richiesta esplicita per non aspettare il resoconto serale
        (send_portfolio_report, che mostra comunque 🔶 ma solo a fine giornata).

        Gira anche sul run silenzioso del mattino (a differenza degli altri
        alert), perché è proprio lì che sta il guadagno: arrivare prima del
        giro schedulato successivo, non prima in senso assoluto — il monitor
        gira su prezzi 1-2 volte al giorno, non intraday.

        events: lista di dict da monitor.py::_update_portfolio_l0_suggerito /
        _update_portfolio_l1_suggerito — {isin, ticker, fund_name, variant,
        current_price, prezzo_stop, prezzo_limite_stop, tp_suggerito, broker}.
        """
        if not events:
            return True

        today = datetime.now().strftime('%d/%m/%Y')
        n = len(events)
        subject = f'🔶 Avvicinamento TP: {n} posizion{"i" if n > 1 else "e"} da aggiornare — {today}'

        rows = ''
        for i, ev in enumerate(events):
            bg = '#f9f9f9' if i % 2 else 'white'
            current = ev.get('current_price')
            tp = ev.get('tp_suggerito')
            dist_pct = ((tp - current) / current * 100) if (tp and current) else None
            dist_str = f'{dist_pct:.2f}%' if dist_pct is not None else '—'
            variant = ev.get('variant', '')
            variant_color = '#E65100' if variant == 'L0' else '#00B050'
            stop_str = f'€{ev["prezzo_stop"]:.2f}' if ev.get('prezzo_stop') else '—'
            lim_str = f'€{ev["prezzo_limite_stop"]:.2f}' if ev.get('prezzo_limite_stop') else '—'
            tp_str = f'€{tp:.2f}' if tp else '—'

            _link = f'https://etf.andreapavan.tech/?isin={ev.get("isin","")}&ticker={ev.get("ticker","")}'
            rows += (
                f'<tr style="background:{bg}">'
                f'<td style="padding:8px;border:1px solid #ddd">'
                f'<a href="{_link}" style="color:{variant_color};text-decoration:none"><strong>{(ev.get("fund_name") or "")[:40]}</strong></a><br>'
                f'<small style="color:#888">{ev.get("ticker","")} · {ev.get("isin","")} · {ev.get("broker") or "Directa"}</small></td>'
                f'<td style="padding:8px;border:1px solid #ddd;text-align:center;color:{variant_color}"><strong>{variant}</strong></td>'
                f'<td style="padding:8px;border:1px solid #ddd;text-align:right">€{current:.2f}</td>'
                f'<td style="padding:8px;border:1px solid #ddd;text-align:right;font-size:12px">{stop_str}</td>'
                f'<td style="padding:8px;border:1px solid #ddd;text-align:right;font-size:12px">{lim_str}</td>'
                f'<td style="padding:8px;border:1px solid #ddd;text-align:right;font-size:12px">{tp_str}</td>'
                f'<td style="padding:8px;border:1px solid #ddd;text-align:right;color:#FFC107"><strong>{dist_str}</strong></td>'
                f'</tr>'
            )

        ts = datetime.now().strftime('%d/%m/%Y %H:%M')
        body_html = (
            f'<html><body style="{_BODY_STYLE}">'
            f'<div style="background:linear-gradient(135deg,#FFC107,#E65100);color:#222;padding:24px;text-align:center">'
            f'<h1 style="margin:0;font-size:20px">🔶 AVVICINAMENTO TP — AGGIORNA LO STOP</h1>'
            f'<p style="margin:6px 0 0;opacity:.85;font-size:14px">{datetime.now().strftime("%A %d %B %Y")}</p>'
            f'</div>'
            f'<div style="padding:20px;background:white">'
            f'<p style="color:#666;font-size:12px;margin:0 0 12px">'
            f'Queste posizioni sono entrate (o avanzate) nella fascia di stringimento verso il TP — '
            f'cancella lo Stop attuale su Directa e piazzane uno nuovo ai valori sotto. Su un conto cash Directa '
            f'non puoi tenere Stop e Limite TP attivi insieme: se preferisci provare a catturare il target pieno, '
            f'cancella lo Stop e piazza un Limite di vendita al prezzo Target TP invece.</p>'
            f'<table style="width:100%;border-collapse:collapse;font-size:12px">'
            f'<thead><tr style="background:#FFC107;color:#222">'
            f'<th style="padding:8px;border:1px solid #ddd;text-align:left">ETF</th>'
            f'<th style="padding:8px;border:1px solid #ddd">L0/L1</th>'
            f'<th style="padding:8px;border:1px solid #ddd;text-align:right">Prezzo</th>'
            f'<th style="padding:8px;border:1px solid #ddd;text-align:right">Nuovo Trigger</th>'
            f'<th style="padding:8px;border:1px solid #ddd;text-align:right">Nuovo Limite</th>'
            f'<th style="padding:8px;border:1px solid #ddd;text-align:right">Target TP</th>'
            f'<th style="padding:8px;border:1px solid #ddd;text-align:right">Dist. da TP</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>'
            f'<p style="margin:12px 0 0;font-size:11px;color:#666">'
            f'<strong>Nuovo Trigger</strong> = Prezzo Stop (Trigger) su Directa · <strong>Nuovo Limite</strong> = Prezzo Limite (esecuzione, 1% sotto il trigger) · '
            f'<strong>Target TP</strong> = ordine Limite separato di riferimento, non piazzabile in parallelo allo Stop su Directa.</p>'
            f'</div>'
            f'{_FOOTER.format(ts=ts)}</body></html>'
        )
        return self._send_email(subject, body_html)

    # ── 2. Uscita L1 ──────────────────────────────────────────────────────
    def send_l1_exit(self, etf_info: dict) -> bool:
        """Email per uscita da L1: regola triggherata + risultato %."""
        pct   = etf_info.get('pct_gain')
        pct_s = f'{pct:+.2f}%' if pct is not None else '—'
        pct_c = '#00B050' if (pct or 0) >= 0 else '#DC3545'
        label = 'GUADAGNO' if (pct or 0) >= 0 else 'PERDITA'
        today = datetime.now().strftime('%d/%m/%Y')
        nome  = etf_info.get('nome', etf_info.get('ticker', '?'))

        entry_d = etf_info.get('entry_date')
        if hasattr(entry_d, 'strftime'): entry_d = entry_d.strftime('%d/%m/%Y')
        elif entry_d: entry_d = str(entry_d)[:10]
        else: entry_d = '—'

        an = etf_info.get('analysis', {})
        cond = an.get('conditions', an.get('buy_conditions', {}))
        exit_rule_key = cond.get('exit_rule') or etf_info.get('exit_rule')
        # exit_rule può essere intero (1-6) o lettera (A-F)
        if isinstance(exit_rule_key, int):
            key_map = {1:'A', 2:'B', 3:'C', 4:'D', 5:'E', 6:'F'}
            exit_rule_key = key_map.get(exit_rule_key, str(exit_rule_key))

        # Gestisci "Stop Loss" come exit rule speciale
        if exit_rule_key == 'Stop Loss':
            rule_name = 'STOP LOSS TRIGGERATO'
            rule_color = '#b71c1c'
            rule_desc = 'Prezzo sceso sotto Stop Loss'
        else:
            rule_name, rule_color, rule_desc = REGOLE.get(
                exit_rule_key, ('Uscita L1', '#555', 'Condizioni non più soddisfatte'))

        ep    = etf_info.get('entry_price')
        xp    = etf_info.get('exit_price')
        ema20 = an.get('ema20')
        ema10 = an.get('ema10')
        sma50 = an.get('sma50')
        rsi   = an.get('rsi')
        adx   = an.get('adx')
        price = an.get('current_price')

        def ind_row(lbl, val, ok):
            bg = '#d4edda' if ok else '#f8d7da'
            tc = '#155724' if ok else '#721c24'
            ic = '✅' if ok else '❌'
            return (f'<tr style="background:{bg}">'
                    f'<td style="padding:7px 10px;border:1px solid #ddd">{ic} {lbl}</td>'
                    f'<td style="padding:7px 10px;border:1px solid #ddd;color:{tc};font-weight:bold">{val}</td></tr>')

        ind_rows = ''
        if price and ema20:
            ind_rows += ind_row('Prezzo vs EMA20', f'Prezzo={price:.4f} · EMA20={ema20:.4f}', price > ema20)
        if ema10 and ema20:
            ind_rows += ind_row('Trailing Stop — EMA10 vs EMA20', f'EMA10={ema10:.4f} · EMA20={ema20:.4f}', ema10 >= ema20)
        if rsi:
            ind_rows += ind_row('RSI al momento dell\'uscita', f'RSI = {rsi:.1f}', 45 <= rsi <= 72)
        if adx:
            ind_rows += ind_row('ADX — forza del trend', f'ADX = {adx:.1f}', adx >= 18)

        subject = f'🔴 Uscita ETF L1 — {nome[:30]} — {rule_name[:10]} — {pct_s}'
        ts = datetime.now().strftime('%d/%m/%Y %H:%M')

        body_html = (
            f'<html><body style="{_BODY_STYLE}">'
            f'<div style="background:linear-gradient(135deg,#DC3545,#AA0000);color:white;padding:24px;text-align:center">'
            f'<h1 style="margin:0;font-size:20px">🔴 USCITA ETF DA L1</h1>'
            f'<p style="margin:6px 0 0;opacity:.9;font-size:14px">{today}</p></div>'
            f'<div style="padding:20px;background:white">'
            f'<h2 style="margin:0 0 4px">'
            f'<a href="https://etf.andreapavan.tech/?isin={etf_info.get("isin","")}&ticker={etf_info.get("ticker","")}" '
            f'style="color:#111;text-decoration:none">{nome}</a></h2>'
            f'<p style="color:#666;margin:0 0 18px;font-size:13px">'
            f'{etf_info.get("ticker","")} · {etf_info.get("isin","")} · {etf_info.get("categoria","")}</p>'
            f'<div style="background:{rule_color};color:white;padding:14px 18px;border-radius:8px;margin-bottom:18px">'
            f'<div style="font-size:16px;font-weight:bold;margin-bottom:4px">📋 {rule_name}</div>'
            f'<div style="font-size:13px;opacity:.9">{rule_desc}</div></div>'
            f'<table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:18px">'
            f'<tr style="background:#f5f5f5">'
            f'<td style="padding:10px;border:1px solid #ddd"><strong>Entrato il</strong></td>'
            f'<td style="padding:10px;border:1px solid #ddd">{entry_d} · {etf_info.get("days_in_l1","—")} giorni in L1</td></tr>'
            f'<tr><td style="padding:10px;border:1px solid #ddd"><strong>Prezzo entrata</strong></td>'
            f'<td style="padding:10px;border:1px solid #ddd">{"€{:.4f}".format(ep) if ep else "—"}</td></tr>'
            f'<tr style="background:#f5f5f5">'
            f'<td style="padding:10px;border:1px solid #ddd"><strong>Prezzo uscita</strong></td>'
            f'<td style="padding:10px;border:1px solid #ddd">{"€{:.4f}".format(xp) if xp else "—"}</td></tr>'
            + (f'<tr style="background:#fff3cd">'
               f'<td style="padding:10px;border:1px solid #ddd"><strong>Stop Loss Triggerato</strong></td>'
               f'<td style="padding:10px;border:1px solid #ddd;font-weight:bold;color:#b71c1c">€{cond.get("stop_loss", xp):.4f}</td></tr>'
               if exit_rule_key == 'Stop Loss' and 'analysis' not in cond else '')
            + (f'<tr style="background:{pct_c};color:white">'
               f'<td style="padding:12px;border:1px solid #ddd;font-weight:bold">{label}</td>'
               f'<td style="padding:12px;border:1px solid #ddd;font-size:20px;font-weight:bold">{pct_s}</td></tr>'
               f'</table>')
            + (f'<div style="font-size:12px;font-weight:bold;color:#555;margin-bottom:8px;text-transform:uppercase">'
               f'Indicatori al momento dell\'uscita</div>'
               f'<table style="width:100%;border-collapse:collapse;font-size:13px">{ind_rows}</table>'
               if ind_rows else '')
            + f'</div>{_FOOTER.format(ts=ts)}</body></html>'
        )
        return self._send_email(subject, body_html)

    # ── 3. Segnali portafoglio ─────────────────────────────────────────────
    def send_portfolio_signals(self, signals: list) -> bool:
        """Email con segnali operativi per ETF ancora in L1."""
        today = datetime.now().strftime('%d/%m/%Y')
        n = len(signals)
        subject = f'⚠️ {n} segnale{"i" if n > 1 else ""} portafoglio ETF — {today}'

        TYPE_CFG = {
            'piede_dentro': ('#E65100', '🦶', 'PIEDE DENTRO',
                             'RSI > 78: zona ipercomprata. Valuta vendita 90% e parcheggio su XEON (€STR).'),
            'stanchezza':   ('#fd7e14', '😮', 'STANCHEZZA RSI',
                             'RSI > 72: possibile inversione imminente. Tieni il dito sul grilletto.'),
            'attenzione':   ('#FFC000', '⚠️', 'CONDIZIONI IN DETERIORAMENTO',
                             'Meno di 5/6 condizioni L1 soddisfatte. Monitora attentamente.'),
        }

        cards = ''
        for s in signals:
            cfg = TYPE_CFG.get(s.get('signal_type', 'attenzione'), TYPE_CFG['attenzione'])
            bg, icon, title, desc = cfg
            text_c = 'white' if bg != '#FFC000' else '#333'

            pct = s.get('pct_gain')
            pct_s = f'{pct:+.2f}%' if pct is not None else '—'
            pct_c = '#00B050' if (pct or 0) >= 0 else '#DC3545'

            entry_d = s.get('entry_date')
            if hasattr(entry_d, 'strftime'): entry_d = entry_d.strftime('%d/%m/%Y')
            elif entry_d: entry_d = str(entry_d)[:10]
            else: entry_d = '—'

            rsi = s.get('rsi')
            adx = s.get('adx')
            det = s.get('signal_detail', '')

            cards += (
                f'<div style="border:1px solid #ddd;border-radius:8px;overflow:hidden;margin-bottom:16px">'
                f'<div style="background:{bg};color:{text_c};padding:12px 16px">'
                f'<div style="font-size:15px;font-weight:bold">{icon} {title}</div>'
                f'<div style="font-size:12px;opacity:.85;margin-top:3px">{desc}</div></div>'
                f'<div style="padding:14px 16px;background:white">'
                f'<div style="font-weight:bold;font-size:14px">'
                f'<a href="https://etf.andreapavan.tech/?isin={s.get("isin","")}&ticker={s.get("ticker","")}" '
                f'style="color:#111;text-decoration:none">{s.get("nome","")[:50]}</a></div>'
                f'<div style="font-size:12px;color:#888;margin:2px 0 10px">'
                f'{s.get("ticker","")} · {s.get("isin","")} · {s.get("categoria","")[:28]}</div>'
                f'<table style="width:100%;border-collapse:collapse;font-size:13px"><tr>'
                f'<td style="padding:5px 8px;border:1px solid #eee;color:#666">Entrato il</td>'
                f'<td style="padding:5px 8px;border:1px solid #eee">{entry_d} ({s.get("days_in_l1","?")} gg)</td>'
                f'<td style="padding:5px 8px;border:1px solid #eee;color:#666">Performance</td>'
                f'<td style="padding:5px 8px;border:1px solid #eee;font-weight:bold;color:{pct_c}">{pct_s}</td>'
                f'</tr><tr>'
                f'<td style="padding:5px 8px;border:1px solid #eee;color:#666">RSI</td>'
                f'<td style="padding:5px 8px;border:1px solid #eee;font-weight:bold">'
                f'{"{:.1f}".format(rsi) if rsi else "—"}</td>'
                f'<td style="padding:5px 8px;border:1px solid #eee;color:#666">ADX</td>'
                f'<td style="padding:5px 8px;border:1px solid #eee">'
                f'{"{:.1f}".format(adx) if adx else "—"}</td>'
                f'</tr></table>'
                + (f'<div style="margin-top:8px;padding:7px 10px;background:#fff3e0;'
                   f'border-left:3px solid {bg};font-size:12px;color:#555">{det}</div>'
                   if det else '')
                + f'</div></div>'
            )

        ts = datetime.now().strftime('%d/%m/%Y %H:%M')
        body_html = (
            f'<html><body style="{_BODY_STYLE}">'
            f'<div style="background:linear-gradient(135deg,#FF8F00,#E65100);color:white;padding:24px;text-align:center">'
            f'<h1 style="margin:0;font-size:20px">⚠️ SEGNALI PORTAFOGLIO ETF</h1>'
            f'<p style="margin:6px 0 0;opacity:.9;font-size:14px">'
            f'{datetime.now().strftime("%A %d %B %Y")} · {n} segnale{"i" if n > 1 else ""}</p></div>'
            f'<div style="padding:20px;background:#f8f9fa">{cards}</div>'
            f'{_FOOTER.format(ts=ts)}</body></html>'
        )
        return self._send_email(subject, body_html)

    # ── 4. Health report (solo se errori) ─────────────────────────────────
    def send_health_report(self, health: dict) -> bool:
        errors_count = health.get('etfs_error', health.get('funds_error', 0))
        no_price     = health.get('etfs_no_price', health.get('funds_no_price', 0))
        db_ok        = health.get('db_available', True)
        if errors_count == 0 and no_price == 0 and db_ok:
            print('✅ Health OK — email non necessaria'); return True

        errors = health.get('errors', [])
        today  = datetime.now().strftime('%d/%m/%Y %H:%M')
        subject = f'🔴 Errori monitor ETF — {today}'

        rows = ''.join(
            f'<tr><td style="padding:7px;border:1px solid #ddd;font-family:monospace">{e.get("ticker",e.get("isin","?"))}</td>'
            f'<td style="padding:7px;border:1px solid #ddd;color:#DC3545">{str(e.get("error",""))[:80]}</td></tr>'
            for e in errors
        )
        table = (
            f'<table style="width:100%;border-collapse:collapse;font-size:13px">'
            f'<tr style="background:#DC3545;color:white">'
            f'<th style="padding:7px;border:1px solid #ddd">Ticker</th>'
            f'<th style="padding:7px;border:1px solid #ddd">Errore</th></tr>'
            f'{rows}</table>'
        ) if errors else ''

        ts = datetime.now().strftime('%d/%m/%Y %H:%M')
        body_html = (
            f'<html><body style="{_BODY_STYLE}">'
            f'<div style="background:#DC3545;color:white;padding:20px;text-align:center">'
            f'<h1 style="margin:0;font-size:18px">🔴 ERRORI MONITOR ETF</h1>'
            f'<p style="margin:4px 0 0;font-size:13px">{today}</p></div>'
            f'<div style="padding:20px;background:white">'
            f'<p>ETF con errore: <strong>{errors_count}</strong> · '
            f'Senza prezzo: <strong>{no_price}</strong> · '
            f'DB: <strong>{"OK" if db_ok else "NON DISPONIBILE"}</strong></p>'
            f'{table}</div>'
            f'{_FOOTER.format(ts=ts)}</body></html>'
        )
        return self._send_email(subject, body_html)

    def _period_returns_row(self, isin: str, colspan: int, bg: str, header_color: str) -> str:
        """
        Riga extra sotto ogni ETF con la variazione % a 1/3/10/30/60/90 giorni
        di trading (non calendario — coincide con le righe disponibili in
        etf_price_history, che si accumula un punto per giorno di mercato).

        Mini-tabella a 6 colonne con intestazione colorata (stesso colore
        dell'header della sezione) e i valori sotto — stesso stile delle
        tabelle principali, non una riga inline.
        """
        periods = [1, 3, 10, 30, 60, 90]
        try:
            from database import db
            df = db.get_close_by_isin(isin, days=130)
        except Exception:
            df = None

        header_cells = ''.join(
            f'<th style="padding:3px 4px;border:1px solid #ddd;font-weight:normal;font-size:10px">{p}g</th>'
            for p in periods
        )

        if df is None or df.empty:
            value_cells = (
                f'<td colspan="{len(periods)}" style="padding:3px 4px;border:1px solid #ddd;'
                f'text-align:center;color:#999;font-size:10px">dati storici insufficienti</td>'
            )
        else:
            closes = df['Close'].values
            n = len(closes)
            last = closes[-1]
            cells = []
            for p in periods:
                if n > p and closes[-1 - p]:
                    ref = closes[-1 - p]
                    pct = (last - ref) / ref * 100
                    color = '#28a745' if pct >= 0 else '#dc3545'
                    sign = '+' if pct >= 0 else ''
                    cells.append(
                        f'<td style="padding:3px 4px;border:1px solid #ddd;text-align:center;'
                        f'color:{color};font-size:10px"><strong>{sign}{pct:.1f}%</strong></td>'
                    )
                else:
                    cells.append(
                        '<td style="padding:3px 4px;border:1px solid #ddd;text-align:center;'
                        'color:#999;font-size:10px">—</td>'
                    )
            value_cells = ''.join(cells)

        return (
            f'<tr style="background:{bg}">'
            f'<td colspan="{colspan}" style="padding:2px 8px 8px;border:1px solid #ddd;border-top:none">'
            f'<table style="width:100%;border-collapse:collapse;margin-top:2px">'
            f'<tr style="background:{header_color};color:white">{header_cells}</tr>'
            f'<tr>{value_cells}</tr>'
            f'</table>'
            f'</td>'
            f'</tr>'
        )

    def send_portfolio_report(self, favorites_digest: list = None, l2_radar: list = None) -> bool:
        """
        STEP 5 — Invia resoconto giornaliero del portafoglio con SL/SG suggerito.

        favorites_digest: lista opzionale (da monitor.py::_build_favorites_digest)
        con lo stato quotidiano dei Preferiti — ETF seguiti manualmente, non
        posizioni reali. Se presente, aggiunge una sezione "Preferiti" alla
        stessa email invece di mandarne una separata (scelta 2026-08-10: un
        digest passivo, niente traffico email aggiuntivo).

        l2_radar: lista opzionale (da monitor.py::_build_l2_radar) — a differenza
        dei Preferiti (lista curata a mano), scandisce TUTTO l'universo L2 di
        oggi e mostra quale delle 7 condizioni manca ancora per L1, non solo
        il conteggio (2026-08-20, "terza via" oltre L0/L1). Stessa scelta di
        digest passivo nella stessa email, nessun traffico aggiuntivo.

        Per ogni posizione L1 attiva, mostra:
        - Prezzo di carico
        - Prezzo corrente
        - Performance %
        - SL Suggerito (formula ibrida calcolata da STEP 4)
        - SG Suggerito (target dinamico calcolato da STEP 4)

        Mostra TUTTE le posizioni attive del portafoglio personale, indipendentemente dalla
        classificazione L1/L2/L3 corrente sul dashboard (fix 2026-08-07: prima filtrava per
        appartenenza a etf_l1_tracking/etf_l0_tracking — le tabelle di classificazione del
        dashboard, da cui un ISIN esce quando il *dashboard* lo declassa L1→L2/L3, es. per
        regola B/C/E o downgrade regime, eventi che NON sono vendite reali, vedi CLAUDE.md
        "L1 — Come Si Esce"). Una posizione reale resta valida ed esce SOLO al tocco di
        SL/TP: filtrarla via dalla mail perché il dashboard l'ha riclassificata la faceva
        sparire dal resoconto anche se ancora attivamente detenuta — bug verificato in
        produzione il 2026-08-07 (tutte e 4 le posizioni attive escluse).
        """
        try:
            from database import db
            from order_pricing import compute_order_prices
            from technical_analysis import ETFTechnicalAnalyzer

            # Leggi il portafoglio personale — nessun filtro sulla classificazione dashboard,
            # solo lo status reale della posizione.
            conn = db._get_connection()
            if not conn:
                return True  # No DB connection available
            cur = conn.cursor()
            cur.execute("""
                SELECT pe.id, pe.isin, pe.entry_price, pe.entry_date, pe.fund_name,
                       pe.portafoglio, pe.sl_suggerito, pe.sg_suggerito, pe.broker,
                       pe.tp_proximity_stop_max
                FROM etf_portfolio_entries pe
                WHERE pe.status = 'active'
                ORDER BY pe.entry_date DESC
            """)
            positions = cur.fetchall()
            conn.close()

            if not positions and not favorites_digest:
                return True  # Nulla da segnalare, niente email

            l1_positions = [p for p in positions if p[5] == 'L1']  # portafoglio at index 5
            l0_positions = [p for p in positions if p[5] == 'L0']  # portafoglio at index 5

            # ── SEZIONE L1 ──────────────────────────────────────────────────
            l1_rows = []
            l1_total_gain = 0
            l1_total_notional = 0
            l1_etf_idx = 0

            for entry_id, isin, entry_price, entry_date, fund_name, portafoglio, sl_sug, sg_sug, broker, prev_tp_stop_max in l1_positions:
                try:
                    entry_price = float(entry_price) if entry_price else 0
                    if entry_price <= 0:
                        continue

                    # Ottieni prezzo corrente da etf_price_history (cerca per ISIN)
                    conn = db._get_connection()
                    if not conn:
                        continue
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT close, date FROM etf_price_history
                        WHERE isin = %s OR ticker = %s ORDER BY date DESC LIMIT 1
                    """, (isin, isin))
                    result = cur.fetchone()
                    conn.close()

                    if result:
                        current_price = float(result[0])
                        price_date = result[1] if len(result) > 1 else datetime.now().date()
                    else:
                        current_price = entry_price
                        price_date = datetime.now().date()

                    pct_change = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                    abs_gain = current_price - entry_price
                    color = '#28a745' if pct_change >= 0 else '#dc3545'
                    sign = '+' if pct_change >= 0 else ''

                    # Accumula per totale
                    l1_total_notional += current_price
                    l1_total_gain += abs_gain

                    # Formato data
                    if hasattr(price_date, 'strftime'):
                        date_str = price_date.strftime('%d/%m')
                    else:
                        date_str = str(price_date)[:5]

                    # Prezzi pronti per l'ordine sul broker reale (Stop/Limite per
                    # lo SL, Limite semplice per il TP). Su Directa lo Stop si
                    # stringe automaticamente se il prezzo è vicino al TP (non si
                    # può tenere il Limite TP in parallelo); su broker con OCO
                    # (es. Webank) entrambi si piazzano subito — vedi order_pricing.py.
                    famiglia = ETFTechnicalAnalyzer.detect_family(fund_name or '')
                    sl_initial_pct = ETFTechnicalAnalyzer(famiglia=famiglia).p.get('sl_initial_pct')
                    op = compute_order_prices(current_price, sl_sug and float(sl_sug),
                                               sg_sug and float(sg_sug), broker,
                                               previous_tightened_stop=float(prev_tp_stop_max) if prev_tp_stop_max else None,
                                               sl_initial_pct=sl_initial_pct)
                    stop_str = f'€{op["prezzo_stop"]:.2f}' if op['prezzo_stop'] else '—'
                    lim_sl_str = f'€{op["prezzo_limite_stop"]:.2f}' if op['prezzo_limite_stop'] else '—'
                    lim_tp_str = f'€{op["prezzo_limite_tp"]:.2f}' if op['prezzo_limite_tp'] else '—'
                    tighten_flag = ' 🔶' if op['tightened'] else ''

                    # Indicatore status
                    status_icon = '⚠️' if pct_change < -2 else ('✓' if pct_change >= 0 else '◆')

                    row_bg = "#f8f9fa" if l1_etf_idx % 2 == 0 else "white"
                    l1_etf_idx += 1
                    l1_link = f'https://etf.andreapavan.tech/?isin={isin}'
                    l1_rows.append(
                        f'<tr style="background:{row_bg}">'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none">'
                        f'<a href="{l1_link}" style="color:#00B050;text-decoration:none"><strong>{fund_name[:35]}</strong></a><br>'
                        f'<small style="color:#888">{isin} · {broker or "Directa"}</small></td>'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none;text-align:right">€{entry_price:.2f}</td>'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none;text-align:right">€{current_price:.2f}</td>'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none;text-align:right;color:{color}"><strong>{status_icon} {sign}{pct_change:.1f}%</strong></td>'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none;text-align:right;font-size:12px">{stop_str}{tighten_flag}</td>'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none;text-align:right;font-size:12px">{lim_sl_str}</td>'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none;text-align:right;font-size:12px">{lim_tp_str}</td>'
                        f'</tr>'
                    )
                    l1_rows.append(self._period_returns_row(isin, colspan=7, bg=row_bg, header_color='#00B050'))
                except Exception as e:
                    print(f"⚠️ Errore L1 {isin}: {e}")
                    continue

            # ── SEZIONE L0 ──────────────────────────────────────────────────
            l0_rows = []
            l0_etf_idx = 0
            for entry_id, isin, entry_price, entry_date, fund_name, portafoglio, sl_sug, sg_sug, broker, prev_tp_stop_max in l0_positions:
                try:
                    entry_price = float(entry_price) if entry_price else 0
                    if entry_price <= 0:
                        continue

                    # Ottieni prezzo corrente
                    conn = db._get_connection()
                    if not conn:
                        continue
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT close FROM etf_price_history
                        WHERE isin = %s OR ticker = %s ORDER BY date DESC LIMIT 1
                    """, (isin, isin))
                    result = cur.fetchone()
                    conn.close()

                    current_price = float(result[0]) if result else entry_price
                    pct_change = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                    color = '#28a745' if pct_change >= 0 else '#dc3545'
                    sign = '+' if pct_change >= 0 else ''

                    # Prezzi pronti per l'ordine sul broker reale — stessa logica della sezione L1
                    famiglia = ETFTechnicalAnalyzer.detect_family(fund_name or '')
                    sl_initial_pct = ETFTechnicalAnalyzer(famiglia=famiglia).p.get('sl_initial_pct')
                    op = compute_order_prices(current_price, sl_sug and float(sl_sug),
                                               sg_sug and float(sg_sug), broker,
                                               previous_tightened_stop=float(prev_tp_stop_max) if prev_tp_stop_max else None,
                                               sl_initial_pct=sl_initial_pct)
                    stop_str = f'€{op["prezzo_stop"]:.2f}' if op['prezzo_stop'] else '—'
                    lim_sl_str = f'€{op["prezzo_limite_stop"]:.2f}' if op['prezzo_limite_stop'] else '—'
                    lim_tp_str = f'€{op["prezzo_limite_tp"]:.2f}' if op['prezzo_limite_tp'] else '—'
                    tighten_flag = ' 🔶' if op['tightened'] else ''

                    row_bg = "#f8f9fa" if l0_etf_idx % 2 == 0 else "white"
                    l0_etf_idx += 1
                    l0_link = f'https://etf.andreapavan.tech/?isin={isin}'
                    l0_rows.append(
                        f'<tr style="background:{row_bg}">'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none">'
                        f'<a href="{l0_link}" style="color:#E65100;text-decoration:none"><strong>{fund_name[:35]}</strong></a><br>'
                        f'<small style="color:#888">{isin} · {broker or "Directa"}</small></td>'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none;text-align:right">€{entry_price:.2f}</td>'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none;text-align:right">€{current_price:.2f}</td>'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none;text-align:right;color:{color}"><strong>{sign}{pct_change:.1f}%</strong></td>'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none;text-align:right;font-size:12px">{stop_str}{tighten_flag}</td>'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none;text-align:right;font-size:12px">{lim_sl_str}</td>'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none;text-align:right;font-size:12px">{lim_tp_str}</td>'
                        f'</tr>'
                    )
                    l0_rows.append(self._period_returns_row(isin, colspan=7, bg=row_bg, header_color='#E65100'))
                except Exception as e:
                    print(f"⚠️ Errore L0 {isin}: {e}")
                    continue

            # ── Costruisci HTML ────────────────────────────────────────────
            l1_section = ''
            if l1_rows:
                l1_total_pct = (l1_total_gain / l1_total_notional * 100) if l1_total_notional > 0 else 0
                l1_section = (
                    f'<h2 style="color:#00B050;margin:12px 0 8px">🟢 PORTAFOGLIO L1 — Breve Termine</h2>'
                    f'<table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:16px">'
                    f'<tr style="background:#00B050;color:white">'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:left">ETF</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:right">Carico</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:right">Prezzo</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:right">Perf</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:right">Prezzo Stop (Trigger)</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:right">Prezzo Limite</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:right">Target TP</th>'
                    f'</tr>'
                    f'{"".join(l1_rows)}'
                    f'</table>'
                    f'<p style="margin:0;font-size:11px;color:#666">'
                    f'<strong>Totale L1:</strong> €{l1_total_gain:+.2f} ({l1_total_pct:+.2f}%)</p>'
                )

            l0_section = ''
            if l0_rows:
                l0_section = (
                    f'<h2 style="color:#E65100;margin:16px 0 8px">🟠 PORTAFOGLIO L0 — Medio/Lungo Termine</h2>'
                    f'<p style="margin:0 0 8px;font-size:11px;color:#666">Posizioni in deep recovery — SL trailing progressivo, TP fisso di famiglia.</p>'
                    f'<table style="width:100%;border-collapse:collapse;font-size:12px">'
                    f'<tr style="background:#E65100;color:white">'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:left">ETF</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:right">Carico</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:right">Prezzo</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:right">Perf</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:right">Prezzo Stop (Trigger)</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:right">Prezzo Limite</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:right">Target TP</th>'
                    f'</tr>'
                    f'{"".join(l0_rows)}'
                    f'</table>'
                )

            # ── SEZIONE CANDIDATI L0 (alert-only) ──────────────────────────────
            # Nota: I candidati L0 verrebbero calcolati dal monitor durante l'analisi.
            # Per ora mostriamo solo le posizioni L0 attive.
            # Se vuoi aggiungere candidati L0, si leggerebbero da un table separato o cache JSON.

            # ── SEZIONE PREFERITI (watchlist personale, digest passivo) ─────────
            favorites_section = ''
            if favorites_digest:
                LEVEL_LABELS = {0: 'L0', 1: 'L1', 2: 'L2', 3: 'L3'}
                fav_rows = []
                for i, fav in enumerate(favorites_digest):
                    bc  = fav.get('buy_count', 0)
                    lvl_str = LEVEL_LABELS.get(fav.get('level'), '—')
                    regime  = fav.get('regime') or '—'
                    regime_color = '#00B050' if regime == 'BULL' else '#DC3545' if regime == 'BEAR' else '#FFC000'

                    delta_bc = fav.get('delta_buy_count')
                    if not delta_bc:
                        delta_str = ''
                    elif delta_bc > 0:
                        delta_str = f' <span style="color:#00B050">▲{delta_bc}</span>'
                    else:
                        delta_str = f' <span style="color:#DC3545">▼{abs(delta_bc)}</span>'

                    flags = ('🔔' if fav.get('level_changed') else '') + ('🔄' if fav.get('regime_changed') else '')

                    row_bg = "#f8f9fa" if i % 2 == 0 else "white"
                    fav_isin = fav.get('isin') or ''
                    fav_link = f'https://etf.andreapavan.tech/?isin={fav_isin}&ticker={fav["ticker"]}'
                    fav_rows.append(
                        f'<tr style="background:{row_bg}">'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none">'
                        f'<a href="{fav_link}" style="color:#58a6ff;text-decoration:none"><strong>{fav["nome"][:35]}</strong></a><br>'
                        f'<small style="color:#888">{fav["ticker"]}{" · " + fav_isin if fav_isin else ""}</small></td>'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none;text-align:center">{lvl_str}</td>'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none;text-align:center"><strong>{bc}/7</strong>{delta_str}</td>'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none;text-align:center;color:{regime_color}">{regime}</td>'
                        f'<td style="padding:8px;border:1px solid #ddd;border-bottom:none;text-align:center">{flags or "—"}</td>'
                        f'</tr>'
                    )
                    fav_rows.append(self._period_returns_row(fav.get('isin') or fav['ticker'], colspan=5, bg=row_bg, header_color='#58a6ff'))

                favorites_section = (
                    f'<h2 style="color:#58a6ff;margin:16px 0 8px">⭐ PREFERITI — Watchlist Personale</h2>'
                    f'<p style="margin:0 0 8px;font-size:11px;color:#666">ETF che segui manualmente — non sono posizioni reali, solo un promemoria di come evolvono le condizioni.</p>'
                    f'<table style="width:100%;border-collapse:collapse;font-size:12px">'
                    f'<tr style="background:#58a6ff;color:white">'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:left">ETF</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:center">Livello</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:center">Condizioni</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:center">Regime</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:center">Novità</th>'
                    f'</tr>'
                    f'{"".join(fav_rows)}'
                    f'</table>'
                    f'<p style="margin:6px 0 0;font-size:10px;color:#999">🔔 = livello cambiato da ieri · 🔄 = regime cambiato da ieri</p>'
                )

            # ── SEZIONE RADAR L2 (universo, quasi pronti per L1) ─────────────────
            l2_radar_section = ''
            if l2_radar:
                radar_rows = []
                for i, item in enumerate(l2_radar):
                    bc = item.get('buy_count', 0)
                    bc_color = '#00B050' if bc >= 7 else ('#FFC107' if bc == 6 else '#888')
                    missing_str = ', '.join(item.get('missing') or ['—'])
                    regime = item.get('regime') or '—'
                    regime_color = '#00B050' if regime == 'BULL' else '#DC3545' if regime == 'BEAR' else '#FFC000'

                    row_bg = "#f8f9fa" if i % 2 == 0 else "white"
                    radar_isin = item.get('isin') or ''
                    radar_ticker = item.get('ticker', '')
                    radar_link = f'https://etf.andreapavan.tech/?isin={radar_isin}&ticker={radar_ticker}'
                    radar_rows.append(
                        f'<tr style="background:{row_bg}">'
                        f'<td style="padding:8px;border:1px solid #ddd">'
                        f'<a href="{radar_link}" style="color:#333;text-decoration:none"><strong>{(item.get("nome") or "")[:35]}</strong></a><br>'
                        f'<small style="color:#888">{radar_ticker}{" · " + radar_isin if radar_isin else ""}</small></td>'
                        f'<td style="padding:8px;border:1px solid #ddd;text-align:center;color:{bc_color}"><strong>{bc}/7</strong></td>'
                        f'<td style="padding:8px;border:1px solid #ddd;text-align:left;font-size:11px">{missing_str}</td>'
                        f'<td style="padding:8px;border:1px solid #ddd;text-align:center;color:{regime_color}">{regime}</td>'
                        f'</tr>'
                    )

                l2_radar_section = (
                    f'<h2 style="color:#FFC107;margin:16px 0 8px">📡 RADAR L2 — Quasi pronti per L1</h2>'
                    f'<p style="margin:0 0 8px;font-size:11px;color:#666">'
                    f'Tutto l\'universo classificato L2 oggi (≥5/7 condizioni, o 7/7 bloccato dal regime/SMA50) — non è una lista curata come i Preferiti, è il radar completo. Ordinato per condizioni soddisfatte.</p>'
                    f'<table style="width:100%;border-collapse:collapse;font-size:12px">'
                    f'<tr style="background:#FFC107;color:#333">'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:left">ETF</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:center">Condizioni</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:left">Manca</th>'
                    f'<th style="padding:8px;border:1px solid #ddd;text-align:center">Regime</th>'
                    f'</tr>'
                    f'{"".join(radar_rows)}'
                    f'</table>'
                )

            if not l1_rows and not l0_rows and not favorites_section and not l2_radar_section:
                return True  # Nulla da segnalare

            table_html = l1_section + l0_section + favorites_section + l2_radar_section

            today = datetime.now().strftime('%d/%m/%Y %H:%M')
            subject = f'📊 Portafoglio L1/L0 — {datetime.now().strftime("%d/%m/%Y")}'
            ts = datetime.now().strftime('%d/%m/%Y %H:%M')

            body_html = (
                f'<html><body style="{_BODY_STYLE}">'
                f'<div style="background:linear-gradient(135deg,#00B050,#E65100);color:white;padding:20px;text-align:center">'
                f'<h1 style="margin:0;font-size:18px">📊 PORTAFOGLIO GIORNALIERO</h1>'
                f'<p style="margin:4px 0 0;font-size:13px">ETF Monitor — {today}</p></div>'
                f'<div style="padding:20px;background:white">'
                f'{table_html}'
                f'<hr style="border:none;border-top:1px solid #ccc;margin:20px 0">'
                f'<p style="margin:12px 0;font-size:11px;color:#666">'
                f'<strong>📌 Legenda — campi pronti per l\'ordine Stop su Directa:</strong><br>'
                f'• <strong>Prezzo Stop (Trigger)</strong> = il campo "Prezzo Stop" dell\'ordine Stop di vendita su Directa (quando il prezzo lo tocca/supera al ribasso, la condizione si avvera — L1: formula ibrida, L0: trailing progressivo; si stringe automaticamente 🔶 se il prezzo è vicino al TP)<br>'
                f'• <strong>Prezzo Limite</strong> = il campo "Prezzo Limite" dello stesso ordine Stop su Directa (il prezzo di garanzia: l\'eseguito non scende sotto questo valore, margine 1% sotto il Prezzo Stop, per garantire l\'esecuzione anche in caso di gap)<br>'
                f'• <strong>Target TP</strong> = il livello a cui punti al rialzo, da piazzare come ordine <strong>Limite</strong> separato (NON lo stesso ordine Stop) quando ci arrivi — su un conto cash Directa <strong>NON puoi tenerlo attivo in parallelo allo Stop</strong> (le stesse quote sono impegnate dallo Stop, un secondo ordine di vendita viene rifiutato: "quantità superiore alla disponibilità"). Quando il prezzo si avvicina, <strong>cancella lo Stop e piazza il Limite</strong> (o vendi) in quel momento — <em>su altri broker con OCO nativo (es. Webank) puoi invece piazzare entrambi subito</em><br>'
                f'• <strong>🔶</strong> = Stop stretto perché il prezzo è entro il 3% dal TP — valuta di cancellarlo e piazzare il Limite a breve (solo Directa — su Webank imposta direttamente il TP)<br>'
                f'• <strong>⚠️</strong> = Performance &lt; -2% (attenzione)<br>'
                f'• <strong>✓</strong> = In profitto<br>'
                f'• <strong>◆</strong> = In perdita ma &gt; -2%<br>'
                f'• <strong>1g/3g/10g/30g/60g/90g</strong> (riquadro sotto ogni ETF) = variazione % del prezzo negli ultimi N giorni di trading (non calendario), indipendente dal prezzo di carico</p>'
                f'</div>'
                f'{_FOOTER.format(ts=ts)}</body></html>'
            )

            return self._send_email(subject, body_html)
        except Exception as e:
            print(f'❌ Errore send_portfolio_report: {e}')
            return False

    def send_portfolio_l1_sync_alert(self, new_entries: list) -> bool:
        """Invia email con nuove posizioni L1 aggiunte al portafoglio."""
        if not new_entries:
            return False

        html_rows = ""
        for entry in new_entries:
            if entry.get('added'):
                html_rows += f"""
                <tr>
                    <td>{entry.get('ticker')}</td>
                    <td>€{entry.get('entry_price', 0):.2f}</td>
                    <td>€{entry.get('sl', 0):.2f}</td>
                    <td>€{entry.get('tp', 0):.2f}</td>
                    <td style="color: #27ae60;">✓ Added</td>
                </tr>
                """

        html = f"""
        <h2>📊 Portfolio L1 Sync Alert</h2>
        <p>Le seguenti posizioni sono state aggiunte automaticamente al portafoglio L1:</p>
        <table style="width:100%; border-collapse: collapse; margin: 20px 0;">
            <tr style="background-color: #ecf0f1;">
                <th>ETF</th>
                <th>Entry Price</th>
                <th>Stop Loss</th>
                <th>Take Profit</th>
                <th>Status</th>
            </tr>
            {html_rows}
        </table>
        <p><strong>Azione richiesta:</strong> Imposta gli ordini Stop Loss e Take Profit su Directa.</p>
        """

        subject = f"✅ Portfolio L1: {len([e for e in new_entries if e.get('added')])} nuove posizioni"
        return self._send_email(subject, html)
