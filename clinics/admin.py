from django.contrib import admin
from .models import Clinic, ClinicCampaign, ClinicMembership, ClinicPetAccess

@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ['name', 'locality', 'province', 'is_active', 'is_24h']

@admin.register(ClinicMembership)
class ClinicMembershipAdmin(admin.ModelAdmin):
    list_display = ['owner', 'clinic', 'status', 'joined_at']

@admin.register(ClinicPetAccess)
class ClinicPetAccessAdmin(admin.ModelAdmin):
    list_display = ['clinic', 'pet', 'last_appointment', 'granted_at']

@admin.register(ClinicCampaign)
class ClinicCampaignAdmin(admin.ModelAdmin):
    list_display = ['title', 'clinic', 'campaign_type', 'starts_at', 'is_active', 'allow_booking']
    list_filter = ['campaign_type', 'is_active', 'allow_booking']
    search_fields = ['title', 'clinic__name', 'location']
