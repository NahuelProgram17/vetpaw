from django.urls import path
from . import views

urlpatterns = [
    path('lost-pets/', views.list_lost_pets, name='list_lost_pets'),
    path('lost-pets/create/', views.create_lost_pet, name='create_lost_pet'),
    path('lost-pets/<int:pk>/report/', views.report_lost_pet, name='report_lost_pet'),

    # Panel admin VetPaw: gestión de publicaciones de mascotas perdidas/encontradas
    path('lost-pets/admin/', views.admin_list_lost_pets, name='admin_list_lost_pets'),
    path('lost-pets/admin/<int:pk>/', views.admin_update_lost_pet, name='admin_update_lost_pet'),
    path('lost-pets/admin/<int:pk>/delete/', views.admin_delete_lost_pet, name='admin_delete_lost_pet'),
    path('lost-pets/admin/<int:pk>/expire/', views.admin_expire_lost_pet, name='admin_expire_lost_pet'),
    path('lost-pets/admin/<int:pk>/renew/', views.admin_renew_lost_pet, name='admin_renew_lost_pet'),
]
