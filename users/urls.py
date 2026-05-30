from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView, ProfileView, VerifyEmailView,
    CustomTokenObtainPairView, ResendVerificationEmailView,
    RegisterClinicView, PasswordResetRequestView, PasswordResetConfirmView
)
from .admin_panel_views import admin_panel


urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('register-clinic/', RegisterClinicView.as_view(), name='register-clinic'),
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('verify-email/<uuid:token>/', VerifyEmailView.as_view(), name='verify-email'),
    path('resend-verification/', ResendVerificationEmailView.as_view(), name='resend-verification'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset'),
    path('password-reset-confirm/<str:uidb64>/<str:token>/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('admin-panel/', admin_panel, name='admin-panel'),
]