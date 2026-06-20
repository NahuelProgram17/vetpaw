from rest_framework.routers import DefaultRouter
from .views import PetViewSet, VaccineViewSet, ClinicalPhotoViewSet, TreatmentViewSet

router = DefaultRouter()
router.register(r'pets', PetViewSet, basename='pet')
router.register(r'vaccines', VaccineViewSet, basename='vaccine')
router.register(r'clinical-photos', ClinicalPhotoViewSet, basename='clinical-photo')
router.register(r'treatments', TreatmentViewSet, basename='treatment')

urlpatterns = router.urls