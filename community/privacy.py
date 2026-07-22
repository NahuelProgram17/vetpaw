from django.db.models import Q

from users.permissions import is_community_moderator

from .models import (
    BlockedUser,
    CommunityPrivacySettings,
    HiddenPost,
    MutedUser,
    PetFollow,
    PetFollowRequest,
    PetSocialProfile,
    Post,
)


def privacy_for(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    settings, _ = CommunityPrivacySettings.objects.get_or_create(user=user)
    return settings


def users_blocked_between(first, second):
    if not first or not second:
        return False
    return BlockedUser.objects.filter(
        Q(blocker=first, blocked=second) | Q(blocker=second, blocked=first)
    ).exists()


def can_access_pet_profile(profile, viewer):
    if profile.is_public:
        return True
    if viewer and viewer.is_authenticated:
        if viewer.id == profile.pet.owner_id or is_community_moderator(viewer):
            return True
        return PetFollow.objects.filter(follower=viewer, pet=profile.pet).exists()
    return False


def follow_request_pending(profile, viewer):
    return bool(
        viewer and viewer.is_authenticated
        and PetFollowRequest.objects.filter(follower=viewer, pet=profile.pet).exists()
    )


def post_owner_id(post):
    return post.created_by_id


def can_comment_on_post(post, user):
    if not user or not user.is_authenticated:
        return False, 'Necesitás iniciar sesión para comentar.'
    if users_blocked_between(post.created_by, user):
        return False, 'No podés interactuar con este perfil.'
    if post.comment_permission == Post.COMMENTS_NONE:
        return False, 'Los comentarios están desactivados en esta publicación.'
    if post.comment_permission == Post.COMMENTS_FOLLOWERS and post.created_by_id != user.id:
        follows = PetFollow.objects.filter(follower=user)
        allowed = False
        if post.pet_id:
            allowed = follows.filter(pet_id=post.pet_id).exists()
        elif post.clinic_id:
            allowed = follows.filter(clinic_id=post.clinic_id).exists()
        elif post.business_id:
            allowed = follows.filter(business_id=post.business_id).exists()
        elif post.shelter_id:
            allowed = follows.filter(shelter_id=post.shelter_id).exists()
        if not allowed:
            return False, 'Solo los seguidores pueden comentar esta publicación.'
    return True, ''


def visible_posts_for(queryset, viewer):
    queryset = queryset.filter(is_public=True)
    if not viewer or not viewer.is_authenticated:
        return queryset.filter(Q(pet__isnull=True) | Q(pet__social_profile__is_public=True))

    followed_pet_ids = PetFollow.objects.filter(follower=viewer, pet__isnull=False).values_list('pet_id', flat=True)
    queryset = queryset.filter(
        Q(pet__isnull=True)
        | Q(pet__social_profile__is_public=True)
        | Q(pet__owner=viewer)
        | Q(pet_id__in=followed_pet_ids)
    )
    blocked = BlockedUser.objects.filter(blocker=viewer).values_list('blocked_id', flat=True)
    blockers = BlockedUser.objects.filter(blocked=viewer).values_list('blocker_id', flat=True)
    muted = MutedUser.objects.filter(user=viewer).values_list('muted_id', flat=True)
    hidden = HiddenPost.objects.filter(user=viewer).values_list('post_id', flat=True)
    return queryset.exclude(created_by_id__in=list(blocked) + list(blockers) + list(muted)).exclude(pk__in=hidden)
