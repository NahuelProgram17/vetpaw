from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from .sanctions import get_active_sanction, sanction_error_payload


class SanctionAwareJWTAuthentication(JWTAuthentication):
    """Bloquea también tokens emitidos antes de que una cuenta fuera sancionada."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, validated_token = result
        sanction = get_active_sanction(user)
        if sanction:
            raise AuthenticationFailed(detail=sanction_error_payload(sanction))
        return user, validated_token
