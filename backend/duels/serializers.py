from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from cats.models import Cat

from .models import CatRating, Duel, Vote


class DuelCatSerializer(serializers.ModelSerializer):
    """Краткая карточка котика внутри дуэли."""

    owner = serializers.SlugRelatedField(slug_field='username',
                                         read_only=True)
    rating = serializers.SerializerMethodField()

    class Meta:
        model = Cat
        fields = ('id', 'name', 'owner', 'rating')

    def get_rating(self, obj) -> int:
        rating = getattr(obj, 'rating', None)
        return rating.rating if rating else settings.DUEL_START_RATING


class DuelSerializer(serializers.ModelSerializer):
    """Дуэль для чтения. Счёт голосов скрыт до подведения итогов
    («слепое» голосование), видно только общее число голосов."""

    challenger = DuelCatSerializer(read_only=True)
    opponent = DuelCatSerializer(read_only=True)
    author = serializers.SlugRelatedField(slug_field='username',
                                          read_only=True)
    status_display = serializers.CharField(source='get_status_display',
                                           read_only=True)
    votes_total = serializers.IntegerField(read_only=True)
    my_vote = serializers.SerializerMethodField()
    winner = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Duel
        fields = ('id', 'status', 'status_display', 'challenger', 'opponent',
                  'author', 'message', 'voting_hours', 'created_at',
                  'started_at', 'ends_at', 'finished_at', 'votes_total',
                  'my_vote', 'winner')

    def get_my_vote(self, obj) -> int | None:
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        for vote in obj.votes.all():
            if vote.voter_id == request.user.id:
                return vote.cat_id
        return None


class DuelCreateSerializer(serializers.ModelSerializer):
    challenger = serializers.PrimaryKeyRelatedField(
        queryset=Cat.objects.select_related('owner'))
    opponent = serializers.PrimaryKeyRelatedField(
        queryset=Cat.objects.select_related('owner'))

    class Meta:
        model = Duel
        fields = ('id', 'challenger', 'opponent', 'voting_hours', 'message')

    def validate_challenger(self, cat):
        if cat.owner_id != self.context['request'].user.id:
            raise serializers.ValidationError(
                'Бросить вызов можно только своим котиком.')
        return cat

    def validate(self, data):
        challenger, opponent = data['challenger'], data['opponent']
        if challenger.id == opponent.id:
            raise serializers.ValidationError(
                {'opponent': 'Котик не может вызвать на дуэль сам себя.'})
        if opponent.owner_id == challenger.owner_id:
            raise serializers.ValidationError(
                {'opponent': 'Нельзя вызвать на дуэль своего же котика.'})
        same_pair = (Q(challenger=challenger, opponent=opponent)
                     | Q(challenger=opponent, opponent=challenger))
        if Duel.objects.filter(same_pair,
                               status__in=Duel.OPEN_STATUSES).exists():
            raise serializers.ValidationError(
                'Между этими котиками уже есть незавершённая дуэль.')
        limit = settings.DUEL_MAX_OPEN_PER_CAT
        for cat in (challenger, opponent):
            open_count = Duel.objects.filter(
                Q(challenger=cat) | Q(opponent=cat),
                status__in=Duel.OPEN_STATUSES,
            ).count()
            if open_count >= limit:
                raise serializers.ValidationError(
                    f'У котика «{cat.name}» уже {open_count} незавершённых '
                    f'дуэли — это максимум.')
        return data

    def to_representation(self, instance):
        return DuelSerializer(instance, context=self.context).data


class VoteSerializer(serializers.ModelSerializer):
    cat = serializers.PrimaryKeyRelatedField(queryset=Cat.objects.all())

    class Meta:
        model = Vote
        fields = ('id', 'cat', 'created_at')
        read_only_fields = ('created_at',)

    def validate(self, data):
        duel = self.context['duel']
        user = self.context['request'].user
        if duel.status != Duel.Status.ACTIVE:
            raise serializers.ValidationError(
                'Голосовать можно только в активной дуэли.')
        if duel.ends_at and duel.ends_at <= timezone.now():
            raise serializers.ValidationError(
                'Время голосования истекло, подведите итоги дуэли.')
        if duel.is_participant(user):
            raise serializers.ValidationError(
                'Хозяева котиков-участников не голосуют в своей дуэли.')
        if not duel.has_cat(data['cat'].id):
            raise serializers.ValidationError(
                {'cat': 'Этот котик не участвует в дуэли.'})
        if duel.votes.filter(voter=user).exists():
            raise serializers.ValidationError(
                'Вы уже проголосовали в этой дуэли.')
        return data


class DuelResultSerializer(serializers.ModelSerializer):
    challenger = DuelCatSerializer(read_only=True)
    opponent = DuelCatSerializer(read_only=True)
    winner = serializers.PrimaryKeyRelatedField(read_only=True)
    result = serializers.SerializerMethodField()

    class Meta:
        model = Duel
        fields = ('id', 'status', 'challenger', 'opponent', 'winner',
                  'finished_at', 'result')

    @staticmethod
    def _rating(before, delta):
        return {'before': before, 'delta': delta, 'after': before + delta}

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_result(self, obj):
        total = obj.challenger_votes + obj.opponent_votes
        share = round(obj.challenger_votes / total, 3) if total else None
        return {
            'votes': {'challenger': obj.challenger_votes,
                      'opponent': obj.opponent_votes,
                      'total': total},
            'challenger_share': share,
            'rating': {
                'challenger': self._rating(obj.challenger_rating_before,
                                           obj.challenger_delta),
                'opponent': self._rating(obj.opponent_rating_before,
                                         obj.opponent_delta),
            },
            'counted': total > 0,
        }


class CatRatingSerializer(serializers.ModelSerializer):
    cat_id = serializers.IntegerField(source='cat.id', read_only=True)
    cat_name = serializers.CharField(source='cat.name', read_only=True)
    owner = serializers.CharField(source='cat.owner.username',
                                  read_only=True)
    place = serializers.IntegerField(read_only=True)

    class Meta:
        model = CatRating
        fields = ('place', 'cat_id', 'cat_name', 'owner', 'rating', 'wins',
                  'losses', 'draws', 'duels_count')
