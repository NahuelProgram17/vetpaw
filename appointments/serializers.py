from rest_framework import serializers
from .models import Visit, Appointment, Review


class VisitSerializer(serializers.ModelSerializer):
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)
    pet_name = serializers.CharField(source='pet.name', read_only=True)
    appointment_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model  = Visit
        fields = [
            'id', 'pet', 'pet_name', 'clinic', 'clinic_name', 'appointment_id',
            'date', 'reason', 'diagnosis', 'treatment', 'observations',
            'next_visit', 'vet_first_name', 'vet_last_name', 'vet_license',
            'vet_clinic_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        validated_data.pop('appointment_id', None)
        return super().create(validated_data)


class AppointmentSerializer(serializers.ModelSerializer):
    pet_name        = serializers.CharField(source='pet.name',             read_only=True)
    clinic_name     = serializers.CharField(source='clinic.name',          read_only=True)
    owner_name      = serializers.CharField(source='owner.get_full_name',  read_only=True)
    owner_phone     = serializers.CharField(source='owner.phone',          read_only=True)
    appointment_type_display = serializers.CharField(source='get_appointment_type_display', read_only=True)

    class Meta:
        model  = Appointment
        fields = [
            'id', 'owner', 'owner_name', 'owner_phone',
            'pet', 'pet_name', 'clinic', 'clinic_name',
            'requested_date', 'reason', 'status',
            'appointment_type', 'appointment_type_display',
            'is_external', 'external_label',
            'vet_notes', 'seen_by_owner', 'reminder_sent',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'owner', 'status', 'seen_by_owner',
            'reminder_sent', 'created_at', 'updated_at',
            'appointment_type_display',
        ]


class ReviewSerializer(serializers.ModelSerializer):
    owner_name  = serializers.CharField(source='owner.username',       read_only=True)
    clinic_name = serializers.CharField(source='clinic.name',          read_only=True)
    pet_name    = serializers.CharField(source='appointment.pet.name', read_only=True)

    class Meta:
        model  = Review
        fields = [
            'id', 'appointment', 'owner', 'owner_name',
            'clinic', 'clinic_name', 'pet_name',
            'rating', 'comment', 'created_at',
        ]
        read_only_fields = ['id', 'owner', 'clinic', 'created_at']