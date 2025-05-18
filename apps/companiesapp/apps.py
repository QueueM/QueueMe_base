# apps/companiesapp/apps.py
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CompaniesappConfig(AppConfig):
    name = "apps.companiesapp"
    verbose_name = _("Companies")

    def ready(self):
        pass
