from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count


ADMIN_USERNAME = 'jaime17'


def is_admin(user):
    return user.is_authenticated and user.username == ADMIN_USERNAME


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_panel(request):
    if not is_admin(request.user):
        return Response({'error': 'Acceso denegado.'}, status=status.HTTP_403_FORBIDDEN)

    from users.models import User
    from clinics.models import Clinic
    from appointments.models import Appointment
    from pets.models import Pet
    from lost_pets.models import LostPet

    now = timezone.now()
    week_ago = now - timedelta(days=7)
    today = now.date()

    # ── Métricas globales ──
    total_owners   = User.objects.filter(role='owner').count()
    total_clinics  = User.objects.filter(role='clinic').count()
    total_pets     = Pet.objects.count()
    total_appts    = Appointment.objects.count()
    total_lost     = LostPet.objects.filter(expires_at__gt=now).count()

    new_owners_week  = User.objects.filter(role='owner',  date_joined__gte=week_ago).count()
    new_clinics_week = User.objects.filter(role='clinic', date_joined__gte=week_ago).count()
    new_appts_week   = Appointment.objects.filter(created_at__gte=week_ago).count()

    # ── Usuarios nuevos últimos 7 días ──
    new_users = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        count = User.objects.filter(date_joined__date=day).count()
        new_users.append({
            'date': day.strftime('%d/%m'),
            'count': count,
        })

    # ── Turnos por día últimos 7 días ──
    appts_by_day = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        count = Appointment.objects.filter(created_at__date=day).count()
        appts_by_day.append({
            'date': day.strftime('%d/%m'),
            'count': count,
        })

    # ── Clínicas más activas ──
    top_clinics = (
        Clinic.objects.filter(is_active=True)
        .annotate(
            appts_total=Count('appointments'),
            appts_week=Count(
                'appointments',
                filter=__import__('django.db.models', fromlist=['Q']).Q(
                    appointments__created_at__gte=week_ago
                )
            )
        )
        .order_by('-appts_week')[:10]
    )
    clinics_data = [
        {
            'name': c.name,
            'locality': c.locality,
            'province': c.province,
            'appts_total': c.appts_total,
            'appts_week': c.appts_week,
        }
        for c in top_clinics
    ]

    # ── Últimos usuarios registrados ──
    last_users = User.objects.order_by('-date_joined')[:10]
    last_users_data = [
        {
            'username': u.username,
            'email': u.email,
            'role': u.role,
            'date_joined': u.date_joined.strftime('%d/%m/%Y %H:%M'),
        }
        for u in last_users
    ]

    # ── Turnos por estado esta semana ──
    appts_week_qs = Appointment.objects.filter(created_at__gte=week_ago)
    appts_by_status = {
        'pending':   appts_week_qs.filter(status='pending').count(),
        'confirmed': appts_week_qs.filter(status='confirmed').count(),
        'completed': appts_week_qs.filter(status='completed').count(),
        'cancelled': appts_week_qs.filter(status='cancelled').count(),
        'no_show':   appts_week_qs.filter(status='no_show').count(),
    }

    # ── Seguridad: intentos fallidos (django-axes) ──
    security_data = []
    try:
        from axes.models import AccessAttempt, AccessFailureLog
        blocked = AccessAttempt.objects.order_by('-attempt_time')[:10]
        security_data = [
            {
                'ip': a.ip_address,
                'username': a.username,
                'attempts': a.failures_since_start,
                'last_attempt': a.attempt_time.strftime('%d/%m/%Y %H:%M'),
                'locked': a.failures_since_start >= 5,
            }
            for a in blocked
        ]
    except Exception:
        security_data = []

    return Response({
        'global': {
            'total_owners':      total_owners,
            'total_clinics':     total_clinics,
            'total_pets':        total_pets,
            'total_appts':       total_appts,
            'total_lost_active': total_lost,
            'new_owners_week':   new_owners_week,
            'new_clinics_week':  new_clinics_week,
            'new_appts_week':    new_appts_week,
        },
        'new_users_by_day':  new_users,
        'appts_by_day':      appts_by_day,
        'appts_by_status':   appts_by_status,
        'top_clinics':       clinics_data,
        'last_users':        last_users_data,
        'security':          security_data,
    })