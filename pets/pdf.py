from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO
from django.utils import timezone
from appointments.models import Visit


def generate_pet_pdf(pet, clinic):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    elements = []

    # Colores
    PRIMARY = colors.HexColor('#1a1a2e')
    ACCENT = colors.HexColor('#4f46e5')
    LIGHT = colors.HexColor('#f4f4fb')
    GRAY = colors.HexColor('#6b7280')

    # Estilos
    title_style = ParagraphStyle('title', fontSize=22, textColor=PRIMARY, fontName='Helvetica-Bold', spaceAfter=6, leading=26)
    subtitle_style = ParagraphStyle('subtitle', fontSize=11, textColor=GRAY, fontName='Helvetica', spaceBefore=4, spaceAfter=2)
    section_style = ParagraphStyle('section', fontSize=13, textColor=ACCENT, fontName='Helvetica-Bold', spaceBefore=16, spaceAfter=6)
    body_style = ParagraphStyle('body', fontSize=10, textColor=PRIMARY, fontName='Helvetica', spaceAfter=4)
    small_style = ParagraphStyle('small', fontSize=9, textColor=GRAY, fontName='Helvetica')

    # Header
    elements.append(Paragraph('VetPaw', title_style))
    elements.append(Paragraph('Historial Clínico Digital', subtitle_style))
    elements.append(Paragraph(f'Emitido por: {clinic.name} — {timezone.now().strftime("%d/%m/%Y")}', small_style))
    elements.append(HRFlowable(width='100%', thickness=2, color=ACCENT, spaceAfter=12))

    # Datos de la mascota
    elements.append(Paragraph('Datos de la Mascota', section_style))
    owner = pet.owner
    species_map = {'dog':'Perro','cat':'Gato','rabbit':'Conejo','bird':'Ave','hamster':'Hamster','reptile':'Reptil','fish':'Pez','other':'Otro'}
    sex_map = {'male':'Macho','female':'Hembra'}

    pet_data = [
        ['Nombre', pet.name, 'Especie', species_map.get(pet.species, pet.species)],
        ['Raza', pet.breed or '—', 'Sexo', sex_map.get(pet.sex, pet.sex)],
        ['Fecha de nacimiento', pet.birth_date.strftime('%d/%m/%Y') if pet.birth_date else '—', 'Peso', f'{pet.weight} kg' if pet.weight else '—'],
        ['Color', pet.color or '—', 'Microchip', pet.microchip or '—'],
        ['Castrado/a', 'Sí' if pet.is_neutered else 'No', 'Alergias', pet.allergies or '—'],
        ['Alimentación', {'balanced':'Balanceada','homemade':'Casera','mixed':'Mixta'}.get(pet.feeding, '—'), 'Hábitat', {'apartment':'Departamento','house':'Casa con patio','field':'Campo'}.get(pet.habitat, '—')],
        ['Convive c/otros animales', 'Sí' if pet.lives_with_animals else 'No', '', ''],
    ]

    pet_table = Table(pet_data, colWidths=[3.5*cm, 5.5*cm, 3.5*cm, 5.5*cm])
    pet_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), LIGHT),
        ('BACKGROUND', (2,0), (2,-1), LIGHT),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TEXTCOLOR', (0,0), (-1,-1), PRIMARY),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#ddddf0')),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white, LIGHT]),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(pet_table)

    # Datos del dueño
    elements.append(Paragraph('Datos del Dueño', section_style))
    owner_data = [
        ['Nombre', f'{owner.first_name} {owner.last_name}'.strip() or owner.username, 'Teléfono', owner.phone or '—'],
        ['Email', owner.email or '—', 'Localidad', f'{owner.locality}, {owner.province}' if owner.locality else '—'],
    ]
    owner_table = Table(owner_data, colWidths=[3.5*cm, 5.5*cm, 3.5*cm, 5.5*cm])
    owner_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), LIGHT),
        ('BACKGROUND', (2,0), (2,-1), LIGHT),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TEXTCOLOR', (0,0), (-1,-1), PRIMARY),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#ddddf0')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(owner_table)

    # Vacunas
    vaccines = pet.vaccines.all()
    elements.append(Paragraph('Historial de Vacunas', section_style))
    if vaccines:
        vac_data = [['Vacuna', 'Fecha', 'Próx. dosis', 'Veterinario', 'Matrícula']]
        for v in vaccines:
            vac_data.append([
                v.name,
                v.date_applied.strftime('%d/%m/%Y'),
                v.next_dose.strftime('%d/%m/%Y') if v.next_dose else '—',
                f'{v.vet_first_name} {v.vet_last_name}'.strip() or '—',
                v.vet_license or '—',
            ])
        vac_table = Table(vac_data, colWidths=[4*cm, 2.5*cm, 2.5*cm, 4.5*cm, 3*cm])
        vac_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), ACCENT),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('TEXTCOLOR', (0,1), (-1,-1), PRIMARY),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#ddddf0')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT]),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(vac_table)
    else:
        elements.append(Paragraph('Sin vacunas registradas.', body_style))

    # Visitas
    visits = pet.visits.all()
    elements.append(Paragraph('Historial de Visitas', section_style))
    if visits:
        for v in visits:
            elements.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#ddddf0'), spaceAfter=4))
            visit_data = [
                ['Fecha', v.date.strftime('%d/%m/%Y %H:%M'), 'Clínica', v.clinic.name if v.clinic else '—'],
                ['Motivo', v.reason, 'Veterinario', f'{v.vet_first_name} {v.vet_last_name} (Mat. {v.vet_license})'],
                ['Diagnóstico', v.diagnosis or '—', 'Tratamiento', v.treatment or '—'],
                ['Observaciones', v.observations or '—', 'Próx. visita', v.next_visit.strftime('%d/%m/%Y') if v.next_visit else '—'],
            ]
            visit_table = Table(visit_data, colWidths=[3*cm, 6*cm, 3*cm, 6*cm])
            visit_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (0,-1), LIGHT),
                ('BACKGROUND', (2,0), (2,-1), LIGHT),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('TEXTCOLOR', (0,0), (-1,-1), PRIMARY),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#ddddf0')),
                ('PADDING', (0,0), (-1,-1), 6),
                ('SPAN', (1,2), (1,2)),
                ('SPAN', (3,2), (3,2)),
            ]))
            elements.append(visit_table)
            elements.append(Spacer(1, 6))
    else:
        elements.append(Paragraph('Sin visitas registradas.', body_style))

    # Footer
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