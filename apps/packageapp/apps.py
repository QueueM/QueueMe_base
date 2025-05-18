from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PackageAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.packageapp"
    verbose_name = _("Service Packages")

    def ready(self):
        # Import signal handlers
        pass
