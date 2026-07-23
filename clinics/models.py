from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from datetime import timedelta
from users.models import User


class Clinic(models.Model):
    PLAN_INACTIVE = 'inactive'
    PLAN_TRIAL = 'trial'
    PLAN_ACTIVE = 'active'
    PLAN_GRACE = 'grace'
    PLAN_EXPIRED = 'expired'
    PLAN_SUSPENDED = 'suspended'
    PLAN_STATUS_CHOICES = [
        (PLAN_INACTIVE, 'Sin plan'),
        (PLAN_TRIAL, 'Mes de prueba gratis'),
        (PLAN_ACTIVE, 'Plan activo'),
        (PLAN_GRACE, 'Período de gracia'),
        (PLAN_EXPIRED, 'Plan vencido'),
        (PLAN_SUSPENDED, 'Plan suspendido'),
    ]

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

    # Suscripción del plan veterinario. Los perfiles y la Comunidad siguen
    # disponibles aunque el plan no esté activo; agenda, turnos y herramientas
    # clínicas se habilitan únicamente con prueba, plan o gracia vigentes.
    plan_status = models.CharField(
        max_length=16,
        choices=PLAN_STATUS_CHOICES,
        default=PLAN_ACTIVE,
    )
    plan_started_at = models.DateTimeField(null=True, blank=True)
    plan_ends_at = models.DateTimeField(null=True, blank=True)
    grace_ends_at = models.DateTimeField(null=True, blank=True)
    trial_used = models.BooleanField(default=False)
    plan_notes = models.CharField(max_length=500, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def effective_plan_status(self):
        now = timezone.now()
        if self.plan_status == self.PLAN_TRIAL:
            return self.PLAN_TRIAL if self.plan_ends_at and self.plan_ends_at >= now else self.PLAN_EXPIRED
        if self.plan_status == self.PLAN_ACTIVE:
            return self.PLAN_ACTIVE if not self.plan_ends_at or self.plan_ends_at >= now else self.PLAN_EXPIRED
        if self.plan_status == self.PLAN_GRACE:
            return self.PLAN_GRACE if self.grace_ends_at and self.grace_ends_at >= now else self.PLAN_EXPIRED
        return self.plan_status

    @property
    def has_active_plan(self):
        return self.effective_plan_status in {
            self.PLAN_TRIAL,
            self.PLAN_ACTIVE,
            self.PLAN_GRACE,
        }

    @property
    def can_use_clinical_tools(self):
        return bool(
            self.is_active
            and self.owner_id
            and self.owner.is_approved
            and self.has_active_plan
        )

    @property
    def can_receive_appointments(self):
        return bool(self.can_use_clinical_tools and hasattr(self, 'schedule'))

    def start_free_trial(self, days=30, notes=''):
        if self.trial_used:
            raise ValidationError({'trial_used': 'Esta veterinaria ya utilizó su mes de prueba gratis.'})
        if self.has_active_plan:
            raise ValidationError({'plan_status': 'La veterinaria ya tiene un plan vigente. La prueba gratis se usa antes del primer abono.'})
        now = timezone.now()
        self.plan_status = self.PLAN_TRIAL
        self.plan_started_at = now
        self.plan_ends_at = now + timedelta(days=max(1, int(days)))
        self.grace_ends_at = None
        self.trial_used = True
        if notes:
            self.plan_notes = notes
        self.save(update_fields=[
            'plan_status', 'plan_started_at', 'plan_ends_at',
            'grace_ends_at', 'trial_used', 'plan_notes',
        ])

    def activate_paid_plan(self, days=30, notes=''):
        now = timezone.now()
        base = self.plan_ends_at if self.plan_ends_at and self.plan_ends_at > now else now
        self.plan_status = self.PLAN_ACTIVE
        self.plan_started_at = self.plan_started_at or now
        # Una cuenta que ya pasó al abono pago no puede solicitar después la prueba inicial.
        self.trial_used = True
        self.plan_ends_at = base + timedelta(days=max(1, int(days)))
        self.grace_ends_at = None
        if notes:
            self.plan_notes = notes
        self.save(update_fields=[
            'plan_status', 'plan_started_at', 'plan_ends_at',
            'grace_ends_at', 'trial_used', 'plan_notes',
        ])

    def grant_grace(self, days=5, notes=''):
        now = timezone.now()
        self.plan_status = self.PLAN_GRACE
        self.grace_ends_at = now + timedelta(days=max(1, int(days)))
        if notes:
            self.plan_notes = notes
        self.save(update_fields=['plan_status', 'grace_ends_at', 'plan_notes'])

    def suspend_plan(self, notes=''):
        self.plan_status = self.PLAN_SUSPENDED
        if notes:
            self.plan_notes = notes
        self.save(update_fields=['plan_status', 'plan_notes'])

    def expire_plan(self, notes=''):
        self.plan_status = self.PLAN_EXPIRED
        if notes:
            self.plan_notes = notes
        self.save(update_fields=['plan_status', 'plan_notes'])

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
    TYPE_OTHER = 'other'
    TYPE_CHOICES = [
        (TYPE_VACCINATION, 'Campaña de vacunación'),
        (TYPE_CASTRATION, 'Campaña de castración'),
        (TYPE_CHECKUP, 'Jornada de controles'),
        (TYPE_EVENT, 'Evento veterinario'),
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
    allow_booking = models.BooleanField(default=False)
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

    def save(self, *args, **kwargs):
        # Las campañas de Comunidad son informativas. La agenda veterinaria
        # se gestiona únicamente desde el módulo pago de turnos de VetPaw.
        self.allow_booking = False
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.clinic.name} — {self.title}'

