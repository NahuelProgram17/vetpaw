from community.models import CommunityNotification
from community.privacy import privacy_for, users_blocked_between
from community.push_utils import schedule_push_notification


def _notifications_enabled(user):
    settings = privacy_for(user)
    return not settings or settings.social_notifications_enabled


def notify_clinic_new_appointment(appointment):
    recipient = appointment.clinic.owner
    actor = appointment.owner
    if not recipient or not actor or users_blocked_between(recipient, actor) or not _notifications_enabled(recipient):
        return None
    pet_name = appointment.pet.name if appointment.pet_id else 'una mascota'
    source = appointment.source_campaign.title if appointment.source_campaign_id else (appointment.reason or 'una publicación veterinaria')
    notification = CommunityNotification.objects.create(
        recipient=recipient,
        actor=actor,
        post=appointment.source_post,
        clinic=appointment.clinic,
        appointment=appointment,
        notification_type=CommunityNotification.TYPE_CLINIC_APPOINTMENT,
        extra_text=f'{pet_name} · {source}'[:300],
    )
    schedule_push_notification(notification)
    return notification


def notify_owner_appointment_update(appointment):
    recipient = appointment.owner
    actor = appointment.clinic.owner
    if not recipient or not actor or users_blocked_between(recipient, actor) or not _notifications_enabled(recipient):
        return None
    labels = {
        'confirmed': 'Turno confirmado',
        'cancelled': 'Turno cancelado',
        'completed': 'Turno completado',
        'no_show': 'Marcado como ausente',
        'pending': 'Solicitud pendiente',
    }
    notification = CommunityNotification.objects.create(
        recipient=recipient,
        actor=actor,
        post=appointment.source_post,
        clinic=appointment.clinic,
        appointment=appointment,
        notification_type=CommunityNotification.TYPE_CLINIC_APPOINTMENT_UPDATE,
        extra_text=f"{labels.get(appointment.status, 'Turno actualizado')} · {appointment.clinic.name}"[:300],
    )
    schedule_push_notification(notification)
    return notification


def notify_clinic_appointment_update(appointment):
    recipient = appointment.clinic.owner
    actor = appointment.owner
    if not recipient or not actor or users_blocked_between(recipient, actor) or not _notifications_enabled(recipient):
        return None
    labels = {
        'confirmed': 'Turno confirmado',
        'cancelled': 'Turno cancelado por el dueño',
        'completed': 'Turno completado',
        'no_show': 'Marcado como ausente',
        'pending': 'Solicitud actualizada',
    }
    notification = CommunityNotification.objects.create(
        recipient=recipient,
        actor=actor,
        post=appointment.source_post,
        clinic=appointment.clinic,
        appointment=appointment,
        notification_type=CommunityNotification.TYPE_CLINIC_APPOINTMENT_UPDATE,
        extra_text=f"{labels.get(appointment.status, 'Turno actualizado')} · {appointment.clinic.name}"[:300],
    )
    schedule_push_notification(notification)
    return notification
