import os
import mimetypes
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django.http import FileResponse
from .models import Pet, Vaccine, ClinicalPhoto, Treatment
from .serializers import PetSerializer, VaccineSerializer, ClinicalPhotoSerializer, TreatmentSerializer
from clinics.models import ClinicMembership
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser


class PetViewSet(viewsets.ModelViewSet):
    serializer_class = PetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_owner:
            return Pet.objects.filter(owner=user)
        elif user.is_clinic:
            try:
                clinic = user.clinic_profile
                from clinics.models import ClinicPetAccess
                from appointments.models import Appointment
                from django.utils import timezone
                from datetime import timedelta

                # Pacientes visibles para la clínica:
                # 1) accesos ya concedidos por turnos/visitas
                # 2) mascotas que tienen o tuvieron turno con esta clínica
                #    aunque el turno sea futuro y todavía no haya historia clínica.
                cutoff = timezone.now() - timedelta(days=270)
                access_pet_ids = ClinicPetAccess.objects.filter(
                    clinic=clinic,
                    last_appointment__gte=cutoff
                ).values_list('pet_id', flat=True)

                appointment_pet_ids = Appointment.objects.filter(
                    clinic=clinic,
                    pet__isnull=False,
                ).exclude(status='cancelled').values_list('pet_id', flat=True)

                return Pet.objects.filter(
                    id__in=list(access_pet_ids) + list(appointment_pet_ids)
                ).distinct()
            except Exception:
                return Pet.objects.none()
        return Pet.objects.none()

    def perform_create(self, serializer):
        if not self.request.user.is_owner:
            raise PermissionDenied('Solo los dueños pueden registrar mascotas.')
        new_photo = self.request.FILES.get('photo')
        if new_photo:
            serializer.save(owner=self.request.user, photo=new_photo)
        else:
            serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        new_photo = self.request.FILES.get('photo')
        if new_photo:
            serializer.save(photo=new_photo)
        else:
            serializer.save()

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def pdf(self, request, pk=None):
        pet = self.get_object()
        user = request.user
        if not user.is_clinic:
            raise PermissionDenied('Solo las clínicas pueden generar el historial PDF.')
        try:
            clinic = user.clinic_profile
        except Exception:
            raise PermissionDenied('No tenés una clínica asociada.')
        from .pdf import generate_pet_pdf
        buffer = generate_pet_pdf(pet, clinic)
        return FileResponse(
            buffer,
            as_attachment=True,
            filename=f'historial_{pet.name}_{pet.id}.pdf',
            content_type='application/pdf',
        )


class VaccineViewSet(viewsets.ModelViewSet):
    serializer_class = VaccineSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_clinic:
            try:
                clinic = user.clinic_profile
                from clinics.models import ClinicPetAccess
                from django.utils import timezone
                from datetime import timedelta
                cutoff = timezone.now() - timedelta(days=270)
                pet_ids = ClinicPetAccess.objects.filter(
                    clinic=clinic,
                    last_appointment__gte=cutoff
                ).values_list('pet_id', flat=True)
                return Vaccine.objects.filter(pet_id__in=pet_ids)
            except Exception:
                return Vaccine.objects.none()
        return Vaccine.objects.filter(pet__owner=user)

    def perform_create(self, serializer):
        if not self.request.user.is_clinic:
            raise PermissionDenied('Solo las clínicas pueden cargar vacunas.')
        serializer.save(clinic=self.request.user.clinic_profile)
        
class ClinicalPhotoViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        if not request.user.is_clinic:
            raise PermissionDenied('Solo las clínicas pueden subir archivos clínicos.')
        try:
            clinic = request.user.clinic_profile
        except Exception:
            raise PermissionDenied('No tenés una clínica asociada.')

        pet_id = request.data.get('pet')
        if not pet_id:
            return Response({'error': 'El campo pet es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)

        image = request.FILES.get('image')
        if not image:
            return Response({'error': 'El archivo es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)
        if image.size > 10 * 1024 * 1024:
            return Response({'error': 'El archivo no puede superar los 10MB.'}, status=status.HTTP_400_BAD_REQUEST)
        filename = (image.name or '').lower()
        content_type = (image.content_type or '').lower()
        allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf']
        allowed_exts = ('.jpg', '.jpeg', '.png', '.webp', '.pdf')
        if content_type not in allowed_types and not filename.endswith(allowed_exts):
            return Response({'error': 'Solo se permiten imágenes JPG, PNG, WebP o archivos PDF.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            pet = Pet.objects.get(pk=pet_id)
        except Pet.DoesNotExist:
            return Response({'error': 'Mascota no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ClinicalPhotoSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(clinic=clinic, pet=pet)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='list')
    def list_photos(self, request):
        pet_id = request.query_params.get('pet')
        if not pet_id:
            return Response({'error': 'El parámetro pet es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)
        photos = ClinicalPhoto.objects.filter(pet_id=pet_id)
        serializer = ClinicalPhotoSerializer(photos, many=True, context={'request': request})
        return Response(serializer.data)


    @action(detail=True, methods=['get'], url_path='download')
    def download_file(self, request, pk=None):
        try:
            photo = ClinicalPhoto.objects.select_related('pet__owner', 'clinic').get(pk=pk)
        except ClinicalPhoto.DoesNotExist:
            return Response({'error': 'Archivo no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        allowed = False
        if getattr(request.user, 'is_clinic', False):
            try:
                allowed = photo.clinic_id == request.user.clinic_profile.id
            except Exception:
                allowed = False
        if photo.pet.owner_id == request.user.id:
            allowed = True
        if not allowed:
            raise PermissionDenied('No tenés permiso para ver este archivo clínico.')

        filename = os.path.basename(photo.image.name or 'archivo-clinico')
        content_type = 'application/pdf' if photo.is_pdf else (mimetypes.guess_type(filename)[0] or 'application/octet-stream')
        try:
            file_handle = photo.image.open('rb')
        except Exception:
            return Response({'error': 'No se pudo abrir el archivo clínico.'}, status=status.HTTP_404_NOT_FOUND)

        response = FileResponse(file_handle, content_type=content_type)
        disposition = 'inline' if photo.is_pdf or content_type.startswith('image/') else 'attachment'
        response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
        return response

    @action(detail=True, methods=['delete'], url_path='delete')
    def delete_photo(self, request, pk=None):
        if not request.user.is_clinic:
            raise PermissionDenied('Solo las clínicas pueden eliminar fotos clínicas.')
        try:
            clinic = request.user.clinic_profile
        except Exception:
            raise PermissionDenied('No tenés una clínica asociada.')
        try:
            photo = ClinicalPhoto.objects.get(pk=pk, clinic=clinic)
        except ClinicalPhoto.DoesNotExist:
            return Response({'error': 'Archivo no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        photo.delete()
        return Response({'message': 'Archivo eliminado.'}, status=status.HTTP_200_OK)

class TreatmentViewSet(viewsets.ModelViewSet):
    serializer_class = TreatmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_owner:
            return Treatment.objects.filter(pet__owner=user)
        if user.is_clinic:
            try:
                clinic = user.clinic_profile
                from clinics.models import ClinicPetAccess
                from django.utils import timezone
                from datetime import timedelta
                cutoff = timezone.now() - timedelta(days=270)
                pet_ids = ClinicPetAccess.objects.filter(
                    clinic=clinic,
                    last_appointment__gte=cutoff
                ).values_list('pet_id', flat=True)
                return Treatment.objects.filter(pet_id__in=pet_ids)
            except Exception:
                return Treatment.objects.none()
        return Treatment.objects.none()

    def perform_create(self, serializer):
        pet = serializer.validated_data.get('pet')
        if not self.request.user.is_owner or pet.owner_id != self.request.user.id:
            raise PermissionDenied('Solo el dueño puede cargar tratamientos de su mascota.')
        serializer.save()

    def perform_update(self, serializer):
        pet = serializer.validated_data.get('pet', serializer.instance.pet)
        if not self.request.user.is_owner or pet.owner_id != self.request.user.id:
            raise PermissionDenied('Solo el dueño puede editar tratamientos de su mascota.')
        serializer.save()
