from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class IsShopManager(permissions.BasePermission):
    """
    Custom permission to only allow shop managers to access their shops.
    """

    def has_object_permission(self, request, view, obj):
        # Check if user is the shop manager
        return obj.manager == request.user


class HasShopPermission(permissions.BasePermission):
    """
    Check if user has permission for shop-specific operations.
    """

    def has_permission(self, request, view):
        # For list endpoint, check if user has general shop view permission
        return PermissionResolver.has_permission(request.user, "shop", "view")

    def has_object_permission(self, request, view, obj):
        action_map = {
            "retrieve": "view",
            "update": "edit",
            "partial_update": "edit",
            "destroy": "delete",
        }
        action = action_map.get(view.action, "view")

        # Check if user has permission for this shop
        return PermissionResolver.has_shop_permission(
            request.user, obj.id if hasattr(obj, "id") else obj.shop.id, "shop", action
        )


class CanManageShopHours(permissions.BasePermission):
    """
    Permission to manage shop hours.
    """

    def has_permission(self, request, view):
        shop_id = view.kwargs.get("shop_id")

        if not shop_id:
            return False

        action = "view"
        if request.method in ["POST", "PUT", "PATCH"]:
            action = "edit"
        elif request.method == "DELETE":
            action = "delete"

        return PermissionResolver.has_shop_permission(request.user, shop_id, "shop", action)

    def has_object_permission(self, request, view, obj):
        action = "view"
        if request.method in ["PUT", "PATCH"]:
            action = "edit"
        elif request.method == "DELETE":
            action = "delete"

        return PermissionResolver.has_shop_permission(request.user, obj.shop.id, "shop", action)


class CanViewShopFollowers(permissions.BasePermission):
    """
    Permission to view shop followers.
    """

    def has_permission(self, request, view):
        shop_id = view.kwargs.get("shop_id")

        if not shop_id:
            return False

        return PermissionResolver.has_shop_permission(request.user, shop_id, "shop", "view")


class CanVerifyShops(permissions.BasePermission):
    """
    Permission to verify shops - limited to Queue Me admins.
    """

    def has_permission(self, request, view):
        return PermissionResolver.has_permission(request.user, "shop", "edit")
