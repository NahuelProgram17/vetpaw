from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from django.db.models import Count, Q


class Command(BaseCommand):
    help = 'Envia resumen semanal de VetPaw a vetpaw.app@gmail.com'

    def handle(self, *args, **kwargs):
        from users.models import User
        from clinics.models import Clinic
        from appointments.models import Appointment
        from pets.models import Pet

        now = timezone.now()
        week_ago = now - timedelta(days=7)

        # ── Métricas globales ──
        total_owners  = User.objects.filter(role='owner').count()
        total_clinics = User.objects.filter(role='clinic').count()
        total_pets    = Pet.objects.count()

        new_owners  = User.objects.filter(role='owner',  date_joined__gte=week_ago).count()
        new_clinics = User.objects.filter(role='clinic', date_joined__gte=week_ago).count()
        new_pets    = Pet.objects.filter(created_at__gte=week_ago).count()

        # ── Turnos de la semana ──
        appts_week = Appointment.objects.filter(created_at__gte=week_ago)
        total_appts_week  = appts_week.count()
        pending_appts     = appts_week.filter(status='pending').count()
        confirmed_appts   = appts_week.filter(status='confirmed').count()
        completed_appts   = appts_week.filter(status='completed').count()
        cancelled_appts   = appts_week.filter(status='cancelled').count()
        noshow_appts      = appts_week.filter(status='no_show').count()

        # ── Turnos por clínica ──
        clinics_stats = (
            Clinic.objects.filter(is_active=True)
            .annotate(appts_week=Count(
                'appointments',
                filter=Q(appointments__created_at__gte=week_ago)
            ))
            .order_by('-appts_week')
        )

        # ── Total histórico de turnos ──
        total_appts_all = Appointment.objects.count()

        fecha_inicio = week_ago.strftime('%d/%m/%Y')
        fecha_fin    = now.strftime('%d/%m/%Y')

        # ── Tabla de clínicas ──
        clinics_rows = ''
        for c in clinics_stats:
            bar = '█' * min(c.appts_week, 20)
            clinics_rows += f"""
                <tr>
                    <td style="padding:8px 12px;color:#fff;font-weight:700;">{c.name}</td>
                    <td style="padding:8px 12px;color:#aaa;font-size:12px;">{c.locality}, {c.province}</td>
                    <td style="padding:8px 12px;color:#4CAF50;font-weight:900;font-size:16px;">{c.appts_week}</td>
                    <td style="padding:8px 12px;">
                        <span style="color:#4CAF50;font-size:11px;letter-spacing:1px;">{bar}</span>
                    </td>
                </tr>
            """

        html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0f1923;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:32px 16px;">
