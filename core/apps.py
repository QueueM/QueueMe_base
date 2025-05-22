from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        """
        Called when Django app registry is fully loaded
        """
        # We don't need to import monkey_patches here since we want it loaded early
