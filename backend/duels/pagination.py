from rest_framework.pagination import LimitOffsetPagination


class DuelsPagination(LimitOffsetPagination):
    """Лента дуэлей: ?limit=N&offset=M."""

    default_limit = 10
    max_limit = 50
