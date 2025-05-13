from django.utils.translation import gettext_lazy as _
from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class CanManageReviews(permissions.BasePermission):
    """Permission to manage reviews"""

    message = _("You do not have permission to manage reviews")

    def has_permission(self, request, view):
        # Check if user has review management permission
        if request.method in permissions.SAFE_METHODS:
            # For read operations, anyone can view
            return True

        # Check for write operations
        return request.user.is_authenticated and PermissionResolver.has_permission(
            request.user, "review", "edit"
        )

    def has_object_permission(self, request, view, obj):
        # Always allow GET, HEAD, OPTIONS requests
        if request.method in permissions.SAFE_METHODS:
            return True

        # For write operations, check permissions
        if not request.user.is_authenticated:
            return False

        # Admin or staff can manage all reviews
        if PermissionResolver.has_permission(request.user, "review", "edit"):
            return True

        # Users can manage their own reviews
        if hasattr(obj, "user") and obj.user == request.user:
            return True

        # Shop managers can manage reviews for their shop
        if hasattr(obj, "shop"):
            # Check if user is shop manager or employee with review permission
            from apps.rolesapp.models import UserRole
            from apps.shopapp.models import Shop

            # Check if user is shop manager
            is_manager = Shop.objects.filter(id=obj.shop.id, manager=request.user).exists()

            if is_manager:
                return True

            # Check if user has role with review permission for this shop
            shop_roles = UserRole.objects.filter(user=request.user, role__shop=obj.shop)

            for user_role in shop_roles:
                if PermissionResolver.has_permission(request.user, "review", "edit"):
                    return True

        return False


class CanViewReviews(permissions.BasePermission):
    """Permission to view reviews"""

    def has_permission(self, request, view):
        # Everyone can view reviews
        return True


class CanReportReviews(permissions.BasePermission):
    """Permission to report inappropriate reviews"""

    def has_permission(self, request, view):
        # Must be authenticated to report reviews
        return request.user.is_authenticated


class CanVoteReviewHelpfulness(permissions.BasePermission):
    """Permission to vote on review helpfulness"""

    def has_permission(self, request, view):
        # Must be authenticated to vote
        return request.user.is_authenticated


class CanModerateReviews(permissions.BasePermission):
    """Permission to moderate reviews (approve/reject/etc.)"""

    message = _("You do not have permission to moderate reviews")

    def has_permission(self, request, view):
        # Check if user can moderate reviews
        return request.user.is_authenticated and PermissionResolver.has_permission(
            request.user, "review", "edit"
        )
