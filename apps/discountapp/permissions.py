# apps/discountapp/permissions.py
from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class IsShopManagerOrAdmin(permissions.BasePermission):
    """
    Permission to only allow shop managers or admins
    """

    def has_permission(self, request, view):
        user = request.user

        # Queue Me Admin has permission
        if user.is_staff or user.is_superuser:
            return True

        # Check if user is a shop manager
        return PermissionResolver.has_permission(user, "discount", "view")

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Queue Me Admin has permission
        if user.is_staff or user.is_superuser:
            return True

        # Shop managers can only manage their own shops
        shop = getattr(obj, "shop", None)
        if not shop:
            return False

        # Check if user is manager of this shop
        user_shops = PermissionResolver.get_user_shops(user)
        return shop in user_shops


class IsShopManagerOrAdminOrReadOnly(permissions.BasePermission):
    """
    Permission to allow read-only access, but only shop managers or admins can modify
    """

    def has_permission(self, request, view):
        # Allow GET, HEAD, OPTIONS requests for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated

        user = request.user

        # Queue Me Admin has permission
        if user.is_staff or user.is_superuser:
            return True

        # Check if user is a shop manager
        return PermissionResolver.has_permission(user, "discount", "edit")

    def has_object_permission(self, request, view, obj):
        # Allow GET, HEAD, OPTIONS requests for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True

        user = request.user

        # Queue Me Admin has permission
        if user.is_staff or user.is_superuser:
            return True

        # Shop managers can only manage their own shops
        shop = getattr(obj, "shop", None)
        if not shop:
            return False

        # Check if user is manager of this shop
        user_shops = PermissionResolver.get_user_shops(user)
        return shop in user_shops


class CanManageDiscounts(permissions.BasePermission):
    """
    Permission to allow users who can manage discounts
    """

    def has_permission(self, request, view):
        user = request.user

        # Queue Me Admin has permission
        if user.is_staff or user.is_superuser:
            return True

        # Check if user has discount management permission
        return PermissionResolver.has_permission(user, "discount", "add")
