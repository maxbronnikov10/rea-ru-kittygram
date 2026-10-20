from django.db.models.signals import post_save
from django.dispatch import receiver

from cats.models import Cat

from .models import CatRating


@receiver(post_save, sender=Cat)
def create_cat_rating(sender, instance, created, **kwargs):
    """Каждый новый котик получает стартовый рейтинг."""
    if created:
        CatRating.objects.get_or_create(cat=instance)
