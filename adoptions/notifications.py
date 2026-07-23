from community.models import CommunityNotification
from community.notification_utils import _can_notify
from community.push_utils import schedule_push_notification


def notify_shelter_new_application(application):
    recipient = application.animal.shelter.owner
    actor = application.applicant
    if not _can_notify(recipient, actor):
        return None

    notification, created = CommunityNotification.objects.get_or_create(
        recipient=recipient,
        actor=actor,
        adoption_animal=application.animal,
        adoption_application=application,
        notification_type=CommunityNotification.TYPE_ADOPTION_APPLICATION,
        defaults={
            'shelter': application.animal.shelter,
            'extra_text': application.animal.name[:300],
        },
    )
    if created:
        schedule_push_notification(notification)
    return notification


def notify_shelter_help_offer(offer):
    recipient = offer.animal.shelter.owner
    actor = offer.user
    if not _can_notify(recipient, actor):
        return None

    notification, created = CommunityNotification.objects.get_or_create(
        recipient=recipient,
        actor=actor,
        adoption_animal=offer.animal,
        help_offer=offer,
        notification_type=CommunityNotification.TYPE_ADOPTION_HELP_OFFER,
        defaults={
            'shelter': offer.animal.shelter,
            'extra_text': offer.get_help_type_display()[:300],
        },
    )
    if created:
        schedule_push_notification(notification)
    return notification


def notify_applicant_application_update(application, *, status_changed=False, notes_changed=False):
    recipient = application.applicant
    actor = application.animal.shelter.owner
    if not (status_changed or notes_changed) or not _can_notify(recipient, actor):
        return None

    details = []
    if status_changed:
        details.append(application.get_status_display())
    if notes_changed:
        details.append('El refugio agregó una observación')

    notification = CommunityNotification.objects.create(
        recipient=recipient,
        actor=actor,
        shelter=application.animal.shelter,
        adoption_animal=application.animal,
        adoption_application=application,
        notification_type=CommunityNotification.TYPE_ADOPTION_APPLICATION_UPDATE,
        extra_text=' · '.join(details)[:300],
    )
    schedule_push_notification(notification)
    return notification
