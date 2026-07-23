from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.db.models import Count
from django.core.exceptions import ValidationError as DjangoValidationError

from .permissions import is_vetpaw_admin


def is_admin(user):
    return is_vetpaw_admin(user)


def format_local_datetime(value):
    """Muestra fechas del panel con la hora configurada para Argentina."""
    if not value:
        return '—'
    return timezone.localtime(value).strftime('%d/%m/%Y %H:%M')


def serialize_clinic_plan(clinic):
    return {
        'clinic_id': clinic.id,
        'user_id': clinic.owner_id,
        'name': clinic.name,
        'username': clinic.owner.username if clinic.owner_id else '',
        'email': clinic.owner.email if clinic.owner_id else '',
        'is_approved': bool(clinic.owner_id and clinic.owner.is_approved),
        'is_active': clinic.is_active,
        'plan_status': clinic.plan_status,
        'effective_plan_status': clinic.effective_plan_status,
        'plan_status_display': clinic.get_plan_status_display(),
        'plan_active': clinic.has_active_plan,
        'can_use_clinical_tools': clinic.can_use_clinical_tools,
        'can_receive_appointments': clinic.can_receive_appointments,
        'trial_used': clinic.trial_used,
        'plan_started_at': clinic.plan_started_at.isoformat() if clinic.plan_started_at else None,
        'plan_ends_at': clinic.plan_ends_at.isoformat() if clinic.plan_ends_at else None,
        'grace_ends_at': clinic.grace_ends_at.isoformat() if clinic.grace_ends_at else None,
        'plan_notes': clinic.plan_notes,
        'has_schedule': hasattr(clinic, 'schedule'),
        'locality': clinic.locality,
        'province': clinic.province,
    }


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
    from partners.models import BusinessProfile, ShelterProfile

    now = timezone.now()
    week_ago = now - timedelta(days=7)
    today = timezone.localdate()

    # ── Métricas globales ──
    total_owners   = User.objects.filter(role='owner').count()
    total_clinics  = User.objects.filter(role='clinic').count()
    total_businesses = User.objects.filter(role='business').count()
    total_shelters = User.objects.filter(role='shelter').count()
    total_pets     = Pet.objects.count()
    total_appts    = Appointment.objects.count()
    total_lost     = LostPet.objects.filter(expires_at__gt=now).count()

    new_owners_week  = User.objects.filter(role='owner',  date_joined__gte=week_ago).count()
    new_clinics_week = User.objects.filter(role='clinic', date_joined__gte=week_ago).count()
    new_businesses_week = User.objects.filter(role='business', date_joined__gte=week_ago).count()
    new_shelters_week = User.objects.filter(role='shelter', date_joined__gte=week_ago).count()
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
            'date_joined': format_local_datetime(u.date_joined),
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
                'last_attempt': format_local_datetime(a.attempt_time),
                'locked': a.failures_since_start >= 5,
            }
            for a in blocked
        ]
    except Exception:
        security_data = []

    # ── Veterinarias pendientes de aprobación ──
    pending_clinics_qs = User.objects.filter(role='clinic', is_approved=False).order_by('-date_joined')
    pending_clinics_data = []
    for u in pending_clinics_qs:
        clinic = Clinic.objects.filter(owner=u).first()
        pending_clinics_data.append({
            'user_id':       u.id,
            'clinic_id':     clinic.id if clinic else None,
            'username':      u.username,
            'email':         u.email,
            'date_joined':   format_local_datetime(u.date_joined),
            'clinic_name':   clinic.name if clinic else '—',
            'clinic_phone':  clinic.phone if clinic else '',
            'clinic_address': clinic.address if clinic else '',
            'clinic_province': clinic.province if clinic else '',
            'clinic_locality': clinic.locality if clinic else '',
        })

    pending_profiles = []
    for u in User.objects.filter(role__in=('business', 'shelter'), is_approved=False).order_by('-date_joined'):
        profile = BusinessProfile.objects.filter(owner=u).first() if u.role == 'business' else ShelterProfile.objects.filter(owner=u).first()
        pending_profiles.append({
            'user_id': u.id,
            'username': u.username,
            'email': u.email,
            'role': u.role,
            'role_display': 'Negocio de mascotas' if u.role == 'business' else 'Refugio o rescatista',
            'date_joined': format_local_datetime(u.date_joined),
            'name': profile.name if profile else '—',
            'profile_type': (
                profile.get_business_type_display() if u.role == 'business' and profile
                else profile.get_shelter_type_display() if profile
                else ''
            ),
            'phone': profile.phone if profile else '',
            'whatsapp': profile.whatsapp if profile else '',
            'province': profile.province if profile else '',
            'locality': profile.locality if profile else '',
        })

    clinic_plans = [
        serialize_clinic_plan(clinic)
        for clinic in Clinic.objects.select_related('owner').order_by('name')
    ]

    return Response({
        'global': {
            'total_owners':      total_owners,
            'total_clinics':     total_clinics,
            'total_pets':        total_pets,
            'total_businesses':  total_businesses,
            'total_shelters':    total_shelters,
            'total_appts':       total_appts,
            'total_lost_active': total_lost,
            'new_owners_week':   new_owners_week,
            'new_clinics_week':  new_clinics_week,
            'new_businesses_week': new_businesses_week,
            'new_shelters_week': new_shelters_week,
            'new_appts_week':    new_appts_week,
        },
        'new_users_by_day':  new_users,
        'appts_by_day':      appts_by_day,
        'appts_by_status':   appts_by_status,
        'top_clinics':       clinics_data,
        'last_users':        last_users_data,
        'security':          security_data,
        'pending_clinics':   pending_clinics_data,
        'pending_profiles':  pending_profiles,
        'clinic_plans':      clinic_plans,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clinic_plan_action(request, clinic_id):
    if not is_admin(request.user):
        return Response({'error': 'Acceso denegado.'}, status=status.HTTP_403_FORBIDDEN)

    from clinics.models import Clinic

    try:
        clinic = Clinic.objects.select_related('owner').get(pk=clinic_id)
    except Clinic.DoesNotExist:
        return Response({'error': 'Veterinaria no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    action = str(request.data.get('action') or '').strip().lower()
    notes = str(request.data.get('notes') or '').strip()[:500]
    try:
        days = int(request.data.get('days') or 30)
    except (TypeError, ValueError):
        return Response({'error': 'La cantidad de días no es válida.'}, status=status.HTTP_400_BAD_REQUEST)
    days = max(1, min(days, 365))

    try:
        if action == 'approve_and_start_trial':
            if not clinic.owner_id:
                return Response({'error': 'La veterinaria no tiene un usuario responsable asociado.'}, status=status.HTTP_400_BAD_REQUEST)
            with transaction.atomic():
                clinic.owner.is_approved = True
                clinic.owner.save(update_fields=['is_approved'])
                clinic.start_free_trial(days=30, notes=notes or 'Primer mes gratis de prueba')
            message = 'Veterinaria aprobada con su primer mes gratis por 30 días.'
        elif action == 'start_trial':
            clinic.start_free_trial(days=30, notes=notes or 'Primer mes gratis de prueba')
            message = 'Mes de prueba gratis activado por 30 días.'
        elif action == 'activate':
            clinic.activate_paid_plan(days=days, notes=notes or f'Plan activado por {days} días')
            message = f'Plan veterinario activado por {days} días.'
        elif action == 'grace':
            clinic.grant_grace(days=days, notes=notes or f'Período de gracia por {days} días')
            message = f'Período de gracia activado por {days} días.'
        elif action == 'suspend':
            clinic.suspend_plan(notes=notes or 'Plan suspendido desde el panel de VetPaw')
            message = 'Plan veterinario suspendido.'
        elif action == 'expire':
            clinic.expire_plan(notes=notes or 'Plan marcado como vencido desde el panel de VetPaw')
            message = 'Plan veterinario marcado como vencido.'
        else:
            return Response({'error': 'Acción de plan no válida.'}, status=status.HTTP_400_BAD_REQUEST)
    except DjangoValidationError as exc:
        if hasattr(exc, 'message_dict'):
            payload = exc.message_dict
        else:
            payload = {'error': exc.messages[0] if exc.messages else str(exc)}
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    clinic.refresh_from_db()
    return Response({'message': message, 'clinic': serialize_clinic_plan(clinic)})
