import base64
import binascii
import datetime as dt

import webcolors
from django.core.files.base import ContentFile
from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator, UniqueValidator

from .models import ACHIEVEMENT_MAX_LENGTH, Achievement, AchievementCat, Cat

MAX_CAT_AGE = 40
MAX_IMAGE_SIZE = 5 * 1024 * 1024


@extend_schema_field(OpenApiTypes.STR)
class Hex2NameColor(serializers.Field):
    """Принимает цвет в HEX (#FFFFFF), хранит и отдаёт название (white)."""

    def to_representation(self, value):
        return value

    def to_internal_value(self, data):
        try:
            return webcolors.hex_to_name(data)
        except (ValueError, TypeError):
            raise serializers.ValidationError('Для этого цвета нет имени.')


class Base64ImageField(serializers.ImageField):
    """Картинка в формате data:image/<ext>;base64,<данные>."""

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            header, imgstr = data.split(';base64,')
            ext = header.split('/')[-1]
            try:
                raw = base64.b64decode(imgstr)
            except (binascii.Error, ValueError):
                raise serializers.ValidationError(
                    'Некорректные данные изображения.')
            if len(raw) > MAX_IMAGE_SIZE:
                raise serializers.ValidationError(
                    'Размер изображения не должен превышать 5 МБ.')
            data = ContentFile(raw, name=f'cat.{ext}')
        return super().to_internal_value(data)


class AchievementSerializer(serializers.ModelSerializer):
    achievement_name = serializers.CharField(
        source='name', max_length=ACHIEVEMENT_MAX_LENGTH,
        validators=[UniqueValidator(
            queryset=Achievement.objects.all(),
            message='Такое достижение уже есть.',
        )],
    )

    class Meta:
        model = Achievement
        fields = ('id', 'achievement_name')


class CatAchievementSerializer(serializers.ModelSerializer):
    """Достижение внутри карточки котика: существующее подставляется,
    новое создаётся (поэтому без проверки уникальности)."""

    achievement_name = serializers.CharField(
        source='name', max_length=ACHIEVEMENT_MAX_LENGTH)

    class Meta:
        model = Achievement
        fields = ('id', 'achievement_name')


class CatSerializer(serializers.ModelSerializer):
    achievements = CatAchievementSerializer(many=True, required=False)
    color = Hex2NameColor()
    age = serializers.SerializerMethodField()
    image = Base64ImageField(required=False, allow_null=True)
    image_url = serializers.SerializerMethodField()
    owner = serializers.PrimaryKeyRelatedField(
        read_only=True, default=serializers.CurrentUserDefault())

    class Meta:
        model = Cat
        fields = ('id', 'name', 'color', 'birth_year', 'achievements',
                  'owner', 'age', 'image', 'image_url')
        validators = [
            UniqueTogetherValidator(
                queryset=Cat.objects.all(),
                fields=('name', 'owner'),
                message='У вас уже есть котик с такой кличкой.',
            ),
        ]

    def get_image_url(self, obj) -> str | None:
        return obj.image.url if obj.image else None

    def get_age(self, obj) -> int:
        return dt.date.today().year - obj.birth_year

    def validate_birth_year(self, value):
        year = dt.date.today().year
        if not (year - MAX_CAT_AGE < value <= year):
            raise serializers.ValidationError(
                f'Год рождения должен быть в диапазоне '
                f'{year - MAX_CAT_AGE + 1}–{year}.')
        return value

    def validate(self, data):
        name = data.get('name', getattr(self.instance, 'name', None))
        color = data.get('color', getattr(self.instance, 'color', None))
        if name and color and name.strip().lower() == color.lower():
            raise serializers.ValidationError(
                {'name': 'Кличка не может совпадать с цветом.'})
        return data

    @staticmethod
    def _set_achievements(cat, achievements):
        objs = [
            Achievement.objects.get_or_create(name=item['name'].strip())[0]
            for item in achievements
        ]
        AchievementCat.objects.filter(cat=cat).delete()
        AchievementCat.objects.bulk_create(
            AchievementCat(cat=cat, achievement=achievement)
            for achievement in {a.id: a for a in objs}.values()
        )

    @transaction.atomic
    def create(self, validated_data):
        achievements = validated_data.pop('achievements', None)
        cat = Cat.objects.create(**validated_data)
        if achievements:
            self._set_achievements(cat, achievements)
        return cat

    @transaction.atomic
    def update(self, instance, validated_data):
        achievements = validated_data.pop('achievements', None)
        instance = super().update(instance, validated_data)
        if achievements is not None:
            self._set_achievements(instance, achievements)
        return instance
