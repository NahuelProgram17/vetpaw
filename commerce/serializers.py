from django.utils import timezone
from rest_framework import serializers

from community.privacy import users_blocked_between
from partners.models import BusinessProfile
from pets.models import Pet
from vetpaw.image_validation import validate_uploaded_image

from .models import (
    BusinessAccess,
    BusinessFavorite,
    BusinessInquiry,
    BusinessReservation,
    CatalogItem,
    Promotion,
)


def absolute_file_url(request, field):
    if not field:
        return None
    try:
        url = field.url
    except (AttributeError, ValueError):
        return None
    return request.build_absolute_uri(url) if request and url.startswith('/') else url


class CatalogItemSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    business_name = serializers.CharField(source='business.name', read_only=True)
    business_slug = serializers.CharField(source='business.slug', read_only=True)
    item_type_display = serializers.CharField(source='get_item_type_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    display_price = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    favorites_count = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    shared_post_id = serializers.IntegerField(source='shared_post.id', read_only=True)

    class Meta:
        model = CatalogItem
        fields = [
            'id', 'business', 'business_name', 'business_slug', 'item_type',
            'item_type_display', 'category', 'category_display', 'title', 'description',
            'image', 'image_url', 'price', 'price_on_request', 'promotional_price',
            'display_price', 'species', 'duration_minutes', 'requires_booking',
            'home_service', 'delivery', 'pickup', 'stock_quantity', 'is_active',
            'views_count', 'favorites_count', 'is_favorite', 'can_edit', 'shared_post_id',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'business', 'business_name', 'business_slug', 'item_type_display',
            'category_display', 'image_url', 'display_price', 'views_count',
            'favorites_count', 'is_favorite', 'can_edit', 'shared_post_id',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {'image': {'write_only': True, 'required': False, 'allow_null': True}}

    def get_image_url(self, obj):
        return absolute_file_url(self.context.get('request'), obj.image)

    def get_display_price(self, obj):
        value = obj.display_price
        return str(value) if value != 'Consultar' and value is not None else value

    def get_favorites_count(self, obj):
        if hasattr(obj, 'favorite_total'):
            return obj.favorite_total
        return obj.favorites.count()

    def get_is_favorite(self, obj):
        if hasattr(obj, 'viewer_is_favorite'):
            return bool(obj.viewer_is_favorite)
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and BusinessFavorite.objects.filter(user=request.user, catalog_item=obj).exists())

    def get_can_edit(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and obj.business.owner_id == request.user.id)

    def validate_image(self, value):
        if value:
            validate_uploaded_image(value)
        return value

    def validate_species(self, value):
        if isinstance(value, str):
            import json
            try:
                value = json.loads(value)
            except (TypeError, ValueError):
                raise serializers.ValidationError('Elegí una lista válida de animales.')
        if not isinstance(value, list):
            raise serializers.ValidationError('Elegí una lista válida de animales.')
        return [str(item)[:30] for item in value[:20]]

    def validate(self, attrs):
        instance = self.instance
        item_type = attrs.get('item_type', getattr(instance, 'item_type', None))
        price_on_request = attrs.get('price_on_request', getattr(instance, 'price_on_request', False))
        price = attrs.get('price', getattr(instance, 'price', None))
        promotional = attrs.get('promotional_price', getattr(instance, 'promotional_price', None))
        requires_booking = attrs.get('requires_booking', getattr(instance, 'requires_booking', False))
        duration = attrs.get('duration_minutes', getattr(instance, 'duration_minutes', None))
        if not price_on_request and price is None:
            raise serializers.ValidationError({'price': 'Ingresá un precio o marcá “Consultar precio”.'})
        if price is not None and price < 0:
            raise serializers.ValidationError({'price': 'El precio no puede ser negativo.'})
        if promotional is not None and price is not None and promotional >= price:
            raise serializers.ValidationError({'promotional_price': 'Debe ser menor al precio habitual.'})
        if item_type == CatalogItem.TYPE_PRODUCT:
            attrs['requires_booking'] = False
            attrs['duration_minutes'] = None
        elif requires_booking and not duration:
            raise serializers.ValidationError({'duration_minutes': 'Indicá la duración del servicio.'})
        return attrs


class PromotionSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    business_name = serializers.CharField(source='business.name', read_only=True)
    business_slug = serializers.CharField(source='business.slug', read_only=True)
    catalog_item_title = serializers.CharField(source='catalog_item.title', read_only=True)
    is_current = serializers.BooleanField(read_only=True)
    is_favorite = serializers.SerializerMethodField()
    favorites_count = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    shared_post_id = serializers.IntegerField(source='shared_post.id', read_only=True)

    class Meta:
        model = Promotion
        fields = [
            'id', 'business', 'business_name', 'business_slug', 'catalog_item',
            'catalog_item_title', 'title', 'description', 'image', 'image_url',
            'previous_price', 'promotional_price', 'starts_at', 'ends_at',
            'quantity_available', 'locality', 'is_active', 'is_current', 'views_count',
            'favorites_count', 'is_favorite', 'can_edit', 'shared_post_id',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'business', 'business_name', 'business_slug', 'catalog_item_title',
            'image_url', 'is_current', 'views_count', 'favorites_count', 'is_favorite',
            'can_edit', 'shared_post_id', 'created_at', 'updated_at',
        ]
        extra_kwargs = {'image': {'write_only': True, 'required': False, 'allow_null': True}}

    def get_image_url(self, obj):
        return absolute_file_url(self.context.get('request'), obj.image)

    def get_favorites_count(self, obj):
        if hasattr(obj, 'favorite_total'):
            return obj.favorite_total
        return obj.favorites.count()

    def get_is_favorite(self, obj):
        if hasattr(obj, 'viewer_is_favorite'):
            return bool(obj.viewer_is_favorite)
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and BusinessFavorite.objects.filter(user=request.user, promotion=obj).exists())

    def get_can_edit(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and obj.business.owner_id == request.user.id)

    def validate_image(self, value):
        if value:
            validate_uploaded_image(value)
        return value

    def validate(self, attrs):
        instance = self.instance
        business = self.context.get('business') or getattr(instance, 'business', None)
        item = attrs.get('catalog_item', getattr(instance, 'catalog_item', None))
        starts_at = attrs.get('starts_at', getattr(instance, 'starts_at', None))
        ends_at = attrs.get('ends_at', getattr(instance, 'ends_at', None))
        previous = attrs.get('previous_price', getattr(instance, 'previous_price', None))
        current = attrs.get('promotional_price', getattr(instance, 'promotional_price', None))
        if item and business and item.business_id != business.id:
            raise serializers.ValidationError({'catalog_item': 'Ese elemento no pertenece a tu negocio.'})
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError({'ends_at': 'La fecha final debe ser posterior al inicio.'})
        if current is not None and previous is not None and current >= previous:
            raise serializers.ValidationError({'promotional_price': 'Debe ser menor al precio anterior.'})
        return attrs


class BusinessInquirySerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business.name', read_only=True)
    user_name = serializers.SerializerMethodField()
    user_phone = serializers.CharField(source='user.phone', read_only=True)
    catalog_item_title = serializers.CharField(source='catalog_item.title', read_only=True)
    promotion_title = serializers.CharField(source='promotion.title', read_only=True)

    class Meta:
        model = BusinessInquiry
        fields = [
            'id', 'business', 'business_name', 'user', 'user_name', 'user_phone',
            'catalog_item', 'catalog_item_title', 'promotion', 'promotion_title',
            'content', 'status', 'message', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'user_name', 'user_phone', 'business_name',
            'catalog_item_title', 'promotion_title', 'message', 'created_at', 'updated_at',
        ]

    def get_user_name(self, obj):
        return obj.user.get_full_name().strip() or obj.user.username

    def validate(self, attrs):
        business = attrs.get('business')
        item = attrs.get('catalog_item')
        promotion = attrs.get('promotion')
        request = self.context['request']
        if business.owner_id == request.user.id:
            raise serializers.ValidationError('No podés consultarte a tu propio negocio.')
        if item and item.business_id != business.id:
            raise serializers.ValidationError({'catalog_item': 'El elemento no pertenece al negocio.'})
        if promotion and promotion.business_id != business.id:
            raise serializers.ValidationError({'promotion': 'La promoción no pertenece al negocio.'})
        if users_blocked_between(request.user, business.owner):
            raise serializers.ValidationError('No podés contactar a este negocio.')
        return attrs


class BusinessReservationSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business.name', read_only=True)
    business_slug = serializers.CharField(source='business.slug', read_only=True)
    catalog_item_title = serializers.CharField(source='catalog_item.title', read_only=True)
    duration_minutes = serializers.IntegerField(source='catalog_item.duration_minutes', read_only=True)
    pet_name = serializers.CharField(source='pet.name', read_only=True)
    user_name = serializers.SerializerMethodField()
    user_phone = serializers.CharField(source='user.phone', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    can_manage = serializers.SerializerMethodField()

    class Meta:
        model = BusinessReservation
        fields = [
            'id', 'business', 'business_name', 'business_slug', 'user', 'user_name',
            'user_phone', 'pet', 'pet_name', 'catalog_item', 'catalog_item_title',
            'duration_minutes', 'date', 'start_time', 'notes', 'status',
            'status_display', 'business_note', 'can_manage', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'business_name', 'business_slug', 'user_name', 'user_phone',
            'pet_name', 'catalog_item_title', 'duration_minutes', 'status',
            'status_display', 'business_note', 'can_manage', 'created_at', 'updated_at',
        ]

    def get_user_name(self, obj):
        return obj.user.get_full_name().strip() or obj.user.username

    def get_can_manage(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and obj.business.owner_id == request.user.id)

    def validate(self, attrs):
        request = self.context['request']
        business = attrs.get('business')
        item = attrs.get('catalog_item')
        pet = attrs.get('pet')
        date = attrs.get('date')
        start_time = attrs.get('start_time')
        if request.user.role != 'owner':
            raise serializers.ValidationError('Las reservas deben realizarse desde una cuenta de dueño de mascota.')
        if not business.accepts_reservations:
            raise serializers.ValidationError({'business': 'Este negocio no está recibiendo reservas.'})
        if users_blocked_between(request.user, business.owner):
            raise serializers.ValidationError('No podés reservar con este negocio.')
        if pet.owner_id != request.user.id:
            raise serializers.ValidationError({'pet': 'Elegí una mascota de tu cuenta.'})
        if item.business_id != business.id or item.item_type != CatalogItem.TYPE_SERVICE or not item.requires_booking or not item.is_active:
            raise serializers.ValidationError({'catalog_item': 'Este servicio no admite reservas.'})
        if date < timezone.localdate():
            raise serializers.ValidationError({'date': 'Elegí una fecha futura.'})
        day_key = str(date.weekday())
        schedule = business.opening_hours or {}
        day = schedule.get(day_key, {})
        if not business.is_24h:
            if day.get('closed'):
                raise serializers.ValidationError({'date': 'El negocio está cerrado ese día.'})
            opening = day.get('open')
            closing = day.get('close')
            if opening and start_time.strftime('%H:%M') < opening:
                raise serializers.ValidationError({'start_time': 'El horario es anterior a la apertura.'})
            if closing and start_time.strftime('%H:%M') >= closing:
                raise serializers.ValidationError({'start_time': 'El horario es posterior al cierre.'})
        conflict = BusinessReservation.objects.filter(
            business=business,
            date=date,
            start_time=start_time,
            status__in=BusinessReservation.ACTIVE_STATUSES,
        )
        if conflict.exists():
            raise serializers.ValidationError({'start_time': 'Ese horario ya no está disponible.'})
        return attrs


class BusinessFavoriteSerializer(serializers.ModelSerializer):
    target_type = serializers.SerializerMethodField()
    target = serializers.SerializerMethodField()

    class Meta:
        model = BusinessFavorite
        fields = ['id', 'target_type', 'target', 'created_at']
        read_only_fields = fields

    def get_target_type(self, obj):
        if obj.business_id:
            return 'business'
        if obj.catalog_item_id:
            return 'catalog_item'
        return 'promotion'

    def get_target(self, obj):
        request = self.context.get('request')
        if obj.business_id:
            business = obj.business
            return {
                'id': business.id, 'name': business.name, 'slug': business.slug,
                'logo_url': absolute_file_url(request, business.logo),
                'locality': business.locality, 'province': business.province,
            }
        if obj.catalog_item_id:
            return CatalogItemSerializer(obj.catalog_item, context=self.context).data
        return PromotionSerializer(obj.promotion, context=self.context).data


class BusinessAccessSerializer(serializers.ModelSerializer):
    plan_display = serializers.CharField(source='get_plan_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    has_full_access = serializers.SerializerMethodField()

    class Meta:
        model = BusinessAccess
        fields = [
            'plan', 'plan_display', 'status', 'status_display', 'monetization_enforced',
            'full_access_override', 'has_full_access', 'trial_ends_at', 'current_period_end',
        ]
        read_only_fields = fields

    def get_has_full_access(self, obj):
        return bool(obj.full_access_override or not obj.monetization_enforced or obj.plan in {BusinessAccess.PLAN_PRO, BusinessAccess.PLAN_PLUS})
