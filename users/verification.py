from django.utils import timezone

from .models import ProfessionalVerificationDecision, User


PROFESSIONAL_ROLES = {'clinic', 'business', 'shelter'}


def professional_profile_for(user):
    if not user:
        return None
    if user.role == 'clinic':
        return getattr(user, 'clinic_profile', None)
    if user.role == 'business':
        return getattr(user, 'business_profile', None)
    if user.role == 'shelter':
        return getattr(user, 'shelter_profile', None)
    return None


def sync_legacy_verified_flag(user):
    """Mantiene compatibles los perfiles de negocio/refugio que ya usan is_verified."""
    verified = user.is_professionally_verified
    profile = professional_profile_for(user)
    if profile is not None and hasattr(profile, 'is_verified') and profile.is_verified != verified:
        profile.is_verified = verified
        profile.save(update_fields=['is_verified', 'updated_at'])


def serialize_verification_decision(decision):
    if not decision:
        return None
    return {
        'id': decision.id,
        'user_id': decision.user_id,
        'from_status': decision.from_status,
        'from_status_display': decision.get_from_status_display(),
        'to_status': decision.to_status,
        'to_status_display': decision.get_to_status_display(),
        'public_note': decision.public_note,
        'internal_note': decision.internal_note,
        'decided_by': (
            {
                'id': decision.decided_by_id,
                'username': decision.decided_by.username,
                'email': decision.decided_by.email,
            }
            if decision.decided_by_id
            else None
        ),
        'created_at': decision.created_at.isoformat(),
    }


def serialize_professional_verification(user, include_internal=False):
    profile = professional_profile_for(user)
    decisions_count = getattr(user, 'verification_decisions_count', None)
    if decisions_count is None:
        decisions_count = user.professional_verification_decisions.count()
    payload = {
        'user_id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'role_display': user.get_role_display(),
        'profile_name': getattr(profile, 'name', '') if profile else '',
        'profile_slug': getattr(profile, 'slug', '') if profile else '',
        'is_approved': user.is_approved,
        'status': user.professional_verification_status,
        'status_display': user.get_professional_verification_status_display(),
        'is_verified': user.is_professionally_verified,
        'public_note': user.verification_public_note,
        'verification_updated_at': (
            user.verification_updated_at.isoformat()
            if user.verification_updated_at
            else None
        ),
        'verified_at': user.verified_at.isoformat() if user.verified_at else None,
        'verified_by': (
            {
                'id': user.verified_by_id,
                'username': user.verified_by.username,
                'email': user.verified_by.email,
            }
            if user.verified_by_id
            else None
        ),
        'decisions_count': decisions_count,
        'date_joined': user.date_joined.isoformat(),
    }
    if include_internal:
        latest = (
            user.professional_verification_decisions.select_related('decided_by')
            .order_by('-created_at')
            .first()
        )
        payload['latest_internal_note'] = latest.internal_note if latest else ''
    return payload


def apply_verification_status(*, user, target_status, public_note='', internal_note='', decided_by=None):
    if user.role not in PROFESSIONAL_ROLES:
        raise ValueError('La verificación profesional solo corresponde a veterinarias, negocios y refugios.')
    if target_status not in dict(User.VERIFICATION_STATUS_CHOICES):
        raise ValueError('El estado de verificación no es válido.')
    if target_status in {User.VERIFICATION_NOT_APPLICABLE}:
        raise ValueError('Ese estado no puede asignarse a un perfil profesional.')
    if target_status == User.VERIFICATION_VERIFIED and not user.is_approved:
        raise ValueError('Primero tenés que aprobar la cuenta profesional antes de verificarla.')

    now = timezone.now()
    previous_status = user.professional_verification_status
    user.professional_verification_status = target_status
    user.verification_public_note = public_note
    user.verification_updated_at = now

    if target_status == User.VERIFICATION_VERIFIED:
        user.verified_at = now
        user.verified_by = decided_by
    else:
        user.verified_at = None
        user.verified_by = None

    user.save(update_fields=[
        'professional_verification_status',
        'verification_public_note',
        'verification_updated_at',
        'verified_at',
        'verified_by',
    ])
    decision = ProfessionalVerificationDecision.objects.create(
        user=user,
        from_status=previous_status,
        to_status=target_status,
        public_note=public_note,
        internal_note=internal_note,
        decided_by=decided_by,
    )
    sync_legacy_verified_flag(user)
    return decision
