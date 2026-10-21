"""Демо-данные для показа проекта: пользователи, котики, дуэли.

    python manage.py seed_demo --password <пароль>

Повторный запуск ничего не дублирует.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from cats.models import Achievement, AchievementCat, Cat
from duels.models import Duel, Vote
from duels.services import finish_duel, start_duel

User = get_user_model()

CATS = [
    # хозяин, кличка, цвет, год, достижения
    ('anna', 'Барсик', 'white', 2019, ['поймал муху', 'спит 20 часов']),
    ('anna', 'Снежок', 'gainsboro', 2022, ['открыл холодильник']),
    ('boris', 'Мурка', 'black', 2018, ['поймала мышь']),
    ('boris', 'Рыжик', 'darkorange', 2021, ['съел огурец']),
    ('vera', 'Пушок', 'burlywood', 2020, ['спит 20 часов']),
    ('vera', 'Тиша', 'gray', 2017, []),
]
USERS = ['anna', 'boris', 'vera', 'gleb', 'dima']


class Command(BaseCommand):
    help = 'Создаёт демо-пользователей, котиков и дуэли.'

    def add_arguments(self, parser):
        parser.add_argument('--password', default='Kittygram-2026',
                            help='Пароль для демо-пользователей')

    def handle(self, *args, **options):
        users = {}
        for name in USERS:
            user, created = User.objects.get_or_create(username=name)
            if created:
                user.set_password(options['password'])
                user.save()
            users[name] = user

        cats = {}
        for owner, name, color, year, achievements in CATS:
            cat, _ = Cat.objects.get_or_create(
                owner=users[owner], name=name,
                defaults={'color': color, 'birth_year': year})
            for title in achievements:
                achievement, _ = Achievement.objects.get_or_create(name=title)
                AchievementCat.objects.get_or_create(cat=cat,
                                                     achievement=achievement)
            cats[name] = cat

        if not Duel.objects.exists():
            self._finished(users, cats['Барсик'], cats['Мурка'],
                           [('vera', 'Барсик'), ('gleb', 'Барсик'),
                            ('dima', 'Мурка')])
            self._finished(users, cats['Пушок'], cats['Рыжик'],
                           [('anna', 'Пушок'), ('gleb', 'Пушок'),
                            ('dima', 'Пушок')])
            active = Duel.objects.create(
                challenger=cats['Снежок'], opponent=cats['Тиша'],
                author=users['anna'], voting_hours=24,
                message='Кто из нас пушистее?')
            start_duel(active)
            Vote.objects.create(duel=active, voter=users['gleb'],
                                cat=cats['Снежок'])
            Duel.objects.create(
                challenger=cats['Рыжик'], opponent=cats['Барсик'],
                author=users['boris'], voting_hours=12,
                message='Реванш за Мурку!')

        self.stdout.write(self.style.SUCCESS(
            f'Готово: пользователей {User.objects.count()}, '
            f'котиков {Cat.objects.count()}, дуэлей {Duel.objects.count()}. '
            f'Пароль демо-пользователей: {options["password"]}'))

    @staticmethod
    def _finished(users, challenger, opponent, votes):
        duel = Duel.objects.create(
            challenger=challenger, opponent=opponent,
            author=challenger.owner, voting_hours=24)
        start_duel(duel)
        for voter, cat_name in votes:
            cat = challenger if cat_name == challenger.name else opponent
            Vote.objects.create(duel=duel, voter=users[voter], cat=cat)
        # Голосование «прошло» вчера: сдвигаем даты дуэли в прошлое.
        now = timezone.now()
        Duel.objects.filter(pk=duel.pk).update(
            created_at=now - timedelta(hours=26),
            started_at=now - timedelta(hours=25),
            ends_at=now - timedelta(hours=1))
        finish_duel(duel)
