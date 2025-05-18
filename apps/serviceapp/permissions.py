from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class ServicePermission(permissions.BasePermission):
    """
    Custom permission for services

    - Anyone can view active services
    - Only admins and shop staff can create/edit services
    - Only staff of the service's shop can edit that service
    """

    def has_permission(self, request, view):
        # Allow anyone to view services (list, retrieve)
        if request.method in permissions.SAFE_METHODS:
            return True

        # For other methods, user must be authenticated
        if not request.user.is_authenticated:
            return False

        # For creating services
        if view.action == "create":
            return PermissionResolver.has_permission(request.user, "service", "add")

        return True

    def has_object_permission(self, request, view, obj):
        # Allow anyone to view active services
        if request.method in permissions.SAFE_METHODS and obj.status == "active":
            return True

        # For other methods, user must be authenticated
        if not request.user.is_authenticated:
            return False

        # Admin can do anything
        if request.user.user_type == "admin":
            return True

        # Shop staff can edit their shop's services
        if view.action in ["update", "partial_update", "destroy"]:
            return PermissionResolver.has_shop_permission(
                request.user, obj.shop.id, "service", "edit"
            )

        # Shop staff can view all services in their shop
        if request.method in permissions.SAFE_METHODS:
            return PermissionResolver.has_shop_permission(
                request.user, obj.shop.id, "service", "view"
            )

        return False
