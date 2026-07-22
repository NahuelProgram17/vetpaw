from django.contrib import admin
from .models import AdoptionAnimal,AdoptionPhoto,AdoptionApplication,HelpOffer,AdoptionStatusHistory
class PhotoInline(admin.TabularInline): model=AdoptionPhoto; extra=0
@admin.register(AdoptionAnimal)
class AdoptionAnimalAdmin(admin.ModelAdmin): list_display=('name','shelter','species','status','locality','is_published','created_at'); list_filter=('status','species','province','is_published'); search_fields=('name','shelter__name','locality'); inlines=[PhotoInline]
admin.site.register(AdoptionApplication); admin.site.register(HelpOffer); admin.site.register(AdoptionStatusHistory)
