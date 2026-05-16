from django.urls import path
from . import views

urlpatterns = [
    path('lost-pets/', views.list_lost_pets, name='list_lost_pets'),
    path('lost-pets/create/', views.create_lost_pet, name='create_lost_pet'),
    path('lost-pets/<int:pk>/report/', views.report_lost_pet, name='report_lost_pet'),
]