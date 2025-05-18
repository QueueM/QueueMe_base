from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ReportAnalyticsConfig(AppConfig):
    name = "apps.reportanalyticsapp"
    verbose_name = _("Report Analytics")

    def ready(self):
        pass
