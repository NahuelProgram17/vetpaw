from rest_framework.routers import DefaultRouter

from .views import (
    BusinessDashboardViewSet,
    CatalogItemViewSet,
    FavoriteViewSet,
    InquiryViewSet,
    PromotionViewSet,
    ReservationViewSet,
)

router = DefaultRouter()
router.register(r'commerce/catalog', CatalogItemViewSet, basename='commerce-catalog')
router.register(r'commerce/promotions', PromotionViewSet, basename='commerce-promotion')
router.register(r'commerce/favorites', FavoriteViewSet, basename='commerce-favorite')
router.register(r'commerce/inquiries', InquiryViewSet, basename='commerce-inquiry')
router.register(r'commerce/reservations', ReservationViewSet, basename='commerce-reservation')
router.register(r'commerce/dashboard', BusinessDashboardViewSet, basename='commerce-dashboard')

urlpatterns = router.urls
