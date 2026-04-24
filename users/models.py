from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    ROLE_CHOICES = [
        ('owner', 'Dueño de mascota'),
        ('vet', 'Veterinario/a'),
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
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def is_owner(self):
        return self.role == 'owner'

    @property
    def is_vet(self):
        return self.role == 'vet'