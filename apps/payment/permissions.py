from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class PaymentPermission(permissions.BasePermission):
    """
    Custom permission for payment-related views
    """

    def has_permission(self, request, view):
        # Allow customers to view their own payment methods and initiate payments
        if request.user.user_type == "customer":
            if view.action in [
                "list",
                "retrieve",
                "create",
                "payment_methods",
                "add_payment_method",
                "set_default_payment_method",
            ]:
                return True

        # Allow shop managers and employees with appropriate permissions
        if request.user.user_type in ["employee", "admin"]:
            if view.action in ["list", "retrieve"]:
                return PermissionResolver.has_permission(
                    request.user, "payment", "view"
                )
            elif view.action in ["create_refund"]:
                return PermissionResolver.has_permission(
                    request.user, "payment", "edit"
                )

        # QueueMe admin and employees with appropriate role can do anything
        if request.user.user_type == "admin":
            return PermissionResolver.has_permission(request.user, "payment", "view")

        return False

    def has_object_permission(self, request, view, obj):
        # Customers can only access their own payment records
        if request.user.user_type == "customer":
            return obj.user == request.user

        # Shop managers and employees can access payments related to their shop
        if request.user.user_type in ["employee", "admin"]:
            # For transactions linked to bookings, check if booking is with user's shop
            if hasattr(obj, "content_object") and hasattr(obj.content_object, "shop"):
                shop = obj.content_object.shop
                return PermissionResolver.has_shop_permission(
                    request.user, str(shop.id), "payment", "view"
                )

        # QueueMe admin can view all
        if request.user.user_type == "admin":
            return PermissionResolver.has_permission(request.user, "payment", "view")

        return False
