from django.contrib import admin
from .models import Pet, Vaccine, ClinicalPhoto, BirthdayCelebration

@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ['name', 'species', 'owner', 'created_at']

@admin.register(Vaccine)
class VaccineAdmin(admin.ModelAdmin):
    list_display = ['name', 'pet', 'clinic', 'date_applied']

@admin.register(ClinicalPhoto)
class ClinicalPhotoAdmin(admin.ModelAdmin):
    list_display = ['pet', 'clinic', 'caption', 'uploaded_at']

@admin.register(BirthdayCelebration)
class BirthdayCelebrationAdmin(admin.ModelAdmin):
    list_display = ['pet', 'year', 'age', 'birthday_date', 'opened_at', 'read_at']
    list_filter = ['year', 'opened_at', 'read_at']
    search_fields = ['pet__name', 'pet__owner__username']
