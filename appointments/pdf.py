from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER
from io import BytesIO
from django.utils import timezone
from datetime import timezone as tz
import pytz


def generate_agenda_pdf(clinic, appointments, date):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    PRIMARY = colors.HexColor('#1a1a2e')
    ACCENT  = colors.HexColor('#4f46e5')
    LIGHT   = colors.HexColor('#f4f4fb')
    GRAY    = colors.HexColor('#6b7280')

    styles = getSampleStyleSheet()
    title_style   = ParagraphStyle('title',    fontSize=22, textColor=PRIMARY, fontName='Helvetica-Bold', spaceAfter=4, leading=26)
    subtitle_style = ParagraphStyle('subtitle', fontSize=11, textColor=GRAY,    fontName='Helvetica', spaceAfter=2)
    small_style   = ParagraphStyle('small',    fontSize=9,  textColor=GRAY,    fontName='Helvetica')
    section_style = ParagraphStyle('section',  fontSize=13, textColor=ACCENT,  fontName='Helvetica-Bold', spaceBefore=16, spaceAfter=6)
    body_style    = ParagraphStyle('body',     fontSize=10, textColor=PRIMARY,  fontName='Helvetica', spaceAfter=4)

    STATUS_MAP = {
        'pending':   'Pendiente',
        'confirmed': 'Confirmado',
        'cancelled': 'Cancelado',
        'completed': 'Realizado',
        'no_show':   'Ausente',
    }

    elements = []

    import os
    from reportlab.platypus import Image as RLImage
    logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'logo_vetpaw.png')
    if os.path.exists(logo_path):
        logo = RLImage(logo_path, width=2.5*cm, height=2.5*cm)
        logo.hAlign = 'RIGHT'
        elements.append(logo)
    elements.append(Paragraph('VetPaw', title_style))
    elements.append(Paragraph('Agenda Diaria', subtitle_style))
    elements.append(Paragraph(f'{clinic.name} — {date.strftime("%d/%m/%Y")}', small_style))
    elements.append(HRFlowable(width='100%', thickness=2, color=ACCENT, spaceAfter=12))

    DIAS = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
    MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']
    dia_nombre = DIAS[date.weekday()]
    mes_nombre = MESES[date.month - 1]
    elements.append(Paragraph(f'Agenda del {dia_nombre} {date.day} de {mes_nombre} de {date.year}', section_style))

    if not appointments:
        elements.append(Paragraph('No hay turnos registrados para este día.', body_style))
    else:
        data = [['Hora', 'Mascota', 'Dueño', 'Motivo', 'Estado']]
        for appt in appointments:
            argentina = pytz.timezone('America/Argentina/Buenos_Aires')
            hora = appt.requested_date.astimezone(argentina).strftime('%H:%M')
            mascota = getattr(appt.pet, 'name', '—')
            dueno = appt.owner.get_full_name() or appt.owner.username
            motivo = appt.reason or '—'
            estado = STATUS_MAP.get(appt.status, appt.status)
            data.append([hora, mascota, dueno, motivo, estado])

        table = Table(data, colWidths=[2*cm, 3.5*cm, 4*cm, 5*cm, 3*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), ACCENT),
            ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0,0), (-1,-1), 9),
            ('TEXTCOLOR',  (0,1), (-1,-1), PRIMARY),
            ('GRID',       (0,0), (-1,-1), 0.5, colors.HexColor('#ddddf0')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT]),
            ('PADDING',    (0,0), (-1,-1), 6),
        ]))
        elements.append(table)

    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width='100%', thickness=1, color=ACCENT))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        f'Documento generado por VetPaw — {clinic.name} — {timezone.now().strftime("%d/%m/%Y %H:%M")} hs',
        ParagraphStyle('footer', fontSize=8, textColor=GRAY, alignment=TA_CENTER)
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer