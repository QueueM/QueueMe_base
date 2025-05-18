from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ShopAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.shopapp"
    verbose_name = _("Shop Management")

    def ready(self):
        pass
