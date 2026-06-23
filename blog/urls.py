from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import PostViewSet, published_posts, post_detail

router = DefaultRouter()
router.register(r'posts', PostViewSet, basename='post')

urlpatterns = [
    path('blog/published/', published_posts, name='published-posts'),
    path('blog/post/<slug:slug>/', post_detail, name='post-detail'),
] + router.urls
