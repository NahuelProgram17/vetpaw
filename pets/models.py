from django.db import models
from users.models import User
from clinics.models import Clinic


class Pet(models.Model):

    SPECIES_CHOICES = [
        ('dog', 'Perro'),
        ('cat', 'Gato'),
        ('rabbit', 'Conejo'),
        ('bird', 'Ave'),
        ('hamster', 'Hamster'),
        ('reptile', 'Reptil'),
        ('fish', 'Pez'),
        ('other', 'Otro'),
    ]

    SEX_CHOICES = [
        ('male', 'Macho'),
        ('female', 'Hembra'),
    ]

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='pets'
    )
    name = models.CharField(max_length=100)
    species = models.CharField(max_length=20, choices=SPECIES_CHOICES)
    breed = models.CharField(max_length=100, blank=True)
    sex = models.CharField(max_length=10, choices=SEX_CHOICES)
    birth_date = models.DateField(null=True, blank=True)
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    color = models.CharField(max_length=100, blank=True)
    microchip = models.CharField(max_length=50, blank=True)
    photo = models.ImageField(
        upload_to='pets/',
        blank=True,
        null=True
    )
    allergies = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_neutered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_species_display()}) — {self.owner.username}"


class Vaccine(models.Model):
    pet = models.ForeignKey(
        Pet,
        on_delete=models.CASCADE,
        related_name='vaccines'
    )
    name = models.CharField(max_length=100)
    date_applied = models.DateField()
    next_dose = models.DateField(null=True, blank=True)
    batch = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} — {self.pet.name}"