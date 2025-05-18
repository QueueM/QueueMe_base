from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class EmployeePermission(permissions.BasePermission):
    """
    Custom permission for employee management:
    - Shop managers can manage their own shop's employees
    - Company owners can manage all employees in their shops
    - Queue Me admins can manage all employees
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Queue Me admin or employee with proper permissions can access
        if request.user.user_type in ["admin"]:
            return True

        # For list and create, check if user has 'employee' resource permission
        if view.action in ["list", "create"]:
            return PermissionResolver.has_permission(
                request.user, "employee", "view" if view.action == "list" else "add"
            )

        return True  # Further checks in has_object_permission

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        # Queue Me admin can do anything
        if request.user.user_type == "admin":
            return True

        # Get required permission for this action
        if view.action in ["retrieve", "list"]:
            action = "view"
        elif view.action in ["update", "partial_update"]:
            action = "edit"
        elif view.action == "destroy":
            action = "delete"
        else:
            action = "view"

        # Check shop-specific permission
        return PermissionResolver.has_shop_permission(request.user, obj.shop.id, "employee", action)


class EmployeeWorkingHoursPermission(permissions.BasePermission):
    """Permission for employee working hours management"""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Queue Me admin or employee with proper permissions can access
        if request.user.user_type in ["admin"]:
            return True

        # For list and create, check if user has 'employee' resource permission
        if view.action in ["list", "create"]:
            return PermissionResolver.has_permission(
                request.user, "employee", "view" if view.action == "list" else "edit"
            )

        return True  # Further checks in has_object_permission

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        # Queue Me admin can do anything
        if request.user.user_type == "admin":
            return True

        # Get required permission for this action
        if view.action in ["retrieve", "list"]:
            action = "view"
        elif view.action in ["update", "partial_update", "destroy", "create"]:
            action = "edit"
        else:
            action = "view"

        # Check shop-specific permission for the employee's shop
        return PermissionResolver.has_shop_permission(
            request.user, obj.employee.shop.id, "employee", action
        )
