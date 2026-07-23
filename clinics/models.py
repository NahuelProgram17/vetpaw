from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from users.models import User


class Clinic(models.Model):
    latitude  = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='clinic_profile',
        null=True,
        blank=True,
        limit_choices_to={'role': 'clinic'}
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)
    address = models.CharField(max_length=255)
    show_public_address = models.BooleanField(default=True)
    province = models.CharField(max_length=100)
    locality = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to='clinics/', blank=True, null=True)
    cover = models.ImageField(upload_to='clinics/covers/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_24h = models.BooleanField(default=False)
    services = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} — {self.locality}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Clinic.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        if self.locality and (self.latitude is None or self.longitude is None):
            from clinics.geocoding import get_coordinates
            lat, lon = get_coordinates(self.locality, self.province)
            self.latitude = lat
            self.longitude = lon

        super().save(*args, **kwargs)


class ClinicMembership(models.Model):
    STATUS_CHOICES = [
        ('active', 'Activo'),
        ('left', 'Se dio de baja'),
    ]

    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='memberships'
    )
    clinic = models.ForeignKey(
        Clinic, on_delete=models.CASCADE, related_name='members'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    leave_reason = models.TextField(blank=True)
    leave_rating = models.IntegerField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('owner', 'clinic')

    def __str__(self):
        return f"{self.owner.username} @ {self.clinic.name}"


class ClinicPhoto(models.Model):
    clinic = models.ForeignKey(
        Clinic, on_delete=models.CASCADE, related_name='photos'
    )
    image = models.ImageField(upload_to='clinic_photos/')
    caption = models.CharField(max_length=100, blank=True)
    order = models.PositiveSmallIntegerField(default=0)  # para ordenar las fotos
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.clinic.name} — foto {self.id}"
    
class ClinicSchedule(models.Model):
    DAYS = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]

    INTERVAL_CHOICES = [
        (0,  'Sin intervalo'),
        (10, '10 minutos'),
        (15, '15 minutos'),
        (20, '20 minutos'),
    ]

    clinic = models.OneToOneField(
        Clinic, on_delete=models.CASCADE, related_name='schedule'
    )
    # Días que atiende — lista de enteros ej: [0,1,2,3,4] = lunes a viernes
    working_days = models.JSONField(default=list)
    # Horarios por día — dict ej: {"0": {"open": "08:30", "close": "17:30"}, "5": {"open": "09:00", "close": "13:00"}}
    day_hours = models.JSONField(default=dict)
    # Duración en minutos por tipo de turno
    duration_control = models.PositiveSmallIntegerField(default=30)
    duration_vaccine  = models.PositiveSmallIntegerField(default=20)
    duration_surgery  = models.PositiveSmallIntegerField(default=90)
    duration_other    = models.PositiveSmallIntegerField(default=30)
    # Intervalo entre turnos
    interval_minutes = models.PositiveSmallIntegerField(default=10, choices=[(0,'Sin intervalo'),(10,'10 min'),(15,'15 min'),(20,'20 min')])
    # Límite de cancelación en horas
    cancel_limit_hours = models.PositiveSmallIntegerField(default=4)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_duration(self, appointment_type):
        return {
            'control': self.duration_control,
            'vaccine': self.duration_vaccine,
            'surgery': self.duration_surgery,
            'other':   self.duration_other,
        }.get(appointment_type, 30)

    def __str__(self):
        return f"Agenda de {self.clinic.name}"
    
class ClinicPetAccess(models.Model):
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name='pet_accesses'
    )
    pet = models.ForeignKey(
        'pets.Pet',
        on_delete=models.CASCADE,
        related_name='clinic_accesses'
    )
    last_appointment = models.DateTimeField()
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('clinic', 'pet')

    @property
    def is_active(self):
        from django.utils import timezone
        from datetime import timedelta
        return (timezone.now() - self.last_appointment) < timedelta(days=270)

    def __str__(self):
        status = 'activo' if self.is_active else 'expirado'
        return f"{self.clinic.name} → {self.pet.name} ({status})"

class ClinicCampaign(models.Model):
    TYPE_VACCINATION = 'vaccination'
    TYPE_CASTRATION = 'castration'
    TYPE_CHECKUP = 'checkup'
    TYPE_EVENT = 'event'
    TYPE_GUARD = 'guard'
    TYPE_OTHER = 'other'
    TYPE_CHOICES = [
        (TYPE_VACCINATION, 'Campaña de vacunación'),
        (TYPE_CASTRATION, 'Campaña de castración'),
        (TYPE_CHECKUP, 'Jornada de controles'),
        (TYPE_EVENT, 'Evento veterinario'),
        (TYPE_GUARD, 'Guardia especial'),
        (TYPE_OTHER, 'Otra actividad'),
    ]

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name='community_campaigns',
    )
    campaign_type = models.CharField(max_length=24, choices=TYPE_CHOICES, default=TYPE_OTHER)
    title = models.CharField(max_length=180)
    description = models.TextField(max_length=3000)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    species = models.JSONField(default=list, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_free = models.BooleanField(default=False)
    image = models.ImageField(upload_to='clinics/campaigns/', blank=True, null=True)
    allow_booking = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['starts_at']
        indexes = [
            models.Index(fields=['clinic', 'is_active', 'starts_at'], name='clinic_campaign_active_idx'),
            models.Index(fields=['campaign_type', 'starts_at'], name='clinic_campaign_type_idx'),
        ]

    def clean(self):
        if self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({'ends_at': 'La fecha de finalización debe ser posterior al inicio.'})
        if self.capacity == 0:
            raise ValidationError({'capacity': 'La capacidad debe ser mayor a cero.'})

    @property
    def appointments_count(self):
        return self.appointments.exclude(status='cancelled').count()

    @property
    def remaining_slots(self):
        if self.capacity is None:
            return None
        return max(0, self.capacity - self.appointments_count)

    def __str__(self):
        return f'{self.clinic.name} — {self.title}'

