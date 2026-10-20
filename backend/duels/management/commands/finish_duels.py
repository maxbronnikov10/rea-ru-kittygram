from django.core.management.base import BaseCommand

from duels.services import finish_expired_duels


class Command(BaseCommand):
    help = 'Подводит итоги дуэлей, у которых истекло время голосования.'

    def handle(self, *args, **options):
        finished = finish_expired_duels()
        self.stdout.write(f'Завершено дуэлей: {len(finished)}')
