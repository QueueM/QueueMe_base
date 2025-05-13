from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class QueueMeAdminAppConfig(AppConfig):
    name = "apps.queueMeAdminApp"
    verbose_name = _("Queue Me Admin")

    def ready(self):
        import apps.queueMeAdminApp.signals  # noqa
