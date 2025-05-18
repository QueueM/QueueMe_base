# apps/subscriptionapp/apps.py
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SubscriptionAppConfig(AppConfig):
    name = "apps.subscriptionapp"
    verbose_name = _("Subscription Management")

    def ready(self):
        pass
