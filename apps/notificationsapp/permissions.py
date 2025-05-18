from rest_framework import permissions


class IsNotificationOwner(permissions.BasePermission):
    """
    Permission to only allow owners of a notification to view or modify it.
    """

    def has_object_permission(self, request, view, obj):
        # Only allow if the notification belongs to the user
        return obj.user == request.user


class IsDeviceTokenOwner(permissions.BasePermission):
    """
    Permission to only allow owners of a device token to view or modify it.
    """

    def has_object_permission(self, request, view, obj):
        # Only allow if the device token belongs to the user
        return obj.user == request.user
