from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
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


def _count_period(queryset, field_name, since):
    """Cuenta registros recientes sin repetir la lógica del panel."""
    return queryset.filter(**{f'{field_name}__gte': since}).count()


def _active_user_ids(since):
    """Usuarios que realizaron al menos una acción real dentro de VetPaw."""
    from appointments.models import Appointment
    from adoptions.models import AdoptionApplication, HelpOffer
    from commerce.models import BusinessInquiry, BusinessReservation
    from community.models import Comment, PetFollow, Post, Reaction
    from messaging.models import Message

    user_ids = set()
    sources = (
        Post.objects.filter(created_at__gte=since).values_list('created_by_id', flat=True),
        Comment.objects.filter(created_at__gte=since).values_list('author_id', flat=True),
        Reaction.objects.filter(created_at__gte=since).values_list('user_id', flat=True),
        PetFollow.objects.filter(created_at__gte=since).values_list('follower_id', flat=True),
        Message.objects.filter(created_at__gte=since).values_list('sender_id', flat=True),
        AdoptionApplication.objects.filter(created_at__gte=since).values_list('applicant_id', flat=True),
        HelpOffer.objects.filter(created_at__gte=since).values_list('user_id', flat=True),
        BusinessInquiry.objects.filter(created_at__gte=since).values_list('user_id', flat=True),
        BusinessReservation.objects.filter(created_at__gte=since).values_list('user_id', flat=True),
        Appointment.objects.filter(created_at__gte=since).values_list('owner_id', flat=True),
    )
    for values in sources:
        user_ids.update(value for value in values if value)
    return user_ids


def _serialize_top_post(post):
    if post.pet_id:
        actor_type, actor_name = 'pet', post.pet.name
    elif post.clinic_id:
        actor_type, actor_name = 'clinic', post.clinic.name
    elif post.business_id:
        actor_type, actor_name = 'business', post.business.name
    elif post.shelter_id:
        actor_type, actor_name = 'shelter', post.shelter.name
    else:
        actor_type, actor_name = 'vetpaw', 'VetPaw'
    return {
        'id': post.id,
        'actor_type': actor_type,
        'actor_name': actor_name,
        'text': (post.text or '')[:180],
        'post_type': post.post_type,
        'paws': post.paws_count,
        'comments': post.comments_count,
        'shares': post.shares_count,
        'score': post.paws_count + (post.comments_count * 2) + (post.shares_count * 3),
        'created_at': post.created_at.isoformat(),
    }


