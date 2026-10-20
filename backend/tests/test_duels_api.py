from datetime import timedelta

import pytest
from django.utils import timezone

from duels.models import CatRating, Duel
from duels.services import expected_score, rating_delta

pytestmark = pytest.mark.django_db


@pytest.fixture
def cats(alice, bob, make_cat):
    return make_cat(alice, 'Барсик'), make_cat(bob, 'Мурка')


@pytest.fixture
def duel(client_for, alice, cats):
    barsik, murka = cats
    response = client_for(alice).post('/api/duels/', {
        'challenger': barsik.id, 'opponent': murka.id, 'voting_hours': 24,
        'message': 'Чья шерсть пушистее?'})
    assert response.status_code == 201, response.json()
    assert response.json()['votes_total'] == 0
    return Duel.objects.get(pk=response.json()['id'])


def expire(duel):
    Duel.objects.filter(pk=duel.pk).update(
        ends_at=timezone.now() - timedelta(minutes=1))


def test_elo_math():
    assert expected_score(1000, 1000) == 0.5
    assert rating_delta(1000, 1000, 1.0) == 16
    assert rating_delta(1000, 1000, 0.7) == 6
    assert rating_delta(1200, 1000, 0.5) < 0


def test_new_cat_gets_start_rating(cats):
    assert CatRating.objects.get(cat=cats[0]).rating == 1000


def test_full_duel_flow(client_for, alice, bob, make_user, cats, duel):
    barsik, murka = cats
    assert duel.status == Duel.Status.PENDING

    accept = client_for(bob).post(f'/api/duels/{duel.id}/accept/')
    assert accept.status_code == 200
    assert accept.json()['status'] == 'active'

    voters = [make_user(f'voter{i}') for i in range(5)]
    for voter, cat in zip(voters, [barsik, barsik, barsik, barsik, murka]):
        response = client_for(voter).post(f'/api/duels/{duel.id}/vote/',
                                          {'cat': cat.id})
        assert response.status_code == 201, response.json()

    detail = client_for(voters[0]).get(f'/api/duels/{duel.id}/').json()
    assert detail['votes_total'] == 5 and detail['my_vote'] == barsik.id
    hidden = client_for(alice).get(f'/api/duels/{duel.id}/results/')
    assert hidden.status_code == 400

    early = client_for(alice).post(f'/api/duels/{duel.id}/finish/')
    assert early.status_code == 400

    expire(duel)
    finish = client_for(alice).post(f'/api/duels/{duel.id}/finish/')
    assert finish.status_code == 200
    result = finish.json()
    assert result['winner'] == barsik.id
    assert result['result']['votes'] == {'challenger': 4, 'opponent': 1,
                                         'total': 5}
    assert result['result']['rating']['challenger']['delta'] == 10

    assert CatRating.objects.get(cat=barsik).rating == 1010
    assert CatRating.objects.get(cat=murka).rating == 990
    board = client_for().get('/api/ratings/').json()['results']
    assert board[0]['cat_name'] == 'Барсик' and board[0]['place'] == 1
    murka_rating = client_for().get(f'/api/ratings/{murka.id}/').json()
    assert murka_rating['losses'] == 1 and murka_rating['place'] == 2


def test_unrated_cats_have_no_place(client_for, make_user, make_cat, cats,
                                    duel, bob):
    newbie = make_cat(make_user('newbie'), 'Новичок')
    rating = client_for().get(f'/api/ratings/{newbie.id}/').json()
    assert rating['place'] is None and rating['rating'] == 1000


def test_duel_without_votes_is_not_counted(client_for, bob, duel, cats):
    client_for(bob).post(f'/api/duels/{duel.id}/accept/')
    expire(duel)
    result = client_for(bob).post(f'/api/duels/{duel.id}/finish/').json()
    assert result['result']['counted'] is False
    assert CatRating.objects.get(cat=cats[0]).duels_count == 0


@pytest.mark.parametrize('who', ['challenger_owner', 'stranger'])
def test_only_opponent_owner_answers(client_for, alice, make_user, duel,
                                     who):
    user = alice if who == 'challenger_owner' else make_user('eve')
    response = client_for(user).post(f'/api/duels/{duel.id}/accept/')
    assert response.status_code == 403


def test_cancel_rules(client_for, alice, bob, duel):
    assert client_for(bob).post(
        f'/api/duels/{duel.id}/cancel/').status_code == 403
    assert client_for(alice).post(
        f'/api/duels/{duel.id}/cancel/').json()['status'] == 'cancelled'
    response = client_for(bob).post(f'/api/duels/{duel.id}/accept/')
    assert response.status_code == 400


def test_create_validation(client_for, alice, bob, make_cat, cats, duel):
    barsik, murka = cats
    client = client_for(alice)
    own_second = make_cat(alice, 'Снежок')
    cases = [
        {'challenger': murka.id, 'opponent': barsik.id},
        {'challenger': barsik.id, 'opponent': own_second.id},
        {'challenger': barsik.id, 'opponent': murka.id},
        {'challenger': own_second.id, 'opponent': murka.id,
         'voting_hours': 100},
    ]
    for body in cases:
        assert client.post('/api/duels/', body).status_code == 400, body


def test_open_duels_limit(client_for, alice, make_user, make_cat, cats):
    barsik = cats[0]
    client = client_for(alice)
    for i in range(3):
        rival = make_cat(make_user(f'rival{i}'), f'Соперник{i}')
        assert client.post('/api/duels/', {
            'challenger': barsik.id, 'opponent': rival.id}).status_code == 201
    extra = make_cat(make_user('rival9'), 'Лишний')
    response = client.post('/api/duels/', {'challenger': barsik.id,
                                           'opponent': extra.id})
    assert response.status_code == 400


def test_vote_rules(client_for, alice, bob, make_user, make_cat, duel, cats):
    url = f'/api/duels/{duel.id}/vote/'
    voter = client_for(make_user('voter'))
    assert voter.post(url, {'cat': cats[0].id}).status_code == 400
    client_for(bob).post(f'/api/duels/{duel.id}/accept/')
    assert client_for(alice).post(url, {'cat': cats[1].id}).status_code == 400
    stranger_cat = make_cat(make_user('carl'), 'Чужак')
    assert voter.post(url, {'cat': stranger_cat.id}).status_code == 400
    assert voter.post(url, {'cat': cats[0].id}).status_code == 201
    assert voter.post(url, {'cat': cats[1].id}).status_code == 400


def test_duel_filters(client_for, alice, bob, make_user, make_cat, cats,
                      duel):
    carl = make_user('carl')
    other = make_cat(carl, 'Тигр')
    client_for(carl).post('/api/duels/', {'challenger': other.id,
                                          'opponent': cats[1].id})
    bob_client = client_for(bob)
    assert bob_client.get('/api/duels/?incoming=true').json()['count'] == 2
    assert client_for(alice).get('/api/duels/?mine=true').json()['count'] == 1
    assert bob_client.get(
        f'/api/duels/?cat={other.id}').json()['count'] == 1
    page = bob_client.get('/api/duels/?limit=1&offset=1').json()
    assert page['count'] == 2 and len(page['results']) == 1
    assert bob_client.get('/api/duels/?status=active').json()['count'] == 0
