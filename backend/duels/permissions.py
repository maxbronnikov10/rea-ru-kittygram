from rest_framework import permissions


class IsOpponentOwner(permissions.BasePermission):
    """Принять или отклонить вызов может только хозяин котика-соперника."""

    message = 'Ответить на вызов может только хозяин котика-соперника.'

    def has_object_permission(self, request, view, obj):
        return obj.opponent.owner_id == request.user.id


class IsDuelAuthor(permissions.BasePermission):
    """Отменить вызов может только его автор."""

    message = 'Отменить вызов может только его автор.'

    def has_object_permission(self, request, view, obj):
        return obj.author_id == request.user.id
