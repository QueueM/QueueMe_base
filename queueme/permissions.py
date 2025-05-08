"""
Global permission classes for Queue Me platform.

This module defines permission classes that can be used across different apps
to enforce consistent access control based on user roles and specific permissions.
"""

from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class HasResourcePermission(permissions.BasePermission):
    """
    Permission class that checks if user has permission for a specific resource and action.

    Usage:
        class MyViewSet(viewsets.ModelViewSet):
            permission_classes = [HasResourcePermission]
            resource = 'booking'  # Resource name

            def get_permissions(self):
                if self.action == 'list':
                    return [HasResourcePermission(action='view')]
                elif self.action == 'create':
                    return [HasResourcePermission(action='add')]
                # ... etc.
    """

    def __init__(self, resource=None, action=None):
        self.resource = resource
        self.action = action

    def has_permission(self, request, view):
        # Default to using view's resource/action attributes if not provided in constructor
        resource = self.resource or getattr(view, "resource", None)

        # Map DRF actions to permission actions
        action_map = {
            "list": "view",
            "retrieve": "view",
            "create": "add",
            "update": "edit",
            "partial_update": "edit",
            "destroy": "delete",
        }

        # Use provided action or map from view.action
        action = self.action or action_map.get(getattr(view, "action", None), None)

        # If resource or action is not defined, deny permission
        if not resource or not action:
            return False

        # Check permission using the PermissionResolver service
        return PermissionResolver.has_permission(request.user, resource, action)

    def has_object_permission(self, request, view, obj):
        # Object-level permission checks
        resource = self.resource or getattr(view, "resource", None)

        # Map DRF actions to permission actions
        action_map = {
            "retrieve": "view",
            "update": "edit",
            "partial_update": "edit",
            "destroy": "delete",
        }

        # Use provided action or map from view.action
        action = self.action or action_map.get(getattr(view, "action", None), None)

        # If resource or action is not defined, deny permission
        if not resource or not action:
            return False

        # Check for shop-specific permissions if object has shop attribute
        if hasattr(obj, "shop_id") and obj.shop_id:
            return PermissionResolver.has_shop_permission(
                request.user, obj.shop_id, resource, action
            )

        # Regular permission check if no shop association
        return PermissionResolver.has_permission(request.user, resource, action)


class IsAdminUser(permissions.BasePermission):
    """
    Permission class for Queue Me admin users.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.user_type == "admin"
        )


class IsShopUser(permissions.BasePermission):
    """
    Permission class for shop employees and managers.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return request.user.user_type == "employee"

    def has_object_permission(self, request, view, obj):
        # Check if user is associated with the shop
        if not hasattr(obj, "shop_id"):
            return False

        from apps.employeeapp.models import Employee

        try:
            # Check if user is an employee of this shop
            employee = Employee.objects.get(user=request.user)
            return employee.shop_id == obj.shop_id
        except Employee.DoesNotExist:
            return False


class IsCustomerUser(permissions.BasePermission):
    """
    Permission class for customer users.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.user_type == "customer"
        )

    def has_object_permission(self, request, view, obj):
        # Check if this object belongs to the customer
        if hasattr(obj, "customer_id"):
            return obj.customer_id == request.user.id

        # For user object itself
        if hasattr(obj, "id") and obj._meta.model_name == "user":
            return obj.id == request.user.id

        return False


class SubscriptionActivePermission(permissions.BasePermission):
    """
    Permission class that checks if the user's shop has an active subscription.
    Used to restrict access to certain features based on subscription status.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Admin users bypass subscription check
        if request.user.user_type == "admin":
            return True

        # For employee users, check subscription
        if request.user.user_type == "employee":
            from apps.employeeapp.models import Employee
            from apps.subscriptionapp.models import Subscription

            try:
                # Get employee record
                employee = Employee.objects.select_related("shop__company").get(
                    user=request.user
                )

                # Check if company has active subscription
                active_subscription = Subscription.objects.filter(
                    company=employee.shop.company, status="active"
                ).exists()

                return active_subscription
            except Employee.DoesNotExist:
                return False

        # Customers don't need subscriptions
        if request.user.user_type == "customer":
            return True

        return False
