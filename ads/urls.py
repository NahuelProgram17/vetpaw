from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import AdvertiserViewSet, active_ads

router = DefaultRouter()
router.register(r'ads', AdvertiserViewSet, basename='advertiser')

urlpatterns = [
    path('ads/active/', active_ads, name='active-ads'),
] + router.urls
