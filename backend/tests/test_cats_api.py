import datetime as dt

import pytest
from rest_framework.authtoken.models import Token

from cats.models import Achievement, Cat

pytestmark = pytest.mark.django_db

YEAR = dt.date.today().year


def test_anonymous_cannot_list_cats(client_for):
    response = client_for().get('/api/cats/')
    assert response.status_code == 401


def test_register_and_get_token(client_for):
    client = client_for()
    response = client.post('/api/users/', {'username': 'murka_fan',
                                           'password': 'Str0ng-pass-123'})
    assert response.status_code == 201
    response = client.post('/api/token/login/', {
        'username': 'murka_fan', 'password': 'Str0ng-pass-123'})
    assert response.status_code == 200
    token = response.json()['auth_token']
    assert Token.objects.filter(key=token).exists()
    client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
    assert client.get('/api/users/me/').json()['username'] == 'murka_fan'


def test_create_cat_sets_owner_from_token(client_for, alice, bob):
    response = client_for(alice).post('/api/cats/', {
        'name': 'Барсик', 'color': '#FFFFFF', 'birth_year': 2020,
        'owner': bob.id,
        'achievements': [{'achievement_name': 'поймал муху'}],
    }, format='json')
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data['owner'] == alice.id
    assert data['color'] == 'white'
    assert data['age'] == YEAR - 2020
    assert data['achievements'][0]['achievement_name'] == 'поймал муху'


@pytest.mark.parametrize('payload, field', [
    ({'birth_year': YEAR + 1}, 'birth_year'),
    ({'birth_year': YEAR - 45}, 'birth_year'),
    ({'color': '#123456'}, 'color'),
    ({'name': 'White'}, 'name'),
])
def test_cat_validation(client_for, alice, payload, field):
    body = {'name': 'Пушок', 'color': '#FFFFFF', 'birth_year': 2019}
    body.update(payload)
    response = client_for(alice).post('/api/cats/', body, format='json')
    assert response.status_code == 400
    assert field in response.json()


def test_duplicate_cat_name_for_same_owner(client_for, alice, make_cat):
    make_cat(alice, 'Пушок')
    response = client_for(alice).post('/api/cats/', {
        'name': 'Пушок', 'color': '#000000', 'birth_year': 2019})
    assert response.status_code == 400
    assert 'non_field_errors' in response.json()


def test_only_owner_can_change_cat(client_for, alice, bob, make_cat):
    cat = make_cat(alice, 'Мурзик')
    url = f'/api/cats/{cat.id}/'
    assert client_for(bob).patch(url, {'name': 'Чужой'}).status_code == 403
    assert client_for(bob).delete(url).status_code == 403
    assert client_for(bob).get(url).status_code == 200
    response = client_for(alice).patch(url, {'name': 'Мурзик II'})
    assert response.status_code == 200
    assert client_for(alice).delete(url).status_code == 204
    assert client_for(alice).get(url).status_code == 404


def test_pagination_filters_search_ordering(client_for, alice, bob,
                                            make_cat):
    for i in range(12):
        make_cat(alice, f'Кот{i:02}', color='black' if i % 2 else 'white',
                 birth_year=2010 + i)
    make_cat(bob, 'Борис', color='gray', birth_year=2015)
    client = client_for(alice)

    page2 = client.get('/api/cats/?page=2').json()
    assert page2['count'] == 13 and len(page2['results']) == 3

    assert len(client.get('/api/cats/?page_size=5').json()['results']) == 5
    assert client.get('/api/cats/?color=black').json()['count'] == 6
    assert client.get(
        '/api/cats/?birth_year_min=2018&birth_year_max=2020'
    ).json()['count'] == 3
    assert client.get('/api/cats/?search=Бор').json()['count'] == 1
    assert client.get('/api/cats/?mine=false').json()['count'] == 1
    first = client.get('/api/cats/?ordering=-birth_year').json()['results'][0]
    assert first['birth_year'] == 2021


def test_achievements(client_for, alice, make_user):
    client = client_for(alice)
    response = client.post('/api/achievements/',
                           {'achievement_name': 'спит 20 часов'})
    assert response.status_code == 201
    assert isinstance(client.get('/api/achievements/').json(), list)
    duplicate = client.post('/api/achievements/',
                            {'achievement_name': 'спит 20 часов'})
    assert duplicate.status_code == 400
    achievement_id = response.json()['id']
    url = f'/api/achievements/{achievement_id}/'
    assert client.patch(url, {'achievement_name': 'x'}).status_code == 403
    admin = client_for(make_user('admin', is_staff=True))
    assert admin.delete(url).status_code == 204
    assert not Achievement.objects.exists()


def test_cat_detail_not_found(client_for, alice):
    response = client_for(alice).get('/api/cats/999/')
    assert response.status_code == 404
    assert response.json() == {'detail': 'Объект не найден.'}
    assert not Cat.objects.exists()
