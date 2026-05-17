from django.urls import path
from . import views

urlpatterns = [
    path('contact/', views.contacto, name='contacto'),
    path('contact/veterinaria/', views.sumar_veterinaria, name='sumar_veterinaria'),
    path('contact/anunciante/', views.anunciante, name='anunciante'),
]