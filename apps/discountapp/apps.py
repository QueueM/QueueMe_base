# apps/discountapp/apps.py
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DiscountappConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.discountapp"
    verbose_name = _("Discounts & Coupons")

    def ready(self):
        pass
