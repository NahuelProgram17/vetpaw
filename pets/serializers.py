from rest_framework import serializers
from .models import Pet, Vaccine


class VaccineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vaccine
        fields = [
            'id', 'name', 'date_applied',
            'next_dose', 'batch', 'notes'
        ]


class PetSerializer(serializers.ModelSerializer):
    vaccines = VaccineSerializer(many=True, read_only=True)
    owner_name = serializers.CharField(
        source='owner.get_full_name',
        read_only=True
    )
    species_display = serializers.CharField(
        source='get_species_display',
        read_only=True
    )

    class Meta:
        model = Pet
        fields = [
            'id', 'name', 'species', 'species_display',
            'breed', 'sex', 'birth_date', 'weight',
            'color', 'microchip', 'photo', 'allergies',
            'notes', 'is_neutered', 'vaccines',
            'owner', 'owner_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']