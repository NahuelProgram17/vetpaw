from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from .models import User
from .permissions import is_vetpaw_admin
from .serializers import (RegisterSerializer, UserSerializer, CustomTokenObtainPairSerializer, RegisterClinicSerializer, RegisterBusinessSerializer, RegisterShelterSerializer)
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str


class RegisterView(generics.CreateAPIView):
    """Registro de DUEÑO de mascota. Cuenta activa al instante."""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        user.is_approved = True  # Dueños se auto-aprueban
        user.save()


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class RegisterClinicView(generics.CreateAPIView):
    """Registro de VETERINARIA. Cuenta queda PENDIENTE de aprobación del admin."""
    queryset = User.objects.all()
    serializer_class = RegisterClinicSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        from clinics.models import Clinic
        from django.db import transaction
        with transaction.atomic():
            user = serializer.save()
            # Clínica queda pendiente de aprobación (is_approved=False por defecto)
            user.save()
            clinic_data = getattr(user, '_clinic_data', {})
            Clinic.objects.create(
                owner=user,
                plan_status=Clinic.PLAN_INACTIVE,
                **clinic_data,
            )


class RegisterBusinessView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterBusinessSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        from django.db import transaction
        from partners.models import BusinessProfile
        with transaction.atomic():
            user = serializer.save()
            user.is_approved = False
            user.save(update_fields=['is_approved'])
            BusinessProfile.objects.create(owner=user, **getattr(user, '_partner_profile_data', {}))


class RegisterShelterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterShelterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        from django.db import transaction
        from partners.models import ShelterProfile
        with transaction.atomic():
            user = serializer.save()
            user.is_approved = False
            user.save(update_fields=['is_approved'])
            ShelterProfile.objects.create(owner=user, **getattr(user, '_partner_profile_data', {}))


class PasswordResetRequestView(APIView):
    """Envía link por mail para recuperar contraseña."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'El email es requerido.'}, status=400)
        try:
            user = User.objects.get(email=email)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = f"https://www.vetpaw.com.ar/reset-password/{uid}/{token}/"

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <body style="margin:0;padding:0;background:#f4f4f4;font-family:Arial,sans-serif;">
            <table width="100%" cellpadding="0" cellspacing="0">
                <tr><td align="center" style="padding:40px 0;">
                <table width="520" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                <tr><td align="center" style="background:#0f1923;padding:32px 40px;">
                    <div style="font-size:36px;">🐾</div>
                    <div style="color:#4CAF50;font-size:26px;font-weight:bold;margin-top:8px;">VetPaw</div>
                    <div style="color:#aaa;font-size:13px;margin-top:4px;">Tu app veterinaria de confianza</div>
                </td></tr>
                <tr><td style="padding:36px 40px;">
                    <p style="font-size:18px;font-weight:bold;color:#1e1b4b;margin:0 0 12px;">Hola, {user.username} 👋</p>
                    <p style="font-size:15px;color:#4b5563;line-height:1.6;margin:0 0 28px;">
                        Recibimos una solicitud para restablecer tu contraseña en VetPaw. Hacé clic en el botón para crear una nueva:
                    </p>
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr><td align="center">
                            <a href="{reset_url}" style="display:inline-block;background:linear-gradient(135deg,#4CAF50,#FF9800);color:#ffffff;font-size:16px;font-weight:bold;padding:14px 36px;border-radius:8px;text-decoration:none;">
                            🔑 Restablecer contraseña
                            </a>
                        </td></tr>
                    </table>
                    <p style="font-size:13px;color:#9ca3af;margin:28px 0 0;text-align:center;">
                        Este link expira en 24 horas. Si no solicitaste esto, ignorá este mensaje.
                    </p>
                </td></tr>
                <tr><td align="center" style="background:#f9fafb;padding:20px 40px;border-top:1px solid #e5e7eb;">
                    <p style="font-size:12px;color:#9ca3af;margin:0;">© 2026 VetPaw · Todos los derechos reservados 🐾</p>
                </td></tr>
                </table>
                </td></tr>
            </table>
            </body></html>
            """

            text_content = f"Hola {user.username}! Restablecé tu contraseña en VetPaw: {reset_url}"
            email_msg = EmailMultiAlternatives(
                subject='Restablecé tu contraseña en VetPaw 🔑',
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            email_msg.attach_alternative(html_content, "text/html")
            email_msg.send()
        except User.DoesNotExist:
            pass
        return Response({'message': 'Si el email existe, recibirás el link en breve.'})


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, User.DoesNotExist):
            return Response({'error': 'Link inválido.'}, status=400)

        if not default_token_generator.check_token(user, token):
            return Response({'error': 'El link expiró o ya fue usado.'}, status=400)

        password = request.data.get('password')
        password2 = request.data.get('password2')

        if not password or not password2:
            return Response({'error': 'Completá ambos campos.'}, status=400)
        if password != password2:
            return Response({'error': 'Las contraseñas no coinciden.'}, status=400)
        if len(password) < 6:
            return Response({'error': 'La contraseña debe tener al menos 6 caracteres.'}, status=400)

        user.set_password(password)
        user.save()
        return Response({'message': 'Contraseña restablecida correctamente.'})


class ApproveClinicView(APIView):
    """Endpoint para que el admin apruebe una clínica pendiente."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, user_id):
        if not is_vetpaw_admin(request.user):
            return Response({'error': 'Acceso denegado.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            user = User.objects.get(pk=user_id, role='clinic')
        except User.DoesNotExist:
            return Response({'error': 'Clínica no encontrada.'}, status=404)
        user.is_approved = True
        user.save()
        return Response({'message': f'Clínica {user.username} aprobada correctamente.', 'user_id': user.id})


class RejectClinicView(APIView):
    """Endpoint para que el admin rechace (elimine) una clínica pendiente."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, user_id):
        if not is_vetpaw_admin(request.user):
            return Response({'error': 'Acceso denegado.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            user = User.objects.get(pk=user_id, role='clinic', is_approved=False)
        except User.DoesNotExist:
            return Response({'error': 'Clínica no encontrada o ya aprobada.'}, status=404)
        username = user.username
        user.delete()
        return Response({'message': f'Solicitud de {username} rechazada y eliminada.'})


class ApproveProfessionalProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, user_id):
        if not is_vetpaw_admin(request.user):
            return Response({'error': 'Acceso denegado.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            user = User.objects.get(pk=user_id, role__in=('clinic', 'business', 'shelter'))
        except User.DoesNotExist:
            return Response({'error': 'Perfil profesional no encontrado.'}, status=404)
        user.is_approved = True
        user.save(update_fields=['is_approved'])
        return Response({'message': f'{user.username} fue aprobado correctamente.', 'user_id': user.id, 'role': user.role})


class RejectProfessionalProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, user_id):
        if not is_vetpaw_admin(request.user):
            return Response({'error': 'Acceso denegado.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            user = User.objects.get(pk=user_id, role__in=('clinic', 'business', 'shelter'), is_approved=False)
        except User.DoesNotExist:
            return Response({'error': 'Perfil no encontrado o ya aprobado.'}, status=404)
        username = user.username
        role = user.role
        user.delete()
        return Response({'message': f'Solicitud de {username} rechazada y eliminada.', 'role': role})
