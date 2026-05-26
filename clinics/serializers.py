from rest_framework import serializers
from django.db.models import Avg
from .models import Clinic, ClinicMembership, ClinicPhoto, ClinicSchedule
from appointments.models import Review


class ReviewSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'owner_name', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'owner_name', 'created_at']

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("El rating debe ser entre 1 y 5.")
        return value


class ClinicPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicPhoto
        fields = ['id', 'image', 'caption', 'order', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_image(self, value):
        if value.size > 3 * 1024 * 1024:
            raise serializers.ValidationError("La foto no puede superar los 3MB.")
        allowed = ['image/jpeg', 'image/png', 'image/webp']
        if hasattr(value, 'content_type') and value.content_type not in allowed:
            raise serializers.ValidationError("Solo se permiten imágenes JPG, PNG o WebP.")
        return value


class ClinicScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicSchedule
        fields = [
            'id',
            'working_days',
            'day_hours',
            'duration_control',
            'duration_vaccine',
            'duration_surgery',
            'duration_other',
            'interval_minutes',
            'cancel_limit_hours',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']

    def validate_working_days(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Debe ser una lista de días.")
        for d in value:
            if d not in range(7):
                raise serializers.ValidationError("Los días deben ser números entre 0 (lunes) y 6 (domingo).")
        return value

    def validate_day_hours(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Debe ser un objeto con horarios por día.")
        for day, hours in value.items():
            if 'open' not in hours or 'close' not in hours:
                raise serializers.ValidationError(f"El día {day} debe tener 'open' y 'close'.")
        return value

    def validate_interval_minutes(self, value):
        if value not in [0, 10, 15, 20]:
            raise serializers.ValidationError("El intervalo debe ser 0, 10, 15 o 20 minutos.")
        return value


class PublicClinicSerializer(serializers.ModelSerializer):
    rating_avg    = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    reviews       = serializers.SerializerMethodField()
    members_count = serializers.SerializerMethodField()
    photos        = ClinicPhotoSerializer(many=True, read_only=True)
    has_schedule  = serializers.SerializerMethodField()

    class Meta:
        model = Clinic
        fields = [
            'id', 'slug', 'name', 'description', 'address',
            'province', 'locality', 'phone',
            'logo', 'is_24h', 'services',
            'rating_avg', 'reviews_count', 'reviews',
            'members_count', 'photos', 'has_schedule',
        ]

    def get_rating_avg(self, obj):
        avg = obj.reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg, 1) if avg else None

    def get_reviews_count(self, obj):
        return obj.reviews.count()

    def get_reviews(self, obj):
        reviews = obj.reviews.order_by('-created_at')[:10]
        return ReviewSerializer(reviews, many=True).data

    def get_members_count(self, obj):
        return obj.members.filter(status='active').count()

    def get_has_schedule(self, obj):
        return hasattr(obj, 'schedule')


class ClinicSerializer(serializers.ModelSerializer):
    members_count = serializers.SerializerMethodField()
    rating_avg    = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    distance_km   = serializers.SerializerMethodField()
    is_member     = serializers.SerializerMethodField()
    has_schedule  = serializers.SerializerMethodField()

    class Meta:
        model = Clinic
        fields = [
            'id', 'owner', 'name', 'slug', 'description', 'address',
            'province', 'locality', 'phone', 'email',
            'logo', 'is_active', 'is_24h', 'services',
            'members_count', 'rating_avg', 'reviews_count',
            'distance_km', 'is_member', 'has_schedule', 'created_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'members_count', 'rating_avg',
                            'reviews_count', 'distance_km', 'is_member', 'has_schedule']

    def get_members_count(self, obj):
        return obj.members.filter(status='active').count()

    def get_rating_avg(self, obj):
        avg = obj.reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg, 1) if avg else None

    def get_reviews_count(self, obj):
        return obj.reviews.count()

    def get_distance_km(self, obj):
        return getattr(obj, '_distance_km', None)

    def get_is_member(self, obj):
        try:
            request = self.context.get('request')
            if not request or not request.user or not request.user.is_authenticated:
                return False
            return obj.members.filter(owner=request.user, status='active').exists()
        except Exception:
            return False

    def get_has_schedule(self, obj):
        return hasattr(obj, 'schedule')


class ClinicMembershipSerializer(serializers.ModelSerializer):
    clinic_name     = serializers.CharField(source='clinic.name',     read_only=True)
    clinic_locality = serializers.CharField(source='clinic.locality', read_only=True)

    class Meta:
        model = ClinicMembership
        fields = [
            'id', 'clinic', 'clinic_name', 'clinic_locality',
            'status', 'leave_reason', 'leave_rating',
            'joined_at', 'left_at'
        ]
        read_only_fields = ['id', 'joined_at', 'left_at', 'status']


class LeaveClinicSerializer(serializers.Serializer):
    leave_reason = serializers.CharField(required=True)
    leave_rating = serializers.IntegerField(min_value=1, max_value=5)