from django.apps import AppConfig


class MedalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'medal'

    def ready(self):
        import medal.signals  # noqa: F401
