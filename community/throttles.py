from rest_framework.throttling import SimpleRateThrottle

from users.abuse import get_client_ip, record_abuse_signal
from users.models import AbuseSignal


class AbuseAwareRateThrottle(SimpleRateThrottle):
    signal_category = AbuseSignal.CATEGORY_RATE_LIMIT
    signal_action_key = 'community_action'
    signal_severity = AbuseSignal.SEVERITY_WARNING

    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        if not allowed:
            record_abuse_signal(
                user=request.user if request.user.is_authenticated else None,
                request=request,
                category=self.signal_category,
                action_key=self.signal_action_key,
                severity=self.signal_severity,
                details={
                    'scope': self.scope,
                    'rate': self.rate,
                    'path': request.path[:300],
                    'method': request.method,
                },
                aggregate_minutes=60,
            )
        return allowed

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = f'user-{request.user.pk}'
        else:
            ident = get_client_ip(request) or self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class CommunityPostThrottle(AbuseAwareRateThrottle):
    scope = 'community_post'
    rate = '20/hour'
    signal_action_key = 'post'


class CommunityPostBurstThrottle(AbuseAwareRateThrottle):
    scope = 'community_post_burst'
    rate = '4/minute'
    signal_action_key = 'post'
    signal_severity = AbuseSignal.SEVERITY_HIGH


class CommunityCommentThrottle(AbuseAwareRateThrottle):
    scope = 'community_comment'
    rate = '120/hour'
    signal_action_key = 'comment'


class CommunityCommentBurstThrottle(AbuseAwareRateThrottle):
    scope = 'community_comment_burst'
    rate = '12/minute'
    signal_action_key = 'comment'
    signal_severity = AbuseSignal.SEVERITY_HIGH


class CommunityActionThrottle(AbuseAwareRateThrottle):
    scope = 'community_action'
    rate = '300/hour'
    signal_action_key = 'community_action'


class CommunityFollowThrottle(AbuseAwareRateThrottle):
    scope = 'community_follow'
    rate = '12/minute'
    signal_category = AbuseSignal.CATEGORY_MASS_FOLLOW
    signal_action_key = 'follow'
    signal_severity = AbuseSignal.SEVERITY_HIGH


class CommunityReportThrottle(AbuseAwareRateThrottle):
    scope = 'community_report'
    rate = '12/day'
    signal_action_key = 'report'
    signal_severity = AbuseSignal.SEVERITY_HIGH


class CommunityReportBurstThrottle(AbuseAwareRateThrottle):
    scope = 'community_report_burst'
    rate = '3/minute'
    signal_action_key = 'report'
    signal_severity = AbuseSignal.SEVERITY_HIGH


class CommunityExploreThrottle(SimpleRateThrottle):
    scope = 'community_explore'
    rate = '240/hour'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = f'user-{request.user.pk}'
        else:
            ident = get_client_ip(request) or self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}