<table width="600" cellpadding="0" cellspacing="0" style="background:#162032;border-radius:16px;overflow:hidden;">

    <!-- Header -->
    <tr><td style="background:#0f1923;padding:28px 32px;border-bottom:2px solid #4CAF50;">
        <div style="color:#4CAF50;font-size:26px;font-weight:900;">🐾 VetPaw</div>
        <div style="color:#aaa;font-size:13px;margin-top:4px;">Resumen semanal — {fecha_inicio} al {fecha_fin}</div>
    </td></tr>

    <!-- Stats globales -->
    <tr><td style="padding:24px 32px;">
        <div style="color:#fff;font-size:16px;font-weight:700;margin-bottom:16px;">📊 Estado general de la plataforma</div>
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
                <td style="background:#0f1923;border-radius:10px;padding:14px;text-align:center;width:25%;">
                    <div style="color:#4CAF50;font-size:28px;font-weight:900;">{total_owners}</div>
                    <div style="color:#aaa;font-size:11px;margin-top:4px;">Duenos totales</div>
                    <div style="color:#66BB6A;font-size:11px;font-weight:700;">+{new_owners} esta semana</div>
                </td>
                <td style="width:2%;"></td>
                <td style="background:#0f1923;border-radius:10px;padding:14px;text-align:center;width:25%;">
                    <div style="color:#6bcaff;font-size:28px;font-weight:900;">{total_clinics}</div>
                    <div style="color:#aaa;font-size:11px;margin-top:4px;">Clinicas totales</div>
                    <div style="color:#6bcaff;font-size:11px;font-weight:700;">+{new_clinics} esta semana</div>
                </td>
                <td style="width:2%;"></td>
                <td style="background:#0f1923;border-radius:10px;padding:14px;text-align:center;width:25%;">
                    <div style="color:#ffd93d;font-size:28px;font-weight:900;">{total_pets}</div>
                    <div style="color:#aaa;font-size:11px;margin-top:4px;">Mascotas totales</div>
                    <div style="color:#ffd93d;font-size:11px;font-weight:700;">+{new_pets} esta semana</div>
                </td>
                <td style="width:2%;"></td>
                <td style="background:#0f1923;border-radius:10px;padding:14px;text-align:center;width:25%;">
                    <div style="color:#ff9800;font-size:28px;font-weight:900;">{total_appts_all}</div>
                    <div style="color:#aaa;font-size:11px;margin-top:4px;">Turnos historicos</div>
                    <div style="color:#ff9800;font-size:11px;font-weight:700;">+{total_appts_week} esta semana</div>
                </td>
            </tr>
        </table>
    </td></tr>

    <!-- Turnos de la semana -->
    <tr><td style="padding:0 32px 24px;">
        <div style="color:#fff;font-size:16px;font-weight:700;margin-bottom:12px;">📅 Turnos esta semana ({total_appts_week} total)</div>
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f1923;border-radius:10px;">
            <tr>
                <td style="padding:10px 14px;text-align:center;">
                    <div style="color:#ffd93d;font-size:20px;font-weight:900;">{pending_appts}</div>
                    <div style="color:#aaa;font-size:10px;">Pendientes</div>
                </td>
                <td style="padding:10px 14px;text-align:center;">
                    <div style="color:#6bcaff;font-size:20px;font-weight:900;">{confirmed_appts}</div>
                    <div style="color:#aaa;font-size:10px;">Confirmados</div>
                </td>
                <td style="padding:10px 14px;text-align:center;">
                    <div style="color:#6bffb8;font-size:20px;font-weight:900;">{completed_appts}</div>
                    <div style="color:#aaa;font-size:10px;">Realizados</div>
                </td>
                <td style="padding:10px 14px;text-align:center;">
                    <div style="color:#ff6b6b;font-size:20px;font-weight:900;">{cancelled_appts}</div>
                    <div style="color:#aaa;font-size:10px;">Cancelados</div>
                </td>
                <td style="padding:10px 14px;text-align:center;">
                    <div style="color:#ff9500;font-size:20px;font-weight:900;">{noshow_appts}</div>
                    <div style="color:#aaa;font-size:10px;">Ausentes</div>
                </td>
            </tr>
        </table>
    </td></tr>

    <!-- Ranking clínicas -->
    <tr><td style="padding:0 32px 24px;">
        <div style="color:#fff;font-size:16px;font-weight:700;margin-bottom:12px;">🏥 Ranking de clinicas por turnos esta semana</div>
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f1923;border-radius:10px;">
            <tr style="border-bottom:1px solid #1a2535;">
                <th style="padding:8px 12px;text-align:left;color:#aaa;font-size:11px;font-weight:600;text-transform:uppercase;">Clinica</th>
                <th style="padding:8px 12px;text-align:left;color:#aaa;font-size:11px;font-weight:600;text-transform:uppercase;">Localidad</th>
                <th style="padding:8px 12px;text-align:left;color:#aaa;font-size:11px;font-weight:600;text-transform:uppercase;">Turnos</th>
                <th style="padding:8px 12px;text-align:left;color:#aaa;font-size:11px;font-weight:600;text-transform:uppercase;">Actividad</th>
            </tr>
            {clinics_rows}
        </table>
        <div style="color:#aaa;font-size:11px;margin-top:8px;font-style:italic;">
            * Las clinicas con mas turnos son candidatas a ofrecer el Plan Pro
        </div>
    </td></tr>

    <!-- Footer -->
    <tr><td style="background:#0f1923;padding:16px 32px;text-align:center;border-top:1px solid #1a2535;">
        <div style="color:#555;font-size:11px;">VetPaw Monitor Semanal — vetpaw.app@gmail.com</div>
        <div style="color:#555;font-size:11px;margin-top:4px;">vetpaw.com.ar | @vetpawoficial</div>
    </td></tr>

</table>
</td></tr>
</table>
</body>
</html>
"""

        try:
            send_mail(
                subject=f'📊 VetPaw — Resumen semanal {fecha_inicio} al {fecha_fin}',
                message=f'Resumen semanal VetPaw: {total_owners} duenos, {total_clinics} clinicas, {total_appts_week} turnos esta semana.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['nahuelpedreyra2017@gmail.com'],
                html_message=html,
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS('Monitor semanal enviado OK'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error enviando monitor: {e}'))