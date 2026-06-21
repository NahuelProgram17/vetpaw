from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import AdvertiserViewSet, active_ads, register_click

router = DefaultRouter()
router.register(r'ads', AdvertiserViewSet, basename='advertiser')

urlpatterns = [
    path('ads/active/', active_ads, name='active-ads'),
    path('ads/<int:pk>/click/', register_click, name='ad-click'),
] + router.urls
