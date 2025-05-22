from functools import wraps

from rest_framework.exceptions import PermissionDenied

from apps.rolesapp.constants import PERMISSION_DENIED_MESSAGES
from apps.rolesapp.services.permission_resolver import PermissionResolver


def _get_user_from_args(args):
    """
    Helper to get user for both ViewSet methods (self) and standard API methods (self, request, ...)
    """
    if not args:
        return None
    # ViewSet method (e.g. get_queryset(self))
    if len(args) == 1:
        self = args[0]
        req = getattr(self, "request", None)
        if req is not None:
            return req.user
        return None
    # View method (e.g. get(self, request, ...))
    elif len(args) > 1:
        request = args[1]
        return getattr(request, "user", None)
    return None


def has_permission(resource, action):
    """
    Universal decorator to check if user has permission for resource/action.
    Works with both ViewSets and APIView methods.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(*args, **kwargs):
            user = _get_user_from_args(args)
            if not PermissionResolver.has_permission(user, resource, action):
                message = PERMISSION_DENIED_MESSAGES.get(
                    action, PERMISSION_DENIED_MESSAGES["default"]
                )
                raise PermissionDenied(message)
            return view_func(*args, **kwargs)

        return _wrapped_view

    return decorator


def has_context_permission(context_resource, context_param, resource, action):
    """
    Universal decorator for context permission.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(*args, **kwargs):
            user = _get_user_from_args(args)
            # Get context_id from kwargs, or query_params if request present
            context_id = kwargs.get(context_param)
            request = args[1] if len(args) > 1 else getattr(args[0], "request", None)
            if not context_id and request is not None:
                context_id = getattr(request, "query_params", {}).get(
                    context_param
                ) or getattr(request, "data", {}).get(context_param)
            if not context_id:
                raise PermissionDenied(f"Missing {context_param} parameter")
            if not PermissionResolver.has_context_permission(
                user, context_resource, context_id, resource, action
            ):
                message = PERMISSION_DENIED_MESSAGES.get(
                    action, PERMISSION_DENIED_MESSAGES["default"]
                )
                raise PermissionDenied(message)
            return view_func(*args, **kwargs)

        return _wrapped_view

    return decorator


def has_shop_permission(resource, action):
    """
    Universal decorator for shop-specific permission.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(*args, **kwargs):
            user = _get_user_from_args(args)
            # Try to get shop_id from kwargs, query_params, or request data
            shop_id = kwargs.get("shop_id")
            request = args[1] if len(args) > 1 else getattr(args[0], "request", None)
            if not shop_id and request is not None:
                shop_id = getattr(request, "query_params", {}).get(
                    "shop_id"
                ) or getattr(request, "data", {}).get("shop_id")
            if not shop_id:
                raise PermissionDenied("Shop ID not found in request")
            if not PermissionResolver.has_context_permission(
                user, "shop", shop_id, resource, action
            ):
                message = PERMISSION_DENIED_MESSAGES.get(
                    action, PERMISSION_DENIED_MESSAGES["default"]
                )
                raise PermissionDenied(message)
            return view_func(*args, **kwargs)

        return _wrapped_view

    return decorator


def is_queue_me_admin(view_func):
    """Decorator to check if user is a Queue Me Admin (universal)."""

    @wraps(view_func)
    def _wrapped_view(*args, **kwargs):
        user = _get_user_from_args(args)
        if not PermissionResolver.is_queue_me_admin(user):
            raise PermissionDenied("Only Queue Me Admins can perform this action.")
        return view_func(*args, **kwargs)

    return _wrapped_view


def is_queue_me_employee(view_func):
    """Decorator to check if user is a Queue Me Employee (universal)."""

    @wraps(view_func)
    def _wrapped_view(*args, **kwargs):
        user = _get_user_from_args(args)
        if not PermissionResolver.is_queue_me_employee(user):
            raise PermissionDenied("Only Queue Me Employees can perform this action.")
        return view_func(*args, **kwargs)

    return _wrapped_view


def has_role_type(allowed_roles):
    """
    Universal decorator to check if user has specific roles.
    """
    if not isinstance(allowed_roles, (list, tuple)):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(*args, **kwargs):
            user = _get_user_from_args(args)
            if not PermissionResolver.has_role_type(user, allowed_roles):
                role_names = ", ".join([role for role in allowed_roles])
                raise PermissionDenied(
                    f"Only users with roles [{role_names}] can perform this action."
                )
            return view_func(*args, **kwargs)

        return _wrapped_view

    return decorator
