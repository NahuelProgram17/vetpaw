from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime, timedelta, date
from .models import Clinic, ClinicMembership, ClinicPhoto, ClinicSchedule
from .serializers import (
    ClinicSerializer,
    ClinicMembershipSerializer,
    LeaveClinicSerializer,
    PublicClinicSerializer,
    ClinicPhotoSerializer,
    ClinicScheduleSerializer,
)


class ClinicViewSet(viewsets.ModelViewSet):
    serializer_class = ClinicSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'public_profile', 'available_slots']:
            return [permissions.AllowAny()]
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = Clinic.objects.filter(is_active=True)
        locality = self.request.query_params.get('locality')
        province = self.request.query_params.get('province')
        if locality:
            qs = qs.filter(locality__icontains=locality)
        if province:
            qs = qs.filter(province__icontains=province)

        lat = self.request.query_params.get('lat')
        lon = self.request.query_params.get('lon')
        if lat and lon:
            try:
                lat = float(lat)
                lon = float(lon)
            except ValueError:
                return qs

            R = 6371
            results = []
            for clinic in qs:
                if clinic.latitude is None or clinic.longitude is None:
                    results.append(clinic)
                    continue
                dlat = radians(clinic.latitude - lat)
                dlon = radians(clinic.longitude - lon)
                a = sin(dlat/2)**2 + cos(radians(lat)) * cos(radians(clinic.latitude)) * sin(dlon/2)**2
                distance_km = R * 2 * atan2(sqrt(a), sqrt(1 - a))
                if distance_km <= 50:
                    clinic._distance_km = round(distance_km, 1)
                    results.append(clinic)

            return results if results else qs

        return qs

    @action(detail=False, methods=['get'], url_path='perfil/(?P<slug>[^/.]+)', permission_classes=[permissions.AllowAny])
    def public_profile(self, request, slug=None):
        try:
            clinic = Clinic.objects.get(slug=slug, is_active=True)
        except Clinic.DoesNotExist:
            return Response({'error': 'Clínica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = PublicClinicSerializer(clinic, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='slots', permission_classes=[permissions.AllowAny])
    def available_slots(self, request, pk=None):
        """
        GET /api/clinics/{id}/slots/?date=2026-05-30&type=control
        Devuelve los horarios disponibles para una clínica en una fecha y tipo de turno.
        """
        clinic = self.get_object()

        # Validar que la clínica tiene agenda configurada
        try:
            schedule = clinic.schedule
        except ClinicSchedule.DoesNotExist:
            return Response({'error': 'Esta clínica no tiene agenda configurada.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validar parámetros
        date_str = request.query_params.get('date')
        appt_type = request.query_params.get('type', 'control')

        if not date_str:
            return Response({'error': 'El parámetro date es requerido (YYYY-MM-DD).'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            requested_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Formato de fecha inválido. Usar YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validar que no sea en el pasado
        if requested_date < date.today():
            return Response({'error': 'No podés sacar turno en una fecha pasada.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validar que la clínica atiende ese día (0=lunes, 6=domingo)
        weekday = requested_date.weekday()
        if weekday not in schedule.working_days:
            return Response({'slots': [], 'message': 'La clínica no atiende ese día.'})

        # Obtener horario del día
        day_config = schedule.day_hours.get(str(weekday))
        if not day_config:
            return Response({'slots': [], 'message': 'La clínica no tiene horario configurado para ese día.'})

        open_time  = datetime.strptime(day_config['open'],  '%H:%M').time()
        close_time = datetime.strptime(day_config['close'], '%H:%M').time()

        # Duración del turno según tipo
        duration = schedule.get_duration(appt_type)
        interval = schedule.interval_minutes

        # Obtener turnos ya reservados ese día
        from appointments.models import Appointment
        existing = Appointment.objects.filter(
            clinic=clinic,
            requested_date__date=requested_date,
            status__in=['confirmed', 'pending'],
        ).values_list('requested_date', 'appointment_type')

        # Construir bloques ocupados (inicio, fin)
        occupied_blocks = []
        for appt_date, appt_t in existing:
            appt_start = appt_date.astimezone(timezone.get_current_timezone()).replace(tzinfo=None)
            appt_duration = schedule.get_duration(appt_t)
            appt_end = appt_start + timedelta(minutes=appt_duration + interval)
            occupied_blocks.append((appt_start, appt_end))

        # Generar todos los slots posibles
        slots = []
        current = datetime.combine(requested_date, open_time)
        end_limit = datetime.combine(requested_date, close_time)

        while current + timedelta(minutes=duration) <= end_limit:
            slot_end = current + timedelta(minutes=duration)

            # Verificar que no se superpone con ningún turno existente
            is_free = True
            for occ_start, occ_end in occupied_blocks:
                if current < occ_end and slot_end > occ_start:
                    is_free = False
                    break

            # No mostrar slots en el pasado
            now = datetime.now()
            if requested_date == date.today() and current <= now:
                current += timedelta(minutes=duration + interval)
                continue

            if is_free:
                slots.append({
                    'time': current.strftime('%H:%M'),
                    'datetime': current.strftime('%Y-%m-%dT%H:%M:00'),
                    'duration_minutes': duration,
                })

            current += timedelta(minutes=duration + interval)

        return Response({
            'date': date_str,
            'type': appt_type,
            'duration_minutes': duration,
            'slots': slots,
            'total_available': len(slots),
        })

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def join(self, request, pk=None):
        clinic = self.get_object()
        user = request.user
        if not user.is_owner:
            return Response(
                {'error': 'Solo los dueños pueden asociarse.'},
                status=status.HTTP_403_FORBIDDEN
            )
        active_count = ClinicMembership.objects.filter(owner=user, status='active').count()
        if active_count >= 5:
            return Response(
                {'error': 'Ya estás asociado a 5 veterinarias.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        membership, created = ClinicMembership.objects.get_or_create(owner=user, clinic=clinic)
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

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def leave(self, request, pk=None):
        clinic = self.get_object()
        user = request.user
        serializer = LeaveClinicSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            membership = ClinicMembership.objects.get(owner=user, clinic=clinic, status='active')
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
        return Response({'message': f'Te diste de baja de {clinic.name}.'})


class MembershipViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ClinicMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ClinicMembership.objects.filter(owner=self.request.user)


class ClinicPhotoViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def _get_clinic(self, user):
        try:
            return user.clinic_profile
        except Exception:
            return None

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        clinic = self._get_clinic(request.user)
        if not clinic:
            return Response({'error': 'No tenés una clínica asociada.'}, status=status.HTTP_403_FORBIDDEN)
        if clinic.photos.count() >= 5:
            return Response({'error': 'Ya tenés 5 fotos. Eliminá una antes de subir otra.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ClinicPhotoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(clinic=clinic)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='list')
    def list_photos(self, request):
        clinic = self._get_clinic(request.user)
        if not clinic:
            return Response({'error': 'No tenés una clínica asociada.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ClinicPhotoSerializer(clinic.photos.all(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['delete'], url_path='delete')
    def delete_photo(self, request, pk=None):
        clinic = self._get_clinic(request.user)
        if not clinic:
            return Response({'error': 'No tenés una clínica asociada.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            photo = clinic.photos.get(pk=pk)
        except ClinicPhoto.DoesNotExist:
            return Response({'error': 'Foto no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        photo.delete()
        return Response({'message': 'Foto eliminada.'}, status=status.HTTP_200_OK)


class ClinicScheduleViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def _get_clinic(self, user):
        try:
            return user.clinic_profile
        except Exception:
            return None

    @action(detail=False, methods=['get'], url_path='me')
    def get_schedule(self, request):
        clinic = self._get_clinic(request.user)
        if not clinic:
            return Response({'error': 'No tenés una clínica asociada.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            schedule = clinic.schedule
            return Response(ClinicScheduleSerializer(schedule).data)
        except ClinicSchedule.DoesNotExist:
            return Response({'error': 'No tenés agenda configurada todavía.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post', 'put'], url_path='configurar')
    def set_schedule(self, request):
        clinic = self._get_clinic(request.user)
        if not clinic:
            return Response({'error': 'No tenés una clínica asociada.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            schedule = clinic.schedule
            serializer = ClinicScheduleSerializer(schedule, data=request.data, partial=True)
        except ClinicSchedule.DoesNotExist:
            serializer = ClinicScheduleSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(clinic=clinic)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='turno-externo')
    def add_external(self, request):
        """La clínica carga un turno manual (por teléfono, WhatsApp, etc.)"""
        from appointments.models import Appointment
        from appointments.serializers import AppointmentSerializer

        clinic = self._get_clinic(request.user)
        if not clinic:
            return Response({'error': 'No tenés una clínica asociada.'}, status=status.HTTP_403_FORBIDDEN)

        requested_date = request.data.get('requested_date')
        appointment_type = request.data.get('appointment_type', 'control')
        external_label = request.data.get('external_label', 'Turno externo')

        if not requested_date:
            return Response({'error': 'La fecha del turno es requerida.'}, status=status.HTTP_400_BAD_REQUEST)

        appt = Appointment.objects.create(
            clinic=clinic,
            requested_date=requested_date,
            appointment_type=appointment_type,
            external_label=external_label,
            is_external=True,
            status='confirmed',
            reason=external_label,
        )
        return Response(AppointmentSerializer(appt).data, status=status.HTTP_201_CREATED)