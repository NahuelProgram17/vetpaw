from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
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
        user = User.objects.create_user(**validated_data)
        return user


class UserSerializer(serializers.ModelSerializer):
    can_access_admin = serializers.SerializerMethodField()
    can_moderate_community = serializers.SerializerMethodField()

    def validate_avatar(self, value):
        return validate_uploaded_image(value, max_mb=3, label='La foto de perfil')

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'gender', 'phone', 'province', 'locality', 'avatar', 'bio',
            'created_at', 'is_approved', 'is_staff', 'is_superuser',
            'can_access_admin', 'can_moderate_community',
        ]
        read_only_fields = [
            'id', 'created_at', 'is_approved', 'is_staff', 'is_superuser',
            'can_access_admin', 'can_moderate_community',
        ]

    def get_can_access_admin(self, obj):
        return is_vetpaw_admin(obj)

    def get_can_moderate_community(self, obj):
        return is_community_moderator(obj)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        # Bloqueo de login para clínicas pendientes de aprobación
        user = self.user
        if user.role == 'clinic' and not user.is_approved:
            raise serializers.ValidationError({
                'detail': 'Tu clínica todavía está pendiente de aprobación. '
                          'Te avisaremos por mail cuando esté lista.'
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
        user = User.objects.create_user(**validated_data)
        user._clinic_data = clinic_data
        return user
