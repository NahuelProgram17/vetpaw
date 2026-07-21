from django.db.models import Q
from django.utils import timezone

from .models import BlockedUser, CommunityNotification
from .push_utils import schedule_push_notification


def _can_notify(recipient, actor):
    if not recipient or not actor or recipient.id == actor.id:
        return False
    return not BlockedUser.objects.filter(
        Q(blocker=recipient, blocked=actor) | Q(blocker=actor, blocked=recipient)
    ).exists()


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
            'is_read': False,
        },
    )
    if not created:
        notification.pet = post.pet if post.pet_id else notification.pet
        notification.is_read = False
        notification.read_at = None
        notification.created_at = timezone.now()
        notification.save(
            update_fields=['pet', 'is_read', 'read_at', 'created_at', 'updated_at']
        )
    schedule_push_notification(notification)
    return notification


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

    if notification:
        notification.comment = comment
        notification.pet = post.pet if post.pet_id else notification.pet
        notification.extra_text = preview
        notification.read_at = None
        notification.created_at = timezone.now()
        notification.save(
            update_fields=[
                'comment', 'pet', 'extra_text', 'read_at', 'created_at', 'updated_at'
            ]
        )
        schedule_push_notification(notification)
        return notification

    notification = CommunityNotification.objects.create(
        recipient=recipient,
        actor=actor,
        post=post,
        comment=comment,
        pet=post.pet if post.pet_id else None,
        notification_type=CommunityNotification.TYPE_COMMENT,
        extra_text=preview,
    )
    schedule_push_notification(notification)
    return notification


def create_follow_notification(pet, actor):
    recipient = pet.owner
    if not _can_notify(recipient, actor):
        return None

    notification, created = CommunityNotification.objects.get_or_create(
        recipient=recipient,
        actor=actor,
        pet=pet,
        notification_type=CommunityNotification.TYPE_FOLLOW,
    )
    if not created:
        notification.is_read = False
        notification.read_at = None
        notification.created_at = timezone.now()
        notification.save(
            update_fields=['is_read', 'read_at', 'created_at', 'updated_at']
        )
    schedule_push_notification(notification)
    return notification


def remove_follow_notification(pet, actor):
    CommunityNotification.objects.filter(
        recipient=pet.owner,
        actor=actor,
        pet=pet,
        notification_type=CommunityNotification.TYPE_FOLLOW,
    ).delete()
