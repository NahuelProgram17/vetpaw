from django.contrib import admin

from .models import BusinessProfile, ShelterProfile


@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'business_type', 'locality', 'province', 'is_verified', 'is_active')
    list_filter = ('business_type', 'is_verified', 'is_active', 'province')
    search_fields = ('name', 'responsible_name', 'owner__username', 'locality')
    prepopulated_fields = {}


@admin.register(ShelterProfile)
class ShelterProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'shelter_type', 'locality', 'capacity_status', 'is_verified', 'is_active')
    list_filter = ('shelter_type', 'capacity_status', 'is_verified', 'is_active', 'province')
    search_fields = ('name', 'responsible_name', 'owner__username', 'locality')
