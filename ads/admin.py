from django.contrib import admin
from .models import Advertiser


@admin.register(Advertiser)
class AdvertiserAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'order', 'start_date', 'end_date', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
