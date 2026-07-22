from community.models import CommunityNotification
from community.notification_utils import _can_notify
from community.push_utils import schedule_push_notification


def create_business_notification(recipient, actor, business, notification_type, text=''):
    if not _can_notify(recipient, actor):
        return None
    notification = CommunityNotification.objects.create(
        recipient=recipient,
        actor=actor,
        business=business,
        notification_type=notification_type,
        extra_text=(text or '')[:300],
    )
    schedule_push_notification(notification)
    return notification
