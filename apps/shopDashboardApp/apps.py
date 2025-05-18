from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ShopDashboardAppConfig(AppConfig):
    name = "apps.shopDashboardApp"
    verbose_name = _("Shop Dashboard")

    def ready(self):
        pass
