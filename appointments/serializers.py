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
            'source_post', 'source_campaign',
            'requested_date', 'reason', 'status',
            'appointment_type', 'appointment_type_display',
            'is_external', 'external_label',
            'vet_notes', 'seen_by_owner', 'reminder_sent',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'owner', 'status', 'seen_by_owner',
            'reminder_sent', 'created_at', 'updated_at',
            'appointment_type_display', 'source_campaign',
        ]


    def validate(self, attrs):
        attrs = super().validate(attrs)
        source_post = attrs.get('source_post', getattr(self.instance, 'source_post', None))
        clinic = attrs.get('clinic', getattr(self.instance, 'clinic', None))
        pet = attrs.get('pet', getattr(self.instance, 'pet', None))
        request = self.context.get('request')

        if source_post:
            if not source_post.clinic_id or source_post.clinic_id != getattr(clinic, 'id', None):
                raise serializers.ValidationError({'source_post': 'La publicación no pertenece a la veterinaria seleccionada.'})
            if source_post.moderation_status != 'published' or not source_post.is_public:
                raise serializers.ValidationError({'source_post': 'Esta publicación ya no está disponible.'})
            campaign = source_post.related_clinic_campaign
            if campaign:
                if not campaign.is_active or not campaign.allow_booking:
                    raise serializers.ValidationError({'source_post': 'Esta campaña no está recibiendo reservas.'})
                if campaign.remaining_slots == 0:
                    raise serializers.ValidationError({'source_post': 'La campaña ya no tiene cupos disponibles.'})
                if request and request.user.is_authenticated and self.instance is None:
                    exists = Appointment.objects.filter(
                        owner=request.user,
                        source_campaign=campaign,
                        status__in=['pending', 'confirmed'],
                    ).exists()
                    if exists:
                        raise serializers.ValidationError({'source_post': 'Ya tenés una solicitud activa para esta campaña.'})
                attrs['requested_date'] = campaign.starts_at
                attrs['source_campaign'] = campaign
                if not attrs.get('reason'):
                    attrs['reason'] = campaign.title
                if campaign.campaign_type == 'vaccination':
                    attrs['appointment_type'] = 'vaccine'
                else:
                    attrs['appointment_type'] = attrs.get('appointment_type') or 'other'

        if request and request.user.is_authenticated and pet and pet.owner_id != request.user.id and request.user.role == 'owner':
            raise serializers.ValidationError({'pet': 'La mascota seleccionada no te pertenece.'})
        return attrs


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