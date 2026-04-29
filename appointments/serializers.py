from rest_framework import serializers
from .models import Visit, Appointment


class VisitSerializer(serializers.ModelSerializer):
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)
    pet_name = serializers.CharField(source='pet.name', read_only=True)

    class Meta:
        model = Visit
        fields = [
            'id', 'pet', 'pet_name', 'clinic', 'clinic_name',
            'date', 'reason', 'diagnosis', 'treatment', 'observations',
            'next_visit', 'vet_first_name', 'vet_last_name', 'vet_license',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AppointmentSerializer(serializers.ModelSerializer):
    pet_name = serializers.CharField(source='pet.name', read_only=True)
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'owner', 'owner_name', 'pet', 'pet_name',
            'clinic', 'clinic_name', 'requested_date', 'reason',
            'status', 'vet_notes', 'seen_by_owner', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'status', 'seen_by_owner', 'created_at', 'updated_at']