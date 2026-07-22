from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'is_approved', 'is_active']
    list_filter = ['role', 'is_active', 'is_approved']
    actions = ['approve_professional_profiles', 'unapprove_professional_profiles']
    fieldsets = UserAdmin.fieldsets + (
        ('VetPaw', {'fields': ('role', 'phone', 'province', 'locality', 'bio', 'avatar', 'is_approved')}),
    )

    @admin.action(description='✅ Aprobar perfiles profesionales seleccionados')
    def approve_professional_profiles(self, request, queryset):
        updated = queryset.filter(role__in=('clinic', 'business', 'shelter')).update(is_approved=True)
        self.message_user(request, f'{updated} perfiles profesionales aprobados correctamente.')

    @admin.action(description='❌ Dejar perfiles profesionales pendientes')
    def unapprove_professional_profiles(self, request, queryset):
        updated = queryset.filter(role__in=('clinic', 'business', 'shelter')).update(is_approved=False)
        self.message_user(request, f'{updated} perfiles profesionales quedaron pendientes.')
