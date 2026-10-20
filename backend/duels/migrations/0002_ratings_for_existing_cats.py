from django.db import migrations


def create_ratings(apps, schema_editor):
    """Стартовый рейтинг для котиков, добавленных до появления дуэлей."""
    Cat = apps.get_model('cats', 'Cat')
    CatRating = apps.get_model('duels', 'CatRating')
    existing = set(CatRating.objects.values_list('cat_id', flat=True))
    CatRating.objects.bulk_create(
        CatRating(cat_id=cat_id)
        for cat_id in Cat.objects.values_list('id', flat=True)
        if cat_id not in existing
    )


class Migration(migrations.Migration):

    dependencies = [
        ('duels', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_ratings, migrations.RunPython.noop),
    ]
