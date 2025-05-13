# apps/rolesapp/apps.py
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RolesappConfig(AppConfig):
    """Configuration for rolesapp"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.rolesapp"
    verbose_name = _("Roles and Permissions")

    def ready(self):
        """
        Initialize app when Django starts

        This:
        1. Imports signal handlers
        2. Creates default permissions and roles
        """
        # Create default permissions if app is migrated
        from django.db import connection

        tables = connection.introspection.table_names()
        if "rolesapp_permission" in tables:
            # Only run this if the database is ready and tables exist
            # This prevents errors during initial migrations
            from apps.rolesapp.services.permission_service import PermissionService

            PermissionService.create_default_permissions()
