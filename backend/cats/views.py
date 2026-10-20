from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, permissions, viewsets

from .filters import CatFilter
from .models import Achievement, Cat
from .permissions import AdminOrReadOnlyAndCreate, OwnerOrReadOnly
from .serializers import AchievementSerializer, CatSerializer


@extend_schema_view(
    list=extend_schema(summary='Список котиков (пагинация, фильтры, поиск)'),
    retrieve=extend_schema(summary='Карточка котика'),
    create=extend_schema(
        summary='Добавить котика (хозяин — текущий пользователь)'),
    update=extend_schema(summary='Изменить котика (только хозяин)'),
    partial_update=extend_schema(
        summary='Частично изменить котика (только хозяин)'),
    destroy=extend_schema(summary='Удалить котика (только хозяин)'),
)
class CatViewSet(viewsets.ModelViewSet):
    serializer_class = CatSerializer
    permission_classes = (permissions.IsAuthenticated, OwnerOrReadOnly)
    filterset_class = CatFilter
    filter_backends = (DjangoFilterBackend, filters.SearchFilter,
                       filters.OrderingFilter)
    search_fields = ('name',)
    ordering_fields = ('id', 'name', 'birth_year')
    ordering = ('id',)

    def get_queryset(self):
        return Cat.objects.select_related('owner').prefetch_related(
            Prefetch('achievements', queryset=Achievement.objects.all()))

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@extend_schema_view(
    list=extend_schema(summary='Список достижений'),
    create=extend_schema(summary='Добавить достижение'),
)
class AchievementViewSet(viewsets.ModelViewSet):
    queryset = Achievement.objects.all()
    serializer_class = AchievementSerializer
    permission_classes = (AdminOrReadOnlyAndCreate,)
    pagination_class = None
    filter_backends = (filters.SearchFilter,)
    search_fields = ('name',)
