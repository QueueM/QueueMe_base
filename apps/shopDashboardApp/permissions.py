from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class HasShopDashboardPermission(permissions.BasePermission):
    """
    Permission check for shop dashboard access.
    User must have view permission for the shop dashboard.
    """

    def has_permission(self, request, view):
        return PermissionResolver.has_permission(request.user, "dashboard", "view")

    def has_object_permission(self, request, view, obj):
        # Get shop ID from the object
        shop_id = None

        if hasattr(obj, "shop_id"):
            shop_id = obj.shop_id
        elif hasattr(obj, "layout") and hasattr(obj.layout, "shop_id"):
            shop_id = obj.layout.shop_id

        if not shop_id:
            return False

        if request.method in permissions.SAFE_METHODS:
            # Check read permissions
            return PermissionResolver.has_shop_permission(
                request.user, shop_id, "dashboard", "view"
            )

        # Check write permissions
        return PermissionResolver.has_shop_permission(request.user, shop_id, "dashboard", "edit")


class CanManageScheduledReports(permissions.BasePermission):
    """
    Permission check for managing scheduled reports.
    User must have permission to manage reports.
    """

    def has_permission(self, request, view):
        return PermissionResolver.has_permission(request.user, "report", "view")

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            # Check read permissions
            return PermissionResolver.has_shop_permission(
                request.user, obj.shop_id, "report", "view"
            )

        # Check write permissions
        return PermissionResolver.has_shop_permission(request.user, obj.shop_id, "report", "edit")


class CanManageDashboardSettings(permissions.BasePermission):
    """
    Permission check for managing dashboard settings.
    User must be shop manager or have dashboard settings permission.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return PermissionResolver.has_permission(request.user, "dashboard", "view")

        return PermissionResolver.has_permission(request.user, "dashboard", "edit")

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            # Check read permissions
            return PermissionResolver.has_shop_permission(
                request.user, obj.shop_id, "dashboard", "view"
            )

        # Check write permissions
        return PermissionResolver.has_shop_permission(
            request.user, obj.shop_id, "dashboard", "edit"
        )
