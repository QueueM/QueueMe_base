from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class IsShopManagerOrStaff(permissions.BasePermission):
    """
    Permission to only allow shop managers or staff with appropriate permissions.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Get shop ID from URL
        shop_id = view.kwargs.get("shop_id")
        if not shop_id:
            return False

        # Check if user has permission for this shop
        return PermissionResolver.has_shop_permission(user, shop_id, "reel", "view")


class CanManageReels(permissions.BasePermission):
    """
    Permission to allow users with reel management permissions for a shop.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Get shop ID from URL
        shop_id = view.kwargs.get("shop_id")
        if not shop_id:
            return False

        # Check action-specific permissions
        if view.action == "create":
            return PermissionResolver.has_shop_permission(user, shop_id, "reel", "add")

        if view.action in ["update", "partial_update", "publish", "archive"]:
            return PermissionResolver.has_shop_permission(user, shop_id, "reel", "edit")

        if view.action == "destroy":
            return PermissionResolver.has_shop_permission(user, shop_id, "reel", "delete")

        # Default to view permission for other actions
        return PermissionResolver.has_shop_permission(user, shop_id, "reel", "view")

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Ensure the reel belongs to the shop in the URL
        shop_id = view.kwargs.get("shop_id")
        if obj.shop.id != shop_id:
            return False

        # Check action-specific permissions
        if view.action in ["update", "partial_update", "publish", "archive"]:
            return PermissionResolver.has_shop_permission(user, shop_id, "reel", "edit")

        if view.action == "destroy":
            return PermissionResolver.has_shop_permission(user, shop_id, "reel", "delete")

        # Default to view permission for other actions
        return PermissionResolver.has_shop_permission(user, shop_id, "reel", "view")
