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
    source_abuse_signal = models.ForeignKey(
        'AbuseSignal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='account_sanctions',
    )
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

class AbuseAction(models.Model):
    ACTION_POST = 'post'
    ACTION_COMMENT = 'comment'
    ACTION_MESSAGE = 'message'
    ACTION_FOLLOW = 'follow'
    ACTION_REPORT = 'report'
    ACTION_REGISTRATION = 'registration'
    ACTION_CHOICES = [
        (ACTION_POST, 'Publicación'),
        (ACTION_COMMENT, 'Comentario'),
        (ACTION_MESSAGE, 'Mensaje'),
        (ACTION_FOLLOW, 'Seguimiento'),
        (ACTION_REPORT, 'Reporte'),
        (ACTION_REGISTRATION, 'Registro'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='abuse_actions',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    action_type = models.CharField(max_length=24, choices=ACTION_CHOICES)
    fingerprint = models.CharField(max_length=64, blank=True)
    link_fingerprint = models.CharField(max_length=64, blank=True)
    target_key = models.CharField(max_length=120, blank=True)
    content_excerpt = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'action_type', '-created_at'], name='users_abact_user_action_idx'),
            models.Index(fields=['ip_address', 'action_type', '-created_at'], name='users_abact_ip_action_idx'),
            models.Index(fields=['fingerprint', '-created_at'], name='users_abact_fingerprint_idx'),
            models.Index(fields=['link_fingerprint', '-created_at'], name='users_abact_link_idx'),
        ]

    def __str__(self):
        actor = self.user.username if self.user_id else (self.ip_address or 'anónimo')
        return f'{self.get_action_type_display()} — {actor}'


class AbuseSignal(models.Model):
    CATEGORY_RATE_LIMIT = 'rate_limit'
    CATEGORY_DUPLICATE_CONTENT = 'duplicate_content'
    CATEGORY_REPEATED_LINK = 'repeated_link'
    CATEGORY_MASS_FOLLOW = 'mass_follow'
    CATEGORY_FALSE_REPORT = 'false_report'
    CATEGORY_REGISTRATION_BURST = 'registration_burst'
    CATEGORY_ACCOUNT_RISK = 'account_risk'
    CATEGORY_CHOICES = [
        (CATEGORY_RATE_LIMIT, 'Límite de acciones superado'),
        (CATEGORY_DUPLICATE_CONTENT, 'Contenido repetido'),
        (CATEGORY_REPEATED_LINK, 'Enlace repetido'),
        (CATEGORY_MASS_FOLLOW, 'Seguimientos masivos'),
        (CATEGORY_FALSE_REPORT, 'Reportes descartados repetidos'),
        (CATEGORY_REGISTRATION_BURST, 'Registros acelerados desde el mismo origen'),
        (CATEGORY_ACCOUNT_RISK, 'Comportamiento de cuenta sospechoso'),
    ]

    SEVERITY_INFO = 'info'
    SEVERITY_WARNING = 'warning'
    SEVERITY_HIGH = 'high'
    SEVERITY_CHOICES = [
        (SEVERITY_INFO, 'Informativa'),
        (SEVERITY_WARNING, 'En observación'),
        (SEVERITY_HIGH, 'Riesgo alto'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_REVIEWED = 'reviewed'
    STATUS_DISMISSED = 'dismissed'
    STATUS_ACTIONED = 'actioned'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_REVIEWED, 'Revisada'),
        (STATUS_DISMISSED, 'Descartada'),
        (STATUS_ACTIONED, 'Se tomó una medida'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='abuse_signals',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES)
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default=SEVERITY_WARNING)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    action_key = models.CharField(max_length=80, blank=True)
    fingerprint = models.CharField(max_length=64, blank=True)
    content_excerpt = models.CharField(max_length=300, blank=True)
    details = models.JSONField(default=dict, blank=True)
    occurrences = models.PositiveIntegerField(default=1)
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='abuse_signals_reviewed',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    moderator_notes = models.TextField(blank=True, max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['status', '-last_seen_at']
        indexes = [
            models.Index(fields=['status', 'severity', '-last_seen_at'], name='users_absig_status_sev_idx'),
            models.Index(fields=['user', 'status', '-last_seen_at'], name='users_absig_user_status_idx'),
            models.Index(fields=['ip_address', 'status', '-last_seen_at'], name='users_absig_ip_status_idx'),
            models.Index(fields=['category', '-last_seen_at'], name='users_absig_category_idx'),
        ]

    def __str__(self):
        actor = self.user.username if self.user_id else (self.ip_address or 'origen desconocido')
        return f'{self.get_category_display()} — {actor} ({self.occurrences})'

