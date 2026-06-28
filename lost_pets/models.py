from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import cloudinary.models


def expiry_default():
    return timezone.now() + timedelta(days=10)


class LostPet(models.Model):
    CONTACT_CHOICES = [
        ('phone', 'Celular'),
        ('home_phone', 'Teléfono de casa'),
        ('email', 'Email'),
    ]
    REPORT_TYPE_CHOICES = [
        ('found', 'Encontré una mascota'),
        ('lost', 'Perdí mi mascota'),
    ]
    SPECIES_CHOICES = [
        ('dog', 'Perro'),
        ('cat', 'Gato'),
        ('bird', 'Pájaro'),
        ('rabbit', 'Conejo'),
        ('fish', 'Pez'),
        ('other', 'Otro'),
    ]

    photo = cloudinary.models.CloudinaryField('image')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='lost_pets'
    )
    # Datos de la mascota (todos opcionales para no romper reportes viejos)
    pet_name = models.CharField(max_length=80, blank=True, default='')
    species = models.CharField(max_length=20, choices=SPECIES_CHOICES, blank=True, default='')
    breed = models.CharField(max_length=80, blank=True, default='')

    description = models.TextField()
    contact_type = models.CharField(max_length=20, choices=CONTACT_CHOICES)
    contact_value = models.CharField(max_length=150)
    report_type = models.CharField(max_length=10, choices=REPORT_TYPE_CHOICES, default='found')
    province = models.CharField(max_length=100, blank=True, default='')
    locality = models.CharField(max_length=100, blank=True, default='')

    # Fecha del incidente (cuándo se perdió/encontró, distinta de created_at)
    incident_date = models.DateField(null=True, blank=True)

    report_count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(default=expiry_default)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        label = self.pet_name or f"Mascota perdida — {self.created_at.strftime('%d/%m/%Y')}"
        return label

    @property
    def is_active(self):
        return timezone.now() < self.expires_at
