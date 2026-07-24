from rest_framework import serializers
from django.db.models import Avg
from .models import Clinic, ClinicCampaign, ClinicMembership, ClinicPhoto, ClinicSchedule
from appointments.models import Review
from vetpaw.image_validation import validate_uploaded_image
from users.permissions import is_vetpaw_admin


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
        return validate_uploaded_image(value, max_mb=3, label='La foto de la veterinaria')


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


class ClinicCampaignSerializer(serializers.ModelSerializer):
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)
    clinic_slug = serializers.CharField(source='clinic.slug', read_only=True)
    image_url = serializers.SerializerMethodField()
    campaign_type_display = serializers.CharField(source='get_campaign_type_display', read_only=True)
    appointments_count = serializers.IntegerField(read_only=True)
    remaining_slots = serializers.IntegerField(read_only=True, allow_null=True)
    post_id = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = ClinicCampaign
        fields = [
            'id', 'clinic', 'clinic_name', 'clinic_slug', 'campaign_type',
            'campaign_type_display', 'title', 'description', 'starts_at', 'ends_at',
            'location', 'capacity', 'species', 'price', 'is_free', 'image', 'image_url',
            'allow_booking', 'is_active', 'appointments_count', 'remaining_slots',
            'post_id', 'can_edit', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'clinic', 'clinic_name', 'clinic_slug', 'campaign_type_display',
            'image_url', 'appointments_count', 'remaining_slots', 'post_id', 'can_edit',
            'allow_booking', 'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'image': {'write_only': True, 'required': False, 'allow_null': True},
        }

    def get_image_url(self, obj):
        if not obj.image:
            return None
        try:
            url = obj.image.url
        except (AttributeError, ValueError):
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request and url.startswith('/') else url

    def get_post_id(self, obj):
        post = getattr(obj, 'community_post', None)
        return post.id if post else None

    def get_can_edit(self, obj):
        request = self.context.get('request')
        return bool(
            request and request.user.is_authenticated
            and (request.user.id == obj.clinic.owner_id or is_vetpaw_admin(request.user))
        )

    def validate_image(self, value):
        return validate_uploaded_image(value, max_mb=6, label='La imagen de la campaña')

    def validate(self, attrs):
        starts_at = attrs.get('starts_at', getattr(self.instance, 'starts_at', None))
        ends_at = attrs.get('ends_at', getattr(self.instance, 'ends_at', None))
        capacity = attrs.get('capacity', getattr(self.instance, 'capacity', None))
        if ends_at and starts_at and ends_at <= starts_at:
            raise serializers.ValidationError({'ends_at': 'La finalización debe ser posterior al inicio.'})
        if capacity == 0:
            raise serializers.ValidationError({'capacity': 'La capacidad debe ser mayor a cero.'})
        return attrs


