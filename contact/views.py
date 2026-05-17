from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.core.mail import EmailMultiAlternatives
from django.conf import settings


def send_email(subject, html_content, text_content):
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=['vetpawapp@gmail.com'],
    )
    email.attach_alternative(html_content, "text/html")
    email.send()


def email_template(titulo, filas):
    rows = ''.join([
        f'<tr><td style="padding:8px 0;color:#9ca3af;font-size:13px;width:160px;vertical-align:top">{k}</td>'
        f'<td style="padding:8px 0;color:#1e1b4b;font-size:13px;font-weight:600">{v}</td></tr>'
        for k, v in filas.items() if v
    ])
    return f"""
    <!DOCTYPE html><html><body style="margin:0;padding:0;background:#f4f4f4;font-family:Arial,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:40px 0;">
    <table width="520" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
    <tr><td align="center" style="background:linear-gradient(135deg,#4CAF50,#FF9800);padding:32px 40px;">
    <div style="color:#fff;font-size:26px;font-weight:bold;">🐾 VetPaw</div>
    <div style="color:rgba(255,255,255,0.8);font-size:13px;margin-top:4px;">{titulo}</div>
    </td></tr>
    <tr><td style="padding:36px 40px;">
    <table width="100%" cellpadding="0" cellspacing="0">{rows}</table>
    </td></tr>
    <tr><td align="center" style="background:#f9fafb;padding:20px 40px;border-top:1px solid #e5e7eb;">
    <p style="font-size:12px;color:#9ca3af;margin:0;">© 2026 VetPaw · vetpawapp@gmail.com</p>
    </td></tr>
    </table></td></tr></table></body></html>
    """


@api_view(['POST'])
@permission_classes([AllowAny])
def contacto(request):
    data = request.data
    nombre = data.get('nombre', '')
    email = data.get('email', '')
    asunto = data.get('asunto', 'Sin asunto')
    mensaje = data.get('mensaje', '')

    if not nombre or not email or not mensaje:
        return Response({'error': 'Campos incompletos.'}, status=status.HTTP_400_BAD_REQUEST)

    html = email_template('Nuevo mensaje de contacto', {
        'Nombre': nombre,
        'Email': email,
        'Asunto': asunto,
        'Mensaje': mensaje,
    })
    send_email(f'📬 Contacto VetPaw — {asunto}', html, f'{nombre} ({email}): {mensaje}')
    return Response({'message': 'Mensaje enviado.'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def sumar_veterinaria(request):
    data = request.data
    nombre_clinica = data.get('nombre_clinica', '')
    email = data.get('email', '')
    telefono = data.get('telefono', '')

    if not nombre_clinica or not email or not telefono:
        return Response({'error': 'Campos incompletos.'}, status=status.HTTP_400_BAD_REQUEST)

    html = email_template('Nueva veterinaria quiere sumarse', {
        'Clínica': nombre_clinica,
        'Contacto': data.get('nombre_contacto', ''),
        'Email': email,
        'Teléfono': telefono,
        'Dirección': data.get('direccion', ''),
        'Localidad': data.get('localidad', ''),
        'Provincia': data.get('provincia', ''),
        'Servicios': data.get('servicios', ''),
        'Mensaje': data.get('mensaje', ''),
    })
    send_email(f'🏥 Nueva veterinaria — {nombre_clinica}', html, f'{nombre_clinica} quiere sumarse a VetPaw.')
    return Response({'message': 'Solicitud enviada.'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def anunciante(request):
    data = request.data
    empresa = data.get('empresa', '')
    email = data.get('email', '')
    producto = data.get('producto', '')

    if not empresa or not email or not producto:
        return Response({'error': 'Campos incompletos.'}, status=status.HTTP_400_BAD_REQUEST)

    html = email_template('Nuevo anunciante interesado', {
        'Empresa': empresa,
        'Contacto': data.get('nombre', ''),
        'Email': email,
        'Teléfono': data.get('telefono', ''),
        'Producto': producto,
        'Presupuesto': data.get('presupuesto', ''),
        'Mensaje': data.get('mensaje', ''),
    })
    send_email(f'📣 Nuevo anunciante — {empresa}', html, f'{empresa} quiere anunciar en VetPaw.')
    return Response({'message': 'Solicitud enviada.'}, status=status.HTTP_200_OK)