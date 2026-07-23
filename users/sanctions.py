from django.db.models import Q
from django.utils import timezone

from .models import AccountSanction


def active_sanctions_queryset(now=None):
    now = now or timezone.now()
    return AccountSanction.objects.filter(revoked_at__isnull=True).filter(
        Q(kind=AccountSanction.KIND_PERMANENT_BAN)
        | Q(kind=AccountSanction.KIND_SUSPENSION, ends_at__gt=now)
    )


def get_active_sanction(user, now=None):
    if not user or not getattr(user, 'pk', None):
        return None
    return (
        active_sanctions_queryset(now)
        .filter(user=user)
        .select_related('user', 'applied_by', 'revoked_by')
        .order_by('-created_at')
        .first()
    )


def _iso(value):
    return value.isoformat() if value else None


def serialize_account_sanction(sanction):
    if not sanction:
        return None
    status = sanction.effective_status
    return {
        'id': sanction.id,
        'user_id': sanction.user_id,
        'kind': sanction.kind,
        'kind_display': sanction.get_kind_display(),
        'status': status,
        'status_display': {
            AccountSanction.STATUS_ACTIVE: 'Activa',
            AccountSanction.STATUS_EXPIRED: 'Vencida',
            AccountSanction.STATUS_REVOKED: 'Revocada',
        }.get(status, status),
        'reason': sanction.reason,
        'internal_note': sanction.internal_note,
        'starts_at': _iso(sanction.starts_at),
        'ends_at': _iso(sanction.ends_at),
        'applied_by_id': sanction.applied_by_id,
        'applied_by': sanction.applied_by.username if sanction.applied_by_id else '',
        'source_report_id': sanction.source_report_id,
        'revoked_at': _iso(sanction.revoked_at),
        'revoked_by_id': sanction.revoked_by_id,
        'revoked_by': sanction.revoked_by.username if sanction.revoked_by_id else '',
        'revocation_note': sanction.revocation_note,
        'created_at': _iso(sanction.created_at),
        'updated_at': _iso(sanction.updated_at),
    }


def sanction_error_payload(sanction):
    is_ban = sanction.kind == AccountSanction.KIND_PERMANENT_BAN
    return {
        'detail': (
            'Tu cuenta fue expulsada permanentemente de VetPaw.'
            if is_ban
            else 'Tu cuenta está suspendida temporalmente.'
        ),
        'code': 'account_banned' if is_ban else 'account_suspended',
        'account_sanction': {
            'kind': sanction.kind,
            'kind_display': sanction.get_kind_display(),
            'reason': sanction.reason,
            'starts_at': _iso(sanction.starts_at),
            'ends_at': _iso(sanction.ends_at),
        },
    }
