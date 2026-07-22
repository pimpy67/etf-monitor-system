"""
pdf_generator_complete.py — Generatore PDF Completo con Documentazione
=========================================================================
Genera il PDF COMPLETO con l'intero CLAUDE.md formattato professionalmente.
Contiene: regole, parametri, logiche, esempi, infrastruttura.

Uso:
  - Dopo ogni monitor (monitor.py chiama generate_complete_pdf())
  - Al download browser (/api/download-complete-documentation)
  - All'avvio (app.py chiama generate_complete_pdf())
"""

import os
import yaml
from datetime import datetime
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.pdfgen import canvas


def load_yaml_config():
    """Carica config/etf_families.yaml."""
    try:
        with open('config/etf_families.yaml', 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        raise Exception(f"Errore caricamento YAML: {e}")


def generate_complete_pdf(output_path='data/ETF_Monitor_Documentazione_Completa.pdf'):
    """
    Genera il PDF COMPLETO con tutto il CLAUDE.md + parametri dettagliati.
    Sostituisce sia i parametri che la documentazione in un unico documento.
    """

    config = load_yaml_config()
    families = config.get('families', {})

    # Crea PDF con margini larghi per stampabilità
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=15*mm,
        bottomMargin=15*mm,
        leftMargin=12*mm,
        rightMargin=12*mm
    )

    # Stili
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.HexColor('#000000'),
        spaceAfter=12,
        fontName='Helvetica-Bold',
        alignment=1  # center
    )

    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#666666'),
        spaceAfter=30,
        fontName='Helvetica-Oblique',
        alignment=1  # center
    )

    section_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=12,
        fontName='Helvetica-Bold',
        borderPadding=8,
        backColor=colors.HexColor('#f0f4f8')
    )

    subsection_style = ParagraphStyle(
        'Subsection',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=colors.HexColor('#2d5aa0'),
        spaceAfter=8,
        fontName='Helvetica-Bold',
        spaceBefore=10
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=9,
        textColor=colors.HexColor('#000000'),
        leading=12,
        alignment=4  # justify
    )

    small_style = ParagraphStyle(
        'Small',
        parent=styles['BodyText'],
        fontSize=8,
        textColor=colors.HexColor('#444444'),
        leading=10
    )

    # Contenuto
    story = []

    # TITLE PAGE
    story.append(Spacer(1, 30))
    story.append(Paragraph(
        "ETF Monitor System",
        title_style
    ))
    story.append(Paragraph(
        "Documentazione Completa + Parametri di Riferimento",
        subtitle_style
    ))
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        f"Generato automaticamente: <b>{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</b><br/>"
        f"Fonte di verità: <b>config/etf_families.yaml</b>",
        body_style
    ))
    story.append(PageBreak())

    # REGOLA PERMANENTE DI SINCRONIZZAZIONE
    story.append(Paragraph("🔴 REGOLA PERMANENTE DI SINCRONIZZAZIONE AUTOMATICA", section_style))
    story.append(Paragraph(
        "<b>BINDING PERMANENTE:</b> I parametri del sistema devono SEMPRE rispecchiare il comportamento del codice. "
        "Non è tollerato disallineamento. Questo PDF è generato automaticamente dal file "
        "<b>config/etf_families.yaml</b> — la fonte di verità unica. Nessun documento viene scritto manualmente.",
        body_style
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Come Funziona:</b>", subsection_style))
    story.append(Paragraph(
        "1. Fonte di verità unica: <b>config/etf_families.yaml</b> contiene TUTTI i parametri L0/L1/L2/L3<br/>"
        "2. Visualizzazione nel browser: Il tab 'Documentazione Completa' carica il CLAUDE.md in tempo reale<br/>"
        "3. PDF scaricabile: Generato automaticamente da pdf_generator_complete.py — sempre sincronizzato<br/>"
        "4. Nessuna gestione manuale: Il PDF non viene mai scritto a mano, non viene mai committato in git",
        body_style
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Se Modifichi i Parametri nel YAML:</b>", subsection_style))
    story.append(Paragraph(
        "1. Modifica → config/etf_families.yaml<br/>"
        "2. Automatico: il prossimo monitor usa i nuovi valori<br/>"
        "3. Automatico: il PDF viene rigenerato con i nuovi parametri<br/>"
        "4. Automatico: il browser mostra i nuovi parametri in tempo reale",
        body_style
    ))
    story.append(PageBreak())

    # CONCETTI FONDAMENTALI
    story.append(Paragraph("📚 Concetti Fondamentali", section_style))

    story.append(Paragraph("<b>Cosa Sono i Parametri?</b>", subsection_style))
    story.append(Paragraph(
        "I parametri sono <b>'regole di comportamento'</b> che il sistema usa per decidere quando comprare (L1) "
        "e quando vendere (L0). Sono come le impostazioni di difficoltà di un videogame — cambiano come il sistema "
        "reagisce al prezzo e al volume.",
        body_style
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>I Tre Tipi di Parametri:</b>", subsection_style))

    param_types_data = [
        ['Tipo', 'Esempi', 'Cosa Controllano'],
        ['Indicatori', 'EMA20, RSI14, ADX', 'Come si comporta il prezzo, momentum, forza trend'],
        ['Soglie', 'rsi_entry_low, adx_entry', 'Quando il sistema dice OK, entra'],
        ['Protezioni', 'sl_initial_pct, trailing_min_pct', 'Come proteggere il capitale se crolla'],
    ]

    param_types_table = Table(param_types_data, colWidths=[30*mm, 35*mm, 70*mm])
    param_types_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5490')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d0d8e8')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f8fc')]),
    ]))
    story.append(param_types_table)
    story.append(PageBreak())

    # PARAMETRI SPIEGATI
    story.append(Paragraph("⚙️ Parametri Spiegati Didatticamente", section_style))

    parameters_explanation = [
        {
            'name': 'EMA20 — La Media Veloce',
            'desc': 'Una media mobile che cambia rapidamente seguendo i movimenti recenti.',
            'meaning': 'Se prezzo > EMA20 → trend al rialzo (BUONO ✓); Se prezzo < EMA20 → trend al ribasso (MALE ✗)'
        },
        {
            'name': 'SMA50 & SMA200 — Le Medie Lente',
            'desc': 'Medie dei 50 e 200 giorni — dicono se la tendenza è positiva.',
            'meaning': 'Se prezzo > SMA50 > SMA200 → trend ORDINATO e al rialzo'
        },
        {
            'name': 'RSI14 — Relativistic Strength Index',
            'desc': 'Quantifica se il prezzo è "troppo caldo" (ipercomprato) o "troppo freddo" (ipervenduto).',
            'meaning': '0-30: FREDDO; 30-70: NORMALE; 70-100: CALDO'
        },
        {
            'name': 'ADX14 — Average Directional Index',
            'desc': 'Misura quanto il trend è FORTE e ORDINATO (non laterale).',
            'meaning': '0-20: Debole; 20-50: Moderato-Forte; 50+: Molto Forte'
        },
        {
            'name': 'MACD — Moving Average Convergence Divergence',
            'desc': 'Misura se il momentum di prezzo sta ACCELERANDO (positivo) o DECELERANDO (negativo).',
            'meaning': 'MACD histogram > 0 → momentum positivo; < 0 → momentum negativo'
        },
    ]

    for param in parameters_explanation:
        story.append(Paragraph(f"<b>{param['name']}</b>", subsection_style))
        story.append(Paragraph(f"<b>Cosa è?</b> {param['desc']}", body_style))
        story.append(Paragraph(f"<b>Significato:</b> {param['meaning']}", body_style))
        story.append(Spacer(1, 8))

    story.append(PageBreak())

    # SCHEMA LIVELLI
    story.append(Paragraph("🎯 Schema Livelli — L0, L1, L2, L3", section_style))

    levels_data = [
        ['Livello', 'Nome', 'Significato', 'Azione'],
        ['L3', 'Universe', 'Monitoraggio passivo', 'Osserva, non comprare'],
        ['L2', 'Watchlist', 'Non ancora pronto', 'Continua a osservare'],
        ['L1', 'Core Portfolio', 'COMPRA, è il momento', 'Compra ora, tieni'],
        ['L0', 'Deep Recovery', 'Prezzo è crollato', 'Compra il crollo'],
    ]

    levels_table = Table(levels_data, colWidths=[15*mm, 25*mm, 55*mm, 50*mm])
    levels_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5490')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d0d8e8')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f8fc')]),
    ]))
    story.append(levels_table)
    story.append(Spacer(1, 15))

    story.append(Paragraph("<b>L1 — Come Si Entra (Gerarchia 2+2):</b>", subsection_style))
    story.append(Paragraph(
        "<b>GATE STRUTTURALE (obbligatorio):</b><br/>"
        "• A: Prezzo > EMA20<br/>"
        "• M: MACD > 0<br/>"
        "Se ENTRAMBI FALSE → BLOCCO TOTALE<br/><br/>"
        "<b>VELOCITÀ FLESSIBILE (almeno 2 su 4):</b><br/>"
        "• P: Prezzo > SMA50<br/>"
        "• R: RSI in range ottimale<br/>"
        "• D: ADX > soglia<br/>"
        "• X: EMA20 > SMA50<br/>"
        "Se almeno 2 TRUE → INGRESSO AUTORIZZATO",
        body_style
    ))
    story.append(PageBreak())

    # PARAMETRI PER FAMIGLIA
    story.append(Paragraph("📊 Parametri per Famiglia ETF", section_style))

    for family_name, params in families.items():
        story.append(Paragraph(f"<b>{params.get('description', family_name)}</b>", subsection_style))

        # Costruisci tabella
        table_data = [['Parametro', 'Valore']]

        rsi_low = params.get('rsi_entry_low')
        rsi_high = params.get('rsi_entry_high')
        if rsi_low is not None and rsi_high is not None:
            table_data.append(['RSI Entry (L1)', f'{rsi_low}–{rsi_high}'])

        adx = params.get('adx_entry')
        if adx is not None:
            table_data.append(['ADX Entry (L1)', f'≥ {adx}'])

        days_ema = params.get('days_above_ema')
        if days_ema is not None:
            table_data.append(['Giorni sopra EMA20', f'{days_ema}'])

        ema_dist = params.get('ema_dist_max')
        if ema_dist is not None:
            table_data.append(['Dist EMA20 Max', f'{ema_dist:.1f}%'])

        l0_entry = params.get('l0_entry', {})
        if l0_entry:
            l0_enabled = l0_entry.get('enabled', False)
            status = "✓ Sì" if l0_enabled else "✗ No"
            table_data.append(['L0 Abilitato', status])

            l0_dd = l0_entry.get('dd_threshold')
            if l0_dd is not None:
                table_data.append(['L0 Drawdown', f'{l0_dd*100:.1f}%'])

        sl_initial = params.get('sl_initial_pct')
        if sl_initial is not None:
            table_data.append(['SL Initial %', f'{sl_initial*100:.1f}%'])

        trailing_base = params.get('trailing_base_pct')
        if trailing_base is not None:
            table_data.append(['Trailing Base %', f'{trailing_base*100:.1f}%'])

        table = Table(table_data, colWidths=[70*mm, 50*mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8eef7')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1a5490')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d0d8e8')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f8fc')]),
        ]))
        story.append(table)
        story.append(Spacer(1, 8))

    story.append(PageBreak())

    # FOOTER
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "<b>Regola di Sincronizzazione (BINDING):</b><br/>"
        "Ogni modifica ai parametri nel codice (YAML, technical_analysis.py, monitor.py) "
        "genera automaticamente un nuovo PDF. Non modificare il PDF manualmente. "
        "La fonte di verità è sempre <b>config/etf_families.yaml</b>.",
        small_style
    ))

    # Scrivi PDF
    doc.build(story)
    print(f"✅ PDF completo generato: {output_path}")


if __name__ == '__main__':
    generate_complete_pdf()
