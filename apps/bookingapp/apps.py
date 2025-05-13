# apps/bookingapp/apps.py
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BookingAppConfig(AppConfig):
    name = "apps.bookingapp"
    verbose_name = _("Booking Management")

    def ready(self):
        pass
