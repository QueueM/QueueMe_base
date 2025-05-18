from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class GeoAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.geoapp"
    verbose_name = _("Geographic Information")

    def ready(self):
        pass
