from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class PackagePermission(permissions.BasePermission):
    """
    Permission class for Package resource access.
    - Shop managers and employees with the right permissions can manage packages
    - Any authenticated user can view active packages
    """

    def has_permission(self, request, view):
        # Allow listing and viewing for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated

        # For write operations, check specific permissions
        if view.action in ["create", "update", "partial_update", "destroy"]:
            # Check if user has the appropriate permission for the action
            action_map = {
                "create": "add",
                "update": "edit",
                "partial_update": "edit",
                "destroy": "delete",
            }

            return PermissionResolver.has_permission(
                request.user, "package", action_map.get(view.action, "edit")
            )

        return False

    def has_object_permission(self, request, view, obj):
        # Any authenticated user can view active packages
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated

        # For write operations, check specific permissions and shop association
        shop_id = obj.shop.id

        action_map = {"update": "edit", "partial_update": "edit", "destroy": "delete"}

        return PermissionResolver.has_shop_permission(
            request.user, shop_id, "package", action_map.get(view.action, "edit")
        )


class PackageFAQPermission(permissions.BasePermission):
    """
    Permission class for Package FAQ resource access.
    """

    def has_permission(self, request, view):
        # Allow viewing for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated

        # For write operations, check specific permissions
        action_map = {
            "create": "add",
            "update": "edit",
            "partial_update": "edit",
            "destroy": "delete",
        }

        return PermissionResolver.has_permission(
            request.user, "package", action_map.get(view.action, "edit")
        )

    def has_object_permission(self, request, view, obj):
        # Any authenticated user can view FAQs
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated

        # For write operations, check specific permissions and shop association
        shop_id = obj.package.shop.id

        action_map = {"update": "edit", "partial_update": "edit", "destroy": "delete"}

        return PermissionResolver.has_shop_permission(
            request.user, shop_id, "package", action_map.get(view.action, "edit")
        )
