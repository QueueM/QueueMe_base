from django.apps import AppConfig


class QueueAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.queueapp"
    verbose_name = "Queue Management"

    def ready(self):
        pass
