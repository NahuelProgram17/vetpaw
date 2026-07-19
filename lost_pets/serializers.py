from rest_framework import serializers
from .models import LostPet
from vetpaw.image_validation import validate_uploaded_image


class LostPetSerializer(serializers.ModelSerializer):
    days_left = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    owner_name = serializers.SerializerMethodField()
    owner_username = serializers.SerializerMethodField()
    owner_email = serializers.SerializerMethodField()
    contact_type_display = serializers.CharField(source='get_contact_type_display', read_only=True)
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)
    species_display = serializers.CharField(source='get_species_display', read_only=True)

    class Meta:
        model = LostPet
        fields = [
            'id', 'photo', 'photo_url', 'description',
            'contact_type', 'contact_type_display', 'contact_value',
            'report_type', 'report_type_display',
            'province', 'locality', 'owner', 'owner_name', 'owner_username', 'owner_email',
            'pet_name', 'species', 'species_display', 'breed', 'incident_date',
            'report_count', 'expires_at', 'days_left', 'created_at'
        ]
        extra_kwargs = {'photo': {'write_only': True}}


    def validate_photo(self, value):
        return validate_uploaded_image(value, max_mb=5, label='La foto')

    def get_days_left(self, obj):
        from django.utils import timezone
        delta = obj.expires_at - timezone.now()
        return max(0, delta.days)

    def get_photo_url(self, obj):
        if obj.photo:
            return obj.photo.url
        return None

    def get_owner_name(self, obj):
        if obj.owner:
            full_name = f"{obj.owner.first_name} {obj.owner.last_name}".strip()
            return full_name or obj.owner.username
        return None

    def get_owner_username(self, obj):
        if obj.owner:
            return obj.owner.username
        return None

    def get_owner_email(self, obj):
        if obj.owner:
            return obj.owner.email
        return None