class PublicClinicSerializer(serializers.ModelSerializer):
    rating_avg = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    members_count = serializers.SerializerMethodField()
    photos = ClinicPhotoSerializer(many=True, read_only=True)
    has_schedule = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()
    profile_url = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    posts_count = serializers.SerializerMethodField()
    paws_count = serializers.SerializerMethodField()
    following = serializers.SerializerMethodField()
    recent_posts = serializers.SerializerMethodField()
    gallery = serializers.SerializerMethodField()
    owner_user_id = serializers.IntegerField(source='owner_id', read_only=True)
    is_verified = serializers.SerializerMethodField()
    upcoming_campaigns = serializers.SerializerMethodField()
    can_request_appointment = serializers.SerializerMethodField()
    appointment_unavailable_reason = serializers.SerializerMethodField()

    class Meta:
        model = Clinic
        fields = [
            'id', 'owner_user_id', 'slug', 'profile_url', 'name', 'description',
            'address', 'show_public_address', 'province', 'locality', 'phone', 'email',
            'logo', 'logo_url', 'cover', 'cover_url', 'is_24h', 'services', 'is_verified',
            'rating_avg', 'reviews_count', 'reviews', 'members_count', 'photos',
            'has_schedule', 'followers_count', 'following_count', 'posts_count',
            'paws_count', 'following', 'recent_posts', 'gallery', 'upcoming_campaigns',
            'can_request_appointment', 'appointment_unavailable_reason', 'can_edit',
        ]
        read_only_fields = [
            'id', 'owner_user_id', 'slug', 'profile_url', 'logo_url', 'cover_url',
            'rating_avg', 'reviews_count', 'reviews', 'members_count', 'photos',
            'has_schedule', 'followers_count', 'following_count', 'posts_count',
            'paws_count', 'following', 'recent_posts', 'gallery', 'upcoming_campaigns',
            'can_request_appointment', 'appointment_unavailable_reason', 'can_edit',
        ]
        extra_kwargs = {
            'logo': {'write_only': True, 'required': False, 'allow_null': True},
            'cover': {'write_only': True, 'required': False, 'allow_null': True},
        }

    def _request(self):
        return self.context.get('request')

    def _file_url(self, field):
        if not field:
            return None
        try:
            url = field.url
        except (AttributeError, ValueError):
            return None
        request = self._request()
        return request.build_absolute_uri(url) if request and url.startswith('/') else url

    def _stats(self, obj):
        cache = getattr(self, '_stats_cache', {})
        if obj.pk not in cache:
            from community.social_profiles import profile_stats
            request = self._request()
            cache[obj.pk] = profile_stats('clinic', obj, request.user if request else None)
            self._stats_cache = cache
        return cache[obj.pk]

    def get_is_verified(self, obj):
        return bool(obj.owner_id and obj.owner.is_professionally_verified and obj.is_active)

    def get_upcoming_campaigns(self, obj):
        from django.utils import timezone
        rows = obj.community_campaigns.filter(
            is_active=True,
            starts_at__gte=timezone.now(),
        ).order_by('starts_at')[:6]
        return ClinicCampaignSerializer(rows, many=True, context=self.context).data

    def get_can_request_appointment(self, obj):
        from community.privacy import privacy_for
        settings = privacy_for(obj.owner) if obj.owner_id else None
        return bool(
            obj.can_receive_appointments
            and (not settings or settings.allow_appointment_requests)
        )

    def get_appointment_unavailable_reason(self, obj):
        if self.get_can_request_appointment(obj):
            return ''
        if not obj.can_use_clinical_tools:
            return 'Esta veterinaria no tiene activo el servicio mensual de turnos en VetPaw.'
        if not hasattr(obj, 'schedule'):
            return 'Esta veterinaria todavía no configuró su agenda en VetPaw.'
        from community.privacy import privacy_for
        settings = privacy_for(obj.owner) if obj.owner_id else None
        if settings and not settings.allow_appointment_requests:
            return 'Esta veterinaria pausó temporalmente las solicitudes de turno.'
        return 'Esta veterinaria no está recibiendo turnos en este momento.'

    def get_logo_url(self, obj):
        return self._file_url(obj.logo)

    def get_cover_url(self, obj):
        return self._file_url(obj.cover)

    def get_profile_url(self, obj):
        return f'/clinicas/{obj.slug}'

    def get_can_edit(self, obj):
        request = self._request()
        return bool(request and request.user.is_authenticated and (
            request.user.id == obj.owner_id or is_vetpaw_admin(request.user)
        ))

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

    def get_followers_count(self, obj):
        return self._stats(obj)['followers_count']

    def get_following_count(self, obj):
        return self._stats(obj)['following_count']

    def get_posts_count(self, obj):
        return self._stats(obj)['posts_count']

    def get_paws_count(self, obj):
        return self._stats(obj)['paws_count']

    def get_following(self, obj):
        return self._stats(obj)['following']

    def get_recent_posts(self, obj):
        from community.serializers import PostSerializer
        from community.social_profiles import target_posts
        posts = target_posts('clinic', obj).select_related(
            'created_by', 'pet__owner', 'pet__social_profile', 'clinic__owner',
            'business__owner', 'shelter__owner', 'related_lost_pet', 'related_birthday',
        ).prefetch_related('comments__author')[:20]
        return PostSerializer(posts, many=True, context=self.context).data

    def get_gallery(self, obj):
        from community.social_profiles import target_posts
        request = self._request()
        rows = target_posts('clinic', obj).exclude(image='').exclude(image__isnull=True)[:24]
        return [
            {
                'post_id': post.id,
                'image_url': self._file_url(post.image),
                'text': post.text[:180],
                'created_at': post.created_at,
            }
            for post in rows
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        from community.privacy import privacy_for
        settings = privacy_for(instance.owner)
        can_edit = self.get_can_edit(instance)
        if not can_edit and not instance.show_public_address:
            data['address'] = ''
        if settings and not can_edit:
            if not settings.show_location:
                data['address'] = ''
                data['province'] = ''
                data['locality'] = ''
            if not settings.show_phone:
                data['phone'] = ''
            if not settings.show_activity:
                data['recent_posts'] = []
                data['gallery'] = []
        data['allow_internal_messages'] = settings.allow_internal_messages if settings else True
        data['allow_appointment_requests'] = self.get_can_request_appointment(instance)
        return data

    def validate_logo(self, value):
        return validate_uploaded_image(value, max_mb=3, label='El logo de la veterinaria')

    def validate_cover(self, value):
        return validate_uploaded_image(value, max_mb=6, label='La portada de la veterinaria')


class ClinicSerializer(serializers.ModelSerializer):
    members_count = serializers.SerializerMethodField()
    rating_avg    = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    distance_km   = serializers.SerializerMethodField()
    is_member     = serializers.SerializerMethodField()
    has_schedule  = serializers.SerializerMethodField()
    can_request_appointment = serializers.SerializerMethodField()
    appointment_unavailable_reason = serializers.SerializerMethodField()
    effective_plan_status = serializers.CharField(read_only=True)
    plan_active = serializers.BooleanField(source='has_active_plan', read_only=True)

    class Meta:
        model = Clinic
        fields = [
            'id', 'owner', 'name', 'slug', 'description', 'address',
            'province', 'locality', 'phone', 'email',
            'logo', 'cover', 'show_public_address', 'is_active', 'is_24h', 'services',
            'members_count', 'rating_avg', 'reviews_count',
            'distance_km', 'is_member', 'has_schedule',
            'can_request_appointment', 'appointment_unavailable_reason',
            'plan_status', 'effective_plan_status', 'plan_active', 'trial_used',
            'plan_started_at', 'plan_ends_at', 'grace_ends_at', 'created_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'members_count', 'rating_avg',
                            'reviews_count', 'distance_km', 'is_member', 'has_schedule',
                            'can_request_appointment', 'appointment_unavailable_reason',
                            'plan_status', 'effective_plan_status', 'plan_active', 'trial_used',
                            'plan_started_at', 'plan_ends_at', 'grace_ends_at']

    def validate_logo(self, value):
        return validate_uploaded_image(value, max_mb=3, label='El logo de la veterinaria')

    def validate_cover(self, value):
        return validate_uploaded_image(value, max_mb=6, label='La portada de la veterinaria')

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

    def get_can_request_appointment(self, obj):
        try:
            from community.privacy import privacy_for
            settings = privacy_for(obj.owner) if obj.owner_id else None
        except Exception:
            settings = None
        return bool(obj.can_receive_appointments and (not settings or settings.allow_appointment_requests))

    def get_appointment_unavailable_reason(self, obj):
        if self.get_can_request_appointment(obj):
            return ''
        if not obj.can_use_clinical_tools:
            return 'Plan mensual de turnos no activo.'
        if not hasattr(obj, 'schedule'):
            return 'Agenda todavía no configurada.'
        return 'Solicitudes de turno pausadas.'


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