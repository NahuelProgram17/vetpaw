from rest_framework.permissions import BasePermission, SAFE_METHODS

from users.permissions import is_community_moderator


class IsOwnerOrModerator(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if is_community_moderator(request.user):
            return True
        owner_id = getattr(obj, 'created_by_id', None) or getattr(obj, 'author_id', None)
        return owner_id == request.user.id
