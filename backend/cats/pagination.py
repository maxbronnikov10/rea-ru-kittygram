from rest_framework.pagination import PageNumberPagination


class CatsPagination(PageNumberPagination):
    """Постраничная выдача: ?page=N, размер страницы — ?page_size= (до 50)."""

    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50
