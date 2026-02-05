"""
alerts.py - Sistema di notifiche email per alert ETF
=====================================================
Gestisce l'invio di email per:
- Alert di acquisto (segnali BUY)
- Alert di vendita (segnali SELL)
- Report giornaliero
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict
import os


class AlertSystem:
    """Sistema di alert via email per ETF"""

    def __init__(self, sender_email: str = None, sender_password: str = None,
                 recipient_email: str = None):
        self.sender_email = sender_email or os.getenv('EMAIL_SENDER', '')
        self.sender_password = sender_password or os.getenv('EMAIL_PASSWORD', '')
        self.recipient_email = recipient_email or os.getenv('EMAIL_RECIPIENT', 'andreapavan67@gmail.com')

        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

    def _send_email(self, subject: str, body_html: str, body_text: str = None) -> bool:
        """Invia email via SMTP"""
        if not all([self.sender_email, self.sender_password, self.recipient_email]):
            print(f"Configurazione email incompleta - email non inviata")
            print(f"   Subject: {subject}")
            return False

        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = self.recipient_email

            if body_text:
                part1 = MIMEText(body_text, "plain")
                message.attach(part1)

            part2 = MIMEText(body_html, "html")
            message.attach(part2)

            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, self.recipient_email, message.as_string())

            print(f"Email inviata: {subject}")
            return True

        except Exception as e:
            print(f"Errore invio email: {e}")
            return False

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
        """Invia report giornaliero con riepilogo ETF"""
        subject = f"Report Giornaliero ETF - {datetime.now().strftime('%d/%m/%Y')}"

        level_tables = ""
        for level in [1, 2, 3]:
            etfs = summary.get(f'level_{level}', [])
            if etfs:
                level_name = 'Livello 1 - BUY Alert' if level == 1 else 'Livello 2 - Watchlist' if level == 2 else 'Livello 3 - Universe'
                bg_color = '#00B050' if level == 1 else '#FFC000' if level == 2 else '#4472C4'
                level_tables += f"""
                <h3>{level_name}</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                    <tr style="background: {bg_color}; color: white;">
                        <th style="padding: 8px; border: 1px solid #ddd;">ETF</th>
                        <th style="padding: 8px; border: 1px solid #ddd;">Prezzo</th>
                        <th style="padding: 8px; border: 1px solid #ddd;">RSI</th>
                        <th style="padding: 8px; border: 1px solid #ddd;">ADX</th>
                        <th style="padding: 8px; border: 1px solid #ddd;">Segnale</th>
                    </tr>
                """
                for f in etfs[:10]:
                    signal_color = '#00B050' if f.get('signal') == 'BUY' else '#DC3545' if f.get('signal') == 'SELL' else '#FFC000'
                    price_str = f"{f['price']:.2f}" if f.get('price') else '-'
                    rsi_str = f"{f['rsi']:.0f}" if f.get('rsi') else '-'
                    adx_str = f"{f['adx']:.0f}" if f.get('adx') else '-'
                    level_tables += f"""
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;">{f.get('nome', f.get('ticker', ''))[:35]}</td>
                        <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">{price_str}</td>
                        <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{rsi_str}</td>
                        <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{adx_str}</td>
                        <td style="padding: 8px; border: 1px solid #ddd; text-align: center; background: {signal_color}; color: white;">{f.get('signal', 'HOLD')}</td>
                    </tr>
                    """
                level_tables += "</table>"

        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #1F4E79, #2E75B6); color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">Report Giornaliero ETF</h1>
                <p style="margin: 5px 0 0 0;">{datetime.now().strftime('%A %d %B %Y')}</p>
            </div>

            <div style="padding: 20px; background: #f5f5f5;">
                <h2 style="color: #1F4E79;">Riepilogo</h2>

                <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                    <div style="flex: 1; background: #00B050; color: white; padding: 15px; text-align: center; border-radius: 8px;">
                        <div style="font-size: 24px; font-weight: bold;">{summary.get('buy_signals', 0)}</div>
                        <div>BUY</div>
                    </div>
                    <div style="flex: 1; background: #FFC000; padding: 15px; text-align: center; border-radius: 8px;">
                        <div style="font-size: 24px; font-weight: bold;">{summary.get('hold_signals', 0)}</div>
                        <div>HOLD</div>
                    </div>
                    <div style="flex: 1; background: #DC3545; color: white; padding: 15px; text-align: center; border-radius: 8px;">
                        <div style="font-size: 24px; font-weight: bold;">{summary.get('sell_signals', 0)}</div>
                        <div>SELL</div>
                    </div>
                </div>

                {level_tables}
            </div>

            <div style="padding: 15px; background: #333; color: #999; text-align: center; font-size: 12px;">
                ETF Monitor System - Prossimo aggiornamento ore 18:00
            </div>
        </body>
        </html>
        """

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
    alert = AlertSystem()
    alert.send_test_email()
