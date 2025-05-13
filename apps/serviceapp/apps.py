from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ServiceAppConfig(AppConfig):
    name = "apps.serviceapp"
    verbose_name = _("Services")

    def ready(self):
        pass
