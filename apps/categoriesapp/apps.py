from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CategoriesappConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.categoriesapp"
    verbose_name = _("Categories")

    def ready(self):
        """
        Import signals when app is ready
        """
