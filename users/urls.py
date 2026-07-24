from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView, ProfileView,
    CustomTokenObtainPairView,
    RegisterClinicView, RegisterBusinessView, RegisterShelterView, PasswordResetRequestView, PasswordResetConfirmView,
    ApproveClinicView, RejectClinicView, ApproveProfessionalProfileView, RejectProfessionalProfileView,
)
from .admin_panel_views import (
    abuse_accounts, abuse_signal_action, abuse_signals,
    account_moderation_accounts, account_moderation_action, account_moderation_history,
    admin_panel, clinic_plan_action,
    professional_verification_action, professional_verification_history,
    professional_verifications,
)


urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('register-clinic/', RegisterClinicView.as_view(), name='register-clinic'),
    path('register-business/', RegisterBusinessView.as_view(), name='register-business'),
    path('register-shelter/', RegisterShelterView.as_view(), name='register-shelter'),
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset'),
    path('password-reset-confirm/<str:uidb64>/<str:token>/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('admin-panel/', admin_panel, name='admin-panel'),
    path('admin/clinic-plan/<int:clinic_id>/', clinic_plan_action, name='admin-clinic-plan'),
    path('admin/moderation/accounts/', account_moderation_accounts, name='admin-moderation-accounts'),
    path('admin/moderation/accounts/<int:user_id>/', account_moderation_action, name='admin-moderation-account-action'),
    path('admin/moderation/history/', account_moderation_history, name='admin-moderation-history'),
    path('admin/abuse/signals/', abuse_signals, name='admin-abuse-signals'),
    path('admin/abuse/accounts/', abuse_accounts, name='admin-abuse-accounts'),
    path('admin/abuse/signals/<int:signal_id>/', abuse_signal_action, name='admin-abuse-signal-action'),
    path('admin/verifications/', professional_verifications, name='admin-professional-verifications'),
    path('admin/verifications/history/', professional_verification_history, name='admin-professional-verification-history'),
    path('admin/verifications/<int:user_id>/', professional_verification_action, name='admin-professional-verification-action'),
    path('admin/approve-clinic/<int:user_id>/', ApproveClinicView.as_view(), name='admin-approve-clinic'),
    path('admin/reject-clinic/<int:user_id>/', RejectClinicView.as_view(), name='admin-reject-clinic'),
    path('admin/approve-profile/<int:user_id>/', ApproveProfessionalProfileView.as_view(), name='admin-approve-profile'),
    path('admin/reject-profile/<int:user_id>/', RejectProfessionalProfileView.as_view(), name='admin-reject-profile'),
]
