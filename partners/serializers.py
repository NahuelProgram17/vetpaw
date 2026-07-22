import json

from rest_framework import serializers

from users.permissions import is_vetpaw_admin
from vetpaw.image_validation import validate_uploaded_image

from .models import BusinessProfile, ShelterProfile


def absolute_file_url(request, field):
    if not field:
        return None
    try:
        url = field.url
    except (AttributeError, ValueError):
        return None
    if request and url.startswith('/'):
        return request.build_absolute_uri(url)
    return url


class ProfileSerializerMixin:
    logo_url = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()
    profile_url = serializers.SerializerMethodField()
    completion_percentage = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    public_address = serializers.SerializerMethodField()

    PRIVATE_FIELDS = set()
    COMPLETION_FIELDS = ()

    def get_logo_url(self, obj):
        return absolute_file_url(self.context.get('request'), obj.logo)

    def get_cover_url(self, obj):
        return absolute_file_url(self.context.get('request'), obj.cover)

    def get_can_edit(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and (
            request.user.id == obj.owner_id or is_vetpaw_admin(request.user)
        ))

    def get_public_address(self, obj):
        return obj.address if obj.show_public_address else ''

    def get_completion_percentage(self, obj):
        completed = 0
        fields = self.COMPLETION_FIELDS
        for field in fields:
            value = getattr(obj, field, None)
            if isinstance(value, (list, dict)):
                completed += bool(value)
            else:
                completed += value not in (None, '', False)
        return round((completed / len(fields)) * 100) if fields else 100

    def _json_value(self, value, expected_type, label):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError(f'{label} tiene un formato inválido.') from exc
        if not isinstance(value, expected_type):
            expected = 'una lista' if expected_type is list else 'un objeto'
            raise serializers.ValidationError(f'{label} debe ser {expected}.')
        return value

    def validate_species(self, value):
        value = self._json_value(value, list, 'Los animales seleccionados')
        from .models import SPECIES_CHOICES
        allowed = set(dict(SPECIES_CHOICES))
        cleaned = list(dict.fromkeys(str(item) for item in value if str(item) in allowed))
        if len(cleaned) > 20:
            raise serializers.ValidationError('Seleccionaste demasiados tipos de animales.')
        return cleaned

    def validate_logo(self, value):
        return validate_uploaded_image(value, max_mb=4, label='El logo')

    def validate_cover(self, value):
        return validate_uploaded_image(value, max_mb=6, label='La portada')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.get_can_edit(instance):
            for field in self.PRIVATE_FIELDS:
                data.pop(field, None)
            data.pop('address', None)
        return data


