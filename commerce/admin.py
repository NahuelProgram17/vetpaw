from django.contrib import admin

from .models import (
    BusinessAccess,
    BusinessFavorite,
    BusinessInquiry,
    BusinessProfileView,
    BusinessReservation,
    CatalogItem,
    Promotion,
)


@admin.register(CatalogItem)
class CatalogItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'business', 'item_type', 'category', 'is_active', 'requires_booking', 'views_count')
    list_filter = ('item_type', 'category', 'is_active', 'requires_booking')
    search_fields = ('title', 'business__name', 'description')


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('title', 'business', 'starts_at', 'ends_at', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title', 'business__name')


@admin.register(BusinessReservation)
class BusinessReservationAdmin(admin.ModelAdmin):
    list_display = ('business', 'catalog_item', 'user', 'pet', 'date', 'start_time', 'status')
    list_filter = ('status', 'date')


admin.site.register(BusinessAccess)
admin.site.register(BusinessFavorite)
admin.site.register(BusinessInquiry)
admin.site.register(BusinessProfileView)
