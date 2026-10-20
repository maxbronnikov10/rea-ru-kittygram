import django_filters
from django.db.models import Q

from .models import CatRating, Duel


class DuelFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Duel.Status.choices)
    cat = django_filters.NumberFilter(method='filter_cat',
                                      label='id котика (любая сторона)')
    mine = django_filters.BooleanFilter(method='filter_mine',
                                        label='Дуэли моих котиков')
    incoming = django_filters.BooleanFilter(
        method='filter_incoming', label='Вызовы, ожидающие моего ответа')
    created_after = django_filters.IsoDateTimeFilter(
        field_name='created_at', lookup_expr='gte')
    created_before = django_filters.IsoDateTimeFilter(
        field_name='created_at', lookup_expr='lte')

    class Meta:
        model = Duel
        fields = ('status', 'cat', 'mine', 'incoming', 'created_after',
                  'created_before')

    def filter_cat(self, queryset, name, value):
        return queryset.filter(Q(challenger_id=value) | Q(opponent_id=value))

    def filter_mine(self, queryset, name, value):
        user = self.request.user
        mine = Q(challenger__owner=user) | Q(opponent__owner=user)
        return queryset.filter(mine) if value else queryset.exclude(mine)

    def filter_incoming(self, queryset, name, value):
        incoming = Q(opponent__owner=self.request.user,
                     status=Duel.Status.PENDING)
        return queryset.filter(incoming) if value else queryset


class CatRatingFilter(django_filters.FilterSet):
    min_duels = django_filters.NumberFilter(field_name='duels_count',
                                            lookup_expr='gte')
    owner = django_filters.CharFilter(field_name='cat__owner__username')

    class Meta:
        model = CatRating
        fields = ('min_duels', 'owner')
