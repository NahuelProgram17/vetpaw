import re

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from .models import BlockedUser, CommunityNotification, MutedUser
from .privacy import privacy_for
from .push_utils import schedule_push_notification

MENTION_PATTERN = re.compile(r'(?<![\w@])@([\w.+-]{3,150})', re.UNICODE)


def _can_notify(recipient, actor):
    if not recipient or not actor or recipient.id == actor.id:
        return False
    settings = privacy_for(recipient)
    if settings and not settings.social_notifications_enabled:
        return False
    if MutedUser.objects.filter(user=recipient, muted=actor).exists():
        return False
    return not BlockedUser.objects.filter(
        Q(blocker=recipient, blocked=actor) | Q(blocker=actor, blocked=recipient)
    ).exists()


def _refresh_notification(notification, **fields):
    for key, value in fields.items():
        setattr(notification, key, value)
    notification.is_read = False
    notification.read_at = None
    notification.created_at = timezone.now()
    update_fields = list(fields.keys()) + ['is_read', 'read_at', 'created_at', 'updated_at']
    notification.save(update_fields=list(dict.fromkeys(update_fields)))
    schedule_push_notification(notification)
    return notification


def create_reaction_notification(post, actor):
    recipient = post.created_by
    if not _can_notify(recipient, actor):
        return None

    notification, created = CommunityNotification.objects.get_or_create(
        recipient=recipient,
        actor=actor,
        post=post,
        notification_type=CommunityNotification.TYPE_REACTION,
        defaults={
            'pet': post.pet if post.pet_id else None,
            'clinic': post.clinic if post.clinic_id else None,
            'business': post.business if post.business_id else None,
            'shelter': post.shelter if post.shelter_id else None,
        },
    )
    if created:
        schedule_push_notification(notification)
        return notification
    return _refresh_notification(
        notification,
        pet=post.pet if post.pet_id else notification.pet,
        clinic=post.clinic if post.clinic_id else notification.clinic,
        business=post.business if post.business_id else notification.business,
        shelter=post.shelter if post.shelter_id else notification.shelter,
    )


def remove_reaction_notification(post, actor):
    CommunityNotification.objects.filter(
        recipient=post.created_by,
        actor=actor,
        post=post,
        notification_type=CommunityNotification.TYPE_REACTION,
    ).delete()


def create_comment_notification(post, actor, comment):
    recipient = post.created_by
    if not _can_notify(recipient, actor):
        return None

    preview = (comment.text or '').strip()[:300]
    notification = CommunityNotification.objects.filter(
        recipient=recipient,
        actor=actor,
        post=post,
        notification_type=CommunityNotification.TYPE_COMMENT,
        is_read=False,
    ).first()

    target_fields = {
        'comment': comment,
        'pet': post.pet if post.pet_id else None,
        'clinic': post.clinic if post.clinic_id else None,
        'business': post.business if post.business_id else None,
        'shelter': post.shelter if post.shelter_id else None,
        'extra_text': preview,
    }
    if notification:
        return _refresh_notification(notification, **target_fields)

    notification = CommunityNotification.objects.create(
        recipient=recipient,
        actor=actor,
        post=post,
        notification_type=CommunityNotification.TYPE_COMMENT,
        **target_fields,
    )
    schedule_push_notification(notification)
    return notification


def create_reply_notification(parent, reply, actor):
    recipient = parent.author
    if not _can_notify(recipient, actor):
        return None
    preview = (reply.text or '').strip()[:300]
    notification, created = CommunityNotification.objects.get_or_create(
        recipient=recipient,
        actor=actor,
        post=reply.post,
        comment=reply,
        notification_type=CommunityNotification.TYPE_REPLY,
        defaults={'extra_text': preview},
    )
    if created:
        schedule_push_notification(notification)
        return notification
    return _refresh_notification(notification, extra_text=preview)


