# apps/rolesapp/middleware/permission_middleware.py
import logging
import re

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from apps.rolesapp.constants import PERMISSION_DENIED_MESSAGES
from apps.rolesapp.services.permission_resolver import PermissionResolver

logger = logging.getLogger(__name__)


class PermissionMiddleware(MiddlewareMixin):
    """
    Middleware for checking permissions

    This middleware checks if a user has permission to access a view
    based on URL patterns and resource mapping.
    """

    # URL pattern to resource/action mapping
    # Format: (regex_pattern, resource, action, context_field)
    URL_PATTERNS = [
        # Shop-related endpoints
        (r"^/api/shops/$", "shop", "view", None),
        (r"^/api/shops/(?P<pk>[^/.]+)/$", "shop", "view", None),
        (r"^/api/shops/create/$", "shop", "add", None),
        (r"^/api/shops/(?P<pk>[^/.]+)/edit/$", "shop", "edit", None),
        (r"^/api/shops/(?P<pk>[^/.]+)/delete/$", "shop", "delete", None),
        # Shop-specific service endpoints
        (
            r"^/api/shops/(?P<shop_id>[^/.]+)/services/$",
            "shop.service",
            "view",
            "shop_id",
        ),
        (
            r"^/api/shops/(?P<shop_id>[^/.]+)/services/create/$",
            "shop.service",
            "add",
            "shop_id",
        ),
        (
            r"^/api/shops/(?P<shop_id>[^/.]+)/services/(?P<pk>[^/.]+)/edit/$",
            "shop.service",
            "edit",
            "shop_id",
        ),
        # Global service endpoints
        (r"^/api/services/$", "service", "view", None),
        (r"^/api/services/(?P<pk>[^/.]+)/$", "service", "view", None),
        # Role-related endpoints
        (r"^/api/roles/$", "roles", "view", None),
        (r"^/api/roles/(?P<pk>[^/.]+)/$", "roles", "view", None),
        (r"^/api/roles/create/$", "roles", "add", None),
        (r"^/api/roles/(?P<pk>[^/.]+)/edit/$", "roles", "edit", None),
        # Add more patterns as needed
    ]

    # Exempted paths that bypass permission checks
    EXEMPT_PATHS = [
        r"^/admin/",
        r"^/api/auth/",
        r"^/api/docs/",
        r"^/api/guide/",
        r"^/api/developers/",
        r"^/api/support/",
        r"^/static/",
        r"^/media/",
    ]

    def process_request(self, request):
        """Check permissions for the request"""
        path = request.path

        # Skip for exempted paths
        for exempt_pattern in self.EXEMPT_PATHS:
            if re.match(exempt_pattern, path):
                return None

        # Skip if user is not authenticated
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return None

        # Skip for superuser
        if request.user.is_superuser:
            return None

        # Check permissions based on URL patterns
        for pattern, resource, action, context_field in self.URL_PATTERNS:
            match = re.match(pattern, path)
            if match:
                # Extract context ID from URL if applicable
                context_id = None
                if context_field and context_field in match.groupdict():
                    context_id = match.groupdict()[context_field]

                # Check permission
                has_permission = self._check_permission(
                    request.user, resource, action, context_id, context_field
                )

                if not has_permission:
                    message = PERMISSION_DENIED_MESSAGES.get(
                        action, PERMISSION_DENIED_MESSAGES["default"]
                    )
                    return JsonResponse({"detail": message}, status=403)

        return None

    def _check_permission(self, user, resource, action, context_id=None, context_field=None):
        """Check if user has permission for resource/action"""
        if "." in resource:
            # Handle format like "shop.service" where "shop" is the context resource
            context_resource, actual_resource = resource.split(".")

            if context_id:
                # Check context-specific permission
                return PermissionResolver.has_context_permission(
                    user, context_resource, context_id, actual_resource, action
                )
        elif context_id and context_field:
            # Check context-specific permission (direct)
            context_resource = context_field.split("_")[0]  # e.g., 'shop_id' -> 'shop'
            return PermissionResolver.has_context_permission(
                user, context_resource, context_id, resource, action
            )

        # Check global permission
        return PermissionResolver.has_permission(user, resource, action)
