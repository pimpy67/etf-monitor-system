"""
pdf_generator.py — Generatore PDF Parametri di Riferimento
===========================================================
Genera PDF lato server dai parametri YAML — sempre sincronizzato.
Rigenerato automaticamente quando:
  1. Il monitor gira (monitor.py chiama generate_parameters_pdf())
  2. Il YAML viene modificato (auto-detect via timestamp)

Questo garantisce che il PDF scaricato è SEMPRE coerente con il codice.
"""

import os
import yaml
from datetime import datetime
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfgen import canvas


def load_yaml_config():
    """Carica config/etf_families.yaml — fonte di verità."""
    try:
        with open('config/etf_families.yaml', 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        raise Exception(f"Errore caricamento YAML: {e}")


def generate_parameters_pdf(output_path='data/ETF_Monitor_Parametri_Riferimento.pdf'):
    """
    Genera il PDF dei parametri direttamente dal YAML.
    Chiamato da:
      - monitor.py::ETFMonitor.run() — alla fine di ogni monitor
      - app.py::startup — all'avvio dell'app
    """
    config = load_yaml_config()
    families = config.get('families', {})

    # Crea PDF
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=15*mm,
        bottomMargin=15*mm,
        leftMargin=12*mm,
        rightMargin=12*mm
    )

    # Stili — Tema LIGHT (stampa senza sprecare inchiostro)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#000000'),
        spaceAfter=10,
        fontName='Helvetica-Bold'
    )

    heading_style = ParagraphStyle(
        'FamilyHeading',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=8,
        fontName='Helvetica-Bold',
        borderPadding=6,
        backColor=colors.HexColor('#f0f4f8')
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=9,
        textColor=colors.HexColor('#000000'),
        leading=12
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

    # Titolo
    story.append(Paragraph(
        "⚙️ Parametri di Riferimento — ETF Monitor System",
        title_style
    ))

    # Timestamp
    story.append(Paragraph(
        f"<i>Generato automaticamente: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</i><br/>"
        f"<b>Fonte di verità:</b> config/etf_families.yaml",
        small_style
    ))
    story.append(Spacer(1, 10))

    # Intro
    story.append(Paragraph(
        "<b>Nota:</b> Questo PDF è generato automaticamente dal file config/etf_families.yaml. "
        "Qualsiasi modifica al codice che cambii i parametri viene sincronizzata qui automaticamente "
        "al prossimo ciclo del monitor. Il PDF è sempre coerente con la versione live del sistema.",
        small_style
    ))
    story.append(Spacer(1, 15))

    # Per ogni famiglia, crea una tabella
    for family_name, params in families.items():
        story.append(Paragraph(f"<b>{params.get('description', family_name)}</b>", heading_style))

        # Costruisci righe della tabella
        table_data = [['Parametro', 'Valore']]

        # Parametri L1 Entry
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

        ema_slope = params.get('ema20_slope_min')
        if ema_slope is not None:
            table_data.append(['EMA20 Slope Min', f'{ema_slope:.2f}%'])  # Già percentuale nel YAML

        ema_dist = params.get('ema_dist_max')
        if ema_dist is not None:
            table_data.append(['Dist EMA20 Max', f'{ema_dist:.1f}%'])  # Già percentuale nel YAML

        # Parametri L0
        l0_dd = params.get('l0_drawdown')
        if l0_dd is not None:
            table_data.append(['L0 Drawdown', f'{l0_dd}%'])

        l0_rsi = params.get('l0_rsi_max')
        if l0_rsi is not None:
            table_data.append(['L0 RSI Max', f'{l0_rsi}'])

        # Stop Loss
        sl_initial = params.get('sl_initial_pct')
        if sl_initial is not None:
            table_data.append(['SL Initial %', f'{sl_initial*100:.1f}%'])

        sl_buffer = params.get('sl_buffer_wide')
        if sl_buffer is not None:
            table_data.append(['SL Buffer Wide', f'{sl_buffer*100:.1f}%'])

        # Trailing Stop
        trailing_base = params.get('trailing_base_pct')
        if trailing_base is not None:
            table_data.append(['Trailing Base %', f'{trailing_base*100:.1f}%'])

        trailing_min = params.get('trailing_min_pct')
        if trailing_min is not None:
            table_data.append(['Trailing Min %', f'{trailing_min*100:.1f}%'])

        # Stop Gain (STEP 2)
        sg_target = params.get('sg_target_pct')
        if sg_target is not None:
            table_data.append(['Stop-Gain Target', f'{sg_target*100:.1f}%'])

        # Crea tabella — Tema LIGHT (stampa)
        table = Table(table_data, colWidths=[80*mm, 50*mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8eef7')),  # Grigio-blu chiarissimo
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1a5490')),    # Blu scuro
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d0d8e8')),   # Grigio-blu leggero
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#f5f8fc')]),  # Bianco e grigio chiarissimo
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#000000')),   # Nero
        ]))

        story.append(table)
        story.append(Spacer(1, 12))

    # Footnote
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "<b>Regola di Sincronizzazione (CLAUDEMD):</b><br/>"
        "Ogni modifica ai parametri nel codice (YAML, technical_analysis.py, monitor.py) "
        "genera automaticamente un nuovo PDF. Non modificare il PDF manualmente. "
        "La fonte di verità è sempre config/etf_families.yaml.",
        small_style
    ))

    # Scrivi PDF
    doc.build(story)
    print(f"✅ PDF generato: {output_path}")


if __name__ == '__main__':
    generate_parameters_pdf()
