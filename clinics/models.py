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
    province = models.CharField(max_length=100)
    locality = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to='clinics/', blank=True, null=True)
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