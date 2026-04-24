from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Clinic, ClinicMembership
from .serializers import (
    ClinicSerializer,
    ClinicMembershipSerializer,
    LeaveClinicSerializer
)


class ClinicViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ClinicSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Clinic.objects.filter(is_active=True)
        locality = self.request.query_params.get('locality')
        province = self.request.query_params.get('province')
        if locality:
            qs = qs.filter(locality__icontains=locality)
        if province:
            qs = qs.filter(province__icontains=province)
        return qs

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def join(self, request, pk=None):
        clinic = self.get_object()
        user = request.user
        if not user.is_owner:
            return Response(
                {'error': 'Solo los dueños pueden asociarse.'},
                status=status.HTTP_403_FORBIDDEN
            )
        active_count = ClinicMembership.objects.filter(
            owner=user, status='active'
        ).count()
        if active_count >= 5:
            return Response(
                {'error': 'Ya estás asociado a 5 veterinarias.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        membership, created = ClinicMembership.objects.get_or_create(
            owner=user, clinic=clinic
        )
        if not created and membership.status == 'active':
            return Response(
                {'error': 'Ya estás asociado a esta veterinaria.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        membership.status = 'active'
        membership.save()
        return Response(
            {'message': f'Te asociaste a {clinic.name} exitosamente.'},
            status=status.HTTP_200_OK
        )

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def leave(self, request, pk=None):
        clinic = self.get_object()
        user = request.user
        serializer = LeaveClinicSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            membership = ClinicMembership.objects.get(
                owner=user, clinic=clinic, status='active'
            )
        except ClinicMembership.DoesNotExist:
            return Response(
                {'error': 'No estás asociado a esta veterinaria.'},
                status=status.HTTP_404_NOT_FOUND
            )
        membership.status = 'left'
        membership.leave_reason = serializer.validated_data['leave_reason']
        membership.leave_rating = serializer.validated_data['leave_rating']
        membership.left_at = timezone.now()
        membership.save()
        return Response(
            {'message': f'Te diste de baja de {clinic.name}.'},
            status=status.HTTP_200_OK
        )


class MembershipViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ClinicMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ClinicMembership.objects.filter(
            owner=self.request.user
        )