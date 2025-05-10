from rest_framework import permissions

from apps.rolesapp.services.permission_resolver import PermissionResolver


class CanViewSpecialist(permissions.BasePermission):
    """
    Permission to check if user can view specialist details.
    Customers can view active specialists from active shops.
    Staff can view specialists from their own shop.
    """

    def has_permission(self, request, view):
        user = request.user

        # Admins and Queue Me employees with proper permissions can always view
        if PermissionResolver.has_permission(user, "specialist", "view"):
            return True

        return True  # Public endpoint for listing/viewing specialists

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Admins and Queue Me employees with proper permissions can always view
        if PermissionResolver.has_permission(user, "specialist", "view"):
            return True

        # Shop managers and employees can view specialists from their shop
        if user.user_type in ["employee", "admin"]:
            try:
                employee = user.employee
                return employee.shop_id == obj.employee.shop_id
            except Exception:
                pass

        # For customers, specialist must be active and from active shop
        if obj.employee.is_active and obj.employee.shop.is_active:
            return True

        return False


class CanManageSpecialist(permissions.BasePermission):
    """
    Permission to check if user can manage specialist details.
    Only shop managers, admins, or users with specialist permissions can manage.
    """

    def has_permission(self, request, view):
        user = request.user

        # Check if user has specialist management permission
        if PermissionResolver.has_permission(user, "specialist", "edit"):
            return True

        # Shop ID from URL or query param
        shop_id = view.kwargs.get("shop_id") or request.query_params.get("shop_id")

        if shop_id:
            # Check if user has permission for this shop
            return PermissionResolver.has_shop_permission(
                user, shop_id, "specialist", "edit"
            )

        return False

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Check if user has specialist management permission
        if PermissionResolver.has_permission(user, "specialist", "edit"):
            return True

        # Shop managers and HR can manage specialists from their shop
        if user.user_type in ["employee", "admin"]:
            try:
                employee = user.employee
                if employee.shop_id == obj.employee.shop_id:
                    # Check if user has shop-specific permission
                    return PermissionResolver.has_shop_permission(
                        user, str(employee.shop_id), "specialist", "edit"
                    )
            except Exception:
                pass

        return False


class CanVerifySpecialist(permissions.BasePermission):
    """
    Permission to check if user can verify specialists.
    Only Queue Me admins or employees with verification permissions can verify.
    """

    def has_permission(self, request, view):
        return PermissionResolver.has_permission(request.user, "specialist", "verify")

    def has_object_permission(self, request, view, obj):
        return PermissionResolver.has_permission(request.user, "specialist", "verify")


class CanManagePortfolio(permissions.BasePermission):
    """
    Permission to check if user can manage portfolio items.
    Only the specialist themselves, shop managers, or admins can manage.
    """

    def has_permission(self, request, view):
        user = request.user

        # Check if user has portfolio management permission
        if PermissionResolver.has_permission(user, "specialist", "edit"):
            return True

        # Get specialist ID from URL
        specialist_id = view.kwargs.get("specialist_id")

        if specialist_id:
            from apps.specialistsapp.models import Specialist

            try:
                specialist = Specialist.objects.get(id=specialist_id)

                # If user is the specialist's employee
                if (
                    hasattr(user, "employee")
                    and user.employee.id == specialist.employee.id
                ):
                    return True

                # If user has permission for this shop
                return PermissionResolver.has_shop_permission(
                    user, str(specialist.employee.shop_id), "specialist", "edit"
                )
            except Specialist.DoesNotExist:
                return False

        return False

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Check if user has portfolio management permission
        if PermissionResolver.has_permission(user, "specialist", "edit"):
            return True

        # If user is the specialist's employee
        if hasattr(user, "employee") and user.employee.id == obj.specialist.employee.id:
            return True

        # If user has permission for this shop
        return PermissionResolver.has_shop_permission(
            user, str(obj.specialist.employee.shop_id), "specialist", "edit"
        )
