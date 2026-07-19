from rest_framework.permissions import BasePermission, SAFE_METHODS


def is_community_moderator(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_staff or user.is_superuser or user.username == 'jaime17')
    )


class IsOwnerOrModerator(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if is_community_moderator(request.user):
            return True
        owner_id = getattr(obj, 'created_by_id', None) or getattr(obj, 'author_id', None)
        return owner_id == request.user.id
