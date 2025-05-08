from rest_framework import permissions


class IsFollowOwner(permissions.BasePermission):
    """
    Custom permission to only allow customers to manage their own follows.
    """

    def has_object_permission(self, request, view, obj):
        # Only allow the customer who created the follow to modify it
        return obj.customer == request.user


class CanViewFollowers(permissions.BasePermission):
    """
    Permission to determine if a user can view a shop's followers.
    Shop owners/managers can view their shop's followers.
    """

    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True

        # Check if requesting shop followers
        shop_id = view.kwargs.get("shop_id")
        if not shop_id:
            return False

        # Check if user is shop manager/employee
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        return PermissionResolver.has_shop_permission(
            request.user, shop_id, "shop", "view"
        )
