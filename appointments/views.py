from datetime import timedelta

from django.db.models import Avg
from django.http import FileResponse
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from pets.models import Pet

from .models import Appointment, Review, Visit
from .serializers import AppointmentSerializer, ReviewSerializer, VisitSerializer

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
            raise PermissionDenied('Solo las clínicas pueden cargar visitas.')

        try:
            clinic = self.request.user.clinic_profile
        except Exception as exc:
            raise PermissionDenied('No tenés una clínica asociada.') from exc

        pet = serializer.validated_data['pet']
        cutoff = timezone.now() - timedelta(days=270)
        has_active_access = pet.clinic_accesses.filter(
            clinic=clinic,
            last_appointment__gte=cutoff,
        ).exists()
        has_appointment = Appointment.objects.filter(
            clinic=clinic,
            pet=pet,
        ).exclude(status='cancelled').exists()

        if not has_active_access and not has_appointment:
            raise PermissionDenied('Esta mascota no está vinculada a tu clínica.')

        appointment_id = serializer.validated_data.get('appointment_id')
        appointment = None
        if appointment_id:
            appointment = Appointment.objects.filter(
                pk=appointment_id,
                clinic=clinic,
                pet=pet,
                status='confirmed',
            ).first()
            if appointment is None:
                raise ValidationError({
                    'appointment_id': 'El turno no existe, no pertenece al paciente o ya no está confirmado.'
                })

        serializer.save(clinic=clinic)

        # Solo se completa el turno desde el que se abrió "Cargar visita".
        # Una visita cargada desde la ficha del paciente no altera turnos futuros.
        if appointment is not None:
            appointment.status = 'completed'
            appointment.save(update_fields=['status', 'updated_at'])


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
        appointment = serializer.save(owner=self.request.user)

        # Desde que un dueño pide un turno, la clínica ya puede ver
        # al paciente en su panel, aunque el turno sea futuro.
        if appointment.pet and appointment.clinic:
            from clinics.models import ClinicPetAccess
            from django.utils import timezone
            ClinicPetAccess.objects.update_or_create(
                clinic=appointment.clinic,
                pet=appointment.pet,
                defaults={'last_appointment': appointment.requested_date or timezone.now()}
            )

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='program_control')
    def program_control(self, request):
        if not request.user.is_clinic:
            return Response({'error': 'Solo las clínicas pueden programar controles.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            clinic = request.user.clinic_profile
        except Exception:
            return Response({'error': 'No tenés una clínica asociada.'}, status=status.HTTP_403_FORBIDDEN)

        pet_id = request.data.get('pet')
        requested_date = request.data.get('requested_date')
        appointment_type = request.data.get('appointment_type', 'control')
        reason = request.data.get('reason', '') or 'Control programado'

        if not pet_id or not requested_date:
            return Response({'error': 'Paciente y fecha/hora son obligatorios.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            pet = Pet.objects.get(pk=pet_id)
        except Pet.DoesNotExist:
            return Response({'error': 'Paciente no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        appointment = Appointment.objects.create(
            owner=pet.owner,
            pet=pet,
            clinic=clinic,
            requested_date=requested_date,
            reason=reason,
            appointment_type=appointment_type,
            status='confirmed',
            is_external=False,
            seen_by_owner=False,
            seen_by_clinic=True,
        )

        from clinics.models import ClinicPetAccess
        ClinicPetAccess.objects.update_or_create(
            clinic=clinic,
            pet=pet,
            defaults={'last_appointment': appointment.requested_date}
        )

        serializer = self.get_serializer(appointment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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
        if appointment.pet:
            from clinics.models import ClinicPetAccess
            from django.utils import timezone
            ClinicPetAccess.objects.update_or_create(
                clinic=appointment.clinic,
                pet=appointment.pet,
                defaults={'last_appointment': timezone.now()}
            )
    
    # Enviar mail al dueño
        try:
            import pytz
            from django.core.mail import EmailMultiAlternatives
            from django.conf import settings
            owner = appointment.owner
            pet_name = appointment.pet.name if appointment.pet else 'tu mascota'
            clinic_name = appointment.clinic.name if appointment.clinic else 'la clínica'
            argentina = pytz.timezone('America/Argentina/Buenos_Aires')
            fecha = appointment.requested_date.astimezone(argentina).strftime('%A %d de %B a las %H:%M')
            
            html = f"""
            <!DOCTYPE html>
            <html>
            <body style="margin:0;padding:0;background:#f4f4f4;font-family:Arial,sans-serif;">
            <table width="100%" cellpadding="0" cellspacing="0">
                <tr><td align="center" style="padding:40px 0;">
                <table width="520" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                <tr><td align="center" style="background:#0f1923;padding:28px 40px;">
                    <div style="color:#4CAF50;font-size:28px;font-weight:bold;">🐾 VetPaw</div>
                    <div style="color:#aaa;font-size:13px;margin-top:4px;">Tu app veterinaria de confianza</div>
                </td></tr>
                <tr><td style="padding:32px 40px;">
                    <p style="font-size:18px;font-weight:bold;color:#1e1b4b;margin:0 0 12px;">¡Tu turno fue confirmado! ✅</p>
                    <p style="font-size:15px;color:#4b5563;line-height:1.6;margin:0 0 20px;">
                        Hola <strong>{owner.first_name or owner.username}</strong>, tu turno para <strong>{pet_name}</strong> 
                        en <strong>{clinic_name}</strong> fue confirmado.
                    </p>
                    <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:10px;padding:16px 20px;margin-bottom:20px;">
                        <p style="margin:0;font-size:15px;color:#166534;">📅 <strong>{fecha.capitalize()}</strong></p>
                        <p style="margin:6px 0 0;font-size:13px;color:#166534;">🏥 {clinic_name}</p>
                        <p style="margin:4px 0 0;font-size:13px;color:#166534;">🐾 Paciente: {pet_name}</p>
                    </div>
                    <p style="font-size:13px;color:#9ca3af;text-align:center;">
                        Si necesitás cancelar, ingresá a <a href="https://www.vetpaw.com.ar" style="color:#4CAF50;">vetpaw.com.ar</a>
                    </p>
                </td></tr>
                <tr><td align="center" style="background:#f9fafb;padding:16px 40px;border-top:1px solid #e5e7eb;">
                    <p style="font-size:12px;color:#9ca3af;margin:0;">© 2026 VetPaw · Todos los derechos reservados 🐾</p>
                </td></tr>
                </table>
                </td></tr>
            </table>
            </body></html>
            """
        
            msg = EmailMultiAlternatives(
                subject=f'✅ Turno confirmado — {pet_name} en {clinic_name}',
                body=f'Tu turno para {pet_name} en {clinic_name} fue confirmado para el {fecha}.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[owner.email],
            )
            msg.attach_alternative(html, 'text/html')
            msg.send()
        except Exception as e:
            print(f'Error enviando mail de confirmación: {e}')
    
        return Response({'message': 'Turno confirmado.'})

    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAuthenticated])
    def cancel(self, request, pk=None):
        appointment = self.get_object()
        appointment.status = 'cancelled'
        appointment.seen_by_owner = False
        appointment.save()
        
    # Enviar mail al dueño
        try:
            import pytz
            from django.core.mail import EmailMultiAlternatives
            from django.conf import settings
            owner = appointment.owner
            pet_name = appointment.pet.name if appointment.pet else 'tu mascota'
            clinic_name = appointment.clinic.name if appointment.clinic else 'la clínica'
            argentina = pytz.timezone('America/Argentina/Buenos_Aires')
            fecha = appointment.requested_date.astimezone(argentina).strftime('%A %d de %B a las %H:%M')
            
            html = f"""
            <!DOCTYPE html>
            <html>
            <body style="margin:0;padding:0;background:#f4f4f4;font-family:Arial,sans-serif;">
            <table width="100%" cellpadding="0" cellspacing="0">
                <tr><td align="center" style="padding:40px 0;">
                <table width="520" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                <tr><td align="center" style="background:#0f1923;padding:28px 40px;">
                    <div style="color:#4CAF50;font-size:28px;font-weight:bold;">🐾 VetPaw</div>
                    <div style="color:#aaa;font-size:13px;margin-top:4px;">Tu app veterinaria de confianza</div>
                </td></tr>
                <tr><td style="padding:32px 40px;">
                    <p style="font-size:18px;font-weight:bold;color:#1e1b4b;margin:0 0 12px;">Turno cancelado ❌</p>
                    <p style="font-size:15px;color:#4b5563;line-height:1.6;margin:0 0 20px;">
                        Hola <strong>{owner.first_name or owner.username}</strong>, tu turno para <strong>{pet_name}</strong> 
                        en <strong>{clinic_name}</strong> fue cancelado.
                    </p>
                    <div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:10px;padding:16px 20px;margin-bottom:20px;">
                        <p style="margin:0;font-size:15px;color:#991b1b;">📅 <strong>{fecha.capitalize()}</strong></p>
                        <p style="margin:6px 0 0;font-size:13px;color:#991b1b;">🏥 {clinic_name}</p>
                        <p style="margin:4px 0 0;font-size:13px;color:#991b1b;">🐾 Paciente: {pet_name}</p>
                    </div>
                    <p style="font-size:13px;color:#4b5563;text-align:center;">
                        Podés sacar un nuevo turno en <a href="https://www.vetpaw.com.ar" style="color:#4CAF50;">vetpaw.com.ar</a>
                    </p>
                </td></tr>
                <tr><td align="center" style="background:#f9fafb;padding:16px 40px;border-top:1px solid #e5e7eb;">
                    <p style="font-size:12px;color:#9ca3af;margin:0;">© 2026 VetPaw · Todos los derechos reservados 🐾</p>
                </td></tr>
                </table>
                </td></tr>
            </table>
            </body></html>
            """
        
            msg = EmailMultiAlternatives(
                subject=f'❌ Turno cancelado — {pet_name} en {clinic_name}',
                body=f'Tu turno para {pet_name} en {clinic_name} del {fecha} fue cancelado.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[owner.email],
            )
            msg.attach_alternative(html, 'text/html')
            msg.send()
        except Exception as e:
            print(f'Error enviando mail de cancelación: {e}')
    
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
    
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def agenda_pdf(self, request):
        if not request.user.is_clinic:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo las clínicas pueden descargar la agenda.')
        try:
            clinic = request.user.clinic_profile
        except Exception:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No tenés una clínica asociada.')
    
        date_str = request.query_params.get('date')
        if date_str:
            from datetime import datetime
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            from django.utils import timezone
            date = timezone.now().date()

        appointments = Appointment.objects.filter(
            clinic=clinic,
            requested_date__date=date,
        ).exclude(status='cancelled').order_by('requested_date')

        from .pdf import generate_agenda_pdf
        buffer = generate_agenda_pdf(clinic, appointments, date)
        return FileResponse(
            buffer,
            as_attachment=True,
            filename=f'agenda_{date}.pdf',
            content_type='application/pdf',
        )
    
    
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
        if not self.request.user.is_owner:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo los dueños pueden dejar reseñas.')

        appointment = serializer.validated_data.get('appointment')
        clinic = appointment.clinic if appointment else serializer.validated_data.get('clinic')

        # Verificar que el turno pertenece al usuario
        if appointment and appointment.owner != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo podés reseñar tus propios turnos.')

        # Verificar que el turno está completado
        if appointment and appointment.status != 'completed':
            from rest_framework.exceptions import ValidationError
            raise ValidationError('Solo podés reseñar turnos completados.')

        serializer.save(owner=self.request.user, clinic=clinic)