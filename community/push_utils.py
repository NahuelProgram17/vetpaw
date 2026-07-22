import json
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from pywebpush import WebPushException, webpush

from .models import CommunityNotification, PushSubscription
from .privacy import privacy_for

logger = logging.getLogger(__name__)

STALE_STATUS_CODES = {404, 410}
MAX_ACTIVE_SUBSCRIPTIONS = 5


def push_is_configured():
    return bool(
        getattr(settings, 'VAPID_PUBLIC_KEY', '')
        and getattr(settings, 'VAPID_PRIVATE_KEY', '')
        and getattr(settings, 'VAPID_SUBJECT', '')
    )


def _actor_name(notification):
    actor = notification.actor
    if actor.role == 'clinic':
        clinic = getattr(actor, 'clinic_profile', None)
        if clinic:
            return clinic.name
    if actor.role == 'business':
        business = getattr(actor, 'business_profile', None)
        if business:
            return business.name
    if actor.role == 'shelter':
        shelter = getattr(actor, 'shelter_profile', None)
        if shelter:
            return shelter.name
    return actor.get_full_name().strip() or actor.username


def _post_subject(notification):
    post = notification.post
    if not post:
        return 'tu publicación'
    if post.pet_id:
        return f'la publicación de {post.pet.name}'
    if post.clinic_id:
        return 'tu publicación de la veterinaria'
    if post.business_id:
        return 'tu publicación del negocio'
    if post.shelter_id:
        return 'tu publicación del refugio'
    if post.related_lost_pet_id:
        return 'tu aviso de mascota perdida o encontrada'
    return 'tu publicación'


def notification_message(notification):
    actor_name = _actor_name(notification)
    if notification.notification_type == CommunityNotification.TYPE_REACTION:
        return f'{actor_name} dejó una patita en {_post_subject(notification)}.'
    if notification.notification_type == CommunityNotification.TYPE_COMMENT:
        return f'{actor_name} comentó {_post_subject(notification)}.'
    if notification.notification_type == CommunityNotification.TYPE_COMMENT_REACTION:
        return f'{actor_name} dejó una patita en tu comentario.'
    if notification.notification_type == CommunityNotification.TYPE_REPLY:
        return f'{actor_name} respondió tu comentario.'
    if notification.notification_type == CommunityNotification.TYPE_MENTION:
        return f'{actor_name} te mencionó en VetPaw.'
    if notification.notification_type == CommunityNotification.TYPE_FOLLOW_REQUEST:
        target_name = notification.pet.name if notification.pet_id else 'tu perfil'
        return f'{actor_name} quiere seguir a {target_name}.'
    if notification.notification_type == CommunityNotification.TYPE_FOLLOW:
        if notification.pet_id:
            target_name = notification.pet.name
        elif notification.clinic_id:
            target_name = notification.clinic.name
        elif notification.business_id:
            target_name = notification.business.name
        elif notification.shelter_id:
            target_name = notification.shelter.name
        else:
            target_name = 'tu perfil'
        return f'{actor_name} comenzó a seguir a {target_name}.'
    return 'Tenés nueva actividad en VetPaw.'


def notification_target_url(notification):
    if notification.notification_type == CommunityNotification.TYPE_FOLLOW_REQUEST:
        target_name = notification.pet.name if notification.pet_id else 'tu perfil'
        return f'{actor_name} quiere seguir a {target_name}.'
    if notification.notification_type == CommunityNotification.TYPE_FOLLOW:
        if notification.pet_id:
            profile = getattr(notification.pet, 'social_profile', None)
            return f'/mascotas/{profile.slug if profile and profile.slug else notification.pet_id}'
        if notification.clinic_id:
            return f'/clinicas/{notification.clinic.slug}'
        if notification.business_id:
            return f'/negocios/{notification.business.slug}'
        if notification.shelter_id:
            return f'/refugios/{notification.shelter.slug}'
    if (
        notification.notification_type in {
            CommunityNotification.TYPE_COMMENT,
            CommunityNotification.TYPE_COMMENT_REACTION,
            CommunityNotification.TYPE_REPLY,
            CommunityNotification.TYPE_MENTION,
        }
        and notification.post_id
        and notification.comment_id
    ):
        return f'/comunidad?publicacion={notification.post_id}&comentario={notification.comment_id}'
    if notification.post_id:
        return f'/comunidad?publicacion={notification.post_id}'
    return '/notifications'


