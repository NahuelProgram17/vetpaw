from django.contrib import admin
from django.utils import timezone

from .models import BlockedUser, Comment, CommunityNotification, PetFollow, PetSocialProfile, Post, PushSubscription, Reaction, Report, SavedPost


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'actor_name', 'post_type', 'moderation_status', 'locality', 'created_at')
    list_filter = ('post_type', 'moderation_status', 'is_public', 'province')
    search_fields = ('text', 'pet__name', 'clinic__name', 'created_by__username')
    actions = ('publish_posts', 'hide_posts', 'remove_posts')

    @admin.display(description='Autor')
    def actor_name(self, obj):
        return obj.pet.name if obj.pet_id else obj.clinic.name if obj.clinic_id else obj.created_by

    @admin.action(description='Publicar seleccionadas')
    def publish_posts(self, request, queryset):
        queryset.update(moderation_status=Post.STATUS_PUBLISHED)

    @admin.action(description='Ocultar seleccionadas')
    def hide_posts(self, request, queryset):
        queryset.update(moderation_status=Post.STATUS_HIDDEN)

    @admin.action(description='Eliminar por moderación')
    def remove_posts(self, request, queryset):
        queryset.update(moderation_status=Post.STATUS_REMOVED)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'author', 'post', 'moderation_status', 'created_at')
    list_filter = ('moderation_status', 'created_at')
    search_fields = ('text', 'author__username')


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'reporter', 'reason', 'status', 'created_at', 'reviewed_by')
    list_filter = ('status', 'reason', 'created_at')
    search_fields = ('details', 'reporter__username', 'post__text', 'comment__text')
    readonly_fields = ('created_at',)
    actions = ('mark_dismissed', 'mark_actioned')

    @admin.action(description='Marcar como descartados')
    def mark_dismissed(self, request, queryset):
        queryset.update(status=Report.STATUS_DISMISSED, reviewed_by=request.user, reviewed_at=timezone.now())

    @admin.action(description='Marcar con medida aplicada')
    def mark_actioned(self, request, queryset):
        queryset.update(status=Report.STATUS_ACTIONED, reviewed_by=request.user, reviewed_at=timezone.now())


admin.site.register(PetSocialProfile)
admin.site.register(Reaction)
admin.site.register(PetFollow)
admin.site.register(SavedPost)
admin.site.register(BlockedUser)


@admin.register(CommunityNotification)
class CommunityNotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipient', 'actor', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('recipient__username', 'actor__username', 'extra_text')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'device_name', 'is_active', 'failure_count',
        'last_success_at', 'updated_at',
    )
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('user__username', 'user__email', 'device_name')
    readonly_fields = (
        'endpoint', 'p256dh', 'auth', 'created_at', 'updated_at',
        'last_success_at', 'last_failure_at',
    )
