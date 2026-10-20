from django.contrib import admin

from .models import CatRating, Duel, Vote


class VoteInline(admin.TabularInline):
    model = Vote
    extra = 0


@admin.register(Duel)
class DuelAdmin(admin.ModelAdmin):
    list_display = ('id', 'challenger', 'opponent', 'status', 'ends_at',
                    'winner')
    list_filter = ('status',)
    search_fields = ('challenger__name', 'opponent__name')
    inlines = (VoteInline,)


@admin.register(CatRating)
class CatRatingAdmin(admin.ModelAdmin):
    list_display = ('cat', 'rating', 'wins', 'losses', 'draws',
                    'duels_count')
    ordering = ('-rating',)


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'duel', 'voter', 'cat', 'created_at')
