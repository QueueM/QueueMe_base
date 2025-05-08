from rest_framework import permissions

from apps.employeeapp.models import Employee
from apps.rolesapp.services.permission_resolver import PermissionResolver


class CanAccessChatPermission(permissions.BasePermission):
    """
    Permission check for chat access.

    Customers can only access their own conversations.
    Employees can only access conversations related to their shop.
    Employees must have 'chat' 'view' permission.
    """

    def has_permission(self, request, view):
        user = request.user

        if user.user_type == "customer":
            # Customers automatically have permission (will be filtered to their own chats)
            return True
        else:
            # For employees, check chat permission
            return PermissionResolver.has_permission(user, "chat", "view")

    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.user_type == "customer":
            # Customer can only access their own conversations
            if hasattr(obj, "customer"):
                # If it's a Conversation
                return obj.customer == user
            elif hasattr(obj, "conversation"):
                # If it's a Message
                return obj.conversation.customer == user
            return False
        else:
            # For employees, check if they belong to the shop
            try:
                employee = Employee.objects.get(user=user)

                # Check if the conversation is for their shop
                if hasattr(obj, "shop"):
                    # If it's a Conversation
                    conversation_shop_id = obj.shop.id
                elif hasattr(obj, "conversation"):
                    # If it's a Message
                    conversation_shop_id = obj.conversation.shop.id
                else:
                    return False

                # Check shop match and permission
                return (
                    employee.shop.id == conversation_shop_id
                    and PermissionResolver.has_permission(user, "chat", "view")
                )
            except Employee.DoesNotExist:
                return False
