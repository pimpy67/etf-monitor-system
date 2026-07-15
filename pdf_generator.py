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
        "<b>STEP 3 v3.0 — Architettura a Due Marce:</b>",
        heading_style
    ))
    story.append(Paragraph(
        "<b>🚀 MARCIA 1 — Rally Veloci (L1 + Stop Gain Dinamico):</b><br/>"
        "Cattura i rally di breve termine con uscita intelligente basata sulla pendenza (slope) della EMA20. "
        "Il target si contrae automaticamente se il momentum rallenta, evitando di rimanere intrappolati con profitti che svaniscono. "
        "Parametri: target_max_pct (ideale), target_floor_pct (protezione minima), slope_window (giorni di lookback), slope_sensitivity (reattività).",
        small_style
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph(
        "<b>🐢 MARCIA 2 — Recuperi dai Minimi (L0 Pragmatico):</b><br/>"
        "Entra sui veri minimi con conferma di ripresa. Usa drawdown realistico (6-10%), RSI moderato (non panico), "
        "e rimbalzo minimo verificato. Disabilitato per strumenti troppo rischiosi (leva, monetario). "
        "Parametri: dd_threshold (% sotto picco), rsi_max (soglia RSI), recovery_min_pct (rimbalzo minimo), ema_fast_period (media veloce).",
        small_style
    ))
    story.append(Spacer(1, 15))

    story.append(Paragraph(
        "<b>Nota:</b> Questo PDF è generato automaticamente dal file config/etf_families.yaml. "
        "Qualsiasi modifica ai parametri viene sincronizzata qui automaticamente al prossimo ciclo del monitor.",
        small_style
    ))
    story.append(Spacer(1, 20))

    # Sezione L1 — Marcia 1
    story.append(Paragraph(
        "<b>═══ MARCIA 1 — L1 CORE PORTFOLIO (RALLY VELOCI) ═══</b>",
        heading_style
    ))
    story.append(Paragraph(
        "<b>Logica di Entrata (6 Condizioni Rigorose):</b><br/>"
        "1. <b>Allineamento</b>: price > EMA20 > SMA50 (prezzo ben posizionato)<br/>"
        "2. <b>Persistenza</b>: days_above_EMA20 ≥ 3, slope(EMA20) > 0 (movimento confermato)<br/>"
        "3. <b>RSI ottimale</b>: entro range configurato per famiglia (momentum positivo non ancora esausto)<br/>"
        "4. <b>Distanza EMA20</b>: 0–4% massimo (non troppo esteso da EMA20)<br/>"
        "5. <b>ADX</b>: ≥ soglia (forza direzionale, es. 22 equity, 15 bond)<br/>"
        "6. <b>MACD momentum</b>: positivo e confermato (volume spike)<br/>"
        "<br/>"
        "<b>Stop Gain Dinamico (NEW — STEP 3 v3.0):</b><br/>"
        "Quando il prezzo entra in L1, il sistema monitora continuamente la pendenza della EMA20. "
        "Se il momentum rallenta (slope diminuisce), il target di profitto si contrae automaticamente per cogliere il punto di uscita ottimale "
        "senza aspettare che il trend si inverta completamente. "
        "<br/><br/>"
        "<i>Parametri</i>: target_max_pct = profitto ideale se trend accelera; target_floor_pct = minimo garantito; "
        "slope_window = giorni osservati per calcolare la pendenza (es. 7gg); slope_sensitivity = fattore di reattività (es. 0.002).",
        small_style
    ))
    story.append(Spacer(1, 15))

    # Sezione L0 — Marcia 2
    story.append(Paragraph(
        "<b>═══ MARCIA 2 — L0 DEEP RECOVERY (RECUPERI DAI MINIMI) ═══</b>",
        heading_style
    ))
    story.append(Paragraph(
        "<b>Logica di Entrata (4 Condizioni Tutte Obbligatorie):</b><br/>"
        "1. <b>Drawdown significativo</b>: almeno X% sotto il picco storico (es. 6.5% equity, 25% crypto)<br/>"
        "2. <b>Ipervenduto moderato</b>: RSI < X (es. 45 equity, 38 crypto — non panico puro, momentum esausto)<br/>"
        "3. <b>Divergenza rialzista</b>: prezzo fa minimo più basso ma RSI fa minimo più alto (conferma che pressione di vendita sta esaurendo)<br/>"
        "4. <b>Segnale di ripresa</b>: RSI rimbalza > 32 OPPURE micro-breakout ≥ 0.3% su 5 giorni (conferma il recupero inizia)<br/>"
        "<br/>"
        "<b>Pragmatismo Calibrato:</b><br/>"
        "I parametri sono stati settati per catturare le correzioni normali (6-10% su equity, 25% su crypto), "
        "non solo crash catastrofici. L0 è disabilitato per leva (troppo rischioso) e monetario (nessuna logic recovery). "
        "Consente di trovare vere opportunità di rimbalzo senza aspettare il panico totale.",
        small_style
    ))
    story.append(Spacer(1, 15))

    # Titolo sezione parametri
    story.append(Paragraph(
        "<b>═══ PARAMETRI PER FAMIGLIA ETF ═══</b>",
        heading_style
    ))
    story.append(Spacer(1, 12))

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

        # Parametri L0 Entry — STEP 3 v3.0 Pragmatico
        l0_entry = params.get('l0_entry', {})
        if l0_entry:
            l0_enabled = l0_entry.get('enabled', False)
            status = "✓ Abilitato" if l0_enabled else "✗ Disabilitato"
            table_data.append(['L0 Stato', status])

            l0_dd = l0_entry.get('dd_threshold')
            if l0_dd is not None:
                table_data.append(['L0 Drawdown (dd_threshold)', f'{l0_dd*100:.1f}%'])

            l0_rsi = l0_entry.get('rsi_max')
            if l0_rsi is not None:
                table_data.append(['L0 RSI Max', f'{l0_rsi}'])

            l0_recovery = l0_entry.get('recovery_min_pct')
            if l0_recovery is not None:
                table_data.append(['L0 Recovery Min', f'{l0_recovery*100:.1f}%'])

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

        # Stop Gain Dinamico (STEP 3 v3.0 — Marcia 1)
        sg_dynamic = params.get('l1_stop_gain_dynamic', {})
        if sg_dynamic:
            sg_max = sg_dynamic.get('target_max_pct')
            if sg_max is not None:
                table_data.append(['SG Target Max (dinamico)', f'{sg_max*100:.1f}%'])

            sg_floor = sg_dynamic.get('target_floor_pct')
            if sg_floor is not None:
                table_data.append(['SG Target Floor (minimo)', f'{sg_floor*100:.1f}%'])

            sg_slope_window = sg_dynamic.get('slope_window')
            if sg_slope_window is not None:
                table_data.append(['SG Slope Window (gg)', f'{sg_slope_window}'])

            sg_sensitivity = sg_dynamic.get('slope_sensitivity')
            if sg_sensitivity is not None:
                table_data.append(['SG Slope Sensitivity', f'{sg_sensitivity}'])

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
