import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from cats.models import Cat

User = get_user_model()


@pytest.fixture(autouse=True)
def no_throttling(settings):
    rest = dict(settings.REST_FRAMEWORK)
    rest['DEFAULT_THROTTLE_RATES'] = {
        'anon': '10000/hour', 'user': '10000/hour',
        'duel_votes': '10000/hour',
    }
    settings.REST_FRAMEWORK = rest


@pytest.fixture
def make_user(db):
    def factory(username, is_staff=False):
        return User.objects.create_user(username=username,
                                        password='Str0ng-pass-123',
                                        is_staff=is_staff)
    return factory


@pytest.fixture
def client_for():
    def factory(user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client
    return factory


@pytest.fixture
def alice(make_user):
    return make_user('alice')


@pytest.fixture
def bob(make_user):
    return make_user('bob')


@pytest.fixture
def make_cat():
    def factory(owner, name, color='white', birth_year=2020):
        return Cat.objects.create(owner=owner, name=name, color=color,
                                  birth_year=birth_year)
    return factory
