from django.db import models
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

    photo = cloudinary.models.CloudinaryField('image')
    description = models.TextField()
    contact_type = models.CharField(max_length=20, choices=CONTACT_CHOICES)
    contact_value = models.CharField(max_length=150)
    report_type = models.CharField(max_length=10, choices=REPORT_TYPE_CHOICES, default='found')
    province = models.CharField(max_length=100, blank=True, default='')
    locality = models.CharField(max_length=100, blank=True, default='')
    report_count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(default=expiry_default)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Mascota perdida — {self.created_at.strftime('%d/%m/%Y')}"

    @property
    def is_active(self):
        return timezone.now() < self.expires_at