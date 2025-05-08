from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class StoriesAppConfig(AppConfig):
    name = "apps.storiesapp"
    verbose_name = _("Stories")

    def ready(self):
        pass
