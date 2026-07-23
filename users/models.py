from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    latitude  = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    email = models.EmailField(unique=True)

    ROLE_CHOICES = [
        ('owner', 'Dueño de mascota'),
        ('clinic', 'Veterinario/a'),
        ('business', 'Negocio de mascotas'),
        ('shelter', 'Refugio o rescatista'),
    ]

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='owner'
    )
    phone = models.CharField(max_length=20, blank=True)
    province = models.CharField(max_length=100, blank=True)
    locality = models.CharField(max_length=100, blank=True)
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True
    )
    bio = models.TextField(blank=True)
    GENDER_CHOICES = [
        ('male', 'Masculino'),
        ('female', 'Femenino'),
        ('other', 'Prefiero no decir'),
    ]
    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        default='other',
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def is_owner(self):
        return self.role == 'owner'

    @property
    def is_clinic(self):
        return self.role == 'clinic'

    @property
    def is_business(self):
        return self.role == 'business'

    @property
    def is_shelter(self):
        return self.role == 'shelter'


class AccountSanction(models.Model):
    KIND_SUSPENSION = 'suspension'
    KIND_PERMANENT_BAN = 'permanent_ban'
    KIND_CHOICES = [
        (KIND_SUSPENSION, 'Suspensión temporal'),
        (KIND_PERMANENT_BAN, 'Expulsión permanente'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_EXPIRED = 'expired'
    STATUS_REVOKED = 'revoked'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='account_sanctions',
    )
    kind = models.CharField(max_length=24, choices=KIND_CHOICES)
    reason = models.TextField(max_length=1000)
    internal_note = models.TextField(blank=True, max_length=2000)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='account_sanctions_applied',
    )
    source_report_id = models.PositiveBigIntegerField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='account_sanctions_revoked',
    )
    revocation_note = models.TextField(blank=True, max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='users_sanct_user_created_idx'),
            models.Index(fields=['kind', 'revoked_at', 'ends_at'], name='users_sanct_active_idx'),
        ]

    def clean(self):
        super().clean()
        if self.kind == self.KIND_SUSPENSION and not self.ends_at:
            raise ValidationError({'ends_at': 'La suspensión temporal necesita una fecha de finalización.'})
        if self.kind == self.KIND_PERMANENT_BAN and self.ends_at:
            raise ValidationError({'ends_at': 'Una expulsión permanente no debe tener fecha de finalización.'})
        if self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({'ends_at': 'La fecha de finalización debe ser posterior al inicio.'})

    @property
    def effective_status(self):
        if self.revoked_at:
            return self.STATUS_REVOKED
        if self.kind == self.KIND_SUSPENSION and self.ends_at and self.ends_at <= timezone.now():
            return self.STATUS_EXPIRED
        return self.STATUS_ACTIVE

    @property
    def is_active(self):
        return self.effective_status == self.STATUS_ACTIVE

    def __str__(self):
        return f'{self.get_kind_display()} para {self.user} ({self.effective_status})'
