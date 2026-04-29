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
        elif user.is_clinic:
            try:
                clinic = user.clinic_profile
                owner_ids = ClinicMembership.objects.filter(
                    clinic=clinic,
                    status='active'
                ).values_list('owner_id', flat=True)
                return Pet.objects.filter(owner_id__in=owner_ids)
            except Exception:
                return Pet.objects.none()
        return Pet.objects.none()

    def perform_create(self, serializer):
        if not self.request.user.is_owner:
            raise PermissionDenied('Solo los dueños pueden registrar mascotas.')
        serializer.save(owner=self.request.user)


class VaccineViewSet(viewsets.ModelViewSet):
    serializer_class = VaccineSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Vaccine.objects.filter(pet__owner=self.request.user)