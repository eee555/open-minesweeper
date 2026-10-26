from django.contrib import admin

from .models import MiniGameBestScore


@admin.register(MiniGameBestScore)
class MiniGameBestScoreAdmin(admin.ModelAdmin):
    list_display = ['player', 'ranking_key', 'score', 'achieved_at']
    list_filter = ['ranking_key']
    search_fields = ['player__username', '=player__id']
    readonly_fields = ['player', 'ranking_key', 'score', 'achieved_at', 'replay_archive']

    def get_queryset(self, request):
        return super().get_queryset(request).defer('replay_archive')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
