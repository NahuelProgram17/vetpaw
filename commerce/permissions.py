from rest_framework.permissions import BasePermission

from users.permissions import is_vetpaw_admin


class IsBusinessOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        business = getattr(obj, 'business', obj)
        return bool(request.user.is_authenticated and (
            getattr(business, 'owner_id', None) == request.user.id
            or is_vetpaw_admin(request.user)
        ))
