from rest_framework.throttling import SimpleRateThrottle


class CommunityPostThrottle(SimpleRateThrottle):
    scope = 'community_post'
    rate = '20/hour'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            return self.cache_format % {'scope': self.scope, 'ident': request.user.pk}
        return None


class CommunityCommentThrottle(SimpleRateThrottle):
    scope = 'community_comment'
    rate = '120/hour'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            return self.cache_format % {'scope': self.scope, 'ident': request.user.pk}
        return None


class CommunityActionThrottle(SimpleRateThrottle):
    scope = 'community_action'
    rate = '300/hour'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            return self.cache_format % {'scope': self.scope, 'ident': request.user.pk}
        return None
