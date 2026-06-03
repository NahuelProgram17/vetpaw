from django.contrib import admin
from .models import Pet, Vaccine, ClinicalPhoto

@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ['name', 'species', 'owner', 'created_at']

@admin.register(Vaccine)
class VaccineAdmin(admin.ModelAdmin):
    list_display = ['name', 'pet', 'clinic', 'date_applied']

@admin.register(ClinicalPhoto)
class ClinicalPhotoAdmin(admin.ModelAdmin):
    list_display = ['pet', 'clinic', 'caption', 'uploaded_at']