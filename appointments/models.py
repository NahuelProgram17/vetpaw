from django.db import models
from users.models import User
from pets.models import Pet
from clinics.models import Clinic


class Visit(models.Model):
    """Visita cargada por el veterinario despues de la consulta"""

    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='visits')
    vet = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='visits_as_vet')
    clinic = models.ForeignKey(Clinic, on_delete=models.SET_NULL, null=True, related_name='visits')
    date = models.DateTimeField()
    reason = models.CharField(max_length=255)
    diagnosis = models.TextField(blank=True)
    treatment = models.TextField(blank=True)
    observations = models.TextField(blank=True)
    next_visit = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.pet.name} — {self.reason} ({self.date})"


class Appointment(models.Model):
    """Turno solicitado por el dueño de la mascota"""

    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado'),
        ('done', 'Realizado'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appointments')
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='appointments')
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='appointments')
    requested_date = models.DateTimeField()
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    vet_notes = models.TextField(blank=True)
    seen_by_owner = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_date']

    def __str__(self):
        return f"{self.pet.name} @ {self.clinic.name} — {self.requested_date}"