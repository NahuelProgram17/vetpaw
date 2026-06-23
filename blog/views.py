from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from .models import Post
from .serializers import PostListSerializer, PostSerializer
from users.admin_panel_views import is_admin


class IsAdminUsername(permissions.BasePermission):
    def has_permission(self, request, view):
        return is_admin(request.user)


class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [IsAdminUsername]
    parser_classes = [MultiPartParser, FormParser, JSONParser]


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def published_posts(request):
    qs = Post.objects.filter(is_published=True)
    data = PostListSerializer(qs, many=True, context={'request': request}).data
    return Response(data)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, is_published=True)
    data = PostSerializer(post, context={'request': request}).data
    return Response(data)
