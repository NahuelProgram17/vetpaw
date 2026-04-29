from django.db import models
from users.models import User


class Clinic(models.Model):
    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='clinic_profile',
        null=True,
        blank=True,
        limit_choices_to={'role': 'clinic'}
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    address = models.CharField(max_length=255)
    province = models.CharField(max_length=100)
    locality = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    logo = models.ImageField(
        upload_to='clinics/',
        blank=True,
        null=True
    )
    is_active = models.BooleanField(default=True)
    is_24h = models.BooleanField(default=False)
    services = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} — {self.locality}"


class ClinicMembership(models.Model):
    STATUS_CHOICES = [
        ('active', 'Activo'),
        ('left', 'Se dio de baja'),
    ]

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name='members'
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='active'
    )
    leave_reason = models.TextField(blank=True)
    leave_rating = models.IntegerField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('owner', 'clinic')

    def __str__(self):
        return f"{self.owner.username} @ {self.clinic.name}"