def build_interaction_statistics(now):
    """Métricas sociales y comerciales para medir el uso real de VetPaw."""
    from appointments.models import Appointment
    from adoptions.models import AdoptionAnimal, AdoptionApplication, HelpOffer
    from clinics.models import Clinic, ClinicSchedule
    from commerce.models import BusinessInquiry, BusinessProfileView, BusinessReservation
    from community.models import Comment, PetFollow, Post, Reaction
    from messaging.models import Message
    from partners.models import BusinessProfile, ShelterProfile
    from pets.models import Pet

    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    published_posts = Post.objects.filter(moderation_status=Post.STATUS_PUBLISHED)
    comments = Comment.objects.filter(moderation_status=Comment.STATUS_PUBLISHED)
    reactions = Reaction.objects.all()
    follows = PetFollow.objects.all()
    messages = Message.objects.all()

    community = {
        'posts_total': Post.objects.count(),
        'posts_published': published_posts.count(),
        'posts_week': _count_period(published_posts, 'created_at', week_ago),
        'posts_30_days': _count_period(published_posts, 'created_at', month_ago),
        'paws_total': reactions.count(),
        'paws_week': _count_period(reactions, 'created_at', week_ago),
        'paws_30_days': _count_period(reactions, 'created_at', month_ago),
        'comments_total': comments.count(),
        'comments_week': _count_period(comments, 'created_at', week_ago),
        'comments_30_days': _count_period(comments, 'created_at', month_ago),
        'replies_total': comments.filter(parent__isnull=False).count(),
        'replies_week': comments.filter(parent__isnull=False, created_at__gte=week_ago).count(),
        'replies_30_days': comments.filter(parent__isnull=False, created_at__gte=month_ago).count(),
        'follows_total': follows.count(),
        'follows_week': _count_period(follows, 'created_at', week_ago),
        'follows_30_days': _count_period(follows, 'created_at', month_ago),
        'messages_total': messages.count(),
        'messages_week': _count_period(messages, 'created_at', week_ago),
        'messages_30_days': _count_period(messages, 'created_at', month_ago),
        'active_users_week': len(_active_user_ids(week_ago)),
        'active_users_30_days': len(_active_user_ids(month_ago)),
    }

    animals = AdoptionAnimal.objects.all()
    applications = AdoptionApplication.objects.all()
    help_offers = HelpOffer.objects.all()
    adoption_statuses = {
        value: animals.filter(status=value).count()
        for value, _label in AdoptionAnimal.STATUS_CHOICES
    }
    application_statuses = {
        value: applications.filter(status=value).count()
        for value, _label in AdoptionApplication.STATUS_CHOICES
    }
    active_shelter_ids = set(
        animals.filter(updated_at__gte=month_ago).values_list('shelter_id', flat=True)
    )
    active_shelter_ids.update(
        applications.filter(created_at__gte=month_ago).values_list('animal__shelter_id', flat=True)
    )
    active_shelter_ids.update(
        help_offers.filter(created_at__gte=month_ago).values_list('animal__shelter_id', flat=True)
    )
    adoptions = {
        'animals_total': animals.count(),
        'animals_published': animals.filter(is_published=True).count(),
        'animals_by_status': adoption_statuses,
        'applications_total': applications.count(),
        'applications_week': _count_period(applications, 'created_at', week_ago),
        'applications_30_days': _count_period(applications, 'created_at', month_ago),
        'applications_by_status': application_statuses,
        'help_offers_total': help_offers.count(),
        'help_offers_week': _count_period(help_offers, 'created_at', week_ago),
        'help_offers_30_days': _count_period(help_offers, 'created_at', month_ago),
        'active_shelters_30_days': len(active_shelter_ids),
    }

    inquiries = BusinessInquiry.objects.all()
    reservations = BusinessReservation.objects.all()
    profile_views = BusinessProfileView.objects.all()
    businesses = {
        'inquiries_total': inquiries.count(),
        'inquiries_week': _count_period(inquiries, 'created_at', week_ago),
        'inquiries_30_days': _count_period(inquiries, 'created_at', month_ago),
        'inquiries_by_status': {
            value: inquiries.filter(status=value).count()
            for value, _label in BusinessInquiry.STATUS_CHOICES
        },
        'reservations_total': reservations.count(),
        'reservations_week': _count_period(reservations, 'created_at', week_ago),
        'reservations_30_days': _count_period(reservations, 'created_at', month_ago),
        'reservations_by_status': {
            value: reservations.filter(status=value).count()
            for value, _label in BusinessReservation.STATUS_CHOICES
        },
        'profile_views_total': profile_views.count(),
        'profile_views_week': _count_period(profile_views, 'created_at', week_ago),
        'profile_views_30_days': _count_period(profile_views, 'created_at', month_ago),
    }

    appointments = Appointment.objects.all()
    clinics = list(Clinic.objects.select_related('owner', 'schedule'))
    effective_plan_counts = {value: 0 for value, _label in Clinic.PLAN_STATUS_CHOICES}
    for clinic in clinics:
        effective_plan_counts[clinic.effective_plan_status] = effective_plan_counts.get(
            clinic.effective_plan_status, 0
        ) + 1
    veterinary = {
        'appointments_total': appointments.count(),
        'appointments_week': _count_period(appointments, 'created_at', week_ago),
        'appointments_30_days': _count_period(appointments, 'created_at', month_ago),
        'appointments_by_status': {
            value: appointments.filter(status=value).count()
            for value, _label in Appointment.STATUS_CHOICES
        },
        'clinics_with_schedule': ClinicSchedule.objects.count(),
        'clinics_receiving_appointments': sum(clinic.can_receive_appointments for clinic in clinics),
        'clinics_by_plan_status': effective_plan_counts,
    }

    today = timezone.localdate()
    first_day = today - timedelta(days=13)

    def daily_count_map(queryset):
        return {
            row['day']: row['count']
            for row in (
                queryset.filter(created_at__date__gte=first_day)
                .annotate(day=TruncDate('created_at'))
                .values('day')
                .annotate(count=Count('id'))
            )
        }

    daily_posts = daily_count_map(published_posts)
    daily_paws = daily_count_map(reactions)
    daily_comments = daily_count_map(comments)
    daily_follows = daily_count_map(follows)
    daily_messages = daily_count_map(messages)
    engagement_by_day = []
    for index in range(13, -1, -1):
        day = today - timedelta(days=index)
        engagement_by_day.append({
            'date': day.strftime('%d/%m'),
            'posts': daily_posts.get(day, 0),
            'paws': daily_paws.get(day, 0),
            'comments': daily_comments.get(day, 0),
            'follows': daily_follows.get(day, 0),
            'messages': daily_messages.get(day, 0),
        })

    top_posts = list(
        published_posts.select_related('pet', 'clinic', 'business', 'shelter')
        .annotate(
            paws_count=Count('reactions', distinct=True),
            comments_count=Count(
                'comments',
                filter=Q(comments__moderation_status=Comment.STATUS_PUBLISHED),
                distinct=True,
            ),
        )
        .order_by('-paws_count', '-comments_count', '-shares_count', '-created_at')[:10]
    )

    profile_rows = []
    profile_specs = (
        ('pet', Pet.objects.all(), 'name', 'owner_id'),
        ('clinic', Clinic.objects.all(), 'name', 'owner_id'),
        ('business', BusinessProfile.objects.all(), 'name', 'owner_id'),
        ('shelter', ShelterProfile.objects.all(), 'name', 'owner_id'),
    )
    for profile_type, queryset, name_field, owner_field in profile_specs:
        rows = queryset.annotate(
            posts_count=Count(
                'community_posts',
                filter=Q(community_posts__moderation_status=Post.STATUS_PUBLISHED),
                distinct=True,
            ),
            paws_count=Count(
                'community_posts__reactions',
                filter=Q(community_posts__moderation_status=Post.STATUS_PUBLISHED),
                distinct=True,
            ),
            comments_count=Count(
                'community_posts__comments',
                filter=Q(
                    community_posts__moderation_status=Post.STATUS_PUBLISHED,
                    community_posts__comments__moderation_status=Comment.STATUS_PUBLISHED,
                ),
                distinct=True,
            ),
            followers_count=Count('social_followers', distinct=True),
        ).order_by('-paws_count', '-comments_count', '-followers_count', '-posts_count')[:10]
        for row in rows:
            score = (
                row.posts_count * 2
                + row.paws_count
                + row.comments_count * 2
                + row.followers_count * 3
            )
            if score == 0:
                continue
            profile_rows.append({
                'profile_type': profile_type,
                'profile_id': row.id,
                'owner_id': getattr(row, owner_field, None),
                'name': getattr(row, name_field),
                'posts': row.posts_count,
                'paws': row.paws_count,
                'comments': row.comments_count,
                'followers': row.followers_count,
                'score': score,
            })
    profile_rows.sort(key=lambda item: (item['score'], item['paws'], item['followers']), reverse=True)

    top_businesses = list(
        BusinessProfile.objects.annotate(
            views_count=Count('profile_views', distinct=True),
            inquiries_count=Count('inquiries', distinct=True),
            reservations_count=Count('reservations', distinct=True),
            followers_count=Count('social_followers', distinct=True),
        ).order_by('-inquiries_count', '-reservations_count', '-views_count', '-followers_count')[:10]
    )
    top_shelters = list(
        ShelterProfile.objects.annotate(
            animals_count=Count('adoption_animals', distinct=True),
            adopted_count=Count(
                'adoption_animals',
                filter=Q(adoption_animals__status=AdoptionAnimal.STATUS_ADOPTED),
                distinct=True,
            ),
            applications_count=Count('adoption_animals__applications', distinct=True),
            help_offers_count=Count('adoption_animals__help_offers', distinct=True),
        ).order_by('-applications_count', '-help_offers_count', '-adopted_count', '-animals_count')[:10]
    )

    return {
        'community': community,
        'adoptions': adoptions,
        'businesses': businesses,
        'veterinary': veterinary,
        'engagement_by_day': engagement_by_day,
        'top_community_posts': [_serialize_top_post(post) for post in top_posts],
        'top_profiles': profile_rows[:10],
        'top_businesses': [
            {
                'id': business.id,
                'name': business.name,
                'locality': business.locality,
                'province': business.province,
                'views': business.views_count,
                'inquiries': business.inquiries_count,
                'reservations': business.reservations_count,
                'followers': business.followers_count,
            }
            for business in top_businesses
        ],
        'top_shelters': [
            {
                'id': shelter.id,
                'name': shelter.name,
                'locality': shelter.locality,
                'province': shelter.province,
                'animals': shelter.animals_count,
                'adopted': shelter.adopted_count,
                'applications': shelter.applications_count,
                'help_offers': shelter.help_offers_count,
            }
            for shelter in top_shelters
        ],
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

    interaction_stats = build_interaction_statistics(now)

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
        'interaction_stats': interaction_stats,
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
