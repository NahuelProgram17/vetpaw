from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'is_approved', 'is_active', 'email_verified']
    list_filter = ['role', 'is_active', 'email_verified', 'is_approved']
    actions = ['aprobar_clinicas', 'desaprobar_clinicas']
    fieldsets = UserAdmin.fieldsets + (
        ('VetPaw', {'fields': ('role', 'phone', 'province', 'locality', 'bio', 'avatar', 'email_verified', 'is_approved')}),
    )

    def aprobar_clinicas(self, request, queryset):
        queryset.filter(role='clinic').update(is_approved=True)
        self.message_user(request, "Clínicas aprobadas correctamente.")
    aprobar_clinicas.short_description = "✅ Aprobar clínicas seleccionadas"

    def desaprobar_clinicas(self, request, queryset):
        queryset.filter(role='clinic').update(is_approved=False)
        self.message_user(request, "Clínicas desaprobadas.")
    desaprobar_clinicas.short_description = "❌ Desaprobar clínicas seleccionadas"