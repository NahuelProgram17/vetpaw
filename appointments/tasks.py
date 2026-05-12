import logging
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from datetime import timedelta

logger = logging.getLogger(__name__)


def send_appointment_reminders():
    from .models import Appointment
    now = timezone.now()
    window_start = now + timedelta(hours=23)
    window_end = now + timedelta(hours=24)

    appointments = Appointment.objects.filter(
        requested_date__gte=window_start,
        requested_date__lt=window_end,
        status__in=['pending', 'confirmed'],
    ).select_related('owner', 'pet', 'clinic')

    for appt in appointments:
        owner = appt.owner
        if not owner.email:
            continue

        fecha = appt.requested_date.strftime('%A %d de %B de %Y')
        hora = appt.requested_date.strftime('%H:%M')
        clinica = appt.clinic.name
        mascota = appt.pet.name
        motivo = appt.reason

        html = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin:0;padding:0;background:#f4f4f4;font-family:Arial,sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr><td align="center" style="padding:40px 0;">
            <table width="520" cellpadding="0" cellspacing="0"
                style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                <tr>
                    <td align="center" style="background:#4f46e5;padding:32px 40px;">
                        <div style="font-size:36px;">🐾</div>
                        <div style="color:#ffffff;font-size:26px;font-weight:bold;margin-top:8px;">VetPaw</div>
                        <div style="color:#c7d2fe;font-size:13px;margin-top:4px;">Recordatorio de turno</div>
                    </td>
                </tr>
                <tr>
                    <td style="padding:36px 40px;">
                        <p style="font-size:18px;font-weight:bold;color:#1e1b4b;margin:0 0 12px;">
                            ¡Hola, {owner.first_name or owner.username}! 👋
                        </p>
                        <p style="font-size:15px;color:#4b5563;line-height:1.6;margin:0 0 24px;">
                            Te recordamos que tenés un turno programado:
                        </p>
                        <table width="100%" cellpadding="0" cellspacing="0"
                            style="background:#f5f3ff;border-radius:10px;padding:20px;margin-bottom:24px;">
                            <tr><td style="padding:8px 20px;">
                                <p style="margin:0;font-size:14px;color:#6b7280;">📅 Fecha</p>
                                <p style="margin:4px 0 0;font-size:16px;font-weight:bold;color:#1e1b4b;">{fecha}</p>
                            </td></tr>
                            <tr><td style="padding:8px 20px;">
                                <p style="margin:0;font-size:14px;color:#6b7280;">🕐 Hora</p>
                                <p style="margin:4px 0 0;font-size:16px;font-weight:bold;color:#1e1b4b;">{hora} hs</p>
                            </td></tr>
                            <tr><td style="padding:8px 20px;">
                                <p style="margin:0;font-size:14px;color:#6b7280;">🏥 Clínica</p>
                                <p style="margin:4px 0 0;font-size:16px;font-weight:bold;color:#1e1b4b;">{clinica}</p>
                            </td></tr>
                            <tr><td style="padding:8px 20px;">
                                <p style="margin:0;font-size:14px;color:#6b7280;">🐾 Mascota</p>
                                <p style="margin:4px 0 0;font-size:16px;font-weight:bold;color:#1e1b4b;">{mascota}</p>
                            </td></tr>
                            <tr><td style="padding:8px 20px;">
                                <p style="margin:0;font-size:14px;color:#6b7280;">📋 Motivo</p>
                                <p style="margin:4px 0 0;font-size:16px;font-weight:bold;color:#1e1b4b;">{motivo}</p>
                            </td></tr>
                        </table>
                        <p style="font-size:13px;color:#9ca3af;text-align:center;margin:0;">
                            Recordá que podés cancelar el turno hasta 24hs antes desde la app.
                        </p>
                    </td>
                </tr>
                <tr>
                    <td align="center" style="background:#f9fafb;padding:20px 40px;border-top:1px solid #e5e7eb;">
                        <p style="font-size:12px;color:#9ca3af;margin:0;">© 2025 VetPaw · Todos los derechos reservados 🐾</p>
                    </td>
                </tr>
            </table>
            </td></tr>
        </table>
        </body>
        </html>
        """

        text = f"Recordatorio VetPaw: tenés turno el {fecha} a las {hora} hs en {clinica} con {mascota}. Motivo: {motivo}."

        try:
            msg = EmailMultiAlternatives(
                subject=f'🐾 Recordatorio de turno — {fecha}',
                body=text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[owner.email],
            )
            msg.attach_alternative(html, "text/html")
            msg.send()
            logger.info(f"Recordatorio enviado a {owner.email} para turno {appt.id}")
        except Exception as e:
            logger.error(f"Error enviando recordatorio turno {appt.id}: {e}")


def send_vaccine_reminders():
    from pets.models import Vaccine
    today = timezone.now().date()
    target = today + timedelta(days=7)

    vaccines = Vaccine.objects.filter(
        next_dose=target,
    ).select_related('pet__owner', 'clinic')

    for vaccine in vaccines:
        owner = vaccine.pet.owner
        if not owner.email:
            continue

        mascota = vaccine.pet.name
        vacuna = vaccine.name
        fecha = vaccine.next_dose.strftime('%d/%m/%Y')
        clinica = vaccine.clinic.name if vaccine.clinic else 'tu veterinaria'

        html = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin:0;padding:0;background:#f4f4f4;font-family:Arial,sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr><td align="center" style="padding:40px 0;">
            <table width="520" cellpadding="0" cellspacing="0"
                style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                <tr>
                    <td align="center" style="background:#059669;padding:32px 40px;">
                        <div style="font-size:36px;">💉</div>
                        <div style="color:#ffffff;font-size:26px;font-weight:bold;margin-top:8px;">VetPaw</div>
                        <div style="color:#a7f3d0;font-size:13px;margin-top:4px;">Recordatorio de vacuna</div>
                    </td>
                </tr>
                <tr>
                    <td style="padding:36px 40px;">
                        <p style="font-size:18px;font-weight:bold;color:#1e1b4b;margin:0 0 12px;">
                            ¡Hola, {owner.first_name or owner.username}! 👋
                        </p>
                        <p style="font-size:15px;color:#4b5563;line-height:1.6;margin:0 0 24px;">
                            En 7 días vence la próxima dosis de una vacuna de <strong>{mascota}</strong>:
                        </p>
                        <table width="100%" cellpadding="0" cellspacing="0"
                            style="background:#ecfdf5;border-radius:10px;padding:20px;margin-bottom:24px;">
                            <tr><td style="padding:8px 20px;">
                                <p style="margin:0;font-size:14px;color:#6b7280;">💉 Vacuna</p>
                                <p style="margin:4px 0 0;font-size:16px;font-weight:bold;color:#1e1b4b;">{vacuna}</p>
                            </td></tr>
                            <tr><td style="padding:8px 20px;">
                                <p style="margin:0;font-size:14px;color:#6b7280;">📅 Fecha límite</p>
                                <p style="margin:4px 0 0;font-size:16px;font-weight:bold;color:#1e1b4b;">{fecha}</p>
                            </td></tr>
                            <tr><td style="padding:8px 20px;">
                                <p style="margin:0;font-size:14px;color:#6b7280;">🏥 Clínica recomendada</p>
                                <p style="margin:4px 0 0;font-size:16px;font-weight:bold;color:#1e1b4b;">{clinica}</p>
                            </td></tr>
                        </table>
                        <p style="font-size:13px;color:#9ca3af;text-align:center;margin:0;">
                            Sacá un turno desde VetPaw para no olvidarte.
                        </p>
                    </td>
                </tr>
                <tr>
                    <td align="center" style="background:#f9fafb;padding:20px 40px;border-top:1px solid #e5e7eb;">
                        <p style="font-size:12px;color:#9ca3af;margin:0;">© 2025 VetPaw · Todos los derechos reservados 🐾</p>
                    </td>
                </tr>
            </table>
            </td></tr>
        </table>
        </body>
        </html>
        """

        text = f"Recordatorio VetPaw: la vacuna {vacuna} de {mascota} vence el {fecha}. Sacá turno en {clinica}."

        try:
            msg = EmailMultiAlternatives(
                subject=f'💉 Vacuna próxima a vencer — {mascota}',
                body=text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[owner.email],
            )
            msg.attach_alternative(html, "text/html")
            msg.send()
            logger.info(f"Recordatorio vacuna enviado a {owner.email} — {vacuna} de {mascota}")
        except Exception as e:
            logger.error(f"Error enviando recordatorio vacuna {vaccine.id}: {e}")