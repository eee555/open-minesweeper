from django.apps import AppConfig


class SpeedrankingConfig(AppConfig):
    name = 'speedranking'

    def ready(self):
        import speedranking.pb_derived.signals  # noqa: F401
        import speedranking.signals  # noqa: F401
        import speedranking.top.signals  # noqa: F401
