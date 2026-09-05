"""
alerts.py - Notifiche email ETF Monitor
=========================================
Solo 2 email, per scelta esplicita dell'utente (2026-09-05 — sostituisce le
~10 email precedenti: digest giornaliero portafoglio, avvicinamento TP,
ingressi ombra individuali per modello, digest mensile Shadow, segnali
operativi L1):

  1. send_new_entries          → nuovi ingressi REALI in L1 (+ L0) — l'unica
                                  email "serve un'azione adesso". Tutto il
                                  resto (SL/TP aggiornati, avvicinamento TP)
                                  si legge dal banner "Cosa devo fare oggi"
                                  della dashboard, non più via email.
  2. send_weekly_shadow_digest → ogni sabato (run principale): quanti/quali
                                  ETF sono entrati nei vari Shadow Monitor
                                  quella settimana + tabella di TUTTE le
                                  posizioni ombra aperte con performance dalla
                                  data di ingresso (+ totali) + archivio di
                                  tutte le uscite con giorni di permanenza e
                                  performance (+ totali).

send_health_report resta come funzione dormiente (già scritta, mai chiamata
dal ciclo principale prima d'ora) — non toccata, fuori dallo scopo di questa
richiesta.
"""
from datetime import datetime, timedelta
import os

try:
    import resend as _resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False

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

    # ── 1. Nuovi ingressi REALI ───────────────────────────────────────────
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

    # ── 2. Digest settimanale Shadow Monitor (ogni sabato) ────────────────
    def send_weekly_shadow_digest(self, all_positions: list) -> bool:
        """all_positions: output di database.py::get_all_shadow_positions() —
        ogni riga ha model_name, ticker, isin, famiglia, entry_date,
        entry_price, exit_date, exit_price, exit_reason, status,
        gross_pct_gain, current_price (quest'ultimo solo per le aperte, via
        LEFT JOIN LATERAL su etf_price_history).

        Tre sezioni, sempre presenti anche se vuote (mostrano un messaggio
        neutro): nuovi ingressi ombra negli ultimi 7 giorni; tabella di TUTTE
        le posizioni ombra aperte con performance dalla data di ingresso e
        totali; archivio di tutte le uscite con giorni di permanenza,
        performance e totali (win rate, profit factor). Nessuna azione
        automatica: sono posizioni ipotetiche, non acquisti reali."""
        if not all_positions:
            return True

        today = datetime.now().date()
        week_ago = today - timedelta(days=7)

        def _days(d1, d2):
            try:
                return (d2 - d1).days
            except Exception:
                return None

        def _pct_color(v):
            return '#00B050' if (v or 0) >= 0 else '#DC3545'

        new_this_week = [p for p in all_positions if p.get('entry_date') and p['entry_date'] >= week_ago]
        open_pos = [p for p in all_positions if p.get('status') == 'open']
        closed_pos = [p for p in all_positions if p.get('status') == 'closed']

        subject_bits = f'{len(new_this_week)} nuovi ingressi' if new_this_week else 'nessun nuovo ingresso'
        subject = f'📅 Digest settimanale Shadow Monitor — {subject_bits} — {today.strftime("%d/%m/%Y")}'

        # ── Sezione 1: nuovi ingressi questa settimana ──
        if new_this_week:
            rows = ''.join(
                f'<tr style="background:{"#f9f9f9" if i % 2 else "white"}">'
                f'<td style="padding:7px;border:1px solid #ddd">{p["model_name"]}</td>'
                f'<td style="padding:7px;border:1px solid #ddd">{p["ticker"]}</td>'
                f'<td style="padding:7px;border:1px solid #ddd;font-size:11px;color:#666">{p.get("famiglia","")}</td>'
                f'<td style="padding:7px;border:1px solid #ddd;text-align:center">{p["entry_date"].strftime("%d/%m")}</td>'
                f'<td style="padding:7px;border:1px solid #ddd;text-align:right">€{float(p["entry_price"]):.2f}</td>'
                f'</tr>'
                for i, p in enumerate(sorted(new_this_week, key=lambda x: x['entry_date']))
            )
            section1 = (
                f'<h2 style="color:#8E44AD;margin:0 0 8px;font-size:16px">🟣 Nuovi ingressi questa settimana — {len(new_this_week)}</h2>'
                f'<table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:20px">'
                f'<thead><tr style="background:#8E44AD;color:white">'
                f'<th style="padding:7px;border:1px solid #ddd;text-align:left">Modello</th>'
                f'<th style="padding:7px;border:1px solid #ddd;text-align:left">Ticker</th>'
                f'<th style="padding:7px;border:1px solid #ddd">Famiglia</th>'
                f'<th style="padding:7px;border:1px solid #ddd">Data</th>'
                f'<th style="padding:7px;border:1px solid #ddd">Prezzo</th>'
                f'</tr></thead><tbody>{rows}</tbody></table>'
            )
        else:
            section1 = '<p style="color:#666;font-size:13px;margin:0 0 20px">🟣 Nessun nuovo ingresso ombra questa settimana.</p>'

        # ── Sezione 2: posizioni aperte (tutte, tutti i modelli) ──
        if open_pos:
            open_rows = ''
            gains = []
            for i, p in enumerate(sorted(open_pos, key=lambda x: (x['model_name'], x['entry_date']))):
                entry_price = float(p['entry_price'])
                current = p.get('current_price')
                pct = round((float(current) / entry_price - 1) * 100, 2) if current else None
                if pct is not None:
                    gains.append(pct)
                days_held = _days(p['entry_date'], today)
                bg = '#f9f9f9' if i % 2 else 'white'
                pct_s = f'{pct:+.2f}%' if pct is not None else '—'
                open_rows += (
                    f'<tr style="background:{bg}">'
                    f'<td style="padding:7px;border:1px solid #ddd">{p["model_name"]}</td>'
                    f'<td style="padding:7px;border:1px solid #ddd">{p["ticker"]}</td>'
                    f'<td style="padding:7px;border:1px solid #ddd;text-align:center">{p["entry_date"].strftime("%d/%m/%Y")}</td>'
                    f'<td style="padding:7px;border:1px solid #ddd;text-align:center">{days_held if days_held is not None else "—"}gg</td>'
                    f'<td style="padding:7px;border:1px solid #ddd;text-align:right">€{entry_price:.2f}</td>'
                    f'<td style="padding:7px;border:1px solid #ddd;text-align:right">{"€{:.2f}".format(float(current)) if current else "—"}</td>'
                    f'<td style="padding:7px;border:1px solid #ddd;text-align:right;font-weight:bold;color:{_pct_color(pct)}">{pct_s}</td>'
                    f'</tr>'
                )
            n_open = len(open_pos)
            avg_open = round(sum(gains) / len(gains), 2) if gains else None
            n_pos = sum(1 for g in gains if g > 0)
            totals_open = (
                f'<tr style="background:#eee;font-weight:bold">'
                f'<td colspan="4" style="padding:7px;border:1px solid #ddd">TOTALI — {n_open} posizioni aperte ({n_pos} in guadagno)</td>'
                f'<td style="padding:7px;border:1px solid #ddd"></td>'
                f'<td style="padding:7px;border:1px solid #ddd;text-align:right">Media</td>'
                f'<td style="padding:7px;border:1px solid #ddd;text-align:right;color:{_pct_color(avg_open)}">'
                f'{"{:+.2f}%".format(avg_open) if avg_open is not None else "—"}</td></tr>'
            )
            section2 = (
                f'<h2 style="color:#2E86C1;margin:0 0 8px;font-size:16px">📊 Posizioni ombra APERTE — {n_open}</h2>'
                f'<table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:20px">'
                f'<thead><tr style="background:#2E86C1;color:white">'
                f'<th style="padding:7px;border:1px solid #ddd;text-align:left">Modello</th>'
                f'<th style="padding:7px;border:1px solid #ddd;text-align:left">Ticker</th>'
                f'<th style="padding:7px;border:1px solid #ddd">Ingresso</th>'
                f'<th style="padding:7px;border:1px solid #ddd">Gg</th>'
                f'<th style="padding:7px;border:1px solid #ddd">Prezzo E.</th>'
                f'<th style="padding:7px;border:1px solid #ddd">Prezzo Att.</th>'
                f'<th style="padding:7px;border:1px solid #ddd">Perf.</th>'
                f'</tr></thead><tbody>{open_rows}{totals_open}</tbody></table>'
            )
        else:
            section2 = '<p style="color:#666;font-size:13px;margin:0 0 20px">📊 Nessuna posizione ombra aperta al momento.</p>'

        # ── Sezione 3: archivio uscite ──
        if closed_pos:
            closed_rows = ''
            c_gains = []
            for i, p in enumerate(sorted(closed_pos, key=lambda x: x.get('exit_date') or x['entry_date'], reverse=True)):
                pct = float(p['gross_pct_gain']) if p.get('gross_pct_gain') is not None else None
                if pct is not None:
                    c_gains.append(pct)
                days_held = _days(p['entry_date'], p['exit_date']) if p.get('exit_date') else None
                bg = '#f9f9f9' if i % 2 else 'white'
                pct_s = f'{pct:+.2f}%' if pct is not None else '—'
                closed_rows += (
                    f'<tr style="background:{bg}">'
                    f'<td style="padding:7px;border:1px solid #ddd">{p["model_name"]}</td>'
                    f'<td style="padding:7px;border:1px solid #ddd">{p["ticker"]}</td>'
                    f'<td style="padding:7px;border:1px solid #ddd;text-align:center">{p["entry_date"].strftime("%d/%m/%Y")}</td>'
                    f'<td style="padding:7px;border:1px solid #ddd;text-align:center">{p["exit_date"].strftime("%d/%m/%Y") if p.get("exit_date") else "—"}</td>'
                    f'<td style="padding:7px;border:1px solid #ddd;text-align:center">{days_held if days_held is not None else "—"}gg</td>'
                    f'<td style="padding:7px;border:1px solid #ddd;text-align:center;font-size:11px;color:#666">{p.get("exit_reason") or "—"}</td>'
                    f'<td style="padding:7px;border:1px solid #ddd;text-align:right;font-weight:bold;color:{_pct_color(pct)}">{pct_s}</td>'
                    f'</tr>'
                )
            n_closed = len(closed_pos)
            wins = sum(1 for g in c_gains if g > 0)
            wr = round(100 * wins / n_closed, 1) if n_closed else None
            avg_closed = round(sum(c_gains) / len(c_gains), 2) if c_gains else None
            sum_win = sum(g for g in c_gains if g > 0)
            sum_loss = -sum(g for g in c_gains if g <= 0)
            if sum_loss:
                pf_s = f'{sum_win / sum_loss:.2f}'
            else:
                pf_s = '∞' if sum_win else '—'
            totals_closed = (
                f'<tr style="background:#eee;font-weight:bold">'
                f'<td colspan="5" style="padding:7px;border:1px solid #ddd">TOTALI — {n_closed} chiuse, WR {wr if wr is not None else "—"}%, PF {pf_s}</td>'
                f'<td style="padding:7px;border:1px solid #ddd;text-align:right">Media</td>'
                f'<td style="padding:7px;border:1px solid #ddd;text-align:right;color:{_pct_color(avg_closed)}">'
                f'{"{:+.2f}%".format(avg_closed) if avg_closed is not None else "—"}</td></tr>'
            )
            section3 = (
                f'<h2 style="color:#5D6D7E;margin:0 0 8px;font-size:16px">🗃️ Archivio uscite — {n_closed}</h2>'
                f'<table style="width:100%;border-collapse:collapse;font-size:12px">'
                f'<thead><tr style="background:#5D6D7E;color:white">'
                f'<th style="padding:7px;border:1px solid #ddd;text-align:left">Modello</th>'
                f'<th style="padding:7px;border:1px solid #ddd;text-align:left">Ticker</th>'
                f'<th style="padding:7px;border:1px solid #ddd">Ingresso</th>'
                f'<th style="padding:7px;border:1px solid #ddd">Uscita</th>'
                f'<th style="padding:7px;border:1px solid #ddd">Gg</th>'
                f'<th style="padding:7px;border:1px solid #ddd">Motivo</th>'
                f'<th style="padding:7px;border:1px solid #ddd">Perf.</th>'
                f'</tr></thead><tbody>{closed_rows}{totals_closed}</tbody></table>'
            )
        else:
            section3 = '<p style="color:#666;font-size:13px;margin:0">🗃️ Nessuna uscita ancora registrata.</p>'

        ts = datetime.now().strftime('%d/%m/%Y %H:%M')
        body_html = (
            f'<html><body style="{_BODY_STYLE}">'
            f'<div style="background:linear-gradient(135deg,#34495e,#2c3e50);color:white;padding:22px;text-align:center">'
            f'<h1 style="margin:0;font-size:19px">📅 Digest Settimanale — Shadow Monitor</h1>'
            f'<p style="margin:6px 0 0;opacity:.9;font-size:13px">{today.strftime("%A %d %B %Y")}</p></div>'
            f'<div style="padding:18px;background:white">'
            f'<p style="color:#666;font-size:12px;margin:0 0 16px">Stato di tutti i candidati tracciati in ombra. '
            f'Nessuna azione automatica: sono posizioni ipotetiche, non acquisti reali. Una promozione a produzione '
            f'resta sempre una decisione esplicita, con soglia N≥30 trade chiusi.</p>'
            f'{section1}{section2}{section3}'
            f'</div>{_FOOTER.format(ts=ts)}</body></html>'
        )
        return self._send_email(subject, body_html)

    # ── Health report (dormiente, mai chiamata dal ciclo principale) ──────
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
