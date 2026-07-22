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
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    posts_count = serializers.SerializerMethodField()
    paws_count = serializers.SerializerMethodField()
    following = serializers.SerializerMethodField()
    recent_posts = serializers.SerializerMethodField()
    gallery = serializers.SerializerMethodField()
    owner_user_id = serializers.IntegerField(source='owner_id', read_only=True)

    PRIVATE_FIELDS = set()
    COMPLETION_FIELDS = ()
    PROFILE_TYPE = ''

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

    def _social_stats(self, obj):
        cache = getattr(self, '_social_stats_cache', {})
        if obj.pk not in cache:
            from community.social_profiles import profile_stats
            request = self.context.get('request')
            cache[obj.pk] = profile_stats(
                self.PROFILE_TYPE,
                obj,
                request.user if request else None,
            )
            self._social_stats_cache = cache
        return cache[obj.pk]

    def get_followers_count(self, obj):
        return self._social_stats(obj)['followers_count']

    def get_following_count(self, obj):
        return self._social_stats(obj)['following_count']

    def get_posts_count(self, obj):
        return self._social_stats(obj)['posts_count']

    def get_paws_count(self, obj):
        return self._social_stats(obj)['paws_count']

    def get_following(self, obj):
        return self._social_stats(obj)['following']

    def get_recent_posts(self, obj):
        from community.serializers import PostSerializer
        from community.social_profiles import target_posts
        posts = target_posts(self.PROFILE_TYPE, obj).select_related(
            'created_by', 'pet__owner', 'pet__social_profile', 'clinic__owner',
            'business__owner', 'shelter__owner', 'related_lost_pet', 'related_birthday',
        ).prefetch_related('comments__author')[:20]
        return PostSerializer(posts, many=True, context=self.context).data

    def get_gallery(self, obj):
        from community.social_profiles import target_posts
        request = self.context.get('request')
        rows = target_posts(self.PROFILE_TYPE, obj).exclude(image='').exclude(image__isnull=True)[:24]
        return [
            {
                'post_id': post.id,
                'image_url': absolute_file_url(request, post.image),
                'text': post.text[:180],
                'created_at': post.created_at,
            }
            for post in rows
        ]

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
        from community.privacy import privacy_for
        settings = privacy_for(instance.owner)
        can_edit = self.get_can_edit(instance)
        if not can_edit:
            for field in self.PRIVATE_FIELDS:
                data.pop(field, None)
            data.pop('address', None)
            if settings:
                if not settings.show_location:
                    data['province'] = ''
                    data['locality'] = ''
                    data['public_address'] = ''
                if not settings.show_phone:
                    data['phone'] = ''
                if not settings.show_whatsapp:
                    data['whatsapp'] = ''
                if not settings.show_responsible_name:
                    data['responsible_name'] = ''
                if not settings.show_activity:
                    data['recent_posts'] = []
                    data['gallery'] = []
                if self.PROFILE_TYPE == 'shelter' and not settings.show_donation_info:
                    data['donation_alias'] = ''
                    data['donation_needs'] = ''
        data['allow_internal_messages'] = settings.allow_internal_messages if settings else True
        data['allow_appointment_requests'] = settings.allow_appointment_requests if settings else True
        return data


class BusinessProfileSerializer(ProfileSerializerMixin, serializers.ModelSerializer):
    PROFILE_TYPE = 'business'
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    posts_count = serializers.SerializerMethodField()
    paws_count = serializers.SerializerMethodField()
    following = serializers.SerializerMethodField()
    recent_posts = serializers.SerializerMethodField()
    gallery = serializers.SerializerMethodField()
    owner_user_id = serializers.IntegerField(source='owner_id', read_only=True)
    logo_url = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()
    profile_url = serializers.SerializerMethodField()
    completion_percentage = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    public_address = serializers.SerializerMethodField()
    business_type_display = serializers.CharField(source='get_business_type_display', read_only=True)
    catalog_preview = serializers.SerializerMethodField()
    active_promotions = serializers.SerializerMethodField()
    catalog_count = serializers.SerializerMethodField()
    favorites_count = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()

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
            'appointment_required', 'accepts_reservations', 'is_24h', 'payment_methods', 'price_range',
            'promotions', 'tax_id', 'legal_name', 'is_verified', 'is_active',
            'owner_user_id', 'followers_count', 'following_count', 'posts_count',
            'paws_count', 'following', 'recent_posts', 'gallery',
            'profile_url', 'completion_percentage', 'can_edit', 'catalog_preview',
            'active_promotions', 'catalog_count', 'favorites_count', 'is_favorite', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'slug', 'business_type_display', 'logo_url', 'cover_url',
            'public_address', 'is_verified', 'is_active', 'owner_user_id',
            'followers_count', 'following_count', 'posts_count', 'paws_count',
            'following', 'recent_posts', 'gallery', 'profile_url',
            'completion_percentage', 'can_edit', 'catalog_preview', 'active_promotions',
            'catalog_count', 'favorites_count', 'is_favorite', 'created_at', 'updated_at',
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

    def get_catalog_preview(self, obj):
        from commerce.models import CatalogItem
        from commerce.serializers import CatalogItemSerializer
        items = CatalogItem.objects.filter(business=obj, is_active=True).order_by('-created_at')[:50]
        return CatalogItemSerializer(items, many=True, context=self.context).data

    def get_active_promotions(self, obj):
        from django.utils import timezone
        from commerce.models import Promotion
        from commerce.serializers import PromotionSerializer
        now = timezone.now()
        promotions = Promotion.objects.filter(
            business=obj, is_active=True, starts_at__lte=now, ends_at__gte=now,
        ).order_by('ends_at')[:20]
        return PromotionSerializer(promotions, many=True, context=self.context).data

    def get_catalog_count(self, obj):
        return obj.catalog_items.filter(is_active=True).count()

    def get_favorites_count(self, obj):
        return obj.favorites.count()

    def get_is_favorite(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        from commerce.models import BusinessFavorite
        return BusinessFavorite.objects.filter(user=request.user, business=obj).exists()

    def get_profile_url(self, obj):
        return f'/negocios/{obj.slug}'


class ShelterProfileSerializer(ProfileSerializerMixin, serializers.ModelSerializer):
    PROFILE_TYPE = 'shelter'
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    posts_count = serializers.SerializerMethodField()
    paws_count = serializers.SerializerMethodField()
    following = serializers.SerializerMethodField()
    recent_posts = serializers.SerializerMethodField()
    gallery = serializers.SerializerMethodField()
    owner_user_id = serializers.IntegerField(source='owner_id', read_only=True)
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
            'owner_user_id', 'followers_count', 'following_count', 'posts_count',
            'paws_count', 'following', 'recent_posts', 'gallery',
            'profile_url', 'completion_percentage', 'can_edit', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'slug', 'shelter_type_display', 'capacity_status_display',
            'logo_url', 'cover_url', 'public_address', 'is_verified', 'is_active',
            'owner_user_id', 'followers_count', 'following_count', 'posts_count',
            'paws_count', 'following', 'recent_posts', 'gallery', 'profile_url',
            'completion_percentage', 'can_edit', 'created_at', 'updated_at',
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
