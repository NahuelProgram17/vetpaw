from rest_framework.routers import DefaultRouter

from .views import BusinessProfileViewSet, ShelterProfileViewSet

router = DefaultRouter()
router.register(r'businesses', BusinessProfileViewSet, basename='business-profile')
router.register(r'shelters', ShelterProfileViewSet, basename='shelter-profile')

urlpatterns = router.urls
