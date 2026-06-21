from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Q
from django.utils import timezone
from .models import Advertiser
from .serializers import AdvertiserSerializer
from users.admin_panel_views import is_admin


class IsAdminUsername(permissions.BasePermission):
    def has_permission(self, request, view):
        return is_admin(request.user)


class AdvertiserViewSet(viewsets.ModelViewSet):
    queryset = Advertiser.objects.all()
    serializer_class = AdvertiserSerializer
    permission_classes = [IsAdminUsername]
    parser_classes = [MultiPartParser, FormParser, JSONParser]


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def active_ads(request):
    today = timezone.now().date()
    qs = Advertiser.objects.filter(is_active=True)
    qs = qs.filter(Q(start_date__isnull=True) | Q(start_date__lte=today))
    qs = qs.filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
    data = AdvertiserSerializer(qs, many=True, context={'request': request}).data
    return Response(data)
