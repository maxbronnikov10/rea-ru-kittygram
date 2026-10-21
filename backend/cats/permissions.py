from rest_framework import permissions


class OwnerOrReadOnly(permissions.BasePermission):
    message = 'Изменять и удалять котика может только его хозяин.'

    def has_object_permission(self, request, view, obj):
        return (request.method in permissions.SAFE_METHODS
                or obj.owner == request.user)


class AdminOrReadOnlyAndCreate(permissions.BasePermission):
    """Достижения: читать и добавлять может любой авторизованный,
    переименовывать и удалять — только администратор."""

    message = 'Изменять и удалять достижения может только администратор.'

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS + ('POST',):
            return request.user.is_authenticated
        return request.user.is_staff
