from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django.http import FileResponse
from .models import Pet, Vaccine, ClinicalPhoto
from .serializers import PetSerializer, VaccineSerializer, ClinicalPhotoSerializer
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
                from django.utils import timezone
                from datetime import timedelta
                cutoff = timezone.now() - timedelta(days=270)
                pet_ids = ClinicPetAccess.objects.filter(
                    clinic=clinic,
                    last_appointment__gte=cutoff
                ).values_list('pet_id', flat=True)
                return Pet.objects.filter(id__in=pet_ids)
            except Exception:
                return Pet.objects.none()
        return Pet.objects.none()

    def perform_create(self, serializer):
        if not self.request.user.is_owner:
            raise PermissionDenied('Solo los dueños pueden registrar mascotas.')
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
            raise PermissionDenied('Solo las clínicas pueden subir fotos clínicas.')
        try:
            clinic = request.user.clinic_profile
        except Exception:
            raise PermissionDenied('No tenés una clínica asociada.')

        pet_id = request.data.get('pet')
        if not pet_id:
            return Response({'error': 'El campo pet es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)

        image = request.FILES.get('image')
        if not image:
            return Response({'error': 'El campo image es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)
        if image.size > 5 * 1024 * 1024:
            return Response({'error': 'La imagen no puede superar los 5MB.'}, status=status.HTTP_400_BAD_REQUEST)
        if image.content_type not in ['image/jpeg', 'image/png', 'image/webp']:
            return Response({'error': 'Solo se permiten imágenes JPG, PNG o WebP.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            pet = Pet.objects.get(pk=pet_id)
        except Pet.DoesNotExist:
            return Response({'error': 'Mascota no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ClinicalPhotoSerializer(data=request.data)
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
        serializer = ClinicalPhotoSerializer(photos, many=True)
        return Response(serializer.data)

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
            return Response({'error': 'Foto no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        photo.delete()
        return Response({'message': 'Foto eliminada.'}, status=status.HTTP_200_OK)