# apps/companiesapp/permissions.py
from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class IsCompanyOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of a company to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner
        return obj.owner == request.user


class HasCompanyPermission(permissions.BasePermission):
    """
    Permission that checks if user has specific company-related permission.
    """

    def __init__(self, resource, action):
        self.resource = resource
        self.action = action

    def has_permission(self, request, view):
        return PermissionResolver.has_permission(
            request.user, self.resource, self.action
        )


class IsAdminOrCompanyOwner(permissions.BasePermission):
    """
    Allow access to admin users or company owners.
    """

    def has_object_permission(self, request, view, obj):
        # Check if user is admin
        if request.user.user_type == "admin":
            return True

        # Check if user is company owner
        return obj.owner == request.user


class CanManageCompanyDocuments(permissions.BasePermission):
    """
    Permission to manage company documents
    """

    def has_object_permission(self, request, view, obj):
        # Company owners can manage documents
        if obj.company.owner == request.user:
            return True

        # QueueMe admins can verify documents
        if request.method == "PATCH" and request.user.user_type == "admin":
            return True

        return False
