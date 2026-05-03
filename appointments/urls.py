from rest_framework.routers import DefaultRouter
from .views import VisitViewSet, AppointmentViewSet, ReviewViewSet

router = DefaultRouter()
router.register(r'visits', VisitViewSet, basename='visit')
router.register(r'appointments', AppointmentViewSet, basename='appointment')
router.register(r'reviews', ReviewViewSet, basename='review')

urlpatterns = router.urls