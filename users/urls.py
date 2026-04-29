from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import RegisterView, ProfileView, VerifyEmailView, CustomTokenObtainPairView, ResendVerificationEmailView, RegisterClinicView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('register-clinic/', RegisterClinicView.as_view(), name='register-clinic'),
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('verify-email/<uuid:token>/', VerifyEmailView.as_view(), name='verify-email'),
    path('resend-verification/', ResendVerificationEmailView.as_view(), name='resend-verification'),
]