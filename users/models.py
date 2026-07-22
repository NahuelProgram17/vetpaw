from django.contrib.auth.models import AbstractUser
from django.db import models


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
