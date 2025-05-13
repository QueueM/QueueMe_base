from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CustomersConfig(AppConfig):
    name = "apps.customersapp"
    verbose_name = _("Customers")

    def ready(self):
        import apps.customersapp.signals  # noqa
