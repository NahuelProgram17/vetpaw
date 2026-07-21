"""Helpers de permisos compartidos por las áreas administrativas de VetPaw."""

VETPAW_ADMIN_GROUP = 'vetpaw_admins'
COMMUNITY_MODERATOR_GROUP = 'community_moderators'


def _is_authenticated(user):
    return bool(user and getattr(user, 'is_authenticated', False))


def _groups_for(user):
    """Devuelve los grupos del usuario una sola vez por request/instancia."""
    cache_name = '_vetpaw_group_names_cache'
    if not hasattr(user, cache_name):
        setattr(user, cache_name, set(user.groups.values_list('name', flat=True)))
    return getattr(user, cache_name)


def is_vetpaw_admin(user):
    """Permiso para panel general, aprobación de clínicas y gestión global."""
    if not _is_authenticated(user):
        return False
    return bool(
        user.is_superuser
        or user.is_staff
        or VETPAW_ADMIN_GROUP in _groups_for(user)
    )


def is_community_moderator(user):
    """Permiso para moderar publicaciones, comentarios y reportes."""
    if not _is_authenticated(user):
        return False
    return bool(
        is_vetpaw_admin(user)
        or COMMUNITY_MODERATOR_GROUP in _groups_for(user)
    )
