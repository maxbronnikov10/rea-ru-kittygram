from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()

NAME_MAX_LENGTH = 16
ACHIEVEMENT_MAX_LENGTH = 64


class Achievement(models.Model):
    name = models.CharField('Название', max_length=ACHIEVEMENT_MAX_LENGTH,
                            unique=True)

    class Meta:
        verbose_name = 'достижение'
        verbose_name_plural = 'Достижения'
        ordering = ('name',)

    def __str__(self):
        return self.name


class Cat(models.Model):
    name = models.CharField('Кличка', max_length=NAME_MAX_LENGTH)
    color = models.CharField('Цвет', max_length=16)
    birth_year = models.PositiveSmallIntegerField('Год рождения')
    owner = models.ForeignKey(
        User, related_name='cats', on_delete=models.CASCADE,
        verbose_name='Хозяин',
    )
    achievements = models.ManyToManyField(
        Achievement, through='AchievementCat', related_name='cats',
        verbose_name='Достижения',
    )
    image = models.ImageField(
        'Фото', upload_to='cats/images/', null=True, blank=True,
        default=None,
    )

    class Meta:
        verbose_name = 'котик'
        verbose_name_plural = 'Котики'
        ordering = ('id',)
        constraints = [
            models.UniqueConstraint(
                fields=('name', 'owner'), name='unique_cat_name_owner',
            ),
        ]

    def __str__(self):
        return self.name


class AchievementCat(models.Model):
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE,
                                    verbose_name='Достижение')
    cat = models.ForeignKey(Cat, on_delete=models.CASCADE,
                            verbose_name='Котик')

    class Meta:
        verbose_name = 'достижение котика'
        verbose_name_plural = 'Достижения котиков'
        constraints = [
            models.UniqueConstraint(
                fields=('achievement', 'cat'),
                name='unique_achievement_cat',
            ),
        ]

    def __str__(self):
        return f'{self.achievement} {self.cat}'
