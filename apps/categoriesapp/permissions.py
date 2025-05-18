from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class CategoryPermission(permissions.BasePermission):
    """
    Custom permission for Category objects:
    - Read operations (list, retrieve) allowed for anyone
    - Write operations (create, update, delete) restricted to admin users or those
      with specific category permissions
    """

    def has_permission(self, request, view):
        # Allow all GET requests (list, retrieve, etc.)
        if request.method in permissions.SAFE_METHODS:
            return True

        # For POST, PUT, PATCH, DELETE:
        user = request.user

        # Check if user is authenticated
        if not user or not user.is_authenticated:
            return False

        # Superuser always has permission
        if user.is_superuser:
            return True

        # Check if user is Queue Me Admin or has the appropriate permission
        if user.user_type == "admin":
            return True

        # Check specific category permissions based on action
        if view.action == "create":
            return PermissionResolver.has_permission(user, "category", "add")
        elif view.action in ["update", "partial_update", "move", "reorder"]:
            return PermissionResolver.has_permission(user, "category", "edit")
        elif view.action == "destroy":
            return PermissionResolver.has_permission(user, "category", "delete")
        else:
            # For custom actions, default to checking for edit permission
            return PermissionResolver.has_permission(user, "category", "edit")

    def has_object_permission(self, request, view, obj):
        # Allow all GET requests
        if request.method in permissions.SAFE_METHODS:
            return True

        # For POST, PUT, PATCH, DELETE:
        user = request.user

        # Check if user is authenticated
        if not user or not user.is_authenticated:
            return False

        # Superuser always has permission
        if user.is_superuser:
            return True

        # Check if user is Queue Me Admin or has the appropriate permission
        if user.user_type == "admin":
            return True

        # Check specific category permissions based on action
        if view.action in ["update", "partial_update"]:
            return PermissionResolver.has_permission(user, "category", "edit")
        elif view.action == "destroy":
            return PermissionResolver.has_permission(user, "category", "delete")
        else:
            # For custom actions, default to checking for edit permission
            return PermissionResolver.has_permission(user, "category", "edit")
