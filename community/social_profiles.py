from django.db.models import Count, Q
from django.shortcuts import get_object_or_404

from clinics.models import Clinic
from partners.models import BusinessProfile, ShelterProfile
from pets.models import Pet

from .models import BlockedUser, PetFollow, PetSocialProfile, Post
from .privacy import can_access_pet_profile, privacy_for


def absolute_file_url(request, field):
    if not field:
        return None
    try:
        url = field.url
    except (AttributeError, ValueError):
        return None
    if request and url.startswith('/'):
        return request.build_absolute_uri(url)
    return url


PROFILE_TYPES = {'pet', 'clinic', 'business', 'shelter'}


def resolve_profile(profile_type, identifier):
    profile_type = str(profile_type or '').strip().lower()
    identifier = str(identifier or '').strip()
    if profile_type not in PROFILE_TYPES:
        raise ValueError('Tipo de perfil inválido.')

    if profile_type == 'pet':
        queryset = Pet.objects.select_related('owner', 'social_profile')
        if identifier.isdigit():
            pet = get_object_or_404(queryset, pk=int(identifier))
            profile, _ = PetSocialProfile.objects.get_or_create(pet=pet)
            return pet
        profile = get_object_or_404(
            PetSocialProfile.objects.select_related('pet__owner'),
            slug=identifier,
        )
        return profile.pet

    model = {
        'clinic': Clinic,
        'business': BusinessProfile,
        'shelter': ShelterProfile,
    }[profile_type]
    queryset = model.objects.select_related('owner')
    if profile_type in {'business', 'shelter'}:
        queryset = queryset.filter(is_active=True, owner__is_approved=True)
    elif profile_type == 'clinic':
        queryset = queryset.filter(is_active=True)

    if identifier.isdigit():
        return get_object_or_404(queryset, pk=int(identifier))
    return get_object_or_404(queryset, slug=identifier)


def target_kwargs(profile_type, target):
    return {
        'pet': {'pet': target},
        'clinic': {'clinic': target},
        'business': {'business': target},
        'shelter': {'shelter': target},
    }[profile_type]


def target_owner(target):
    return getattr(target, 'owner', None)


def target_owner_id(target):
    return getattr(target, 'owner_id', None)


def is_target_public(profile_type, target, viewer=None):
    if profile_type == 'pet':
        profile, _ = PetSocialProfile.objects.get_or_create(pet=target)
        return can_access_pet_profile(profile, viewer)
    if profile_type == 'clinic':
        return bool(target.is_active)
    return bool(target.is_active and target.owner.is_approved)


def follow_queryset_for_target(profile_type, target):
    return PetFollow.objects.filter(**target_kwargs(profile_type, target))


def following_count_for_user(user):
    if not user:
        return 0
    return PetFollow.objects.filter(follower=user).count()


def blocked_user_ids(viewer):
    if not viewer or not viewer.is_authenticated:
        return set()
    made = BlockedUser.objects.filter(blocker=viewer).values_list('blocked_id', flat=True)
    received = BlockedUser.objects.filter(blocked=viewer).values_list('blocker_id', flat=True)
    return set(made).union(received)


def primary_identity_for_user(user, request=None):
    if not user:
        return None

    if user.role == 'clinic':
        profile = getattr(user, 'clinic_profile', None)
        if profile and profile.is_active:
            return identity_for_target('clinic', profile, request=request)
    elif user.role == 'business':
        profile = getattr(user, 'business_profile', None)
        if profile and profile.is_active and user.is_approved:
            return identity_for_target('business', profile, request=request)
    elif user.role == 'shelter':
        profile = getattr(user, 'shelter_profile', None)
        if profile and profile.is_active and user.is_approved:
            return identity_for_target('shelter', profile, request=request)
    else:
        pet = Pet.objects.filter(owner=user, social_profile__is_public=True).select_related('social_profile').order_by('created_at').first()
        if pet:
            return identity_for_target('pet', pet, request=request)

    display_name = user.get_full_name().strip() or user.username
    return {
        'type': 'user',
        'id': user.id,
        'name': display_name,
        'subtitle': 'Miembro de VetPaw',
        'photo': absolute_file_url(request, user.avatar),
        'profile_url': '',
        'verified': False,
        'owner_user_id': user.id,
    }


