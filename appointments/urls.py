from rest_framework.routers import DefaultRouter
from .views import VisitViewSet, AppointmentViewSet

router = DefaultRouter()
router.register(r'visits', VisitViewSet, basename='visit')
router.register(r'appointments', AppointmentViewSet, basename='appointment')

urlpatterns = router.urls