from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User
from .sanctions import get_active_sanction, sanction_error_payload
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed
from vetpaw.image_validation import validate_uploaded_image
from .permissions import is_community_moderator, is_vetpaw_admin


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password2',
            'first_name', 'last_name', 'role', 'gender',
            'phone', 'province', 'locality',
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError(
                {'password': 'Las contraseñas no coinciden.'}
            )
        if not attrs.get('email'):
            raise serializers.ValidationError(
                {'email': 'El email es obligatorio.'}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        validated_data['role'] = 'owner'
        user = User.objects.create_user(**validated_data)
        return user


class UserSerializer(serializers.ModelSerializer):
    can_access_admin = serializers.SerializerMethodField()
    can_moderate_community = serializers.SerializerMethodField()
    profile_name = serializers.SerializerMethodField()
    profile_url = serializers.SerializerMethodField()
    profile_completion = serializers.SerializerMethodField()
    profile_logo = serializers.SerializerMethodField()
    account_status = serializers.SerializerMethodField()
    professional_verification = serializers.SerializerMethodField()

    def validate_avatar(self, value):
        return validate_uploaded_image(value, max_mb=3, label='La foto de perfil')

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'gender', 'phone', 'province', 'locality', 'avatar', 'bio',
            'created_at', 'is_approved', 'is_staff', 'is_superuser',
            'can_access_admin', 'can_moderate_community',
            'profile_name', 'profile_url', 'profile_completion', 'profile_logo',
            'account_status', 'professional_verification',
        ]
        read_only_fields = [
            'id', 'created_at', 'role', 'is_approved', 'is_staff', 'is_superuser',
            'can_access_admin', 'can_moderate_community',
            'profile_name', 'profile_url', 'profile_completion', 'profile_logo',
            'account_status', 'professional_verification',
        ]

    def get_account_status(self, obj):
        sanction = get_active_sanction(obj)
        if not sanction:
            return {'status': 'active', 'sanction': None}
        payload = sanction_error_payload(sanction)
        return {'status': payload['code'], 'sanction': payload['account_sanction']}

    def get_professional_verification(self, obj):
        if not obj.is_professional:
            return None
        from .verification import serialize_professional_verification
        return serialize_professional_verification(obj)

    def get_can_access_admin(self, obj):
        return is_vetpaw_admin(obj)

    def get_can_moderate_community(self, obj):
        return is_community_moderator(obj)

    def _role_profile(self, obj):
        if obj.role == 'clinic':
            return getattr(obj, 'clinic_profile', None)
        if obj.role == 'business':
            return getattr(obj, 'business_profile', None)
        if obj.role == 'shelter':
            return getattr(obj, 'shelter_profile', None)
        return None

    def get_profile_name(self, obj):
        profile = self._role_profile(obj)
        return getattr(profile, 'name', '') if profile else ''

    def get_profile_url(self, obj):
        profile = self._role_profile(obj)
        if not profile:
            return ''
        if obj.role == 'clinic':
            return f'/clinicas/{profile.slug}'
        if obj.role == 'business':
            return f'/negocios/{profile.slug}'
        if obj.role == 'shelter':
            return f'/refugios/{profile.slug}'
        return ''

    def get_profile_completion(self, obj):
        profile = self._role_profile(obj)
        if not profile:
            return 100 if obj.role == 'owner' else 0
        fields = ['name', 'responsible_name', 'description', 'logo', 'phone', 'whatsapp', 'province', 'locality', 'species']
        values = [getattr(profile, field, None) for field in fields if hasattr(profile, field)]
        if not values:
            return 100
        return round(sum(bool(value) for value in values) / len(values) * 100)


    def get_profile_logo(self, obj):
        profile = self._role_profile(obj)
        if not profile or not getattr(profile, 'logo', None):
            return None
        request = self.context.get('request')
        try:
            url = profile.logo.url
        except (ValueError, AttributeError):
            return None
        return request.build_absolute_uri(url) if request and url.startswith('/') else url


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        sanction = get_active_sanction(user)
        if sanction:
            raise AuthenticationFailed(detail=sanction_error_payload(sanction))
        if user.role in ('clinic', 'business', 'shelter') and not user.is_approved:
            labels = {
                'clinic': 'veterinaria',
                'business': 'negocio',
                'shelter': 'refugio',
            }
            label = labels.get(user.role, 'perfil')
            raise serializers.ValidationError({
                'detail': f'Tu {label} todavía está pendiente de aprobación. Te avisaremos cuando esté listo.'
            })
        return data


class RegisterClinicSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)
    clinic_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    clinic_address = serializers.CharField(write_only=True, required=False, allow_blank=True)
    clinic_province = serializers.CharField(write_only=True, required=False, allow_blank=True)
    clinic_locality = serializers.CharField(write_only=True, required=False, allow_blank=True)
    clinic_phone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    clinic_description = serializers.CharField(write_only=True, required=False, allow_blank=True)
    clinic_is_24h = serializers.BooleanField(write_only=True, required=False, default=False)
    clinic_services = serializers.ListField(write_only=True, required=False, default=list)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password2',
            'clinic_name', 'clinic_address', 'clinic_province',
            'clinic_locality', 'clinic_phone', 'clinic_description',
            'clinic_is_24h', 'clinic_services',
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password': 'Las contraseñas no coinciden.'})
        if not attrs.get('email'):
            raise serializers.ValidationError({'email': 'El email es obligatorio.'})
        if not attrs.get('clinic_name'):
            raise serializers.ValidationError({'clinic_name': 'El nombre de la clínica es obligatorio.'})
        if not attrs.get('clinic_address'):
            raise serializers.ValidationError({'clinic_address': 'La dirección es obligatoria.'})
        if not attrs.get('clinic_province'):
            raise serializers.ValidationError({'clinic_province': 'La provincia es obligatoria.'})
        if not attrs.get('clinic_locality'):
            raise serializers.ValidationError({'clinic_locality': 'La localidad es obligatoria.'})
        return attrs

    def create(self, validated_data):
        clinic_data = {
            'name': validated_data.pop('clinic_name'),
            'address': validated_data.pop('clinic_address'),
            'province': validated_data.pop('clinic_province'),
            'locality': validated_data.pop('clinic_locality'),
            'phone': validated_data.pop('clinic_phone', ''),
            'description': validated_data.pop('clinic_description', ''),
            'is_24h': validated_data.pop('clinic_is_24h', False),
            'services': validated_data.pop('clinic_services', []),
        }
        validated_data.pop('password2')
        validated_data['role'] = 'clinic'
        validated_data['professional_verification_status'] = User.VERIFICATION_PENDING
        user = User.objects.create_user(**validated_data)
        user._clinic_data = clinic_data
        return user


class RegisterBusinessSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    business_name = serializers.CharField(write_only=True)
    business_type = serializers.CharField(write_only=True)
    responsible_name = serializers.CharField(write_only=True)
    business_phone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    business_whatsapp = serializers.CharField(write_only=True, required=False, allow_blank=True)
    business_province = serializers.CharField(write_only=True)
    business_locality = serializers.CharField(write_only=True)
    business_address = serializers.CharField(write_only=True, required=False, allow_blank=True)
    business_description = serializers.CharField(write_only=True, required=False, allow_blank=True)
    business_species = serializers.ListField(child=serializers.CharField(max_length=30), write_only=True, required=False, default=list)
    business_services = serializers.ListField(child=serializers.CharField(max_length=80), write_only=True, required=False, default=list)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password2', 'business_name',
            'business_type', 'responsible_name', 'business_phone',
            'business_whatsapp', 'business_province', 'business_locality',
            'business_address', 'business_description', 'business_species',
            'business_services',
        ]

    def validate(self, attrs):
        from partners.models import BusinessProfile, SPECIES_CHOICES
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password': 'Las contraseñas no coinciden.'})
        if attrs.get('business_type') not in dict(BusinessProfile.BUSINESS_TYPE_CHOICES):
            raise serializers.ValidationError({'business_type': 'Elegí un tipo de negocio válido.'})
        if not attrs.get('business_phone') and not attrs.get('business_whatsapp'):
            raise serializers.ValidationError({'business_whatsapp': 'Agregá un teléfono o WhatsApp de contacto.'})
        allowed_species = set(dict(SPECIES_CHOICES))
        species = list(dict.fromkeys(attrs.get('business_species') or []))
        if not species or any(item not in allowed_species for item in species):
            raise serializers.ValidationError({'business_species': 'Seleccioná al menos un tipo de animal válido.'})
        attrs['business_species'] = species
        attrs['business_services'] = list(dict.fromkeys(attrs.get('business_services') or []))[:80]
        return attrs

    def create(self, validated_data):
        profile_data = {
            'name': validated_data.pop('business_name'),
            'business_type': validated_data.pop('business_type'),
            'responsible_name': validated_data.pop('responsible_name'),
            'phone': validated_data.pop('business_phone', ''),
            'whatsapp': validated_data.pop('business_whatsapp', ''),
            'province': validated_data.pop('business_province'),
            'locality': validated_data.pop('business_locality'),
            'address': validated_data.pop('business_address', ''),
            'description': validated_data.pop('business_description', ''),
            'species': validated_data.pop('business_species', []),
            'services': validated_data.pop('business_services', []),
        }
        validated_data.pop('password2')
        validated_data['role'] = 'business'
        validated_data['professional_verification_status'] = User.VERIFICATION_PENDING
        user = User.objects.create_user(**validated_data)
        user._partner_profile_data = profile_data
        return user


class RegisterShelterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    shelter_name = serializers.CharField(write_only=True)
    shelter_type = serializers.CharField(write_only=True)
    responsible_name = serializers.CharField(write_only=True)
    shelter_phone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    shelter_whatsapp = serializers.CharField(write_only=True, required=False, allow_blank=True)
    shelter_province = serializers.CharField(write_only=True)
    shelter_locality = serializers.CharField(write_only=True)
    shelter_description = serializers.CharField(write_only=True, required=False, allow_blank=True)
    shelter_species = serializers.ListField(child=serializers.CharField(max_length=30), write_only=True, required=False, default=list)
    shelter_activities = serializers.ListField(child=serializers.CharField(max_length=80), write_only=True, required=False, default=list)
    accepting_animals = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password2', 'shelter_name',
            'shelter_type', 'responsible_name', 'shelter_phone',
            'shelter_whatsapp', 'shelter_province', 'shelter_locality',
            'shelter_description', 'shelter_species', 'shelter_activities',
            'accepting_animals',
        ]

    def validate(self, attrs):
        from partners.models import ShelterProfile, SPECIES_CHOICES
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password': 'Las contraseñas no coinciden.'})
        if attrs.get('shelter_type') not in dict(ShelterProfile.SHELTER_TYPE_CHOICES):
            raise serializers.ValidationError({'shelter_type': 'Elegí un tipo de refugio válido.'})
        if not attrs.get('shelter_phone') and not attrs.get('shelter_whatsapp'):
            raise serializers.ValidationError({'shelter_whatsapp': 'Agregá un teléfono o WhatsApp de contacto.'})
        allowed_species = set(dict(SPECIES_CHOICES))
        species = list(dict.fromkeys(attrs.get('shelter_species') or []))
        if not species or any(item not in allowed_species for item in species):
            raise serializers.ValidationError({'shelter_species': 'Seleccioná al menos un tipo de animal válido.'})
        attrs['shelter_species'] = species
        attrs['shelter_activities'] = list(dict.fromkeys(attrs.get('shelter_activities') or []))[:80]
        return attrs

    def create(self, validated_data):
        profile_data = {
            'name': validated_data.pop('shelter_name'),
            'shelter_type': validated_data.pop('shelter_type'),
            'responsible_name': validated_data.pop('responsible_name'),
            'phone': validated_data.pop('shelter_phone', ''),
            'whatsapp': validated_data.pop('shelter_whatsapp', ''),
            'province': validated_data.pop('shelter_province'),
            'locality': validated_data.pop('shelter_locality'),
            'description': validated_data.pop('shelter_description', ''),
            'species': validated_data.pop('shelter_species', []),
            'activities': validated_data.pop('shelter_activities', []),
            'accepting_animals': validated_data.pop('accepting_animals', False),
        }
        validated_data.pop('password2')
        validated_data['role'] = 'shelter'
        validated_data['professional_verification_status'] = User.VERIFICATION_PENDING
        user = User.objects.create_user(**validated_data)
        user._partner_profile_data = profile_data
        return user
