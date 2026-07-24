import hashlib
import re
import unicodedata
from datetime import timedelta
from difflib import SequenceMatcher

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_ipv46_address
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import APIException

from .models import AbuseAction, AbuseSignal


URL_RE = re.compile(r'https?://[^\s<>()]+|www\.[^\s<>()]+', re.IGNORECASE)
ZERO_WIDTH_RE = re.compile(r'[\u200b-\u200d\ufeff]')
SPACE_RE = re.compile(r'\s+')


class AbuseProtectionTriggered(APIException):
    status_code = 429
    default_code = 'abuse_protection'
    default_detail = 'VetPaw frenó temporalmente esta acción para proteger a la comunidad.'

    def __init__(self, message, code='abuse_protection'):
        super().__init__({'error': message, 'code': code})


def get_client_ip(request):
    if not request:
        return None
    forwarded = str(request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
    candidate = forwarded or str(request.META.get('REMOTE_ADDR') or '').strip()
    if not candidate:
        return None
    try:
        validate_ipv46_address(candidate)
    except DjangoValidationError:
        return None
    return candidate


def normalize_content(value):
    value = unicodedata.normalize('NFKC', str(value or '')).lower()
    value = ZERO_WIDTH_RE.sub('', value)
    value = SPACE_RE.sub(' ', value).strip()
    return value


def content_fingerprint(value):
    normalized = normalize_content(value)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest() if normalized else ''


def extract_links(value):
    links = []
    for raw in URL_RE.findall(str(value or '')):
        cleaned = raw.rstrip('.,;:!?)]}\'"').lower()
        if cleaned.startswith('www.'):
            cleaned = f'https://{cleaned}'
        links.append(cleaned)
    return sorted(set(links))


def links_fingerprint(value):
    links = extract_links(value)
    if not links:
        return ''
    return hashlib.sha256('\n'.join(links).encode('utf-8')).hexdigest()


def _severity_rank(value):
    return {
        AbuseSignal.SEVERITY_INFO: 1,
        AbuseSignal.SEVERITY_WARNING: 2,
        AbuseSignal.SEVERITY_HIGH: 3,
    }.get(value, 1)


def record_abuse_signal(
    *,
    category,
    action_key='',
    user=None,
    request=None,
    ip_address=None,
    severity=AbuseSignal.SEVERITY_WARNING,
    fingerprint='',
    content='',
    details=None,
    aggregate_minutes=1440,
):
    now = timezone.now()
    ip_address = ip_address or get_client_ip(request)
    since = now - timedelta(minutes=max(1, aggregate_minutes))
    queryset = AbuseSignal.objects.filter(
        category=category,
        action_key=action_key or '',
        status=AbuseSignal.STATUS_PENDING,
        fingerprint=fingerprint or '',
        last_seen_at__gte=since,
    )
    if user and getattr(user, 'pk', None):
        queryset = queryset.filter(user=user)
    elif ip_address:
        queryset = queryset.filter(user__isnull=True, ip_address=ip_address)
    else:
        queryset = queryset.filter(user__isnull=True, ip_address__isnull=True)

    with transaction.atomic():
        existing = queryset.select_for_update().order_by('-last_seen_at').first()
        if existing:
            existing.occurrences += 1
            existing.last_seen_at = now
            if _severity_rank(severity) > _severity_rank(existing.severity):
                existing.severity = severity
            merged = dict(existing.details or {})
            merged.update(details or {})
            existing.details = merged
            if content and not existing.content_excerpt:
                existing.content_excerpt = normalize_content(content)[:300]
            existing.save(update_fields=[
                'occurrences', 'last_seen_at', 'severity', 'details',
                'content_excerpt', 'updated_at',
            ])
            return existing
        return AbuseSignal.objects.create(
            user=user if user and getattr(user, 'pk', None) else None,
            ip_address=ip_address,
            category=category,
            severity=severity,
            action_key=action_key or '',
            fingerprint=fingerprint or '',
            content_excerpt=normalize_content(content)[:300],
            details=details or {},
            first_seen_at=now,
            last_seen_at=now,
        )


def record_successful_action(*, user=None, request=None, action_type, text='', target_key=''):
    normalized = normalize_content(text)
    action = AbuseAction.objects.create(
        user=user if user and getattr(user, 'pk', None) else None,
        ip_address=get_client_ip(request),
        action_type=action_type,
        fingerprint=content_fingerprint(normalized),
        link_fingerprint=links_fingerprint(normalized),
        target_key=str(target_key or '')[:120],
        content_excerpt=normalized[:500],
    )
    if user and getattr(user, 'pk', None):
        now = timezone.now()
        joined = getattr(user, 'date_joined', None)
        if joined and joined >= now - timedelta(minutes=20):
            recent_count = AbuseAction.objects.filter(
                user=user,
                created_at__gte=now - timedelta(minutes=10),
            ).count()
            if recent_count >= 15:
                record_abuse_signal(
                    user=user,
                    request=request,
                    category=AbuseSignal.CATEGORY_ACCOUNT_RISK,
                    action_key='new_account_activity',
                    severity=(
                        AbuseSignal.SEVERITY_HIGH
                        if recent_count >= 25
                        else AbuseSignal.SEVERITY_WARNING
                    ),
                    details={'actions_in_10_minutes': recent_count},
                    aggregate_minutes=60,
                )
    return action


def guard_text_action(
    *,
    user,
    request,
    action_type,
    text,
    target_key='',
    duplicate_minutes=20,
    repeated_link_limit=3,
    minimum_length=18,
    similarity_threshold=0.94,
    duplicate_limit=1,
):
    normalized = normalize_content(text)
    if not normalized:
        return
    now = timezone.now()
    recent = AbuseAction.objects.filter(
        user=user,
        action_type=action_type,
        created_at__gte=now - timedelta(minutes=duplicate_minutes),
    ).order_by('-created_at')[:30]
    rows = list(recent)
    fingerprint = content_fingerprint(normalized)

    if len(normalized) >= minimum_length:
        exact = [row for row in rows if row.fingerprint and row.fingerprint == fingerprint]
        similar = []
        if not exact and len(normalized) >= 40:
            similar = [
                row for row in rows
                if row.content_excerpt
                and SequenceMatcher(None, normalized[:500], row.content_excerpt).ratio() >= similarity_threshold
            ]
        matches = len(exact or similar)
        if matches >= max(1, duplicate_limit):
            record_abuse_signal(
                user=user,
                request=request,
                category=AbuseSignal.CATEGORY_DUPLICATE_CONTENT,
                action_key=action_type,
                severity=(
                    AbuseSignal.SEVERITY_HIGH
                    if matches >= 2
                    else AbuseSignal.SEVERITY_WARNING
                ),
                fingerprint=fingerprint,
                content=normalized,
                details={
                    'matches': matches,
                    'target_key': str(target_key or ''),
                    'window_minutes': duplicate_minutes,
                },
                aggregate_minutes=duplicate_minutes,
            )
            raise AbuseProtectionTriggered(
                'Esa acción repite contenido enviado hace muy poco. Esperá unos minutos o cambiá el texto.',
                code='duplicate_content',
            )

    link_hash = links_fingerprint(normalized)
    if link_hash:
        repeats = sum(1 for row in rows if row.link_fingerprint == link_hash)
        if repeats >= repeated_link_limit:
            record_abuse_signal(
                user=user,
                request=request,
                category=AbuseSignal.CATEGORY_REPEATED_LINK,
                action_key=action_type,
                severity=AbuseSignal.SEVERITY_HIGH,
                fingerprint=link_hash,
                content=normalized,
                details={
                    'previous_occurrences': repeats,
                    'target_key': str(target_key or ''),
                    'window_minutes': duplicate_minutes,
                },
                aggregate_minutes=duplicate_minutes,
            )
            raise AbuseProtectionTriggered(
                'Ese enlace fue compartido demasiadas veces en poco tiempo.',
                code='repeated_link',
            )


def record_registration(user, request):
    action = record_successful_action(
        user=user,
        request=request,
        action_type=AbuseAction.ACTION_REGISTRATION,
        target_key=f'user:{user.pk}',
    )
    if not action.ip_address:
        return action
    now = timezone.now()
    total = AbuseAction.objects.filter(
        ip_address=action.ip_address,
        action_type=AbuseAction.ACTION_REGISTRATION,
        created_at__gte=now - timedelta(hours=24),
    ).count()
    if total >= 3:
        record_abuse_signal(
            user=user,
            request=request,
            category=AbuseSignal.CATEGORY_REGISTRATION_BURST,
            action_key='registration',
            severity=AbuseSignal.SEVERITY_HIGH if total >= 5 else AbuseSignal.SEVERITY_WARNING,
            details={'registrations_from_ip_24h': total},
            aggregate_minutes=1440,
        )
    return action


def record_false_report_pattern(reporter, request=None):
    from community.models import Report

    now = timezone.now()
    dismissed = Report.objects.filter(
        reporter=reporter,
        status=Report.STATUS_DISMISSED,
        reviewed_at__gte=now - timedelta(days=30),
    ).count()
    if dismissed < 3:
        return None
    return record_abuse_signal(
        user=reporter,
        request=request,
        category=AbuseSignal.CATEGORY_FALSE_REPORT,
        action_key='report',
        severity=AbuseSignal.SEVERITY_HIGH if dismissed >= 5 else AbuseSignal.SEVERITY_WARNING,
        details={'dismissed_reports_30_days': dismissed},
        aggregate_minutes=1440,
    )


def risk_score_for_signals(signals):
    score = 0
    for signal in signals:
        weight = {
            AbuseSignal.SEVERITY_INFO: 1,
            AbuseSignal.SEVERITY_WARNING: 3,
            AbuseSignal.SEVERITY_HIGH: 8,
        }.get(signal.severity, 1)
        score += weight + min(max(signal.occurrences - 1, 0), 5)
    return score


def risk_status_for_score(score, active_sanction=None):
    if active_sanction and active_sanction.kind == active_sanction.KIND_SUSPENSION:
        return 'temporarily_blocked'
    if active_sanction and active_sanction.kind == active_sanction.KIND_PERMANENT_BAN:
        return 'banned'
    if score >= 12:
        return 'high_risk'
    if score >= 4:
        return 'watch'
    return 'normal'
