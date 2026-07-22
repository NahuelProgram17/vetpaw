from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class BusinessAccess(models.Model):
    PLAN_FREE = 'free'
    PLAN_PRO = 'pro'
    PLAN_PLUS = 'plus'
    PLAN_CHOICES = [
        (PLAN_FREE, 'Gratis'),
        (PLAN_PRO, 'Pro'),
        (PLAN_PLUS, 'Plus'),
    ]
    STATUS_DEVELOPMENT = 'development'
    STATUS_TRIAL = 'trial'
    STATUS_ACTIVE = 'active'
    STATUS_PAST_DUE = 'past_due'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_DEVELOPMENT, 'Acceso completo durante desarrollo'),
        (STATUS_TRIAL, 'Prueba'),
        (STATUS_ACTIVE, 'Activo'),
        (STATUS_PAST_DUE, 'Pago pendiente'),
        (STATUS_CANCELLED, 'Cancelado'),
    ]

    business = models.OneToOneField(
        'partners.BusinessProfile',
        on_delete=models.CASCADE,
        related_name='commerce_access',
    )
    plan = models.CharField(max_length=12, choices=PLAN_CHOICES, default=PLAN_FREE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DEVELOPMENT)
    monetization_enforced = models.BooleanField(default=False)
    full_access_override = models.BooleanField(default=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.business.name}: {self.get_plan_display()}'


class CatalogItem(models.Model):
    TYPE_PRODUCT = 'product'
    TYPE_SERVICE = 'service'
    TYPE_CHOICES = [
        (TYPE_PRODUCT, 'Producto'),
        (TYPE_SERVICE, 'Servicio'),
    ]
    CATEGORY_GROOMING = 'grooming'
    CATEGORY_FOOD = 'food'
    CATEGORY_ACCESSORIES = 'accessories'
    CATEGORY_DAYCARE = 'daycare'
    CATEGORY_BOARDING = 'boarding'
    CATEGORY_WALKING = 'walking'
    CATEGORY_TRAINING = 'training'
    CATEGORY_TRANSPORT = 'transport'
    CATEGORY_PHARMACY = 'pharmacy'
    CATEGORY_PHOTOGRAPHY = 'photography'
    CATEGORY_OTHER = 'other'
    CATEGORY_CHOICES = [
        (CATEGORY_GROOMING, 'Peluquería e higiene'),
        (CATEGORY_FOOD, 'Alimentos'),
        (CATEGORY_ACCESSORIES, 'Accesorios y juguetes'),
        (CATEGORY_DAYCARE, 'Guardería'),
        (CATEGORY_BOARDING, 'Hospedaje'),
        (CATEGORY_WALKING, 'Paseos'),
        (CATEGORY_TRAINING, 'Adiestramiento'),
        (CATEGORY_TRANSPORT, 'Transporte'),
        (CATEGORY_PHARMACY, 'Farmacia e higiene'),
        (CATEGORY_PHOTOGRAPHY, 'Fotografía'),
        (CATEGORY_OTHER, 'Otro'),
    ]

    business = models.ForeignKey(
        'partners.BusinessProfile',
        on_delete=models.CASCADE,
        related_name='catalog_items',
    )
    item_type = models.CharField(max_length=12, choices=TYPE_CHOICES)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    title = models.CharField(max_length=180)
    description = models.TextField(max_length=3000)
    image = models.ImageField(upload_to='commerce/catalog/', blank=True, null=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_on_request = models.BooleanField(default=False)
    promotional_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    species = models.JSONField(default=list, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    requires_booking = models.BooleanField(default=False)
    home_service = models.BooleanField(default=False)
    delivery = models.BooleanField(default=False)
    pickup = models.BooleanField(default=False)
    stock_quantity = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    views_count = models.PositiveIntegerField(default=0)
    shared_post = models.OneToOneField(
        'community.Post',
        on_delete=models.SET_NULL,
        related_name='catalog_item',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'is_active', '-created_at'], name='commerce_cat_business_idx'),
            models.Index(fields=['item_type', 'category', 'is_active'], name='commerce_cat_filter_idx'),
        ]

    def clean(self):
        if not self.price_on_request and self.price is None:
            raise ValidationError({'price': 'Ingresá un precio o marcá “Consultar precio”.'})
        if self.price is not None and self.price < 0:
            raise ValidationError({'price': 'El precio no puede ser negativo.'})
        if self.promotional_price is not None:
            if self.promotional_price < 0:
                raise ValidationError({'promotional_price': 'El precio promocional no puede ser negativo.'})
            if self.price is not None and self.promotional_price >= self.price:
                raise ValidationError({'promotional_price': 'El precio promocional debe ser menor al precio habitual.'})
        if self.item_type == self.TYPE_PRODUCT:
            self.requires_booking = False
            self.duration_minutes = None
        if self.requires_booking and not self.duration_minutes:
            raise ValidationError({'duration_minutes': 'Indicá la duración aproximada del servicio.'})

    @property
    def display_price(self):
        if self.price_on_request:
            return 'Consultar'
        return self.promotional_price if self.promotional_price is not None else self.price

    def __str__(self):
        return f'{self.business.name}: {self.title}'


