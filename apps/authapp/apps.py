from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AuthAppConfig(AppConfig):
    name = "apps.authapp"
    verbose_name = _("Authentication")

    def ready(self):
        # Import signals to ensure they are registered
        pass
