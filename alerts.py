"""
alerts.py - Sistema di notifiche email per alert ETF
=====================================================
Gestisce l'invio di email per:
- Alert di acquisto (segnali BUY)
- Alert di vendita (segnali SELL)
- Report giornaliero

Email via Resend API (HTTPS) — non bloccato da Railway/hosting.
"""

from datetime import datetime
from typing import Dict
import os

try:
    import resend as _resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    print("Libreria 'resend' non installata. Installa con: pip install resend")


class AlertSystem:
    """Sistema di alert via email (Resend API)"""

    def __init__(self, sender_email: str = None, sender_password: str = None,
                 recipient_email: str = None):
        """
        Args:
            sender_email:    Indirizzo mittente (dominio verificato Resend).
                             Default: EMAIL_SENDER dall'env.
            sender_password: Ignorato (legacy, mantenuto per compatibilita').
            recipient_email: Email destinatario. Default: EMAIL_RECIPIENT dall'env.
        """
        self.sender_email = sender_email or os.getenv('EMAIL_SENDER', 'onboarding@resend.dev')
        self.recipient_email = recipient_email or os.getenv('EMAIL_RECIPIENT', 'andreapavan67@gmail.com')
        self.resend_api_key = os.getenv('RESEND_API_KEY', '')

        if RESEND_AVAILABLE and self.resend_api_key:
            _resend.api_key = self.resend_api_key

    def _send_email(self, subject: str, body_html: str, body_text: str = None) -> bool:
        """Invia email tramite Resend API"""
        if not RESEND_AVAILABLE:
            print("Resend non disponibile — installa con: pip install resend")
            print(f"   Subject: {subject}")
            return False

        if not self.resend_api_key:
            print("RESEND_API_KEY non configurata — email non inviata")
            print(f"   Subject: {subject}")
            return False

        if not self.recipient_email:
            print("EMAIL_RECIPIENT non configurata — email non inviata")
            return False

        try:
            params: _resend.Emails.SendParams = {
                "from": f"ETF Monitor <{self.sender_email}>",
                "to": [self.recipient_email],
                "subject": subject,
                "html": body_html,
            }
            if body_text:
                params["text"] = body_text

            _resend.Emails.send(params)
            print(f"Email inviata via Resend: {subject}")
            return True

        except Exception as e:
            print(f"Errore invio email (Resend): {e}")
            return False

    def send_l1_digest(self, l1_etfs: list) -> bool:
        """
        Email giornaliera: lista di tutti gli ETF in Livello 1 con tracking entrata.

        Args:
            l1_etfs: Lista di dict con campi:
                nome, isin, ticker, categoria,
                entry_date, entry_price, price, days_in_l1, pct_gain
        """
        today = datetime.now().strftime('%d/%m/%Y')
        n = len(l1_etfs)
        subject = f"📊 Portfolio ETF L1 — {n} ETF — {today}"

        def ind_cell(label, ref, value_str, ok):
            """Cella indicatore compatta: verde=ok, rosso=ko"""
            bg  = '#d4edda' if ok else '#f8d7da'
            col = '#155724' if ok else '#721c24'
            icon = '✅' if ok else '❌'
            return (f'<td style="padding:4px 6px;border:1px solid #ddd;background:{bg};'
                    f'color:{col};font-size:11px;text-align:center;">'
                    f'<div style="font-weight:bold;">{icon} {label}</div>'
                    f'<div style="font-size:10px;color:#555;">{ref}</div>'
                    f'<div style="font-weight:bold;">{value_str}</div>'
                    f'</td>')

        rows_html = ""
        for i, f in enumerate(l1_etfs, start=1):
            entry_date_str = (
                f['entry_date'].strftime('%d/%m/%Y')
                if hasattr(f['entry_date'], 'strftime')
                else str(f['entry_date'])
            )
            entry_price = f.get('entry_price')
            price = f.get('price')
            pct = f.get('pct_gain')
            days = f.get('days_in_l1', 0)

            pct_color = '#00B050' if pct and pct >= 0 else '#DC3545'
            pct_str = f"{pct:+.2f}%" if pct is not None else '–'
            bg = '#f9f9f9' if i % 2 == 0 else 'white'

            # Valori indicatori del giorno
            ema20    = f.get('ema20')
            sma50    = f.get('sma50')
            rsi      = f.get('rsi')
            adx      = f.get('adx')
            bc       = f.get('conditions', f.get('buy_conditions', {}))

            align_ok  = bool(bc.get('allineamento_ok'))
            persist_ok= bool(bc.get('persistenza_ok'))
            rsi_ok    = bool(bc.get('rsi_ok') or bc.get('rsi_optimal'))
            dist_ok   = bool(bc.get('distance_ok'))
            adx_ok    = bool(bc.get('adx_ok'))

            ema20_str  = f"{ema20:.4f}" if ema20 else '–'
            sma50_str  = f"{sma50:.4f}" if sma50 else '–'
            rsi_str    = f"{rsi:.1f}" if rsi else '–'
            adx_str    = f"{adx:.1f}" if adx else '–'

            ind_row = (
                ind_cell('Allineamento', f'EMA20>SMA50', f'EMA20={ema20_str}', align_ok) +
                ind_cell('Persistenza 3gg+slope', f'EMA20={ema20_str}', f'SMA50={sma50_str}', persist_ok) +
                ind_cell('RSI range target', 'range: 50–65', rsi_str, rsi_ok) +
                ind_cell('Distanza EMA20', 'dist ≤ max%', f'EMA={ema20_str}', dist_ok) +
                ind_cell('ADX trend', f'ADX ≥ 20', adx_str, adx_ok)
            )

            rows_html += f"""
            <tr style="background:{bg};">
              <td style="padding:8px;border:1px solid #ddd;text-align:center;color:#666;">{i}</td>
              <td style="padding:8px;border:1px solid #ddd;">
                <strong>{f['nome'][:45]}</strong><br>
                <span style="font-size:11px;color:#888;">{f['ticker']} · {f['isin']}</span>
              </td>
              <td style="padding:8px;border:1px solid #ddd;text-align:center;font-size:12px;color:#666;">{f.get('categoria','')[:30]}</td>
              <td style="padding:8px;border:1px solid #ddd;text-align:center;">{entry_date_str}</td>
              <td style="padding:8px;border:1px solid #ddd;text-align:center;">{days}</td>
              <td style="padding:8px;border:1px solid #ddd;text-align:right;">{"€{:.4f}".format(entry_price) if entry_price else '–'}</td>
              <td style="padding:8px;border:1px solid #ddd;text-align:right;">{"€{:.4f}".format(price) if price else '–'}</td>
              <td style="padding:8px;border:1px solid #ddd;text-align:center;font-weight:bold;color:{pct_color};">{pct_str}</td>
            </tr>
            <tr style="background:{bg};">
              <td style="padding:4px;border:1px solid #ddd;"></td>
              <td colspan="7" style="padding:4px 8px;border:1px solid #ddd;">
                <table style="width:100%;border-collapse:collapse;">
                  <tr>{ind_row}</tr>
                </table>
              </td>
            </tr>"""

        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 860px; margin: 0 auto; background: #f0f2f5;">
          <div style="background: linear-gradient(135deg, #00B050, #007A36); color: white; padding: 25px; text-align: center;">
            <h1 style="margin: 0; font-size: 22px;">📊 Portfolio ETF Livello 1</h1>
            <p style="margin: 6px 0 0 0; opacity: 0.9; font-size: 14px;">
              {datetime.now().strftime('%A %d %B %Y')} &nbsp;·&nbsp; {n} ETF in portafoglio
            </p>
          </div>

          <div style="padding: 20px; background: white;">
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
              <thead>
                <tr style="background:#00B050;color:white;">
                  <th style="padding:8px;border:1px solid #ddd;">#</th>
                  <th style="padding:8px;border:1px solid #ddd;text-align:left;">ETF</th>
                  <th style="padding:8px;border:1px solid #ddd;">Categoria</th>
                  <th style="padding:8px;border:1px solid #ddd;">Entrato il</th>
                  <th style="padding:8px;border:1px solid #ddd;">Giorni in L1</th>
                  <th style="padding:8px;border:1px solid #ddd;">Prezzo entrata</th>
                  <th style="padding:8px;border:1px solid #ddd;">Prezzo attuale</th>
                  <th style="padding:8px;border:1px solid #ddd;">Guadagno %</th>
                </tr>
              </thead>
              <tbody>{rows_html}</tbody>
            </table>
          </div>

          <div style="padding: 15px; background: #333; color: #999; text-align: center; font-size: 12px;">
            ETF Monitor System &nbsp;·&nbsp; Prossimo aggiornamento ore 18:00
          </div>
        </body>
        </html>
        """
        return self._send_email(subject, body_html)

    def send_sell_l1_exit(self, etf_info: dict) -> bool:
        """
        Email di uscita da L1: prezzo entrata, prezzo uscita, % guadagno/perdita
        con dettaglio indicatori tecnici al momento dell'uscita.

        Args:
            etf_info: dict con nome, isin, ticker, categoria,
                      entry_date, entry_price, exit_price, days_in_l1, pct_gain,
                      analysis (dict con ema13, sma50, rsi, macd_histogram, bb_pct_b, level_reason)
        """
        pct = etf_info.get('pct_gain')
        pct_str = f"{pct:+.2f}%" if pct is not None else 'N/D'
        pct_color = '#00B050' if pct and pct >= 0 else '#DC3545'
        result_label = 'GUADAGNO' if pct and pct >= 0 else 'PERDITA'

        entry_date_str = (
            etf_info['entry_date'].strftime('%d/%m/%Y')
            if hasattr(etf_info.get('entry_date'), 'strftime')
            else str(etf_info.get('entry_date', '–'))
        )
        today = datetime.now().strftime('%d/%m/%Y')
        subject = f"🔴 Uscita ETF L1 — {etf_info['nome'][:40]} — {today}"

        # Indicatori tecnici al momento dell'uscita
        an = etf_info.get('analysis', {})
        ema20         = an.get('ema20')
        sma50         = an.get('sma50')
        sma200        = an.get('sma200')
        rsi           = an.get('rsi')
        adx           = an.get('adx')
        current_price = an.get('current_price')
        level_reason  = an.get('level_reason', '–')
        buy_count     = an.get('buy_count', 0)
        bc            = an.get('conditions', an.get('buy_conditions', {}))

        c1_ok = bool(bc.get('allineamento_ok'))
        c2_ok = bool(bc.get('persistenza_ok'))
        c3_ok = bool(bc.get('rsi_ok') or bc.get('rsi_optimal'))
        c4_ok = bool(bc.get('distance_ok'))
        c5_ok = bool(bc.get('adx_ok'))

        ema20_str  = f"{ema20:.4f}" if ema20 else 'N/D'
        sma50_str  = f"{sma50:.4f}" if sma50 else 'N/D'
        price_str  = f"{current_price:.4f}" if current_price else 'N/D'
        rsi_str    = f"{rsi:.1f}" if rsi else 'N/D'
        adx_str    = f"{adx:.1f}" if adx else 'N/D'

        def ind_row(label, ref_str, value_str, ok, is_cause=False):
            if is_cause:
                color = '#DC3545'; text_color = 'white'; icon = '🔴'
            elif ok:
                color = '#d4edda'; text_color = '#155724'; icon = '✅'
            else:
                color = '#f8d7da'; text_color = '#721c24'; icon = '❌'
            return (f'<tr style="background:{color};">'
                    f'<td style="padding:8px 12px;border:1px solid #ddd;text-align:center;font-size:15px;">{icon}</td>'
                    f'<td style="padding:8px 12px;border:1px solid #ddd;font-weight:bold;color:{text_color};font-size:12px;">{label}</td>'
                    f'<td style="padding:8px 12px;border:1px solid #ddd;color:{text_color};font-size:12px;">{ref_str}</td>'
                    f'<td style="padding:8px 12px;border:1px solid #ddd;font-weight:bold;color:{text_color};font-size:13px;">{value_str}</td>'
                    f'</tr>')

        ind_rows = (
            ind_row('1. Allineamento (Prezzo>EMA20>SMA50)',
                    f'EMA20={ema20_str} · SMA50={sma50_str}',
                    f'Prezzo={price_str}',
                    c1_ok, is_cause=not c1_ok) +
            ind_row('2. Persistenza ≥3gg + slope EMA20↑',
                    'EMA20 deve salire',
                    f'EMA20={ema20_str}',
                    c2_ok, is_cause=not c2_ok) +
            ind_row('3. RSI nel range target',
                    'range: 50–65',
                    f'RSI={rsi_str}',
                    c3_ok, is_cause=not c3_ok) +
            ind_row('4. Distanza EMA20 entro limite',
                    'dist ≤ max%',
                    f'EMA={ema20_str}',
                    c4_ok, is_cause=not c4_ok) +
            ind_row('5. ADX sopra soglia (trend presente)',
                    'ADX ≥ 20',
                    f'ADX={adx_str}',
                    c5_ok, is_cause=not c5_ok)
        )

        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 620px; margin: 0 auto; background: #f0f2f5;">
          <div style="background: linear-gradient(135deg, #DC3545, #AA0000); color: white; padding: 25px; text-align: center;">
            <h1 style="margin: 0; font-size: 22px;">🔴 USCITA ETF DA LIVELLO 1</h1>
            <p style="margin: 6px 0 0 0; opacity: 0.9; font-size: 14px;">{today}</p>
          </div>

          <div style="padding: 20px; background: white;">
            <h2 style="color:#333;margin-top:0;">{etf_info['nome']}</h2>
            <p style="color:#666;margin-top:-10px;">{etf_info['ticker']} · {etf_info['categoria']} · {etf_info['isin']}</p>

            <div style="margin-bottom:18px;padding:14px 18px;background:#555;border-radius:8px;color:white;">
              <div style="font-size:15px;font-weight:bold;margin-bottom:4px;">📉 Motivo uscita</div>
              <div style="font-size:13px;opacity:0.9;">{level_reason}</div>
              <div style="font-size:12px;margin-top:6px;">Condizioni soddisfatte al momento dell'uscita: {buy_count}/5</div>
            </div>

            <table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:20px;">
              <tr style="background:#f5f5f5;">
                <td style="padding:12px;border:1px solid #ddd;"><strong>Data entrata in L1</strong></td>
                <td style="padding:12px;border:1px solid #ddd;">{entry_date_str}</td>
              </tr>
              <tr>
                <td style="padding:12px;border:1px solid #ddd;"><strong>Giorni in L1</strong></td>
                <td style="padding:12px;border:1px solid #ddd;">{etf_info.get('days_in_l1', '–')} giorni</td>
              </tr>
              <tr style="background:#f5f5f5;">
                <td style="padding:12px;border:1px solid #ddd;"><strong>Prezzo di entrata</strong></td>
                <td style="padding:12px;border:1px solid #ddd;">{"€{:.4f}".format(etf_info['entry_price']) if etf_info.get('entry_price') else '–'}</td>
              </tr>
              <tr>
                <td style="padding:12px;border:1px solid #ddd;"><strong>Prezzo di uscita</strong></td>
                <td style="padding:12px;border:1px solid #ddd;">{"€{:.4f}".format(etf_info['exit_price']) if etf_info.get('exit_price') else '–'}</td>
              </tr>
              <tr style="background:{pct_color};color:white;">
                <td style="padding:12px;border:1px solid #ddd;"><strong>{result_label}</strong></td>
                <td style="padding:12px;border:1px solid #ddd;font-size:18px;font-weight:bold;">{pct_str}</td>
              </tr>
            </table>

            <div style="font-size:13px;font-weight:bold;color:#333;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px;">
              Stato 5 condizioni L1 al momento dell'uscita
              <span style="font-weight:normal;font-size:12px;color:#DC3545;margin-left:8px;">🔴 = causa uscita</span>
            </div>
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
              <thead>
                <tr style="background:#555;color:white;">
                  <th style="padding:8px;border:1px solid #ddd;width:35px;"></th>
                  <th style="padding:8px;border:1px solid #ddd;text-align:left;">Condizione</th>
                  <th style="padding:8px;border:1px solid #ddd;text-align:left;">Riferimento</th>
                  <th style="padding:8px;border:1px solid #ddd;text-align:left;">Valore reale</th>
                </tr>
              </thead>
              <tbody>{ind_rows}</tbody>
            </table>
          </div>

          <div style="padding: 15px; background: #333; color: #999; text-align: center; font-size: 12px;">
            ETF Monitor System &nbsp;·&nbsp; {datetime.now().strftime('%d/%m/%Y %H:%M')}
          </div>
        </body>
        </html>
        """
        return self._send_email(subject, body_html)

    def send_buy_alert(self, etf: Dict, analysis: Dict) -> bool:
        """Invia alert di acquisto ETF"""
        subject = f"ALERT BUY - ETF {etf['nome'][:40]}"

        ema13_str = f"{analysis['ema13']:.2f}" if analysis.get('ema13') else 'N/A'
        sma50_str = f"{analysis['sma50']:.2f}" if analysis.get('sma50') else 'N/A'
        rsi_str = f"{analysis['rsi']:.1f}" if analysis.get('rsi') else 'N/A'
        adx_str = f"{analysis['adx']:.1f}" if analysis.get('adx') else 'N/A'
        vol_str = f"{analysis['volume_ratio']:.2f}x" if analysis.get('volume_ratio') else 'N/A'
        price_str = f"{analysis.get('current_price', 0):.2f}"

        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #00B050, #00D060); color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">SEGNALE BUY - ETF</h1>
            </div>

            <div style="padding: 20px; background: #f5f5f5;">
                <h2 style="color: #333; margin-top: 0;">{etf['nome']}</h2>

                <table style="width: 100%; border-collapse: collapse; background: white;">
                    <tr style="background: #e8e8e8;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Ticker</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{etf['ticker']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Categoria</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{etf['categoria']}</td>
                    </tr>
                    <tr style="background: #e8e8e8;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Livello</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">L{etf['livello']}</td>
                    </tr>
                </table>

                <h3 style="color: #00B050; margin-top: 20px;">Analisi Tecnica</h3>

                <table style="width: 100%; border-collapse: collapse; background: white;">
                    <tr style="background: #00B050; color: white;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Prezzo</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>{price_str}</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;">EMA 13</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{ema13_str}</td>
                    </tr>
                    <tr style="background: #e8e8e8;">
                        <td style="padding: 10px; border: 1px solid #ddd;">SMA 50</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{sma50_str}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;">RSI (14)</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{rsi_str}</td>
                    </tr>
                    <tr style="background: #e8e8e8;">
                        <td style="padding: 10px; border: 1px solid #ddd;">ADX</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{adx_str}</td>
                    </tr>
                    <tr style="background: #00B050; color: white;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Volume Ratio</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>{vol_str}</strong></td>
                    </tr>
                </table>

                <div style="margin-top: 20px; padding: 15px; background: #d4edda; border-left: 4px solid #00B050;">
                    <strong>Tutte le 5 condizioni BUY sono soddisfatte!</strong><br>
                    EMA13 &gt; SMA50, Prezzo sopra MA, RSI ottimale, Volume alto, ADX forte
                </div>
            </div>

            <div style="padding: 15px; background: #333; color: #999; text-align: center; font-size: 12px;">
                ETF Monitor System - {datetime.now().strftime('%d/%m/%Y %H:%M')}
            </div>
        </body>
        </html>
        """

        return self._send_email(subject, body_html)

    def send_sell_alert(self, etf: Dict, analysis: Dict) -> bool:
        """Invia alert di vendita ETF"""
        subject = f"ALERT SELL - ETF {etf['nome'][:40]}"

        ema13_str = f"{analysis['ema13']:.2f}" if analysis.get('ema13') else 'N/A'
        sma50_str = f"{analysis['sma50']:.2f}" if analysis.get('sma50') else 'N/A'
        rsi_str = f"{analysis['rsi']:.1f}" if analysis.get('rsi') else 'N/A'
        adx_str = f"{analysis['adx']:.1f}" if analysis.get('adx') else 'N/A'
        price_str = f"{analysis.get('current_price', 0):.2f}"

        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #DC3545, #FF4444); color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">SEGNALE SELL - ETF</h1>
            </div>

            <div style="padding: 20px; background: #f5f5f5;">
                <h2 style="color: #333; margin-top: 0;">{etf['nome']}</h2>

                <table style="width: 100%; border-collapse: collapse; background: white;">
                    <tr style="background: #e8e8e8;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Ticker</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{etf['ticker']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Categoria</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{etf['categoria']}</td>
                    </tr>
                    <tr style="background: #e8e8e8;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Livello</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">L{etf['livello']}</td>
                    </tr>
                </table>

                <h3 style="color: #DC3545; margin-top: 20px;">Analisi Tecnica</h3>

                <table style="width: 100%; border-collapse: collapse; background: white;">
                    <tr style="background: #DC3545; color: white;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Prezzo</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>{price_str}</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;">EMA 13</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{ema13_str}</td>
                    </tr>
                    <tr style="background: #e8e8e8;">
                        <td style="padding: 10px; border: 1px solid #ddd;">SMA 50</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{sma50_str}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;">RSI (14)</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{rsi_str}</td>
                    </tr>
                    <tr style="background: #e8e8e8;">
                        <td style="padding: 10px; border: 1px solid #ddd;">ADX</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{adx_str}</td>
                    </tr>
                </table>

                <div style="margin-top: 20px; padding: 15px; background: #f8d7da; border-left: 4px solid #DC3545;">
                    <strong>Attenzione:</strong> {'Considera la vendita immediata!' if etf['livello'] == 1 else 'Monitora attentamente questo ETF.'}
                </div>
            </div>

            <div style="padding: 15px; background: #333; color: #999; text-align: center; font-size: 12px;">
                ETF Monitor System - {datetime.now().strftime('%d/%m/%Y %H:%M')}
            </div>
        </body>
        </html>
        """

        return self._send_email(subject, body_html)

    def send_daily_report(self, summary: Dict) -> bool:
        """Invia report giornaliero con riepilogo ETF per livello"""
        subject = f"Report Giornaliero ETF - {datetime.now().strftime('%d/%m/%Y')}"
        today   = datetime.now().strftime('%A %d %B %Y')

        def etf_table(etfs, bg_color, title):
            if not etfs:
                return ''
            rows = ''
            for f in etfs[:15]:
                price_str = f"{f['price']:.4f}" if f.get('price') else '-'
                rsi_str   = f"{f['rsi']:.0f}"   if f.get('rsi')   else '-'
                adx_str   = f"{f['adx']:.0f}"   if f.get('adx')   else '-'
                bc        = f.get('buy_count', 0)
                rows += f"""
                <tr>
                  <td style="padding:7px 10px;border:1px solid #ddd;">{f.get('nome', f.get('ticker',''))[:40]}</td>
                  <td style="padding:7px 10px;border:1px solid #ddd;text-align:center;">{f.get('ticker','')}</td>
                  <td style="padding:7px 10px;border:1px solid #ddd;text-align:right;">{price_str}</td>
                  <td style="padding:7px 10px;border:1px solid #ddd;text-align:center;">{rsi_str}</td>
                  <td style="padding:7px 10px;border:1px solid #ddd;text-align:center;">{adx_str}</td>
                  <td style="padding:7px 10px;border:1px solid #ddd;text-align:center;">{bc}/5</td>
                </tr>"""
            return f"""
            <h3 style="color:#333;margin-top:18px;">{title} ({len(etfs)} ETF)</h3>
            <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:14px;">
              <tr style="background:{bg_color};color:white;">
                <th style="padding:7px;border:1px solid #ddd;text-align:left;">ETF</th>
                <th style="padding:7px;border:1px solid #ddd;">Ticker</th>
                <th style="padding:7px;border:1px solid #ddd;">Prezzo</th>
                <th style="padding:7px;border:1px solid #ddd;">RSI</th>
                <th style="padding:7px;border:1px solid #ddd;">ADX</th>
                <th style="padding:7px;border:1px solid #ddd;">Cond.</th>
              </tr>{rows}
            </table>"""

        l0_html = etf_table(summary.get('l0_etfs', []), '#CC5500', 'L0 — Deep Recovery')
        l1_html = etf_table(summary.get('l1_etfs', []), '#00B050', 'L1 — Trend Sicuro')
        l2_html = etf_table(summary.get('l2_etfs', []), '#CC8800', 'L2 — Watchlist')
        total   = summary.get('total', 0)

        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 720px; margin: 0 auto;">
          <div style="background: linear-gradient(135deg, #0d1117, #1c2e4a); color: white; padding: 22px; text-align: center;">
            <h1 style="margin: 0; font-size: 20px;">ETF Monitor — Report Giornaliero</h1>
            <p style="margin: 6px 0 0 0; opacity: 0.75; font-size: 13px;">{today} &nbsp;·&nbsp; {total} ETF monitorati</p>
          </div>
          <div style="padding: 20px; background: #f8f9fa;">
            <div style="display:flex;gap:10px;margin-bottom:18px;">
              <div style="flex:1;background:#CC5500;color:white;padding:12px;text-align:center;border-radius:7px;">
                <div style="font-size:22px;font-weight:bold;">{len(summary.get('l0_etfs',[]))}</div><div>L0 Recovery</div>
              </div>
              <div style="flex:1;background:#00B050;color:white;padding:12px;text-align:center;border-radius:7px;">
                <div style="font-size:22px;font-weight:bold;">{len(summary.get('l1_etfs',[]))}</div><div>L1 Trend</div>
              </div>
              <div style="flex:1;background:#CC8800;color:white;padding:12px;text-align:center;border-radius:7px;">
                <div style="font-size:22px;font-weight:bold;">{len(summary.get('l2_etfs',[]))}</div><div>L2 Watchlist</div>
              </div>
            </div>
            {l0_html}{l1_html}{l2_html}
          </div>
          <div style="padding:14px;background:#333;color:#999;text-align:center;font-size:12px;">
            ETF Monitor System &nbsp;·&nbsp; Prossimo aggiornamento ore 18:00
          </div>
        </body>
        </html>"""

        return self._send_email(subject, body_html)

    def send_test_email(self) -> bool:
        """Invia email di test"""
        subject = "Test ETF Monitor System"

        body_html = """
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: #4472C4; color: white; padding: 20px; text-align: center; border-radius: 8px;">
                <h1>Sistema Configurato Correttamente!</h1>
            </div>
            <div style="padding: 20px; background: #f5f5f5; margin-top: 20px; border-radius: 8px;">
                <p>Questa e' un'email di test dal ETF Monitor System.</p>
                <p>Se la ricevi, significa che il sistema di alert e' configurato correttamente.</p>
                <p><strong>Indicatori monitorati:</strong></p>
                <ul>
                    <li>EMA 13 (Exponential Moving Average veloce)</li>
                    <li>SMA 50 (Simple Moving Average lenta)</li>
                    <li>RSI 14 (Relative Strength Index)</li>
                    <li>ADX 14 (Average Directional Index)</li>
                    <li>Volume Ratio (vs media 20 giorni)</li>
                </ul>
            </div>
        </body>
        </html>
        """

        return self._send_email(subject, body_html)


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    alert = AlertSystem()
    alert.send_test_email()
