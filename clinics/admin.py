from django.contrib import admin

from .models import Clinic, ClinicCampaign, ClinicMembership, ClinicPetAccess


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'locality', 'province', 'is_active', 'is_24h',
        'plan_status', 'plan_ends_at', 'trial_used',
    ]
    list_filter = ['is_active', 'is_24h', 'plan_status', 'trial_used']
    search_fields = ['name', 'owner__username', 'owner__email', 'locality', 'province']
    readonly_fields = ['created_at', 'plan_started_at']


@admin.register(ClinicMembership)
class ClinicMembershipAdmin(admin.ModelAdmin):
    list_display = ['owner', 'clinic', 'status', 'joined_at']


@admin.register(ClinicPetAccess)
class ClinicPetAccessAdmin(admin.ModelAdmin):
    list_display = ['clinic', 'pet', 'last_appointment', 'granted_at']


@admin.register(ClinicCampaign)
class ClinicCampaignAdmin(admin.ModelAdmin):
    list_display = ['title', 'clinic', 'campaign_type', 'starts_at', 'is_active']
    list_filter = ['campaign_type', 'is_active']
    search_fields = ['title', 'clinic__name', 'location']
