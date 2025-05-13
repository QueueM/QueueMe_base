from functools import wraps

from rest_framework.exceptions import PermissionDenied

from apps.rolesapp.constants import PERMISSION_DENIED_MESSAGES
from apps.rolesapp.services.permission_resolver import PermissionResolver


def has_permission(resource, action):
    """
    Decorator to check if user has permission to access resource

    This decorator can be used on view methods to check permissions.

    Args:
        resource: The resource to check permission for (e.g., 'shop', 'service')
        action: The action to check permission for (e.g., 'view', 'add', 'edit')

    Returns:
        Decorator function that raises PermissionDenied if user doesn't have permission

    Example:
        @has_permission('shop', 'view')
        def get(self, request, *args, **kwargs):
            # This will only execute if user has permission to view shops
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(view, request, *args, **kwargs):
            user = request.user

            if not PermissionResolver.has_permission(user, resource, action):
                message = PERMISSION_DENIED_MESSAGES.get(
                    action, PERMISSION_DENIED_MESSAGES["default"]
                )
                raise PermissionDenied(message)

            return view_func(view, request, *args, **kwargs)

        return _wrapped_view

    return decorator


def has_context_permission(context_resource, context_param, resource, action):
    """
    Decorator to check if user has permission for a resource in a specific context

    This is useful for shop-specific permissions or other contextual permissions.

    Args:
        context_resource: The context resource type (e.g., 'shop', 'company')
        context_param: The URL parameter name that contains the context ID (e.g., 'shop_id')
        resource: The resource to check permission for (e.g., 'service', 'employee')
        action: The action to check permission for (e.g., 'view', 'add', 'edit')

    Returns:
        Decorator function that raises PermissionDenied if user doesn't have permission

    Example:
        @has_context_permission('shop', 'shop_id', 'service', 'add')
        def post(self, request, *args, **kwargs):
            # This will only execute if user has permission to add services to the specific shop
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(view, request, *args, **kwargs):
            user = request.user

            # Get context ID from URL kwargs or query params
            context_id = kwargs.get(context_param) or request.query_params.get(context_param)

            if not context_id:
                raise PermissionDenied(f"Missing {context_param} parameter")

            if not PermissionResolver.has_context_permission(
                user, context_resource, context_id, resource, action
            ):
                message = PERMISSION_DENIED_MESSAGES.get(
                    action, PERMISSION_DENIED_MESSAGES["default"]
                )
                raise PermissionDenied(message)

            return view_func(view, request, *args, **kwargs)

        return _wrapped_view

    return decorator


def has_shop_permission(resource, action):
    """
    Decorator to check if user has shop-specific permission for a resource

    Args:
        resource: The resource to check permission for (e.g., 'queue', 'service')
        action: The action to check permission for (e.g., 'view', 'add', 'edit')

    Returns:
        Decorator function that raises PermissionDenied if user doesn't have permission

    Example:
        @has_shop_permission('queue', 'view')
        def get(self, request, *args, **kwargs):
            # This will only execute if user has permission to view queues in the shop
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(view, request, *args, **kwargs):
            user = request.user

            # Try to get shop_id from URL kwargs, query params, or request data
            shop_id = (
                kwargs.get("shop_id")
                or request.query_params.get("shop_id")
                or request.data.get("shop_id")
            )

            if not shop_id:
                raise PermissionDenied("Shop ID not found in request")

            if not PermissionResolver.has_context_permission(
                user, "shop", shop_id, resource, action
            ):
                message = PERMISSION_DENIED_MESSAGES.get(
                    action, PERMISSION_DENIED_MESSAGES["default"]
                )
                raise PermissionDenied(message)

            return view_func(view, request, *args, **kwargs)

        return _wrapped_view

    return decorator


def is_queue_me_admin(view_func):
    """Decorator to check if user is a Queue Me Admin"""

    @wraps(view_func)
    def _wrapped_view(view, request, *args, **kwargs):
        user = request.user

        if not PermissionResolver.is_queue_me_admin(user):
            raise PermissionDenied("Only Queue Me Admins can perform this action.")

        return view_func(view, request, *args, **kwargs)

    return _wrapped_view


def is_queue_me_employee(view_func):
    """Decorator to check if user is a Queue Me Employee"""

    @wraps(view_func)
    def _wrapped_view(view, request, *args, **kwargs):
        user = request.user

        if not PermissionResolver.is_queue_me_employee(user):
            raise PermissionDenied("Only Queue Me Employees can perform this action.")

        return view_func(view, request, *args, **kwargs)

    return _wrapped_view


def has_role_type(allowed_roles):
    """
    Decorator to check if user has specific roles

    Args:
        allowed_roles: List of role types that are allowed to access
    """
    if not isinstance(allowed_roles, (list, tuple)):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(view, request, *args, **kwargs):
            user = request.user

            if not PermissionResolver.has_role_type(user, allowed_roles):
                role_names = ", ".join([role for role in allowed_roles])
                raise PermissionDenied(
                    f"Only users with roles [{role_names}] can perform this action."
                )

            return view_func(view, request, *args, **kwargs)

        return _wrapped_view

    return decorator