class BusinessProfileSerializer(ProfileSerializerMixin, serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()
    profile_url = serializers.SerializerMethodField()
    completion_percentage = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    public_address = serializers.SerializerMethodField()
    business_type_display = serializers.CharField(source='get_business_type_display', read_only=True)

    PRIVATE_FIELDS = {'tax_id', 'legal_name'}
    COMPLETION_FIELDS = (
        'name', 'business_type', 'responsible_name', 'description', 'logo', 'phone',
        'whatsapp', 'province', 'locality', 'species', 'services', 'opening_hours',
    )

    class Meta:
        model = BusinessProfile
        fields = [
            'id', 'name', 'slug', 'business_type', 'business_type_display',
            'responsible_name', 'description', 'logo', 'logo_url', 'cover', 'cover_url',
            'phone', 'whatsapp', 'province', 'locality', 'address', 'public_address',
            'show_public_address', 'latitude', 'longitude', 'species', 'services',
            'opening_hours', 'home_service', 'delivery', 'online_sales',
            'appointment_required', 'is_24h', 'payment_methods', 'price_range',
            'promotions', 'tax_id', 'legal_name', 'is_verified', 'is_active',
            'profile_url', 'completion_percentage', 'can_edit', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'slug', 'business_type_display', 'logo_url', 'cover_url',
            'public_address', 'is_verified', 'is_active', 'profile_url',
            'completion_percentage', 'can_edit', 'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'logo': {'write_only': True, 'required': False, 'allow_null': True},
            'cover': {'write_only': True, 'required': False, 'allow_null': True},
        }

    def validate_services(self, value):
        return self._json_value(value, list, 'Los servicios')[:80]

    def validate_opening_hours(self, value):
        value = self._json_value(value, dict, 'Los horarios')
        return {str(key)[:12]: item for key, item in list(value.items())[:14] if isinstance(item, dict)}

    def validate_payment_methods(self, value):
        return self._json_value(value, list, 'Los métodos de pago')[:20]

    def get_profile_url(self, obj):
        return f'/negocios/{obj.slug}'


class ShelterProfileSerializer(ProfileSerializerMixin, serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()
    profile_url = serializers.SerializerMethodField()
    completion_percentage = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    public_address = serializers.SerializerMethodField()
    shelter_type_display = serializers.CharField(source='get_shelter_type_display', read_only=True)
    capacity_status_display = serializers.CharField(source='get_capacity_status_display', read_only=True)

    PRIVATE_FIELDS = {
        'tax_id', 'legal_status', 'registration_number', 'donation_cbu',
        'capacity_max', 'current_animals',
    }
    COMPLETION_FIELDS = (
        'name', 'shelter_type', 'responsible_name', 'description', 'logo', 'phone',
        'whatsapp', 'province', 'locality', 'species', 'activities',
        'adoption_requirements',
    )

    class Meta:
        model = ShelterProfile
        fields = [
            'id', 'name', 'slug', 'shelter_type', 'shelter_type_display',
            'responsible_name', 'description', 'logo', 'logo_url', 'cover', 'cover_url',
            'phone', 'whatsapp', 'province', 'locality', 'address', 'public_address',
            'show_public_address', 'latitude', 'longitude', 'species', 'founded_year',
            'work_area', 'activities', 'capacity_status', 'capacity_status_display',
            'capacity_max', 'current_animals', 'accepting_animals',
            'adoption_requirements', 'adoption_area', 'adoption_interview',
            'adoption_follow_up', 'adoption_castration_commitment',
            'adoption_safe_home_required', 'adoption_outside_province',
            'needs_volunteers', 'needs_foster_homes', 'accepts_donations',
            'accepts_food', 'accepts_medicine', 'needs_transport', 'needs_vet_help',
            'needs_sharing', 'donation_alias', 'donation_cbu', 'donation_needs',
            'legal_status', 'tax_id', 'registration_number', 'is_verified', 'is_active',
            'profile_url', 'completion_percentage', 'can_edit', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'slug', 'shelter_type_display', 'capacity_status_display',
            'logo_url', 'cover_url', 'public_address', 'is_verified', 'is_active',
            'profile_url', 'completion_percentage', 'can_edit', 'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'logo': {'write_only': True, 'required': False, 'allow_null': True},
            'cover': {'write_only': True, 'required': False, 'allow_null': True},
        }

    def validate_activities(self, value):
        return self._json_value(value, list, 'Las actividades')[:80]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        maximum = attrs.get('capacity_max', getattr(self.instance, 'capacity_max', None))
        current = attrs.get('current_animals', getattr(self.instance, 'current_animals', None))
        if maximum is not None and current is not None and current > maximum:
            raise serializers.ValidationError({'current_animals': 'La cantidad actual no puede superar la capacidad máxima.'})
        founded_year = attrs.get('founded_year')
        if founded_year is not None:
            from django.utils import timezone
            current_year = timezone.localdate().year
            if founded_year < 1900 or founded_year > current_year:
                raise serializers.ValidationError({'founded_year': 'Ingresá un año de creación válido.'})
        return attrs

    def get_profile_url(self, obj):
        return f'/refugios/{obj.slug}'
