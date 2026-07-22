from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .explore import community_explore

from .views import (
    BlockedUserViewSet,
    CommentViewSet,
    CommunityNotificationViewSet,
    CommunityPostViewSet,
    PetSocialProfileViewSet,
    PushSubscriptionViewSet,
    ReportViewSet,
    community_discover,
    community_profile_connections,
    community_profile_follow,
)

router = DefaultRouter()
router.register(r'community/posts', CommunityPostViewSet, basename='community-post')
router.register(r'community/comments', CommentViewSet, basename='community-comment')
router.register(r'community/notifications', CommunityNotificationViewSet, basename='community-notification')
router.register(r'community/push', PushSubscriptionViewSet, basename='community-push')
router.register(r'community/pets', PetSocialProfileViewSet, basename='community-pet')
router.register(r'community/reports', ReportViewSet, basename='community-report')
router.register(r'community/blocks', BlockedUserViewSet, basename='community-block')

urlpatterns = [
    path('', include(router.urls)),
    path('community/discover/', community_discover, name='community-discover'),
    path('community/explore/', community_explore, name='community-explore'),
    path('community/profiles/<str:profile_type>/<str:identifier>/follow/', community_profile_follow, name='community-profile-follow'),
    path('community/profiles/<str:profile_type>/<str:identifier>/connections/', community_profile_connections, name='community-profile-connections'),
]