class Promotion(models.Model):
    business = models.ForeignKey(
        'partners.BusinessProfile',
        on_delete=models.CASCADE,
        related_name='commerce_promotions',
    )
    catalog_item = models.ForeignKey(
        CatalogItem,
        on_delete=models.SET_NULL,
        related_name='promotions',
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=180)
    description = models.TextField(max_length=2500)
    image = models.ImageField(upload_to='commerce/promotions/', blank=True, null=True)
    previous_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    promotional_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    quantity_available = models.PositiveIntegerField(null=True, blank=True)
    locality = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    views_count = models.PositiveIntegerField(default=0)
    shared_post = models.OneToOneField(
        'community.Post',
        on_delete=models.SET_NULL,
        related_name='commerce_promotion',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ends_at', '-created_at']
        indexes = [
            models.Index(fields=['business', 'is_active', 'ends_at'], name='commerce_prom_business_idx'),
            models.Index(fields=['is_active', 'starts_at', 'ends_at'], name='commerce_prom_dates_idx'),
        ]

    def clean(self):
        if self.ends_at <= self.starts_at:
            raise ValidationError({'ends_at': 'La promoción debe finalizar después de su inicio.'})
        if self.catalog_item_id and self.catalog_item.business_id != self.business_id:
            raise ValidationError({'catalog_item': 'El elemento no pertenece a este negocio.'})
        if self.promotional_price is not None and self.promotional_price < 0:
            raise ValidationError({'promotional_price': 'El precio promocional no puede ser negativo.'})
        if self.previous_price is not None and self.promotional_price is not None and self.promotional_price >= self.previous_price:
            raise ValidationError({'promotional_price': 'El precio promocional debe ser menor al anterior.'})

    @property
    def is_current(self):
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.ends_at

    def __str__(self):
        return f'{self.business.name}: {self.title}'


class BusinessFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='business_favorites')
    business = models.ForeignKey('partners.BusinessProfile', on_delete=models.CASCADE, related_name='favorites', null=True, blank=True)
    catalog_item = models.ForeignKey(CatalogItem, on_delete=models.CASCADE, related_name='favorites', null=True, blank=True)
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='favorites', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'business'], condition=models.Q(business__isnull=False), name='unique_user_business_favorite'),
            models.UniqueConstraint(fields=['user', 'catalog_item'], condition=models.Q(catalog_item__isnull=False), name='unique_user_catalog_favorite'),
            models.UniqueConstraint(fields=['user', 'promotion'], condition=models.Q(promotion__isnull=False), name='unique_user_promotion_favorite'),
        ]

    def clean(self):
        if sum(bool(value) for value in (self.business_id, self.catalog_item_id, self.promotion_id)) != 1:
            raise ValidationError('Un favorito debe apuntar a un único negocio, producto, servicio o promoción.')


class BusinessInquiry(models.Model):
    STATUS_NEW = 'new'
    STATUS_REPLIED = 'replied'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_NEW, 'Nueva'),
        (STATUS_REPLIED, 'Respondida'),
        (STATUS_CLOSED, 'Cerrada'),
    ]
    business = models.ForeignKey('partners.BusinessProfile', on_delete=models.CASCADE, related_name='inquiries')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='business_inquiries')
    catalog_item = models.ForeignKey(CatalogItem, on_delete=models.SET_NULL, related_name='inquiries', null=True, blank=True)
    promotion = models.ForeignKey(Promotion, on_delete=models.SET_NULL, related_name='inquiries', null=True, blank=True)
    content = models.TextField(max_length=1500)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_NEW)
    message = models.ForeignKey('messaging.Message', on_delete=models.SET_NULL, related_name='business_inquiries', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['business', 'status', '-created_at'], name='commerce_inq_business_idx')]


class BusinessReservation(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_REJECTED = 'rejected'
    STATUS_RESCHEDULED = 'rescheduled'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_CONFIRMED, 'Confirmada'),
        (STATUS_REJECTED, 'Rechazada'),
        (STATUS_RESCHEDULED, 'Reprogramada'),
        (STATUS_COMPLETED, 'Completada'),
        (STATUS_CANCELLED, 'Cancelada'),
    ]
    ACTIVE_STATUSES = (STATUS_PENDING, STATUS_CONFIRMED, STATUS_RESCHEDULED)

    business = models.ForeignKey('partners.BusinessProfile', on_delete=models.CASCADE, related_name='reservations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='business_reservations')
    pet = models.ForeignKey('pets.Pet', on_delete=models.PROTECT, related_name='business_reservations')
    catalog_item = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name='reservations')
    date = models.DateField()
    start_time = models.TimeField()
    notes = models.TextField(blank=True, max_length=1200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    business_note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date', 'start_time', '-created_at']
        indexes = [
            models.Index(fields=['business', 'date', 'status'], name='commerce_res_business_idx'),
            models.Index(fields=['user', '-created_at'], name='commerce_res_user_idx'),
        ]

    def clean(self):
        if self.catalog_item_id:
            if self.catalog_item.business_id != self.business_id:
                raise ValidationError({'catalog_item': 'El servicio no pertenece a este negocio.'})
            if self.catalog_item.item_type != CatalogItem.TYPE_SERVICE or not self.catalog_item.requires_booking:
                raise ValidationError({'catalog_item': 'Este elemento no admite reservas.'})
        if self.pet_id and self.user_id and self.pet.owner_id != self.user_id:
            raise ValidationError({'pet': 'Solo podés reservar para una mascota de tu cuenta.'})


class BusinessProfileView(models.Model):
    business = models.ForeignKey('partners.BusinessProfile', on_delete=models.CASCADE, related_name='profile_views')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='viewed_business_profiles', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['business', '-created_at'], name='commerce_view_business_idx')]
