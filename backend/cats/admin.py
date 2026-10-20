from django.contrib import admin

from .models import Achievement, AchievementCat, Cat


class AchievementCatInline(admin.TabularInline):
    model = AchievementCat
    extra = 0


@admin.register(Cat)
class CatAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'color', 'birth_year', 'owner')
    list_filter = ('color',)
    search_fields = ('name', 'owner__username')
    inlines = (AchievementCatInline,)


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
