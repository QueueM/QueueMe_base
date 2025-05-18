from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class FollowappConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.followapp"
    verbose_name = _("Follow Management")

    def ready(self):
        # Import signals to register them
        pass
