from rest_framework import serializers
from .models import Pet, Vaccine, ClinicalPhoto, Treatment


class TreatmentSerializer(serializers.ModelSerializer):
    treatment_type_display = serializers.CharField(
        source='get_treatment_type_display',
        read_only=True
    )

    class Meta:
        model = Treatment
        fields = [
            'id', 'pet', 'treatment_type', 'treatment_type_display',
            'date_applied', 'next_dose', 'product', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class VaccineSerializer(serializers.ModelSerializer):
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)

    class Meta:
        model = Vaccine
        fields = [
            'id', 'pet', 'clinic', 'clinic_name', 'name',
            'date_applied', 'next_dose', 'batch', 'notes',
            'vet_first_name', 'vet_last_name', 'vet_license', 'vet_clinic_name',
        ]


class PetSerializer(serializers.ModelSerializer):
    vaccines = VaccineSerializer(many=True, read_only=True)
    treatments = TreatmentSerializer(many=True, read_only=True)
    owner_name = serializers.CharField(
        source='owner.get_full_name',
        read_only=True
    )
    owner_phone = serializers.SerializerMethodField()
    species_display = serializers.CharField(
        source='get_species_display',
        read_only=True
    )
    temperament_display = serializers.CharField(
        source='get_temperament_display',
        read_only=True
    )
    photo = serializers.SerializerMethodField()

    def get_photo(self, obj):
        if not obj.photo:
            return None
        url = obj.photo.url
        request = self.context.get('request')
        if request and url.startswith('/'):
            return request.build_absolute_uri(url)
        return url

    def get_owner_phone(self, obj):
        if obj.owner:
            return obj.owner.phone or ""
        return ""

    class Meta:
        model = Pet
        fields = [
            'id', 'name', 'species', 'species_display',
            'breed', 'sex', 'birth_date', 'weight',
            'color', 'microchip', 'photo', 'allergies',
            'notes', 'is_neutered', 'vaccines', 'treatments',
            'feeding', 'habitat', 'lives_with_animals',
            'temperament', 'temperament_display',
            'owner', 'owner_name', 'owner_phone', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']


class ClinicalPhotoSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)
    file_type = serializers.SerializerMethodField()
    is_pdf = serializers.SerializerMethodField()
    filename = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    content_type = serializers.SerializerMethodField()

    def _download_url(self, obj):
        request = self.context.get('request')
        path = f'/api/clinical-photos/{obj.id}/download/'
        return request.build_absolute_uri(path) if request else path

    def get_image_url(self, obj):
        # Para PDFs guardados en base, nunca devolvemos URL de Cloudinary.
        # Chrome/Cloudinary puede responder 401 si la cuenta no permite entrega pública de PDFs.
        if obj.is_pdf:
            return None
        if not obj.image:
            return None
        url = obj.image.url
        request = self.context.get('request')
        if request and url.startswith('/'):
            return request.build_absolute_uri(url)
        return url

    def get_file_type(self, obj):
        return obj.file_type

    def get_file_url(self, obj):
        if obj.is_pdf:
            return self._download_url(obj)
        return self.get_image_url(obj)

    def get_content_type(self, obj):
        if obj.is_pdf:
            return obj.pdf_content_type or 'application/pdf'
        name = (obj.image.name or '').lower() if obj.image else ''
        if name.endswith('.png'):
            return 'image/png'
        if name.endswith('.webp'):
            return 'image/webp'
        if name.endswith('.jpg') or name.endswith('.jpeg'):
            return 'image/jpeg'
        return ''

    def get_is_pdf(self, obj):
        return obj.is_pdf

    def get_filename(self, obj):
        if obj.is_pdf and obj.pdf_filename:
            return obj.pdf_filename
        if not obj.image:
            return ''
        return obj.image.name.split('/')[-1]

    class Meta:
        model = ClinicalPhoto
        fields = ['id', 'pet', 'clinic', 'clinic_name', 'image', 'image_url', 'file_url', 'caption', 'file_type', 'is_pdf', 'filename', 'content_type', 'uploaded_at']
        read_only_fields = ['id', 'clinic', 'uploaded_at', 'file_url', 'file_type', 'is_pdf', 'filename', 'content_type']
