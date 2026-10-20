from django.apps import AppConfig


class DuelsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'duels'
    verbose_name = 'Кото-дуэли'

    def ready(self):
        from . import signals  # noqa: F401
