from rest_framework import serializers
from .models import Pet, Vaccine


class VaccineSerializer(serializers.ModelSerializer):
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)

    class Meta:
        model = Vaccine
        fields = [
            'id', 'pet', 'clinic', 'clinic_name', 'name',
            'date_applied', 'next_dose', 'batch', 'notes',
            'vet_first_name', 'vet_last_name', 'vet_license',
        ]

class PetSerializer(serializers.ModelSerializer):
    vaccines = VaccineSerializer(many=True, read_only=True)
    owner_name = serializers.CharField(
        source='owner.get_full_name',
        read_only=True
    )
    owner_phone = serializers.CharField(
        source='owner.phone',
        read_only=True
    )
    species_display = serializers.CharField(
        source='get_species_display',
        read_only=True
    )
    photo = serializers.SerializerMethodField()

    def get_photo(self, obj):
        if obj.photo:
            return obj.photo.url
        return None

    class Meta:
        model = Pet
        fields = [
            'id', 'name', 'species', 'species_display',
            'breed', 'sex', 'birth_date', 'weight',
            'color', 'microchip', 'photo', 'allergies',
            'notes', 'is_neutered', 'vaccines',
            'feeding', 'habitat', 'lives_with_animals',
            'owner', 'owner_name''owner_phone', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']