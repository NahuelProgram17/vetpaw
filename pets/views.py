from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django.http import FileResponse
from .models import Pet, Vaccine
from .serializers import PetSerializer, VaccineSerializer
from clinics.models import ClinicMembership


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