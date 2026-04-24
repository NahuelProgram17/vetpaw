from rest_framework.routers import DefaultRouter
from .views import PetViewSet, VaccineViewSet

router = DefaultRouter()
router.register(r'pets', PetViewSet, basename='pet')
router.register(r'vaccines', VaccineViewSet, basename='vaccine')

urlpatterns = router.urls