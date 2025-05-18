from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class HasResourcePermission(permissions.BasePermission):
    """
    Permission class to check if a user has permission to access a resource

    This checks if the user has the required permission for the resource and action.
    It can be used with or without context (e.g., a specific shop).
    """

    def __init__(self, resource, action, context_field=None):
        """
        Initialize permission check

        Args:
            resource: The resource to check permission for (e.g., 'shop', 'service')
            action: The action to check permission for (e.g., 'view', 'add', 'edit')
            context_field: Optional field name to extract context object ID from URL kwargs
                        For example, if checking shop-specific permission, use 'shop_id'
        """
        self.resource = resource
        self.action = action
        self.context_field = context_field

    def has_permission(self, request, view):
        """Check if user has general permission"""
        user = request.user

        # Check for global permission first
        if PermissionResolver.has_permission(user, self.resource, self.action):
            return True

        # If context field is specified, check context-specific permission
        if self.context_field:
            context_id = view.kwargs.get(self.context_field) or request.query_params.get(
                self.context_field
            )

            if context_id:
                resource_parts = self.resource.split(".")
                if len(resource_parts) == 2:
                    # Handle format like "shop.service" where "shop" is the context resource
                    context_resource, actual_resource = resource_parts
                    return PermissionResolver.has_context_permission(
                        user, context_resource, context_id, actual_resource, self.action
                    )
                else:
                    # Direct context permission check
                    return PermissionResolver.has_context_permission(
                        user, "shop", context_id, self.resource, self.action
                    )

        return False

    def has_object_permission(self, request, view, obj):
        """Check if user has permission for specific object"""
        user = request.user

        # If object has a shop attribute, check shop-specific permission
        if hasattr(obj, "shop") and obj.shop:
            return PermissionResolver.has_context_permission(
                user, "shop", obj.shop.id, self.resource, self.action
            )

        # Check for object-specific permissions
        # This can be extended based on different types of objects
        return PermissionResolver.has_permission(user, self.resource, self.action)


class IsQueueMeAdmin(permissions.BasePermission):
    """Permission class to check if user is a Queue Me Admin"""

    message = "Only Queue Me Admins can perform this action."

    def has_permission(self, request, view):
        return PermissionResolver.is_queue_me_admin(request.user)


class IsQueueMeEmployee(permissions.BasePermission):
    """Permission class to check if user is a Queue Me Employee"""

    message = "Only Queue Me Employees can perform this action."

    def has_permission(self, request, view):
        return PermissionResolver.is_queue_me_employee(request.user)


class IsCompanyOwner(permissions.BasePermission):
    """Permission class to check if user is a Company Owner"""

    message = "Only Company Owners can perform this action."

    def has_permission(self, request, view):
        return PermissionResolver.is_company_owner(request.user)

    def has_object_permission(self, request, view, obj):
        # For company-owned objects
        if hasattr(obj, "company"):
            return PermissionResolver.is_company_owner_for(request.user, obj.company.id)

        # For shop-owned objects
        if hasattr(obj, "shop") and obj.shop and hasattr(obj.shop, "company"):
            return PermissionResolver.is_company_owner_for(request.user, obj.shop.company.id)

        return False


class IsShopManager(permissions.BasePermission):
    """Permission class to check if user is a Shop Manager"""

    message = "Only Shop Managers can perform this action."

    def has_permission(self, request, view):
        # For list views, check if user is any shop manager
        return PermissionResolver.is_shop_manager(request.user)

    def has_object_permission(self, request, view, obj):
        # For shop objects
        if hasattr(obj, "id") and getattr(obj, "__class__").__name__ == "Shop":
            return PermissionResolver.is_shop_manager_for(request.user, obj.id)

        # For shop-owned objects
        if hasattr(obj, "shop"):
            return PermissionResolver.is_shop_manager_for(request.user, obj.shop.id)

        return False


class HasRolePermission(permissions.BasePermission):
    """
    Permission class to check if a user has specific roles

    This is useful for allowing access to views based on roles rather than permissions.
    """

    def __init__(self, allowed_roles):
        """
        Initialize with allowed roles

        Args:
            allowed_roles: List of role types that are allowed to access
        """
        self.allowed_roles = (
            allowed_roles if isinstance(allowed_roles, (list, tuple)) else [allowed_roles]
        )

    def has_permission(self, request, view):
        """Check if user has any of the allowed roles"""
        user = request.user
        return PermissionResolver.has_role_type(user, self.allowed_roles)


# Add the previously missing IsAuthenticated class
class IsAuthenticated(permissions.BasePermission):
    """
    Allows access only to authenticated users.
    Similar to DRF's IsAuthenticated but can be extended with QueueMe-specific logic.
    """

    message = "Authentication is required to perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


# Add the previously missing IsShopStaffOrAdmin class
class IsShopStaffOrAdmin(permissions.BasePermission):
    """
    Permission class to check if user is shop staff or admin
    """

    message = "Only shop staff or admins can perform this action."

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        # Check if user is Queue Me admin
        if PermissionResolver.is_queue_me_admin(user):
            return True

        # Check if user has any shop staff role
        return PermissionResolver.is_shop_manager(user) or PermissionResolver.has_permission(
            user, "shop", "manage"
        )

    def has_object_permission(self, request, view, obj):
        user = request.user

        # QueueMe admins can access everything
        if PermissionResolver.is_queue_me_admin(user):
            return True

        # For shop objects
        shop_id = None
        if hasattr(obj, "id") and getattr(obj, "__class__").__name__ == "Shop":
            shop_id = obj.id
        # For shop-owned objects
        elif hasattr(obj, "shop") and obj.shop:
            shop_id = obj.shop.id

        if shop_id:
            return PermissionResolver.is_shop_manager_for(
                user, shop_id
            ) or PermissionResolver.has_context_permission(user, "shop", shop_id, "shop", "manage")

        return False


# Add the newly missing IsShopStaffOrReadOnly class
class IsShopStaffOrReadOnly(permissions.BasePermission):
    """
    Permission class that allows read-only access to anyone,
    but restricts write operations to shop staff (managers/owners).
    """

    message = "Only shop staff can modify this resource."

    def has_permission(self, request, view):
        # Allow GET, HEAD, OPTIONS requests for anyone
        if request.method in permissions.SAFE_METHODS:
            return True

        user = request.user
        if not user.is_authenticated:
            return False

        # Check if user is Queue Me admin
        if PermissionResolver.is_queue_me_admin(user):
            return True

        # Check if user has any shop staff role for write operations
        return PermissionResolver.is_shop_manager(user) or PermissionResolver.has_permission(
            user, "shop", "manage"
        )

    def has_object_permission(self, request, view, obj):
        # Allow read permissions for any request
        if request.method in permissions.SAFE_METHODS:
            return True

        user = request.user

        # QueueMe admins can access everything
        if PermissionResolver.is_queue_me_admin(user):
            return True

        # For shop objects
        shop_id = None
        if hasattr(obj, "id") and getattr(obj, "__class__").__name__ == "Shop":
            shop_id = obj.id
        # For shop-owned objects
        elif hasattr(obj, "shop") and obj.shop:
            shop_id = obj.shop.id

        if shop_id:
            return PermissionResolver.is_shop_manager_for(
                user, shop_id
            ) or PermissionResolver.has_context_permission(user, "shop", shop_id, "shop", "manage")

        return False
