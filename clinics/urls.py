from rest_framework.routers import DefaultRouter
from .views import ClinicViewSet, MembershipViewSet, ClinicPhotoViewSet, ClinicScheduleViewSet

router = DefaultRouter()
router.register(r'clinics', ClinicViewSet, basename='clinic')
router.register(r'memberships', MembershipViewSet, basename='membership')
router.register(r'clinic-photos', ClinicPhotoViewSet, basename='clinic-photo')
router.register(r'clinic-schedule', ClinicScheduleViewSet, basename='clinic-schedule')

urlpatterns = router.urls