def create_comment_reaction_notification(comment, actor):
    recipient = comment.author
    if not _can_notify(recipient, actor):
        return None
    notification, created = CommunityNotification.objects.get_or_create(
        recipient=recipient,
        actor=actor,
        post=comment.post,
        comment=comment,
        notification_type=CommunityNotification.TYPE_COMMENT_REACTION,
    )
    if created:
        schedule_push_notification(notification)
        return notification
    return _refresh_notification(notification)


def remove_comment_reaction_notification(comment, actor):
    CommunityNotification.objects.filter(
        recipient=comment.author,
        actor=actor,
        comment=comment,
        notification_type=CommunityNotification.TYPE_COMMENT_REACTION,
    ).delete()


def sync_mention_notifications(text, actor, post, comment=None, exclude_recipient_ids=None):
    """Sincroniza menciones hechas por un usuario en una publicación o comentario."""
    base = CommunityNotification.objects.filter(
        actor=actor,
        post=post,
        notification_type=CommunityNotification.TYPE_MENTION,
    )
    if comment is None:
        base = base.filter(comment__isnull=True)
    else:
        base = base.filter(comment=comment)

    usernames = {match for match in MENTION_PATTERN.findall(text or '')}
    User = get_user_model()
    username_query = Q(pk__in=[])
    for username in usernames:
        username_query |= Q(username__iexact=username)
    recipients = list(User.objects.filter(username_query, is_active=True)) if usernames else []
    excluded = set(exclude_recipient_ids or [])
    recipient_ids = {
        user.id for user in recipients
        if user.id not in excluded and _can_notify(user, actor)
    }
    base.exclude(recipient_id__in=recipient_ids).delete()

    created_notifications = []
    preview = (text or '').strip()[:300]
    for recipient in recipients:
        if recipient.id not in recipient_ids:
            continue
        notification, created = CommunityNotification.objects.get_or_create(
            recipient=recipient,
            actor=actor,
            post=post,
            comment=comment,
            notification_type=CommunityNotification.TYPE_MENTION,
            defaults={'extra_text': preview},
        )
        if created:
            schedule_push_notification(notification)
        else:
            _refresh_notification(notification, extra_text=preview)
        created_notifications.append(notification)
    return created_notifications


def create_follow_request_notification(pet, actor):
    recipient = pet.owner
    if not _can_notify(recipient, actor):
        return None
    notification, created = CommunityNotification.objects.get_or_create(
        recipient=recipient,
        actor=actor,
        pet=pet,
        notification_type=CommunityNotification.TYPE_FOLLOW_REQUEST,
    )
    if created:
        schedule_push_notification(notification)
        return notification
    return _refresh_notification(notification)


def remove_follow_request_notification(pet, actor):
    CommunityNotification.objects.filter(
        recipient=pet.owner,
        actor=actor,
        pet=pet,
        notification_type=CommunityNotification.TYPE_FOLLOW_REQUEST,
    ).delete()


def _target_data(target):
    from clinics.models import Clinic
    from partners.models import BusinessProfile, ShelterProfile
    from pets.models import Pet

    if isinstance(target, Pet):
        return target.owner, {'pet': target}, 'pet'
    if isinstance(target, Clinic):
        return target.owner, {'clinic': target}, 'clinic'
    if isinstance(target, BusinessProfile):
        return target.owner, {'business': target}, 'business'
    if isinstance(target, ShelterProfile):
        return target.owner, {'shelter': target}, 'shelter'
    raise TypeError('Perfil de seguimiento no compatible.')


def create_follow_notification(target, actor):
    recipient, target_fields, _ = _target_data(target)
    if not _can_notify(recipient, actor):
        return None

    notification, created = CommunityNotification.objects.get_or_create(
        recipient=recipient,
        actor=actor,
        notification_type=CommunityNotification.TYPE_FOLLOW,
        **target_fields,
    )
    if created:
        schedule_push_notification(notification)
        return notification
    return _refresh_notification(notification)


def remove_follow_notification(target, actor):
    recipient, target_fields, _ = _target_data(target)
    CommunityNotification.objects.filter(
        recipient=recipient,
        actor=actor,
        notification_type=CommunityNotification.TYPE_FOLLOW,
        **target_fields,
    ).delete()
