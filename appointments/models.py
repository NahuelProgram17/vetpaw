from django.db import models
from users.models import User
from pets.models import Pet
from clinics.models import Clinic


class Visit(models.Model):
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='visits')
    clinic = models.ForeignKey(Clinic, on_delete=models.SET_NULL, null=True, related_name='visits')
    date = models.DateTimeField()
    reason = models.CharField(max_length=255)
    diagnosis = models.TextField(blank=True)
    treatment = models.TextField(blank=True)
    observations = models.TextField(blank=True)
    next_visit = models.DateField(null=True, blank=True)
    vet_first_name = models.CharField(max_length=100)
    vet_last_name = models.CharField(max_length=100)
    vet_license = models.CharField(max_length=50)
    vet_clinic_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.pet.name} — {self.reason} ({self.date})"


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado'),
        ('completed', 'Realizado'),
        ('no_show', 'Ausente'),
    ]

    TYPE_CHOICES = [
        ('control', 'Control general'),
        ('vaccine', 'Vacunación'),
        ('surgery', 'Cirugía'),
        ('other', 'Otro'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appointments', null=True, blank=True)
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='appointments', null=True, blank=True)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='appointments')
    source_post = models.ForeignKey(
        'community.Post',
        on_delete=models.SET_NULL,
        related_name='generated_appointments',
        null=True,
        blank=True,
    )
    source_campaign = models.ForeignKey(
        'clinics.ClinicCampaign',
        on_delete=models.SET_NULL,
        related_name='appointments',
        null=True,
        blank=True,
    )
    requested_date = models.DateTimeField()
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='confirmed')
    appointment_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='control')
    is_external = models.BooleanField(default=False)  # turno cargado manualmente por la clínica
    external_label = models.CharField(max_length=100, blank=True)  # ej: "Turno por teléfono - Juan"
    vet_notes = models.TextField(blank=True)
    seen_by_owner = models.BooleanField(default=True)
    seen_by_clinic = models.BooleanField(default=True)
    reminder_sent = models.BooleanField(default=False)
    consent_shown = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_date']

    def __str__(self):
        return f"{self.pet.name if self.pet else 'Externo'} @ {self.clinic.name} — {self.requested_date}"


class Review(models.Model):
    appointment = models.OneToOneField(
        Appointment, on_delete=models.CASCADE, related_name='review'
    )
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='reviews'
    )
    clinic = models.ForeignKey(
        'clinics.Clinic', on_delete=models.CASCADE, related_name='reviews'
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.owner.username} → {self.clinic.name} ({self.rating}★)"