from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from appointments.models import Appointment
from pets.models import Vaccine


class Command(BaseCommand):
    help = 'Envía recordatorios de turnos, vacunas y mensajes sin leer por email'

    def handle(self, *args, **kwargs):
        self.send_appointment_reminders()
        self.send_vaccine_reminders()
        self.send_unread_message_reminders()

    def send_appointment_reminders(self):
        """
        Envía un recordatorio a los dueños por los turnos próximos.

        Antes se buscaban turnos exactamente a 24/48 hs con una ventana de 30 minutos.
        Eso podía dejar afuera turnos creados con menos de 24 hs de anticipación,
        como el caso de Karen Matus y Gusano para mañana a las 09:40.

        Ahora se toma cualquier turno pendiente/confirmado entre este momento y las
        próximas 24 horas, siempre que todavía no tenga reminder_sent=True.
        """
        now = timezone.now()
        window_end = now + timedelta(hours=24)

        appointments = Appointment.objects.filter(
            requested_date__gte=now,
            requested_date__lte=window_end,
            status__in=['pending', 'confirmed'],
            reminder_sent=False,
            owner__isnull=False,
            pet__isnull=False,
        ).select_related('owner', 'pet', 'clinic').order_by('requested_date')

        for appt in appointments:
            owner = appt.owner
            if not owner.email:
                continue

            hours_left = (appt.requested_date - now).total_seconds() / 3600
            if hours_left <= 2:
                label = "en menos de 2 horas"
            elif hours_left <= 12:
                label = "hoy"
            else:
                label = "mañana"

            fecha = appt.requested_date.astimezone(
                timezone.get_current_timezone()
            ).strftime("%d/%m/%Y a las %H:%M")
            status_label = "Confirmado ✅" if appt.status == "confirmed" else "Pendiente ⏳"
            subject = f"🐾 Recordatorio: turno de {appt.pet.name} {label}"

            html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f4f4fb; margin: 0; padding: 0; }}
    .wrap {{ max-width: 560px; margin: 32px auto; background: #fff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }}
    .header {{ background: #1a1a2e; padding: 32px 32px 24px; text-align: center; }}
    .header h1 {{ color: #fff; font-size: 26px; margin: 0; letter-spacing: -0.5px; }}
    .header p {{ color: rgba(255,255,255,0.5); font-size: 13px; margin: 6px 0 0; }}
    .body {{ padding: 28px 32px; }}
    .greeting {{ font-size: 16px; color: #1a1a2e; font-weight: 700; margin-bottom: 8px; }}
    .msg {{ font-size: 14px; color: #555; line-height: 1.6; margin-bottom: 20px; }}
    .card {{ background: #f4f4fb; border: 1px solid #ddddf0; border-radius: 12px; padding: 18px 20px; margin-bottom: 20px; }}
    .card-label {{ font-size: 12px; color: #888; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }}
    .card-value {{ font-size: 14px; color: #1a1a2e; font-weight: 700; text-align: right; }}
    .status-confirmed {{ color: #1a7a50; background: #e6fff5; border-radius: 6px; padding: 2px 10px; font-size: 12px; font-weight: 700; }}
    .status-pending {{ color: #8a6a00; background: #fff8e0; border-radius: 6px; padding: 2px 10px; font-size: 12px; font-weight: 700; }}
    .tip {{ background: #fff8e0; border: 1px solid #ffe082; border-radius: 10px; padding: 14px 16px; font-size: 13px; color: #8a6a00; margin-bottom: 20px; line-height: 1.5; }}
    .footer {{ background: #f4f4fb; padding: 16px 32px; text-align: center; font-size: 11px; color: #aaa; }}
    .paw {{ font-size: 32px; display: block; margin-bottom: 8px; }}
</style>
</head>
<body>
<div class="wrap">
    <div class="header">
        <span class="paw">🐾</span>
        <h1>VetPaw</h1>
        <p>Recordatorio de turno</p>
    </div>
    <div class="body">
        <p class="greeting">Hola, {owner.first_name or owner.username}!</p>
        <p class="msg">
            Te recordamos que tenés un turno veterinario programado <strong>{label}</strong>.
            Asegurate de llegar a tiempo y llevar toda la documentación de tu mascota.
        </p>
        <div class="card">
            <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                    <td class="card-label">Dueño/a</td>
                    <td class="card-value">{owner.get_full_name() or owner.username}</td>
                </tr>
                <tr><td colspan="2" style="padding:4px 0;"></td></tr>
                <tr>
                    <td class="card-label">Mascota</td>
                    <td class="card-value">🐾 {appt.pet.name}</td>
                </tr>
                <tr><td colspan="2" style="padding:4px 0;"></td></tr>
                <tr>
                    <td class="card-label">Clínica</td>
                    <td class="card-value">🏥 {appt.clinic.name}</td>
                </tr>
                <tr><td colspan="2" style="padding:4px 0;"></td></tr>
                <tr>
                    <td class="card-label">Fecha y hora</td>
                    <td class="card-value">📅 {fecha}</td>
                </tr>
                <tr><td colspan="2" style="padding:4px 0;"></td></tr>
                <tr>
                    <td class="card-label">Motivo</td>
                    <td class="card-value">{appt.appointment_type_display if hasattr(appt, 'appointment_type_display') else appt.get_appointment_type_display()}</td>
                </tr>
                <tr><td colspan="2" style="padding:4px 0;"></td></tr>
                <tr>
                    <td class="card-label">Estado</td>
                    <td class="card-value">
                        <span class="{'status-confirmed' if appt.status == 'confirmed' else 'status-pending'}">
                            {status_label}
                        </span>
                    </td>
                </tr>
            </table>
        </div>
        <div class="tip">
            💡 <strong>Recordá:</strong> Si necesitás cancelar, hacelo con anticipación desde VetPaw para evitar inconvenientes.
        </div>
        <p class="msg" style="font-size:13px; color:#888;">
            Si ya no tenés este turno o creés que este email es un error, podés ignorarlo.
        </p>
    </div>
    <div class="footer">
        VetPaw &mdash; Tu compañero de salud animal<br>
        vetpaw.app@gmail.com
    </div>
</div>
</body>
</html>
"""

            try:
                send_mail(
                    subject=subject,
                    message=f"Recordatorio: turno de {appt.pet.name} {label} — {fecha} en {appt.clinic.name}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[owner.email],
                    html_message=html,
                    fail_silently=False,
                )
                appt.reminder_sent = True
                appt.save(update_fields=['reminder_sent'])
                self.stdout.write(self.style.SUCCESS(f"  ✅ Turno [{appt.id}] → {owner.email} ({label})"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Error turno [{appt.id}]: {e}"))

    def send_vaccine_reminders(self):
        now = timezone.now().date()
        window_end = now + timedelta(days=7)

        vaccines = Vaccine.objects.filter(
            next_dose__isnull=False,
            next_dose__gte=now,
            next_dose__lte=window_end,
            reminder_sent=False,
        ).select_related('pet', 'pet__owner', 'clinic')

        for vaccine in vaccines:
            owner = vaccine.pet.owner
            if not owner.email:
                continue

            days_left = (vaccine.next_dose - now).days
            if days_left == 0:
                when = "hoy"
            elif days_left == 1:
                when = "mañana"
            else:
                when = f"en {days_left} días"

            fecha_venc = vaccine.next_dose.strftime("%d/%m/%Y")
            subject = f"💉 Vacuna de {vaccine.pet.name} vence {when}"

            html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f4f4fb; margin: 0; padding: 0; }}
    .wrap {{ max-width: 560px; margin: 32px auto; background: #fff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }}
    .header {{ background: #1a1a2e; padding: 32px 32px 24px; text-align: center; }}
    .header h1 {{ color: #fff; font-size: 26px; margin: 0; letter-spacing: -0.5px; }}
    .header p {{ color: rgba(255,255,255,0.5); font-size: 13px; margin: 6px 0 0; }}
    .body {{ padding: 28px 32px; }}
    .greeting {{ font-size: 16px; color: #1a1a2e; font-weight: 700; margin-bottom: 8px; }}
    .msg {{ font-size: 14px; color: #555; line-height: 1.6; margin-bottom: 20px; }}
    .card {{ background: #f4f4fb; border: 1px solid #ddddf0; border-radius: 12px; padding: 18px 20px; margin-bottom: 20px; }}
    .card-label {{ font-size: 12px; color: #888; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }}
    .card-value {{ font-size: 14px; color: #1a1a2e; font-weight: 700; text-align: right; }}
    .alert {{ background: #fff3e0; border: 1px solid #ffcc80; border-radius: 10px; padding: 14px 16px; font-size: 13px; color: #e65100; margin-bottom: 20px; line-height: 1.5; }}
    .badge-warn {{ color: #e65100; background: #fff3e0; border-radius: 6px; padding: 2px 10px; font-size: 12px; font-weight: 700; }}
    .footer {{ background: #f4f4fb; padding: 16px 32px; text-align: center; font-size: 11px; color: #aaa; }}
    .paw {{ font-size: 32px; display: block; margin-bottom: 8px; }}
</style>
</head>
<body>
<div class="wrap">
    <div class="header">
        <span class="paw">💉</span>
        <h1>VetPaw</h1>
        <p>Recordatorio de vacuna</p>
    </div>
    <div class="body">
        <p class="greeting">Hola, {owner.first_name or owner.username}!</p>
        <p class="msg">
            La próxima dosis de una vacuna de <strong>{vaccine.pet.name}</strong>
            vence <strong>{when}</strong> ({fecha_venc}).
            Te recomendamos coordinar un turno con tu veterinaria para no perder la cobertura.
        </p>
        <div class="card">
            <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                    <td class="card-label">Mascota</td>
                    <td class="card-value">🐾 {vaccine.pet.name}</td>
                </tr>
                <tr><td colspan="2" style="padding:4px 0;"></td></tr>
                <tr>
                    <td class="card-label">Vacuna</td>
                    <td class="card-value">💉 {vaccine.name}</td>
                </tr>
                <tr><td colspan="2" style="padding:4px 0;"></td></tr>
                <tr>
                    <td class="card-label">Próxima dosis</td>
                    <td class="card-value">
                        <span class="badge-warn">⚠️ {fecha_venc}</span>
                    </td>
                </tr>
                {f'<tr><td colspan="2" style="padding:4px 0;"></td></tr><tr><td class="card-label">Clínica</td><td class="card-value">🏥 {vaccine.clinic.name}</td></tr>' if vaccine.clinic else ''}
            </table>
        </div>
        <div class="alert">
            ⚠️ <strong>Importante:</strong> No retrasar las vacunas protege a tu mascota
            y a otras mascotas con las que convive. Sacar un turno toma menos de 1 minuto en VetPaw.
        </div>
    </div>
    <div class="footer">
        VetPaw &mdash; Tu compañero de salud animal<br>
        vetpaw.app@gmail.com
    </div>
</div>
</body>
</html>
"""

            try:
                send_mail(
                    subject=subject,
                    message=f"Recordatorio: vacuna {vaccine.name} de {vaccine.pet.name} vence {when} ({fecha_venc})",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[owner.email],
                    html_message=html,
                    fail_silently=False,
                )
                vaccine.reminder_sent = True
                vaccine.save(update_fields=['reminder_sent'])
                self.stdout.write(self.style.SUCCESS(f"  💉 Vacuna [{vaccine.id}] → {owner.email} (vence {fecha_venc})"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Error vacuna [{vaccine.id}]: {e}"))

    def send_unread_message_reminders(self):
        from messaging.models import Message

        cutoff = timezone.now() - timedelta(hours=12)

        unread = Message.objects.filter(
            read=False,
            created_at__lte=cutoff,
        ).select_related('recipient', 'sender')

        by_recipient = {}
        for msg in unread:
            uid = msg.recipient.id
            if uid not in by_recipient:
                by_recipient[uid] = {
                    'user':    msg.recipient,
                    'count':   0,
                    'senders': set(),
                }
            by_recipient[uid]['count'] += 1
            by_recipient[uid]['senders'].add(msg.sender.username)

        for uid, data in by_recipient.items():
            user    = data['user']
            count   = data['count']
            senders = ', '.join(data['senders'])

            if not user.email:
                continue

            subject = f"💬 Tenés {count} mensaje{'s' if count > 1 else ''} sin leer en VetPaw"

            html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f4f4fb; margin: 0; padding: 0; }}
    .wrap {{ max-width: 560px; margin: 32px auto; background: #fff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }}
    .header {{ background: #1a1a2e; padding: 32px 32px 24px; text-align: center; }}
    .header h1 {{ color: #fff; font-size: 26px; margin: 0; }}
    .header p {{ color: rgba(255,255,255,0.5); font-size: 13px; margin: 6px 0 0; }}
    .body {{ padding: 28px 32px; }}
    .greeting {{ font-size: 16px; color: #1a1a2e; font-weight: 700; margin-bottom: 8px; }}
    .msg {{ font-size: 14px; color: #555; line-height: 1.6; margin-bottom: 20px; }}
    .card {{ background: #f4f4fb; border: 1px solid #ddddf0; border-radius: 12px; padding: 18px 20px; margin-bottom: 20px; text-align: center; }}
    .badge {{ font-size: 40px; font-weight: 900; color: #1a1a2e; display: block; line-height: 1; }}
    .badge-label {{ font-size: 13px; color: #888; margin-top: 6px; display: block; }}
    .btn-wrap {{ text-align: center; margin-bottom: 20px; }}
    .btn {{ display: inline-block; background: linear-gradient(135deg, #ff6b6b, #ff4a4a); color: #fff; text-decoration: none; border-radius: 10px; padding: 13px 32px; font-weight: 700; font-size: 14px; }}
    .footer {{ background: #f4f4fb; padding: 16px 32px; text-align: center; font-size: 11px; color: #aaa; }}
    .paw {{ font-size: 32px; display: block; margin-bottom: 8px; }}
</style>
</head>
<body>
<div class="wrap">
    <div class="header">
        <span class="paw">💬</span>
        <h1>VetPaw</h1>
        <p>Mensajes sin leer</p>
    </div>
    <div class="body">
        <p class="greeting">Hola, {user.first_name or user.username}!</p>
        <p class="msg">
            Tenés mensajes sin leer de <strong>{senders}</strong>.
            Entrá a VetPaw para verlos y responder.
        </p>
        <div class="card">
            <span class="badge">{count}</span>
            <span class="badge-label">mensaje{'s' if count > 1 else ''} sin leer</span>
        </div>
        <div class="btn-wrap">
            <a href="https://www.vetpaw.com.ar/messages" class="btn">Ver mensajes en VetPaw →</a>
        </div>
        <p class="msg" style="font-size:12px; color:#aaa; text-align:center;">
            Este es un aviso automático. El contenido de los mensajes solo está disponible dentro de VetPaw.
        </p>
    </div>
    <div class="footer">
        VetPaw &mdash; Tu compañero de salud animal<br>
        vetpaw.app@gmail.com
    </div>
</div>
</body>
</html>
"""

            try:
                send_mail(
                    subject=subject,
                    message=f"Tenés {count} mensaje(s) sin leer de {senders} en VetPaw.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html,
                    fail_silently=False,
                )
                self.stdout.write(self.style.SUCCESS(f"  💬 Aviso mensajes → {user.email} ({count} sin leer de {senders})"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Error mensajes [{uid}]: {e}"))