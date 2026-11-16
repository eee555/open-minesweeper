from django.apps import AppConfig


class TournamentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tournament'

    def ready(self):
        import tournament.signals  # noqa: F401 - 信号注册需要
        import tournament.gsc.signals  # noqa: F401 - 信号注册需要
        import tournament.weekly.signals  # noqa: F401 - 信号注册需要
        import tournament.weekly_eff.signals  # noqa: F401 - 信号注册需要
