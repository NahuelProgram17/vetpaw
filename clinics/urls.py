from rest_framework.routers import DefaultRouter
from .views import ClinicViewSet, MembershipViewSet

router = DefaultRouter()
router.register(r'clinics', ClinicViewSet, basename='clinic')
router.register(r'memberships', MembershipViewSet, basename='membership')

urlpatterns = router.urls