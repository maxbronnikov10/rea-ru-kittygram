from django.http import Http404
from rest_framework.exceptions import NotFound
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Единый ответ 404 на русском вместо «No Cat matches the given query»."""
    if isinstance(exc, Http404):
        exc = NotFound('Объект не найден.')
    return exception_handler(exc, context)
