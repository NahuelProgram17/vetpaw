from django.db import models
from users.models import User
from clinics.models import Clinic
from .storage import ClinicalFileCloudinaryStorage


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
    
    FEEDING_CHOICES = [
        ('balanced', 'Balanceada'),
        ('homemade', 'Casera'),
        ('mixed', 'Mixta'),
    ]

    HABITAT_CHOICES = [
        ('apartment', 'Departamento'),
        ('house', 'Casa con patio'),
        ('field', 'Campo'),
    ]

    TEMPERAMENT_CHOICES = [
        ('friendly', 'Amigable'),
        ('shy', 'Tímido'),
        ('nervous', 'Nervioso'),
        ('protective', 'Protector'),
        ('playful', 'Juguetón'),
        ('sleepy', 'Dormilón'),
        ('eater', 'Comilón'),
        ('intimidating', 'Intimidante'),
    ]

    feeding = models.CharField(max_length=20, choices=FEEDING_CHOICES, blank=True)
    habitat = models.CharField(max_length=20, choices=HABITAT_CHOICES, blank=True)
    lives_with_animals = models.BooleanField(default=False)
    temperament = models.CharField(max_length=20, choices=TEMPERAMENT_CHOICES, blank=True, default='')

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
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vaccines'
    )
    name = models.CharField(max_length=100)
    date_applied = models.DateField()
    next_dose = models.DateField(null=True, blank=True)
    batch = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    vet_first_name = models.CharField(max_length=100, blank=True)
    vet_last_name = models.CharField(max_length=100, blank=True)
    vet_license = models.CharField(max_length=50, blank=True)
    vet_clinic_name = models.CharField(max_length=255, blank=True)
    reminder_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ['-date_applied']

    def __str__(self):
        return f"{self.name} — {self.pet.name}"
    
    
class ClinicalPhoto(models.Model):
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='clinical_photos')
    clinic = models.ForeignKey('clinics.Clinic', on_delete=models.SET_NULL, null=True, blank=True, related_name='clinical_photos')
    # Se mantiene el nombre del campo `image` para no romper la API existente,
    # pero ahora permite imágenes y documentos PDF.
    image = models.FileField(upload_to='clinical_files/', storage=ClinicalFileCloudinaryStorage())
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    @property
    def is_pdf(self):
        return bool(self.image and self.image.name.lower().endswith('.pdf'))

    @property
    def file_type(self):
        return 'pdf' if self.is_pdf else 'image'

    def __str__(self):
        tipo = 'PDF clínico' if self.is_pdf else 'foto clínica'
        return f"{self.pet.name} — {self.caption or tipo}"


class Treatment(models.Model):
    TREATMENT_TYPES = [
        ('deworming', 'Desparasitación'),
        ('flea', 'Pastilla antipulgas'),
        ('pipette', 'Pipeta'),
    ]
    pet = models.ForeignKey(
        Pet,
        on_delete=models.CASCADE,
        related_name='treatments'
    )
    treatment_type = models.CharField(max_length=20, choices=TREATMENT_TYPES)
    date_applied = models.DateField()
    next_dose = models.DateField(null=True, blank=True)
    product = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_applied']

    def __str__(self):
        return f"{self.get_treatment_type_display()} — {self.pet.name} ({self.date_applied})"
