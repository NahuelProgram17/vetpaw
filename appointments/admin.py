from django.contrib import admin
from .models import Appointment, Visit, Review

admin.site.register(Appointment)
admin.site.register(Visit)
admin.site.register(Review)