import django_filters

from .models import Cat


class CatFilter(django_filters.FilterSet):
    color = django_filters.CharFilter(lookup_expr='iexact')
    birth_year_min = django_filters.NumberFilter(
        field_name='birth_year', lookup_expr='gte')
    birth_year_max = django_filters.NumberFilter(
        field_name='birth_year', lookup_expr='lte')
    achievement = django_filters.CharFilter(
        field_name='achievements__name', lookup_expr='iexact')
    mine = django_filters.BooleanFilter(method='filter_mine')

    class Meta:
        model = Cat
        fields = ('color', 'owner', 'birth_year_min', 'birth_year_max',
                  'achievement', 'mine')

    def filter_mine(self, queryset, name, value):
        if value:
            return queryset.filter(owner=self.request.user)
        return queryset.exclude(owner=self.request.user)
