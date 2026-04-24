from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied
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
        elif user.is_vet:
            # Vet solo ve mascotas de dueños asociados a su clinica
            clinic_ids = user.vet_clinics.values_list('id', flat=True)
            owner_ids = ClinicMembership.objects.filter(
                clinic_id__in=clinic_ids,
                status='active'
            ).values_list('owner_id', flat=True)
            return Pet.objects.filter(owner_id__in=owner_ids)
        return Pet.objects.none()

    def perform_create(self, serializer):
        if not self.request.user.is_owner:
            raise PermissionDenied(
                'Solo los dueños pueden registrar mascotas.'
            )
        serializer.save(owner=self.request.user)


class VaccineViewSet(viewsets.ModelViewSet):
    serializer_class = VaccineSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Vaccine.objects.filter(
            pet__owner=self.request.user
        )