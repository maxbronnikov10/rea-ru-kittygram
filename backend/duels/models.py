from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from cats.models import Cat

User = get_user_model()

MIN_VOTING_HOURS = 1
MAX_VOTING_HOURS = 72
MESSAGE_MAX_LENGTH = 200


class CatRating(models.Model):
    """Рейтинг Эло котика и его статистика дуэлей."""

    cat = models.OneToOneField(
        Cat, on_delete=models.CASCADE, primary_key=True,
        related_name='rating', verbose_name='Котик',
    )
    rating = models.IntegerField('Рейтинг',
                                 default=settings.DUEL_START_RATING)
    wins = models.PositiveIntegerField('Победы', default=0)
    losses = models.PositiveIntegerField('Поражения', default=0)
    draws = models.PositiveIntegerField('Ничьи', default=0)
    duels_count = models.PositiveIntegerField('Проведено дуэлей', default=0)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'рейтинг котика'
        verbose_name_plural = 'Рейтинги котиков'
        ordering = ('-rating', 'cat_id')

    def __str__(self):
        return f'{self.cat}: {self.rating}'


class Duel(models.Model):
    """Дуэль двух котиков разных хозяев."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Ждёт ответа соперника'
        ACTIVE = 'active', 'Идёт голосование'
        FINISHED = 'finished', 'Завершена'
        DECLINED = 'declined', 'Отклонена'
        CANCELLED = 'cancelled', 'Отменена'

    OPEN_STATUSES = (Status.PENDING, Status.ACTIVE)

    challenger = models.ForeignKey(
        Cat, on_delete=models.CASCADE, related_name='duels_as_challenger',
        verbose_name='Котик, бросивший вызов',
    )
    opponent = models.ForeignKey(
        Cat, on_delete=models.CASCADE, related_name='duels_as_opponent',
        verbose_name='Котик-соперник',
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='duels_created',
        verbose_name='Автор вызова',
    )
    message = models.CharField('Сообщение сопернику',
                               max_length=MESSAGE_MAX_LENGTH, blank=True)
    voting_hours = models.PositiveSmallIntegerField(
        'Длительность голосования, ч', default=24,
        validators=(MinValueValidator(MIN_VOTING_HOURS),
                    MaxValueValidator(MAX_VOTING_HOURS)),
    )
    status = models.CharField('Статус', max_length=10, choices=Status.choices,
                              default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    started_at = models.DateTimeField('Начало голосования', null=True,
                                      blank=True)
    ends_at = models.DateTimeField('Конец голосования', null=True,
                                   blank=True)
    finished_at = models.DateTimeField('Итоги подведены', null=True,
                                       blank=True)
    winner = models.ForeignKey(
        Cat, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='duels_won', verbose_name='Победитель',
    )
    challenger_votes = models.PositiveIntegerField(
        'Голоса за бросившего вызов', default=0)
    opponent_votes = models.PositiveIntegerField('Голоса за соперника',
                                                 default=0)
    challenger_rating_before = models.IntegerField(
        'Рейтинг бросившего вызов до итогов', null=True, blank=True)
    opponent_rating_before = models.IntegerField(
        'Рейтинг соперника до итогов', null=True, blank=True)
    challenger_delta = models.IntegerField(
        'Изменение рейтинга бросившего вызов', null=True, blank=True)
    opponent_delta = models.IntegerField('Изменение рейтинга соперника',
                                         null=True, blank=True)

    class Meta:
        verbose_name = 'дуэль'
        verbose_name_plural = 'Дуэли'
        ordering = ('-created_at', '-id')
        constraints = [
            models.CheckConstraint(
                condition=~Q(challenger=F('opponent')),
                name='duel_cats_differ',
            ),
            models.CheckConstraint(
                condition=Q(voting_hours__gte=MIN_VOTING_HOURS,
                            voting_hours__lte=MAX_VOTING_HOURS),
                name='duel_voting_hours_range',
            ),
        ]

    def __str__(self):
        return (f'{self.challenger} vs {self.opponent} '
                f'({self.get_status_display().lower()})')

    def has_cat(self, cat_id):
        return cat_id in (self.challenger_id, self.opponent_id)

    def is_participant(self, user):
        return user.id in (self.challenger.owner_id, self.opponent.owner_id)


class Vote(models.Model):
    """Голос пользователя в дуэли. Один пользователь — один голос."""

    duel = models.ForeignKey(Duel, on_delete=models.CASCADE,
                             related_name='votes', verbose_name='Дуэль')
    voter = models.ForeignKey(User, on_delete=models.CASCADE,
                              related_name='duel_votes',
                              verbose_name='Проголосовал')
    cat = models.ForeignKey(Cat, on_delete=models.CASCADE, related_name='+',
                            verbose_name='За котика')
    created_at = models.DateTimeField('Время голоса', auto_now_add=True)

    class Meta:
        verbose_name = 'голос'
        verbose_name_plural = 'Голоса'
        ordering = ('created_at',)
        constraints = [
            models.UniqueConstraint(fields=('duel', 'voter'),
                                    name='unique_vote_per_duel'),
        ]

    def __str__(self):
        return f'{self.voter} → {self.cat} ({self.duel_id})'
