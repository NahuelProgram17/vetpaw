from django.conf import settings
from django.db import models
from django.utils.text import slugify


SPECIES_CHOICES = [
    ('dog', 'Perros'),
    ('cat', 'Gatos'),
    ('rabbit', 'Conejos'),
    ('bird', 'Aves'),
    ('horse', 'Caballos'),
    ('rodent', 'Roedores'),
    ('reptile', 'Reptiles'),
    ('farm', 'Animales de granja'),
    ('other', 'Otros'),
]


class SluggedProfileMixin(models.Model):
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=210, unique=True, blank=True)
    responsible_name = models.CharField(max_length=180)
    description = models.TextField(blank=True, max_length=3000)
    logo = models.ImageField(upload_to='partners/logos/', blank=True, null=True)
    cover = models.ImageField(upload_to='partners/covers/', blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    province = models.CharField(max_length=100)
    locality = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    show_public_address = models.BooleanField(default=False)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    species = models.JSONField(default=list, blank=True)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or 'perfil-vetpaw'
            candidate = base
            index = 2
            model = self.__class__
            while model.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f'{base}-{index}'
                index += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def public_address(self):
        return self.address if self.show_public_address else ''


class BusinessProfile(SluggedProfileMixin):
    TYPE_GROOMING = 'grooming'
    TYPE_PETSHOP = 'petshop'
    TYPE_FOOD = 'food'
    TYPE_DAYCARE = 'daycare'
    TYPE_BOARDING = 'boarding'
    TYPE_WALKER = 'walker'
    TYPE_TRAINING = 'training'
    TYPE_TRANSPORT = 'transport'
    TYPE_PHARMACY = 'pharmacy'
    TYPE_PHOTOGRAPHY = 'photography'
    TYPE_FUNERAL = 'funeral'
    TYPE_OTHER = 'other'
    BUSINESS_TYPE_CHOICES = [
        (TYPE_GROOMING, 'Peluquería canina o felina'),
        (TYPE_PETSHOP, 'Petshop'),
        (TYPE_FOOD, 'Alimentos y accesorios'),
        (TYPE_DAYCARE, 'Guardería'),
        (TYPE_BOARDING, 'Hospedaje'),
        (TYPE_WALKER, 'Paseador'),
        (TYPE_TRAINING, 'Adiestramiento'),
        (TYPE_TRANSPORT, 'Transporte de mascotas'),
        (TYPE_PHARMACY, 'Farmacia veterinaria'),
        (TYPE_PHOTOGRAPHY, 'Fotografía de mascotas'),
        (TYPE_FUNERAL, 'Servicios funerarios'),
        (TYPE_OTHER, 'Otro servicio'),
    ]

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='business_profile',
        limit_choices_to={'role': 'business'},
    )
    business_type = models.CharField(max_length=30, choices=BUSINESS_TYPE_CHOICES)
    services = models.JSONField(default=list, blank=True)
    opening_hours = models.JSONField(default=dict, blank=True)
    home_service = models.BooleanField(default=False)
    delivery = models.BooleanField(default=False)
    online_sales = models.BooleanField(default=False)
    appointment_required = models.BooleanField(default=False)
    is_24h = models.BooleanField(default=False)
    payment_methods = models.JSONField(default=list, blank=True)
    price_range = models.CharField(max_length=80, blank=True)
    promotions = models.TextField(blank=True, max_length=1200)
    tax_id = models.CharField(max_length=30, blank=True)
    legal_name = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['business_type', 'is_active']),
            models.Index(fields=['province', 'locality']),
        ]

    def __str__(self):
        return f'{self.name} — {self.get_business_type_display()}'


class ShelterProfile(SluggedProfileMixin):
    TYPE_SHELTER = 'shelter'
    TYPE_ASSOCIATION = 'association'
    TYPE_RESCUE = 'rescue'
    TYPE_FOSTER = 'foster'
    TYPE_INDEPENDENT = 'independent'
    TYPE_SANCTUARY = 'sanctuary'
    TYPE_OTHER = 'other'
    SHELTER_TYPE_CHOICES = [
        (TYPE_SHELTER, 'Refugio'),
        (TYPE_ASSOCIATION, 'Asociación protectora'),
        (TYPE_RESCUE, 'Organización de rescate'),
        (TYPE_FOSTER, 'Hogar de tránsito'),
        (TYPE_INDEPENDENT, 'Rescatista independiente'),
        (TYPE_SANCTUARY, 'Santuario'),
        (TYPE_OTHER, 'Otro'),
    ]

    CAPACITY_AVAILABLE = 'available'
    CAPACITY_LIMITED = 'limited'
    CAPACITY_FULL = 'full'
    CAPACITY_EMERGENCY = 'emergency'
    CAPACITY_CHOICES = [
        (CAPACITY_AVAILABLE, 'Puede recibir animales'),
        (CAPACITY_LIMITED, 'Cupos limitados'),
        (CAPACITY_FULL, 'Capacidad completa'),
        (CAPACITY_EMERGENCY, 'Solo casos urgentes'),
    ]

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shelter_profile',
        limit_choices_to={'role': 'shelter'},
    )
    shelter_type = models.CharField(max_length=30, choices=SHELTER_TYPE_CHOICES)
    founded_year = models.PositiveSmallIntegerField(null=True, blank=True)
    work_area = models.CharField(max_length=255, blank=True)
    activities = models.JSONField(default=list, blank=True)
    capacity_status = models.CharField(max_length=20, choices=CAPACITY_CHOICES, default=CAPACITY_LIMITED)
    capacity_max = models.PositiveIntegerField(null=True, blank=True)
    current_animals = models.PositiveIntegerField(null=True, blank=True)
    accepting_animals = models.BooleanField(default=False)
    adoption_requirements = models.TextField(blank=True, max_length=2500)
    adoption_area = models.CharField(max_length=255, blank=True)
    adoption_interview = models.BooleanField(default=True)
    adoption_follow_up = models.BooleanField(default=True)
    adoption_castration_commitment = models.BooleanField(default=True)
    adoption_safe_home_required = models.BooleanField(default=True)
    adoption_outside_province = models.BooleanField(default=False)
    needs_volunteers = models.BooleanField(default=False)
    needs_foster_homes = models.BooleanField(default=False)
    accepts_donations = models.BooleanField(default=False)
    accepts_food = models.BooleanField(default=False)
    accepts_medicine = models.BooleanField(default=False)
    needs_transport = models.BooleanField(default=False)
    needs_vet_help = models.BooleanField(default=False)
    needs_sharing = models.BooleanField(default=True)
    donation_alias = models.CharField(max_length=120, blank=True)
    donation_cbu = models.CharField(max_length=80, blank=True)
    donation_needs = models.TextField(blank=True, max_length=1800)
    legal_status = models.CharField(max_length=180, blank=True)
    tax_id = models.CharField(max_length=30, blank=True)
    registration_number = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['shelter_type', 'is_active']),
            models.Index(fields=['province', 'locality']),
            models.Index(fields=['capacity_status', 'accepting_animals']),
        ]

    def __str__(self):
        return f'{self.name} — {self.get_shelter_type_display()}'
