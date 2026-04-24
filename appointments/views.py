from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Visit, Appointment
from .serializers import VisitSerializer, AppointmentSerializer


class VisitViewSet(viewsets.ModelViewSet):
    serializer_class = VisitSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_vet:
            return Visit.objects.filter(vet=user)
        return Visit.objects.filter(pet__owner=user)

    def perform_create(self, serializer):
        if not self.request.user.is_vet:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                'Solo los veterinarios pueden cargar visitas.'
            )
        serializer.save(vet=self.request.user)


class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_owner:
            return Appointment.objects.filter(owner=user)
        elif user.is_vet:
            clinic_ids = user.vet_clinics.values_list('id', flat=True)
            return Appointment.objects.filter(clinic_id__in=clinic_ids)
        return Appointment.objects.none()

    def perform_create(self, serializer):
        if not self.request.user.is_owner:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                'Solo los dueños pueden pedir turnos.'
            )
        serializer.save(owner=self.request.user)

    @action(
        detail=True,
        methods=['patch'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def confirm(self, request, pk=None):
        appointment = self.get_object()
        if not request.user.is_vet:
            return Response(
                {'error': 'Solo los veterinarios pueden confirmar turnos.'},
                status=status.HTTP_403_FORBIDDEN
            )
        appointment.status = 'confirmed'
        appointment.save()
        return Response({'message': 'Turno confirmado.'})

    @action(
        detail=True,
        methods=['patch'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def cancel(self, request, pk=None):
        appointment = self.get_object()
        appointment.status = 'cancelled'
        appointment.save()
        return Response({'message': 'Turno cancelado.'})