from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SpecialistsAppConfig(AppConfig):
    name = "apps.specialistsapp"
    verbose_name = _("Specialists")

    def ready(self):
        pass
