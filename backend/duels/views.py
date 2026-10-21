from django.db.models import (Case, Count, F, IntegerField, OuterRef,
                              Subquery, Value, When)
from django.db.models.functions import Coalesce
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (OpenApiResponse, extend_schema,
                                   extend_schema_view)
from rest_framework import filters, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from cats.pagination import CatsPagination

from . import services
from .filters import CatRatingFilter, DuelFilter
from .models import CatRating, Duel
from .pagination import DuelsPagination
from .permissions import IsDuelAuthor, IsOpponentOwner
from .serializers import (CatRatingSerializer, DuelCreateSerializer,
                          DuelResultSerializer, DuelSerializer,
                          VoteSerializer)


def require_status(duel, expected, message):
    if duel.status != expected:
        raise ValidationError({'detail': message})


@extend_schema_view(
    list=extend_schema(summary='Лента дуэлей (фильтры, limit/offset)'),
    retrieve=extend_schema(summary='Дуэль'),
    create=extend_schema(summary='Бросить вызов своим котиком'),
)
class DuelViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                  mixins.CreateModelMixin, viewsets.GenericViewSet):
    pagination_class = DuelsPagination
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = DuelFilter
    ordering_fields = ('created_at', 'ends_at')

    def get_queryset(self):
        return (
            Duel.objects
            .select_related('challenger__owner', 'challenger__rating',
                            'opponent__owner', 'opponent__rating', 'author')
            .prefetch_related('votes')
            .annotate(votes_total=Count('votes'))
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return DuelCreateSerializer
        if self.action == 'vote':
            return VoteSerializer
        if self.action in ('results', 'finish'):
            return DuelResultSerializer
        return DuelSerializer

    def get_throttles(self):
        if self.action == 'vote':
            self.throttle_scope = 'duel_votes'
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def _reply(self, duel, status_code=status.HTTP_200_OK):
        duel = self.get_queryset().get(pk=duel.pk)
        serializer = DuelSerializer(duel, context={'request': self.request})
        return Response(serializer.data, status=status_code)

    @extend_schema(summary='Принять вызов (хозяин котика-соперника)',
                   request=None, responses=DuelSerializer)
    @action(detail=True, methods=['post'],
            permission_classes=(permissions.IsAuthenticated, IsOpponentOwner))
    def accept(self, request, pk=None):
        duel = self.get_object()
        require_status(duel, Duel.Status.PENDING,
                       'Принять можно только вызов, ожидающий ответа.')
        services.start_duel(duel)
        return self._reply(duel)

    @extend_schema(summary='Отклонить вызов (хозяин котика-соперника)',
                   request=None, responses=DuelSerializer)
    @action(detail=True, methods=['post'],
            permission_classes=(permissions.IsAuthenticated, IsOpponentOwner))
    def decline(self, request, pk=None):
        duel = self.get_object()
        require_status(duel, Duel.Status.PENDING,
                       'Отклонить можно только вызов, ожидающий ответа.')
        duel.status = Duel.Status.DECLINED
        duel.save(update_fields=('status',))
        return self._reply(duel)

    @extend_schema(summary='Отменить свой вызов, пока его не приняли',
                   request=None, responses=DuelSerializer)
    @action(detail=True, methods=['post'],
            permission_classes=(permissions.IsAuthenticated, IsDuelAuthor))
    def cancel(self, request, pk=None):
        duel = self.get_object()
        require_status(duel, Duel.Status.PENDING,
                       'Отменить можно только вызов, который ещё не принят.')
        duel.status = Duel.Status.CANCELLED
        duel.save(update_fields=('status',))
        return self._reply(duel)

    @extend_schema(summary='Проголосовать за котика в активной дуэли',
                   responses={201: VoteSerializer})
    @action(detail=True, methods=['post'])
    def vote(self, request, pk=None):
        duel = self.get_object()
        serializer = VoteSerializer(
            data=request.data, context={'request': request, 'duel': duel})
        serializer.is_valid(raise_exception=True)
        serializer.save(duel=duel, voter=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(summary='Подвести итоги (после окончания голосования)',
                   request=None, responses=DuelResultSerializer)
    @action(detail=True, methods=['post'])
    def finish(self, request, pk=None):
        duel = self.get_object()
        require_status(duel, Duel.Status.ACTIVE,
                       'Подвести итоги можно только у активной дуэли.')
        if duel.ends_at > timezone.now() and not request.user.is_staff:
            local_end = timezone.localtime(duel.ends_at)
            raise ValidationError({'detail': (
                'Голосование ещё идёт, итоги можно подвести после '
                f'{local_end:%d.%m.%Y %H:%M}.')})
        duel = services.finish_duel(duel)
        return Response(DuelResultSerializer(duel).data)

    @extend_schema(
        summary='Итоги дуэли: счёт и изменение рейтинга',
        responses={200: DuelResultSerializer,
                   400: OpenApiResponse(description='Итоги ещё не подведены')})
    @action(detail=True, methods=['get'])
    def results(self, request, pk=None):
        duel = self.get_object()
        require_status(duel, Duel.Status.FINISHED,
                       'Итоги ещё не подведены: счёт скрыт до завершения '
                       'дуэли.')
        return Response(DuelResultSerializer(duel).data)


@extend_schema_view(
    list=extend_schema(summary='Таблица лидеров по рейтингу Эло'),
    retrieve=extend_schema(summary='Рейтинг котика (по id котика)'),
)
class CatRatingViewSet(viewsets.ReadOnlyModelViewSet):
    """Место считается только среди котиков, проведших хотя бы одну дуэль;
    у остальных place = null, в списке они идут последними."""

    serializer_class = CatRatingSerializer
    permission_classes = (permissions.AllowAny,)
    lookup_field = 'cat'
    lookup_url_kwarg = 'cat_id'
    pagination_class = CatsPagination
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = CatRatingFilter
    ordering_fields = ('rating', 'wins', 'duels_count')

    def get_queryset(self):
        higher = (
            CatRating.objects
            .filter(duels_count__gt=0, rating__gt=OuterRef('rating'))
            .order_by().annotate(group=Value(1)).values('group')
            .annotate(cnt=Count('*')).values('cnt')
        )
        place = Case(
            When(duels_count=0, then=Value(None)),
            default=Coalesce(Subquery(higher, output_field=IntegerField()),
                             0) + 1,
            output_field=IntegerField(),
        )
        return (
            CatRating.objects.select_related('cat__owner')
            .annotate(place=place)
            .order_by(F('place').asc(nulls_last=True), '-rating', 'cat_id')
        )
