from django.db.models import Q
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from users.permissions import is_vetpaw_admin

from .models import BusinessProfile, ShelterProfile
from .serializers import BusinessProfileSerializer, ShelterProfileSerializer


class OwnProfileMixin:
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    lookup_field = 'slug'

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = self.queryset.filter(is_active=True, owner__is_approved=True).select_related('owner')
        query = str(self.request.query_params.get('q') or '').strip()[:80]
        locality = str(self.request.query_params.get('locality') or '').strip()[:100]
        province = str(self.request.query_params.get('province') or '').strip()[:100]
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(locality__icontains=query)
                | Q(province__icontains=query)
            )
        if locality:
            queryset = queryset.filter(locality__icontains=locality)
        if province:
            queryset = queryset.filter(province__icontains=province)
        return queryset

    @action(detail=False, methods=['get', 'patch'], url_path='me')
    def me(self, request):
        try:
            profile = self.model.objects.get(owner=request.user)
        except self.model.DoesNotExist:
            return Response({'detail': 'No encontramos el perfil asociado.'}, status=status.HTTP_404_NOT_FOUND)
        if request.method == 'GET':
            return Response(self.get_serializer(profile, context={'request': request}).data)
        serializer = self.get_serializer(profile, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        profile = self.get_object()
        if request.user.id != profile.owner_id and not is_vetpaw_admin(request.user):
            return Response({'detail': 'Solo podés editar tu propio perfil.'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)


class BusinessProfileViewSet(OwnProfileMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = BusinessProfile.objects.all()
    serializer_class = BusinessProfileSerializer
    model = BusinessProfile

    def get_queryset(self):
        queryset = super().get_queryset()
        business_type = str(self.request.query_params.get('type') or '').strip()[:30]
        if business_type in dict(BusinessProfile.BUSINESS_TYPE_CHOICES):
            queryset = queryset.filter(business_type=business_type)
        if str(self.request.query_params.get('is_24h') or '').lower() in ('1', 'true', 'yes'):
            queryset = queryset.filter(is_24h=True)
        if str(self.request.query_params.get('home_service') or '').lower() in ('1', 'true', 'yes'):
            queryset = queryset.filter(home_service=True)
        if str(self.request.query_params.get('accepts_reservations') or '').lower() in ('1', 'true', 'yes'):
            queryset = queryset.filter(accepts_reservations=True)
        if str(self.request.query_params.get('has_promotions') or '').lower() in ('1', 'true', 'yes'):
            from django.utils import timezone
            queryset = queryset.filter(
                commerce_promotions__is_active=True,
                commerce_promotions__starts_at__lte=timezone.now(),
                commerce_promotions__ends_at__gte=timezone.now(),
            ).distinct()
        return queryset

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        profile = self.get_object()
        if not request.user.is_authenticated or request.user.id != profile.owner_id:
            from commerce.models import BusinessProfileView
            BusinessProfileView.objects.create(
                business=profile,
                user=request.user if request.user.is_authenticated else None,
            )
        return response


class ShelterProfileViewSet(OwnProfileMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = ShelterProfile.objects.all()
    serializer_class = ShelterProfileSerializer
    model = ShelterProfile

    def get_queryset(self):
        queryset = super().get_queryset()
        shelter_type = str(self.request.query_params.get('type') or '').strip()[:30]
        if shelter_type in dict(ShelterProfile.SHELTER_TYPE_CHOICES):
            queryset = queryset.filter(shelter_type=shelter_type)
        if str(self.request.query_params.get('accepting_animals') or '').lower() in ('1', 'true', 'yes'):
            queryset = queryset.filter(accepting_animals=True)
        return queryset
