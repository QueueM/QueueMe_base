# apps/subscriptionapp/permissions.py
from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class CanViewSubscriptions(permissions.BasePermission):
    """Permission to view subscriptions"""

    def has_permission(self, request, view):
        return PermissionResolver.has_permission(request.user, "subscription", "view")


class CanManageSubscriptions(permissions.BasePermission):
    """Permission to manage subscriptions (CRUD)"""

    def has_permission(self, request, view):
        # Check if user is from Queue Me Admin (only admin can manage subscriptions)
        if request.method == "GET":
            return PermissionResolver.has_permission(
                request.user, "subscription", "view"
            )

        if request.method == "POST":
            return PermissionResolver.has_permission(
                request.user, "subscription", "add"
            )

        if request.method in ["PUT", "PATCH"]:
            return PermissionResolver.has_permission(
                request.user, "subscription", "edit"
            )

        if request.method == "DELETE":
            return PermissionResolver.has_permission(
                request.user, "subscription", "delete"
            )

        return False


class CanViewOwnCompanySubscription(permissions.BasePermission):
    """Permission for company to view their own subscription"""

    def has_permission(self, request, view):
        # Company owners and managers can view their own subscription
        if request.user.user_type != "employee":
            return False

        # Check if user is linked to a company
        from apps.employeeapp.models import Employee

        try:
            employee = Employee.objects.get(user=request.user)
            # Check if employee is a manager or has subscription view permission
            is_manager = employee.position == "manager"
            has_permission = PermissionResolver.has_permission(
                request.user, "subscription", "view"
            )
            return is_manager or has_permission
        except Employee.DoesNotExist:
            return False

    def has_object_permission(self, request, view, obj):
        # Check if subscription belongs to user's company
        from apps.employeeapp.models import Employee

        try:
            employee = Employee.objects.get(user=request.user)
            return obj.company == employee.shop.company
        except (Employee.DoesNotExist, AttributeError):
            return False


class CanManageOwnCompanySubscription(permissions.BasePermission):
    """Permission for company to manage their own subscription"""

    def has_permission(self, request, view):
        # Company owners and managers can manage their own subscription
        if request.user.user_type != "employee":
            return False

        # Check if user is linked to a company
        from apps.employeeapp.models import Employee

        try:
            employee = Employee.objects.get(user=request.user)
            # Only managers can manage subscription
            return employee.position == "manager"
        except Employee.DoesNotExist:
            return False

    def has_object_permission(self, request, view, obj):
        # Check if subscription belongs to user's company
        from apps.employeeapp.models import Employee

        try:
            employee = Employee.objects.get(user=request.user)
            return obj.company == employee.shop.company
        except (Employee.DoesNotExist, AttributeError):
            return False
