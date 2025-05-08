from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ReviewAppConfig(AppConfig):
    name = "apps.reviewapp"
    verbose_name = _("Reviews")

    def ready(self):
        pass
