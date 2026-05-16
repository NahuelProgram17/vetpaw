from django.contrib import admin
from .models import LostPet

@admin.register(LostPet)
class LostPetAdmin(admin.ModelAdmin):
    list_display = ['id', 'contact_value', 'report_count', 'expires_at', 'created_at']
    list_filter = ['contact_type']