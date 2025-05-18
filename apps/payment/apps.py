from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PaymentConfig(AppConfig):
    name = "apps.payment"
    verbose_name = _("Payment Processing")

    def ready(self):
        pass
