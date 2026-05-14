from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Visit, Appointment
from .serializers import VisitSerializer, AppointmentSerializer
from .models import Visit, Appointment, Review
from .serializers import VisitSerializer, AppointmentSerializer, ReviewSerializer
from django.db.models import Avg


class VisitViewSet(viewsets.ModelViewSet):
    serializer_class = VisitSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_clinic:
            try:
                clinic = user.clinic_profile
                return Visit.objects.filter(clinic=clinic)
            except Exception:
                return Visit.objects.none()
        return Visit.objects.filter(pet__owner=user)

    def perform_create(self, serializer):
        if not self.request.user.is_clinic:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo las clínicas pueden cargar visitas.')
        clinic = self.request.user.clinic_profile
        visit = serializer.save(clinic=clinic)
        Appointment.objects.filter(
            pet=visit.pet,
            clinic=clinic,
            status='confirmed'
        ).update(status='completed')


class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_owner:
            return Appointment.objects.filter(owner=user)
        elif user.is_clinic:
            try:
                clinic = user.clinic_profile
                return Appointment.objects.filter(clinic=clinic)
            except Exception:
                return Appointment.objects.none()
        return Appointment.objects.none()

    def perform_create(self, serializer):
        if not self.request.user.is_owner:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo los dueños pueden pedir turnos.')
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAuthenticated])
    def confirm(self, request, pk=None):
        appointment = self.get_object()
        if not request.user.is_clinic:
            return Response(
                {'error': 'Solo las clínicas pueden confirmar turnos.'},
                status=status.HTTP_403_FORBIDDEN
            )
        appointment.status = 'confirmed'
        appointment.seen_by_owner = False
        appointment.save()
        return Response({'message': 'Turno confirmado.'})

    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAuthenticated])
    def cancel(self, request, pk=None):
        appointment = self.get_object()
        appointment.status = 'cancelled'
        appointment.seen_by_owner = False
        appointment.save()
        return Response({'message': 'Turno cancelado.'})

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def mark_seen(self, request):
        Appointment.objects.filter(
            owner=request.user,
            seen_by_owner=False
        ).update(seen_by_owner=True)
        return Response({'message': 'Notificaciones marcadas como vistas.'})

    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAuthenticated])
    def mark_no_show(self, request, pk=None):
        appointment = self.get_object()
        if not request.user.is_clinic:
            return Response(
                {'error': 'Solo las clínicas pueden marcar ausencias.'},
                status=status.HTTP_403_FORBIDDEN
            )
        appointment.status = 'no_show'
        appointment.seen_by_owner = False
        appointment.save()
        return Response({'message': 'Turno marcado como ausente.'})
    
class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class   = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names  = ['get', 'post']

    def get_queryset(self):
        user = self.request.user
        clinic_id = self.request.query_params.get('clinic')
        if clinic_id:
            return Review.objects.filter(clinic_id=clinic_id)
        if user.is_owner:
            return Review.objects.filter(owner=user)
        if user.is_clinic:
            try:
                return Review.objects.filter(clinic=user.clinic_profile)
            except Exception:
                return Review.objects.none()
        return Review.objects.none()

    def perform_create(self, serializer):
        from rest_framework.exceptions import PermissionDenied, ValidationError
        user = self.request.user
        if not user.is_owner:
            raise PermissionDenied('Solo los dueños pueden dejar reseñas.')
        appt_id = self.request.data.get('appointment')
        try:
            appt = Appointment.objects.get(id=appt_id, owner=user, status='completed')
        except Appointment.DoesNotExist:
            raise ValidationError('El turno no existe, no te pertenece o no está completado.')
        if Review.objects.filter(appointment=appt).exists():
            raise ValidationError('Ya calificaste esta visita.')
        rating = int(self.request.data.get('rating', 0))
        if not 1 <= rating <= 5:
            raise ValidationError('El puntaje debe ser entre 1 y 5.')
        serializer.save(
            owner=user,
            clinic=appt.clinic,
            appointment=appt,
        )