from rest_framework.routers import DefaultRouter
from .views import ClinicViewSet, MembershipViewSet, ClinicPhotoViewSet

router = DefaultRouter()
router.register(r'clinics', ClinicViewSet, basename='clinic')
router.register(r'memberships', MembershipViewSet, basename='membership')
router.register(r'clinic-photos', ClinicPhotoViewSet, basename='clinic-photo')

urlpatterns = router.urls