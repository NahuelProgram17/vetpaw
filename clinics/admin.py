from django.contrib import admin
from django.contrib import admin
from .models import Clinic, ClinicMembership

@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ['name', 'locality', 'province', 'is_active', 'is_24h']

@admin.register(ClinicMembership)
class ClinicMembershipAdmin(admin.ModelAdmin):
    list_display = ['owner', 'clinic', 'status', 'joined_at']