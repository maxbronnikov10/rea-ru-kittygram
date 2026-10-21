"""Старт голосования и подведение итогов дуэли.

В формулу Эло вместо результата 1/0/0.5 подставляется доля голосов.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import CatRating, Duel

logger = logging.getLogger('duels')


def expected_score(rating_a, rating_b):
    """Ожидаемый результат котика A против котика B по формуле Эло."""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def rating_delta(rating_a, rating_b, score_a):
    """Изменение рейтинга котика A; изменение для B — с обратным знаком."""
    return round(settings.DUEL_ELO_K
                 * (score_a - expected_score(rating_a, rating_b)))


def start_duel(duel):
    duel.status = Duel.Status.ACTIVE
    duel.started_at = timezone.now()
    duel.ends_at = duel.started_at + timedelta(hours=duel.voting_hours)
    duel.save(update_fields=('status', 'started_at', 'ends_at'))


@transaction.atomic
def finish_duel(duel):
    """Подсчитывает голоса, определяет победителя и меняет рейтинги."""
    duel = Duel.objects.select_for_update().get(pk=duel.pk)
    if duel.status != Duel.Status.ACTIVE:
        return duel

    votes_a = duel.votes.filter(cat_id=duel.challenger_id).count()
    votes_b = duel.votes.filter(cat_id=duel.opponent_id).count()
    total = votes_a + votes_b

    rating_a, _ = CatRating.objects.select_for_update().get_or_create(
        cat_id=duel.challenger_id)
    rating_b, _ = CatRating.objects.select_for_update().get_or_create(
        cat_id=duel.opponent_id)

    duel.challenger_votes, duel.opponent_votes = votes_a, votes_b
    duel.challenger_rating_before = rating_a.rating
    duel.opponent_rating_before = rating_b.rating

    delta = 0  # без голосов дуэль не засчитывается
    if total:
        delta = rating_delta(rating_a.rating, rating_b.rating,
                             votes_a / total)
        rating_a.rating += delta
        rating_b.rating -= delta
        rating_a.duels_count += 1
        rating_b.duels_count += 1
        if votes_a > votes_b:
            duel.winner_id = duel.challenger_id
            rating_a.wins += 1
            rating_b.losses += 1
        elif votes_b > votes_a:
            duel.winner_id = duel.opponent_id
            rating_b.wins += 1
            rating_a.losses += 1
        else:
            rating_a.draws += 1
            rating_b.draws += 1
        rating_a.save()
        rating_b.save()

    duel.challenger_delta, duel.opponent_delta = delta, -delta
    duel.status = Duel.Status.FINISHED
    duel.finished_at = timezone.now()
    duel.save()
    logger.info('Дуэль %s завершена: %s:%s, Δ=%s', duel.pk, votes_a,
                votes_b, delta)
    return duel


def finish_expired_duels():
    """Завершает все дуэли, у которых истекло время голосования."""
    expired = Duel.objects.filter(status=Duel.Status.ACTIVE,
                                  ends_at__lte=timezone.now())
    return [finish_duel(duel) for duel in expired]
