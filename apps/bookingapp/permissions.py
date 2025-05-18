# apps/bookingapp/permissions.py
from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class AppointmentPermission(permissions.BasePermission):
    """
    Permission class for appointments with different rules for different user types.

    - Customers can only view and modify their own appointments
    - Staff can view and modify appointments for their shop
    - Admins have full access
    """

    def has_permission(self, request, view):
        # unused_unused_user = request.user

        # Allow list and create for all authenticated users
        if view.action in ["list", "create"]:
            return True

        # Allow retrieve, update, partial_update, destroy with object-level permissions
        if view.action in [
            "retrieve",
            "update",
            "partial_update",
            "destroy",
            "cancel",
            "reschedule",
        ]:
            return True

        return False

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Customers can only access their own appointments
        if user.user_type == "customer":
            return obj.customer == user

        # Check permissions for shop employees/managers
        if user.user_type == "employee":
            # First check if the user is associated with the shop
            if hasattr(obj, "shop"):
                # Get employee for this user
                from apps.employeeapp.models import Employee

                try:
                    employee = Employee.objects.get(user=user)
                    if employee.shop != obj.shop:
                        return False
                except Employee.DoesNotExist:
                    return False

                # Check if user has permission for the appointment
                if view.action in ["retrieve", "list"]:
                    return PermissionResolver.has_permission(user, "booking", "view")
                elif view.action in ["update", "partial_update"]:
                    return PermissionResolver.has_permission(user, "booking", "edit")
                elif view.action == "destroy":
                    return PermissionResolver.has_permission(user, "booking", "delete")
                elif view.action == "cancel":
                    return PermissionResolver.has_permission(user, "booking", "edit")
                elif view.action == "reschedule":
                    return PermissionResolver.has_permission(user, "booking", "edit")

                return False

        # Queue Me admins can do anything
        if user.user_type == "admin":
            return True

        return False


class MultiServiceBookingPermission(permissions.BasePermission):
    """Permission class for multi-service bookings"""

    def has_permission(self, request, view):
        # unused_unused_user = request.user

        # Allow list and create for all authenticated users
        if view.action in ["list", "create"]:
            return True

        # Allow retrieve with object-level permissions
        if view.action in ["retrieve"]:
            return True

        return False

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Customers can only access their own bookings
        if user.user_type == "customer":
            return obj.customer == user

        # Check permissions for shop employees/managers
        if user.user_type == "employee":
            # First check if the user is associated with the shop
            if hasattr(obj, "shop"):
                # Get employee for this user
                from apps.employeeapp.models import Employee

                try:
                    employee = Employee.objects.get(user=user)
                    if employee.shop != obj.shop:
                        return False
                except Employee.DoesNotExist:
                    return False

                # Check if user has permission
                if view.action in ["retrieve", "list"]:
                    return PermissionResolver.has_permission(user, "booking", "view")

                return False

        # Queue Me admins can do anything
        if user.user_type == "admin":
            return True

        return False
