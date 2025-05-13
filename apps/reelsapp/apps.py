from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ReelsAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reelsapp"
    verbose_name = _("Reels")

    def ready(self):
        # Import signals
        pass
