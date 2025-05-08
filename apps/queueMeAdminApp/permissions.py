from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class IsQueueMeAdmin(permissions.BasePermission):
    """
    Permission to check if the user is a Queue Me admin.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Check if the user is a superuser or has the Queue Me Admin role
        if request.user.is_superuser:
            return True

        # Delegate to permission resolver for more granular control
        return PermissionResolver.has_permission(request.user, "admin", "view")


class IsQueueMeSuperAdmin(permissions.BasePermission):
    """
    Permission to check if the user is a Queue Me super admin with full access.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Only superusers or those with explicit super admin permission
        if request.user.is_superuser:
            return True

        # Delegate to permission resolver for system level permissions
        return PermissionResolver.has_permission(request.user, "system", "manage")


class AdminPermission(permissions.BasePermission):
    """
    Fine-grained permission checks for admin actions.
    """

    def __init__(self, required_action, required_resource):
        self.required_action = required_action
        self.required_resource = required_resource

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Superusers have all permissions
        if request.user.is_superuser:
            return True

        # Check specific permission using the resolver
        return PermissionResolver.has_permission(
            request.user, self.required_resource, self.required_action
        )


class CanManageVerifications(permissions.BasePermission):
    """Permission to manage shop verifications"""

    def has_permission(self, request, view):
        return PermissionResolver.has_permission(request.user, "verification", "manage")


class CanManageSupportTickets(permissions.BasePermission):
    """Permission to manage support tickets"""

    def has_permission(self, request, view):
        return PermissionResolver.has_permission(request.user, "support", "manage")


class CanViewSystemMetrics(permissions.BasePermission):
    """Permission to view system performance metrics"""

    def has_permission(self, request, view):
        return PermissionResolver.has_permission(request.user, "metrics", "view")


class CanManageSystemSettings(permissions.BasePermission):
    """Permission to manage system settings"""

    def has_permission(self, request, view):
        return PermissionResolver.has_permission(request.user, "settings", "manage")


class CanViewAuditLogs(permissions.BasePermission):
    """Permission to view audit logs"""

    def has_permission(self, request, view):
        return PermissionResolver.has_permission(request.user, "audit", "view")
