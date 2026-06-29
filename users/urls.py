from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView, ProfileView,
    CustomTokenObtainPairView,
    RegisterClinicView, PasswordResetRequestView, PasswordResetConfirmView,
    ApproveClinicView, RejectClinicView,
)
from .admin_panel_views import admin_panel


urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('register-clinic/', RegisterClinicView.as_view(), name='register-clinic'),
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset'),
    path('password-reset-confirm/<str:uidb64>/<str:token>/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('admin-panel/', admin_panel, name='admin-panel'),
    path('admin/approve-clinic/<int:user_id>/', ApproveClinicView.as_view(), name='admin-approve-clinic'),
    path('admin/reject-clinic/<int:user_id>/', RejectClinicView.as_view(), name='admin-reject-clinic'),
]