def identity_for_target(profile_type, target, request=None):
    if profile_type == 'pet':
        social, _ = PetSocialProfile.objects.get_or_create(pet=target)
        settings = privacy_for(target.owner)
        subtitle_parts = [target.get_species_display(), target.breed]
        return {
            'type': 'pet',
            'id': target.id,
            'identifier': social.slug or str(target.id),
            'name': target.name,
            'subtitle': ' · '.join(filter(None, subtitle_parts)),
            'photo': absolute_file_url(request, target.photo),
            'profile_url': f'/mascotas/{social.slug or target.id}',
            'verified': False,
            'owner_user_id': target.owner_id,
        }
    if profile_type == 'clinic':
        return {
            'type': 'clinic',
            'id': target.id,
            'identifier': target.slug,
            'name': target.name,
            'subtitle': ' · '.join(filter(None, [target.locality, target.province])),
            'photo': absolute_file_url(request, target.logo),
            'profile_url': f'/clinicas/{target.slug}',
            'verified': bool(target.owner and target.owner.is_approved),
            'owner_user_id': target.owner_id,
        }
    if profile_type == 'business':
        return {
            'type': 'business',
            'id': target.id,
            'identifier': target.slug,
            'name': target.name,
            'subtitle': ' · '.join(filter(None, [target.get_business_type_display(), target.locality])),
            'photo': absolute_file_url(request, target.logo),
            'profile_url': f'/negocios/{target.slug}',
            'verified': target.is_verified,
            'owner_user_id': target.owner_id,
        }
    return {
        'type': 'shelter',
        'id': target.id,
        'identifier': target.slug,
        'name': target.name,
        'subtitle': ' · '.join(filter(None, [target.get_shelter_type_display(), target.locality])),
        'photo': absolute_file_url(request, target.logo),
        'profile_url': f'/refugios/{target.slug}',
        'verified': target.is_verified,
        'owner_user_id': target.owner_id,
    }


def identity_for_follow(follow, request=None):
    if follow.pet_id:
        return identity_for_target('pet', follow.pet, request=request)
    if follow.clinic_id:
        return identity_for_target('clinic', follow.clinic, request=request)
    if follow.business_id:
        return identity_for_target('business', follow.business, request=request)
    if follow.shelter_id:
        return identity_for_target('shelter', follow.shelter, request=request)
    return None


def target_posts(profile_type, target):
    lookup = {
        'pet': {'pet': target},
        'clinic': {'clinic': target},
        'business': {'business': target},
        'shelter': {'shelter': target},
    }[profile_type]
    return Post.objects.filter(
        moderation_status=Post.STATUS_PUBLISHED,
        is_public=True,
        **lookup,
    )


def profile_stats(profile_type, target, viewer=None):
    posts = target_posts(profile_type, target)
    paws_count = posts.aggregate(total=Count('reactions', distinct=True))['total'] or 0
    owner = target_owner(target)
    following = False
    if viewer and viewer.is_authenticated:
        following = PetFollow.objects.filter(follower=viewer, **target_kwargs(profile_type, target)).exists()
    settings = privacy_for(owner)
    is_owner = bool(viewer and viewer.is_authenticated and viewer.id == getattr(owner, 'id', None))
    return {
        'followers_count': follow_queryset_for_target(profile_type, target).count() if is_owner or not settings or settings.show_followers else None,
        'following_count': following_count_for_user(owner) if is_owner or not settings or settings.show_following else None,
        'posts_count': posts.count() if is_owner or not settings or settings.show_activity else 0,
        'paws_count': paws_count if is_owner or not settings or settings.show_paws else None,
        'following': following,
    }


def follows_owned_profile_q(user):
    if not user:
        return Q(pk__in=[])
    pet_ids = Pet.objects.filter(owner=user).values_list('id', flat=True)
    clinic_ids = Clinic.objects.filter(owner=user).values_list('id', flat=True)
    business_ids = BusinessProfile.objects.filter(owner=user).values_list('id', flat=True)
    shelter_ids = ShelterProfile.objects.filter(owner=user).values_list('id', flat=True)
    return (
        Q(pet_id__in=pet_ids)
        | Q(clinic_id__in=clinic_ids)
        | Q(business_id__in=business_ids)
        | Q(shelter_id__in=shelter_ids)
    )