def build_push_payload(notification):
    return {
        'title': 'VetPaw 🐾',
        'body': notification_message(notification),
        'url': notification_target_url(notification),
        'icon': '/icon-192.png',
        'badge': '/icon-192.png',
        'tag': f'vetpaw-social-{notification.id}',
        'notification_id': notification.id,
        'notification_type': notification.notification_type,
    }


def _subscription_info(subscription):
    return {
        'endpoint': subscription.endpoint,
        'keys': {
            'p256dh': subscription.p256dh,
            'auth': subscription.auth,
        },
    }


def send_payload_to_subscription(subscription, payload):
    if not push_is_configured():
        return {'sent': False, 'reason': 'not_configured'}

    try:
        webpush(
            subscription_info=_subscription_info(subscription),
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={'sub': settings.VAPID_SUBJECT},
            ttl=getattr(settings, 'WEB_PUSH_TTL', 86400),
            timeout=getattr(settings, 'WEB_PUSH_TIMEOUT', 5),
        )
    except WebPushException as exc:
        status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
        now = timezone.now()
        subscription.failure_count += 1
        subscription.last_failure_at = now
        update_fields = ['failure_count', 'last_failure_at', 'updated_at']
        if status_code in STALE_STATUS_CODES or subscription.failure_count >= 3:
            subscription.is_active = False
            update_fields.append('is_active')
        subscription.save(update_fields=update_fields)
        logger.warning(
            'No se pudo enviar Web Push a la suscripción %s (HTTP %s).',
            subscription.id,
            status_code,
        )
        return {'sent': False, 'reason': 'push_error', 'status_code': status_code}
    except Exception:
        now = timezone.now()
        subscription.failure_count += 1
        subscription.last_failure_at = now
        if subscription.failure_count >= 3:
            subscription.is_active = False
        subscription.save(
            update_fields=[
                'failure_count', 'last_failure_at', 'is_active', 'updated_at'
            ]
        )
        logger.exception('Error inesperado al enviar Web Push a %s.', subscription.id)
        return {'sent': False, 'reason': 'unexpected_error'}

    now = timezone.now()
    subscription.failure_count = 0
    subscription.last_success_at = now
    subscription.last_failure_at = None
    subscription.is_active = True
    subscription.save(
        update_fields=[
            'failure_count', 'last_success_at', 'last_failure_at',
            'is_active', 'updated_at',
        ]
    )
    return {'sent': True}


def send_push_for_notification(notification_id):
    if not push_is_configured():
        return {'sent': 0, 'configured': False}

    try:
        notification = CommunityNotification.objects.select_related(
            'actor', 'actor__clinic_profile', 'pet', 'post__pet',
            'post__clinic', 'post__related_lost_pet',
        ).get(pk=notification_id)
    except CommunityNotification.DoesNotExist:
        return {'sent': 0, 'configured': True}

    payload = build_push_payload(notification)
    subscriptions = PushSubscription.objects.filter(
        user=notification.recipient,
        is_active=True,
    ).order_by('-updated_at')[:MAX_ACTIVE_SUBSCRIPTIONS]

    sent = 0
    for subscription in subscriptions:
        if send_payload_to_subscription(subscription, payload).get('sent'):
            sent += 1
    return {'sent': sent, 'configured': True}


def schedule_push_notification(notification):
    if not notification or not push_is_configured():
        return
    settings = privacy_for(notification.recipient)
    if settings and not settings.push_notifications_enabled:
        return
    notification_id = notification.pk
    transaction.on_commit(lambda: send_push_for_notification(notification_id))


def send_test_push(subscription):
    payload = {
        'title': 'VetPaw 🐾',
        'body': '¡Las notificaciones están activadas correctamente en este dispositivo!',
        'url': '/notifications',
        'icon': '/icon-192.png',
        'badge': '/icon-192.png',
        'tag': 'vetpaw-push-test',
        'notification_type': 'test',
    }
    return send_payload_to_subscription(subscription, payload)
