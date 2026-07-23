from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AccountSanction, User


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


@admin.register(AccountSanction)
class AccountSanctionAdmin(admin.ModelAdmin):
    list_display = ['user', 'kind', 'effective_status_display', 'starts_at', 'ends_at', 'applied_by', 'revoked_at']
    list_filter = ['kind', 'revoked_at', 'starts_at', 'ends_at']
    search_fields = ['user__username', 'user__email', 'reason', 'internal_note']
    readonly_fields = ['created_at', 'updated_at']

    @admin.display(description='Estado')
    def effective_status_display(self, obj):
        return obj.effective_status
