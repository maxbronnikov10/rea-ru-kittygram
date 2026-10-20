from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from djoser.views import TokenCreateView, TokenDestroyView
from drf_spectacular.utils import extend_schema, extend_schema_view
from drf_spectacular.views import (SpectacularAPIView, SpectacularRedocView,
                                   SpectacularSwaggerView)
from rest_framework import routers

from cats.views import AchievementViewSet, CatViewSet
from duels.views import CatRatingViewSet, DuelViewSet

# Описание эндпоинтов токена для Swagger (djoser не задаёт схему выхода).
extend_schema_view(post=extend_schema(summary='Получить токен'))(
    TokenCreateView)
extend_schema_view(post=extend_schema(
    summary='Выйти (удалить токен)', request=None, responses={204: None}))(
    TokenDestroyView)

router = routers.DefaultRouter()
router.register('cats', CatViewSet, basename='cat')
router.register('achievements', AchievementViewSet, basename='achievement')
router.register('duels', DuelViewSet, basename='duel')
router.register('ratings', CatRatingViewSet, basename='rating')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'),
         name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'),
         name='redoc'),
    path('api/', include(router.urls)),
    path('api/', include('djoser.urls')),
    path('api/', include('djoser.urls.authtoken')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
