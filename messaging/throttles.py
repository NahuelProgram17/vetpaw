from rest_framework.throttling import SimpleRateThrottle

from users.abuse import get_client_ip, record_abuse_signal
from users.models import AbuseSignal


class MessageRateThrottle(SimpleRateThrottle):
    scope = 'messages_hourly'
    rate = '120/hour'

    def get_cache_key(self, request, view):
        ident = f'user-{request.user.pk}' if request.user.is_authenticated else (get_client_ip(request) or self.get_ident(request))
        return self.cache_format % {'scope': self.scope, 'ident': ident}

    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        if not allowed:
            record_abuse_signal(
                user=request.user if request.user.is_authenticated else None,
                request=request,
                category=AbuseSignal.CATEGORY_RATE_LIMIT,
                action_key='message',
                severity=AbuseSignal.SEVERITY_HIGH,
                details={'scope': self.scope, 'rate': self.rate, 'path': request.path[:300]},
                aggregate_minutes=60,
            )
        return allowed


class MessageBurstThrottle(MessageRateThrottle):
    scope = 'messages_burst'
    rate = '15/minute'
