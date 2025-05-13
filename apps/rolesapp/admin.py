# apps/rolesapp/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.rolesapp.models import Permission, Role, RolePermissionLog, UserRole


class PermissionAdmin(admin.ModelAdmin):
    """Admin configuration for Permission model"""

    list_display = ["code_name", "resource", "action", "description"]
    list_filter = ["resource", "action"]
    search_fields = ["code_name", "description"]
    ordering = ["resource", "action"]
    readonly_fields = ["code_name"]


class RolePermissionInline(admin.TabularInline):
    """Inline admin for Role-Permission relationship"""

    model = Role.permissions.through
    extra = 1
    verbose_name = _("Permission")
    verbose_name_plural = _("Permissions")


class UserRoleInline(admin.TabularInline):
    """Inline admin for User-Role relationship"""

    model = UserRole
    extra = 1
    verbose_name = _("User")
    verbose_name_plural = _("Users")


class RoleAdmin(admin.ModelAdmin):
    """Admin configuration for Role model"""

    list_display = [
        "name",
        "role_type",
        "entity_str",
        "weight",
        "is_active",
        "is_system",
        "user_count",
    ]
    list_filter = ["role_type", "is_active", "is_system", "content_type"]
    search_fields = ["name", "description"]
    ordering = ["-weight", "name"]
    readonly_fields = ["is_system"]
    inlines = [RolePermissionInline, UserRoleInline]
    exclude = ["permissions"]

    def entity_str(self, obj):
        """Display entity information"""
        if obj.entity:
            return str(obj.entity)
        return "-"

    entity_str.short_description = _("Entity")

    def user_count(self, obj):
        """Display count of users with this role"""
        return obj.user_roles.count()

    user_count.short_description = _("Users")


class UserRoleAdmin(admin.ModelAdmin):
    """Admin configuration for UserRole model"""

    list_display = ["user", "role", "is_primary", "assigned_at", "assigned_by"]
    list_filter = ["is_primary", "role__role_type"]
    search_fields = ["user__phone_number", "role__name"]
    ordering = ["-assigned_at"]
    raw_id_fields = ["user", "role", "assigned_by"]


class RolePermissionLogAdmin(admin.ModelAdmin):
    """Admin configuration for RolePermissionLog model"""

    list_display = ["role", "permission", "action_type", "performed_by", "timestamp"]
    list_filter = ["action_type", "timestamp", "role__role_type"]
    search_fields = [
        "role__name",
        "permission__code_name",
        "performed_by__phone_number",
    ]
    ordering = ["-timestamp"]
    raw_id_fields = ["role", "permission", "performed_by"]
    readonly_fields = ["timestamp"]


# Register models with admin site
admin.site.register(Permission, PermissionAdmin)
admin.site.register(Role, RoleAdmin)
admin.site.register(UserRole, UserRoleAdmin)
admin.site.register(RolePermissionLog, RolePermissionLogAdmin)
