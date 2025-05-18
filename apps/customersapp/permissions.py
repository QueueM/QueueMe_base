from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class IsCustomerOwner(permissions.BasePermission):
    """
    Permission to only allow owners of a customer profile to view or edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Check if the requesting user is the owner
        if hasattr(obj, "customer"):
            # For related models like preferences
            return obj.customer.user == request.user
        # For customer model directly
        return obj.user == request.user


class IsCustomerOrAdmin(permissions.BasePermission):
    """
    Permission to allow customer owners or admins with appropriate permissions
    """

    def has_permission(self, request, view):
        # Allow if user is a customer
        if request.user.user_type == "customer":
            return True

        # Check if admin/staff has proper permission
        return PermissionResolver.has_permission(request.user, "customer", "view")

    def has_object_permission(self, request, view, obj):
        # Allow if user is the customer
        if hasattr(obj, "customer"):
            if obj.customer.user == request.user:
                return True
        elif hasattr(obj, "user"):
            if obj.user == request.user:
                return True

        # Check if admin/staff has proper permission
        if request.method in permissions.SAFE_METHODS:
            return PermissionResolver.has_permission(request.user, "customer", "view")
        elif request.method == "DELETE":
            return PermissionResolver.has_permission(request.user, "customer", "delete")
        else:
            return PermissionResolver.has_permission(request.user, "customer", "edit")


class CanViewCustomerProfile(permissions.BasePermission):
    """
    Permission to view customer profiles based on role
    """

    def has_permission(self, request, view):
        # Customers can view their own profile
        if request.user.user_type == "customer":
            return True

        # Shop employees with customer management permission
        return PermissionResolver.has_permission(request.user, "customer", "view")

    def has_object_permission(self, request, view, obj):
        # Customer can only view their own profile
        if request.user.user_type == "customer":
            return obj.user == request.user

        # Shop employees with customer management permission
        return PermissionResolver.has_permission(request.user, "customer", "view")
