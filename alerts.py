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
            l1_rows += (
                f'<tr style="background:{bg}">'
                f'<td style="padding:8px;border:1px solid #ddd">'
                f'<strong>{f["nome"][:45]}</strong><br>'
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
                l0_rows += (
                    f'<tr style="background:{bg}">'
                    f'<td style="padding:8px;border:1px solid #ddd">'
                    f'<strong>{f["nome"][:45]}</strong><br>'
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
            f'<h2 style="margin:0 0 4px">{nome}</h2>'
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
            f'<tr style="background:{pct_c};color:white">'
            f'<td style="padding:12px;border:1px solid #ddd;font-weight:bold">{label}</td>'
            f'<td style="padding:12px;border:1px solid #ddd;font-size:20px;font-weight:bold">{pct_s}</td></tr>'
            f'</table>'
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
                f'<div style="font-weight:bold;font-size:14px">{s.get("nome","")[:50]}</div>'
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
