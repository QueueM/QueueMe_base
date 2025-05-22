from django.apps import AppConfig


class MarketingAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.marketingapp"
    verbose_name = "Marketing and Advertisements"

    def ready(self):
        try:
            pass
        except ImportError:
            pass
