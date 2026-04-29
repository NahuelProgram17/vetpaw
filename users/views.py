from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.shortcuts import redirect
from .models import User
from .serializers import RegisterSerializer, UserSerializer, CustomTokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView



def send_verification_email(user):
    token = user.email_verification_token
    verify_url = f"http://localhost:8000/api/users/verify-email/{token}/"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0;padding:0;background:#f4f4f4;font-family:Arial,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
        <td align="center" style="padding:40px 0;">
            <table width="520" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
            <!-- Header -->
            <tr>
                <td align="center" style="background:#4f46e5;padding:32px 40px;">
                <div style="font-size:36px;">🐾</div>
                <div style="color:#ffffff;font-size:26px;font-weight:bold;margin-top:8px;">VetPaw</div>
                <div style="color:#c7d2fe;font-size:13px;margin-top:4px;">Tu app veterinaria de confianza</div>
                </td>
            </tr>
            <!-- Body -->
            <tr>
                <td style="padding:36px 40px;">
                <p style="font-size:18px;font-weight:bold;color:#1e1b4b;margin:0 0 12px;">¡Hola, {user.username}! 👋</p>
                <p style="font-size:15px;color:#4b5563;line-height:1.6;margin:0 0 28px;">
                    Gracias por registrarte en <strong>VetPaw</strong>. Para activar tu cuenta y empezar a cuidar a tus mascotas, verificá tu email haciendo clic en el botón:
                </p>
                <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                    <td align="center">
                        <a href="{verify_url}" style="display:inline-block;background:#4f46e5;color:#ffffff;font-size:16px;font-weight:bold;padding:14px 36px;border-radius:8px;text-decoration:none;">
                        ✅ Verificar mi cuenta
                        </a>
                    </td>
                    </tr>
                </table>
                <p style="font-size:13px;color:#9ca3af;margin:28px 0 0;text-align:center;">
                    Si no creaste una cuenta en VetPaw, ignorá este mensaje.
                </p>
                </td>
            </tr>
            <!-- Footer -->
            <tr>
                <td align="center" style="background:#f9fafb;padding:20px 40px;border-top:1px solid #e5e7eb;">
                <p style="font-size:12px;color:#9ca3af;margin:0;">© 2025 VetPaw · Todos los derechos reservados 🐾</p>
                </td>
            </tr>
            </table>
        </td>
        </tr>
    </table>
    </body>
    </html>
    """

    text_content = f"Hola {user.username}! Verificá tu cuenta en VetPaw: {verify_url}"

    email = EmailMultiAlternatives(
        subject='Verificá tu cuenta en VetPaw 🐾',
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send()


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        send_verification_email(user)


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        try:
            user = User.objects.get(email_verification_token=token)
            if not user.email_verified:
                user.email_verified = True
                user.save()
            return redirect('http://localhost:5173/login?verified=true')
        except User.DoesNotExist:
            return redirect('http://localhost:5173/login?verified=false')


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
    
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    
class ResendVerificationEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'El email es requerido.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(email=email)
            if user.email_verified:
                return Response({'message': 'Este email ya fue verificado. Podés iniciar sesión.'}, status=status.HTTP_200_OK)
            send_verification_email(user)
            return Response({'message': 'Email de verificación reenviado. Revisá tu casilla.'}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'message': 'Si el email existe, recibirás el link en breve.'}, status=status.HTTP_200_OK)