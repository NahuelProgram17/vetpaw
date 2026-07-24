from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AbuseAction, AbuseSignal, AccountSanction, User


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


@admin.register(AbuseSignal)
class AbuseSignalAdmin(admin.ModelAdmin):
    list_display = ['category', 'user', 'ip_address', 'severity', 'status', 'occurrences', 'last_seen_at']
    list_filter = ['category', 'severity', 'status', 'last_seen_at']
    search_fields = ['user__username', 'user__email', 'ip_address', 'content_excerpt', 'action_key']
    readonly_fields = ['first_seen_at', 'last_seen_at', 'created_at', 'updated_at']


@admin.register(AbuseAction)
class AbuseActionAdmin(admin.ModelAdmin):
    list_display = ['action_type', 'user', 'ip_address', 'target_key', 'created_at']
    list_filter = ['action_type', 'created_at']
    search_fields = ['user__username', 'user__email', 'ip_address', 'target_key', 'content_excerpt']
    readonly_fields = ['created_at']
