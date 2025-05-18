from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class NotificationsAppConfig(AppConfig):
    name = "apps.notificationsapp"
    verbose_name = _("Notifications")

    def ready(self):
        pass
