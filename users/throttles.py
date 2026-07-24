from rest_framework.throttling import SimpleRateThrottle

from .abuse import get_client_ip, record_abuse_signal
from .models import AbuseSignal


class RegistrationThrottle(SimpleRateThrottle):
    scope = 'registration_hourly'
    rate = '3/hour'

    def get_cache_key(self, request, view):
        ident = get_client_ip(request) or self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}

    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        if not allowed:
            record_abuse_signal(
                request=request,
                category=AbuseSignal.CATEGORY_REGISTRATION_BURST,
                action_key='registration',
                severity=AbuseSignal.SEVERITY_HIGH,
                details={'scope': self.scope, 'rate': self.rate, 'path': request.path[:300]},
                aggregate_minutes=1440,
            )
        return allowed


class RegistrationDailyThrottle(RegistrationThrottle):
    scope = 'registration_daily'
    rate = '8/day'
