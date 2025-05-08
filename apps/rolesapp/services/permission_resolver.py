# apps/rolesapp/services/permission_resolver.py
import logging
from functools import wraps

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache

from apps.rolesapp.models import Permission, UserRole

logger = logging.getLogger(__name__)


# Cache decorator for performance optimization
def cache_permission_result(ttl=300):  # Cache for 5 minutes by default
    """
    Decorator to cache permission results

    This is a performance optimization for frequent permission checks.
    The cache key is based on the function name and arguments.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate a cache key based on function name and arguments
            key_parts = [func.__name__]
            key_parts.extend([str(arg) for arg in args])
            key_parts.extend([f"{k}={v}" for k, v in kwargs.items()])
            cache_key = f"permission_{'_'.join(key_parts)}"

            # Try to get result from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Calculate result and store in cache
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result

        return wrapper

    return decorator


class PermissionResolver:
    """
    Service for resolving user permissions

    This is the core logic for checking if a user has permission to perform
    an action on a resource. It implements a sophisticated permission resolution
    algorithm that considers roles, hierarchies, and contexts.
    """

    @staticmethod
    @cache_permission_result(ttl=60)
    def get_user_permissions(user, context_type=None, context_id=None):
        """
        Get all permissions for a user, optionally in a specific context

        Args:
            user: The user to check permissions for
            context_type: Optional context type (e.g., 'shop', 'company')
            context_id: Optional context ID (UUID)

        Returns:
            QuerySet of Permission objects
        """
        if user.is_superuser:
            # Superuser has all permissions
            return Permission.objects.all()

        # Get all user roles
        if context_type and context_id:
            # For context-specific roles
            content_type = ContentType.objects.get(
                app_label="apps", model=context_type.lower()
            )
            user_roles = UserRole.objects.filter(
                user=user,
                role__content_type=content_type,
                role__object_id=context_id,
                role__is_active=True,
            )
        else:
            # For all roles
            user_roles = UserRole.objects.filter(user=user, role__is_active=True)

        # Get permissions from all roles
        permissions = Permission.objects.none()
        for user_role in user_roles:
            # Get direct permissions
            role_permissions = user_role.role.permissions.all()
            permissions = permissions | role_permissions

            # Get inherited permissions from parent roles
            current_role = user_role.role
            while current_role.parent:
                parent_permissions = current_role.parent.permissions.all()
                permissions = permissions | parent_permissions
                current_role = current_role.parent

        return permissions.distinct()

    @staticmethod
    @cache_permission_result()
    def has_permission(user, resource, action):
        """
        Check if user has a specific permission

        Args:
            user: The user to check permissions for
            resource: The resource to check (e.g., 'shop', 'service')
            action: The action to check (e.g., 'view', 'add', 'edit')

        Returns:
            bool: True if user has permission, False otherwise
        """
        # Superuser always has permission
        if user.is_superuser:
            return True

        # Check for Queue Me Admin role (special case)
        if PermissionResolver.is_queue_me_admin(user):
            return True

        # Special wildcard check for "*" permissions
        user_permissions = PermissionResolver.get_user_permissions(user)

        # Check for wildcard permissions
        if user_permissions.filter(resource="*", action="*").exists():
            return True

        if user_permissions.filter(resource=resource, action="*").exists():
            return True

        if user_permissions.filter(resource="*", action=action).exists():
            return True

        # Check for specific permission
        return user_permissions.filter(resource=resource, action=action).exists()

    @staticmethod
    @cache_permission_result()
    def has_context_permission(user, context_type, context_id, resource, action):
        """
        Check if user has permission for a resource in a specific context

        Args:
            user: The user to check permissions for
            context_type: The context type (e.g., 'shop', 'company')
            context_id: The context ID (UUID)
            resource: The resource to check (e.g., 'service', 'employee')
            action: The action to check (e.g., 'view', 'add', 'edit')

        Returns:
            bool: True if user has permission, False otherwise
        """
        # Superuser always has permission
        if user.is_superuser:
            return True

        # Check for Queue Me Admin role (special case)
        if PermissionResolver.is_queue_me_admin(user):
            return True

        try:
            # Get context-specific permissions
            context_permissions = PermissionResolver.get_user_permissions(
                user, context_type, context_id
            )

            # Check for wildcard permissions in context
            if context_permissions.filter(resource="*", action="*").exists():
                return True

            if context_permissions.filter(resource=resource, action="*").exists():
                return True

            if context_permissions.filter(resource="*", action=action).exists():
                return True

            # Check for specific permission in context
            context_has_permission = context_permissions.filter(
                resource=resource, action=action
            ).exists()

            if context_has_permission:
                return True

            # If not found in context, check for global permission
            return PermissionResolver.has_permission(user, resource, action)

        except Exception as e:
            logger.error(f"Error checking context permission: {e}")
            return False

    @staticmethod
    @cache_permission_result()
    def is_queue_me_admin(user):
        """Check if user is a Queue Me Admin"""
        if user.is_superuser:
            return True

        return UserRole.objects.filter(
            user=user, role__role_type="queue_me_admin", role__is_active=True
        ).exists()

    @staticmethod
    @cache_permission_result()
    def is_queue_me_employee(user):
        """Check if user is a Queue Me Employee or Admin"""
        if PermissionResolver.is_queue_me_admin(user):
            return True

        return UserRole.objects.filter(
            user=user, role__role_type="queue_me_employee", role__is_active=True
        ).exists()

    @staticmethod
    @cache_permission_result()
    def is_company_owner(user):
        """Check if user is a Company Owner"""
        return UserRole.objects.filter(
            user=user, role__role_type="company", role__is_active=True
        ).exists()

    @staticmethod
    @cache_permission_result()
    def is_company_owner_for(user, company_id):
        """Check if user is the owner of a specific company"""
        from django.apps.companiesapp.models import Company

        # Check direct company ownership (user is in company's owner field)
        direct_owner = Company.objects.filter(id=company_id, owner=user).exists()

        if direct_owner:
            return True

        # Check role-based ownership
        return UserRole.objects.filter(
            user=user,
            role__role_type="company",
            role__is_active=True,
            role__content_type__model="company",
            role__object_id=company_id,
        ).exists()

    @staticmethod
    @cache_permission_result()
    def is_shop_manager(user):
        """Check if user is a Shop Manager"""
        return UserRole.objects.filter(
            user=user, role__role_type="shop_manager", role__is_active=True
        ).exists()

    @staticmethod
    @cache_permission_result()
    def is_shop_manager_for(user, shop_id):
        """Check if user is the manager of a specific shop"""
        from django.apps.shopapp.models import Shop

        # Check direct shop management (user is in shop's manager field)
        direct_manager = Shop.objects.filter(id=shop_id, manager=user).exists()

        if direct_manager:
            return True

        # Check role-based management
        return UserRole.objects.filter(
            user=user,
            role__role_type="shop_manager",
            role__is_active=True,
            role__content_type__model="shop",
            role__object_id=shop_id,
        ).exists()

    @staticmethod
    @cache_permission_result()
    def get_user_roles(user):
        """Get all roles for a user"""
        return UserRole.objects.filter(user=user, role__is_active=True)

    @staticmethod
    @cache_permission_result()
    def get_user_roles_by_context(user, context_type, context_id):
        """Get all roles for a user in a specific context"""
        content_type = ContentType.objects.get(
            app_label="apps", model=context_type.lower()
        )
        return UserRole.objects.filter(
            user=user,
            role__is_active=True,
            role__content_type=content_type,
            role__object_id=context_id,
        )

    @staticmethod
    @cache_permission_result()
    def has_role_type(user, role_types):
        """
        Check if user has any of the specified role types

        Args:
            user: The user to check
            role_types: List of role type values (or single string)

        Returns:
            bool: True if user has any of the specified role types
        """
        if not isinstance(role_types, (list, tuple)):
            role_types = [role_types]

        if user.is_superuser:
            return True

        return UserRole.objects.filter(
            user=user, role__role_type__in=role_types, role__is_active=True
        ).exists()

    @staticmethod
    @cache_permission_result()
    def get_user_accessible_entities(user, entity_type):
        """
        Get all entities of a specific type that the user has access to

        This is useful for getting all shops a user can manage, etc.

        Args:
            user: The user to check
            entity_type: The entity type (e.g., 'shop', 'company')

        Returns:
            QuerySet of entity IDs
        """
        if user.is_superuser or PermissionResolver.is_queue_me_admin(user):
            # Admin users can access all entities
            content_type = ContentType.objects.get(
                app_label="apps", model=entity_type.lower()
            )
            model_class = content_type.model_class()
            return model_class.objects.all()

        # Get all roles with entities
        user_roles = UserRole.objects.filter(
            user=user,
            role__is_active=True,
            role__content_type__model=entity_type.lower(),
        )

        # Extract entity IDs
        entity_ids = user_roles.values_list("role__object_id", flat=True).distinct()

        content_type = ContentType.objects.get(
            app_label="apps", model=entity_type.lower()
        )
        model_class = content_type.model_class()

        # Return entities by ID
        return model_class.objects.filter(id__in=entity_ids)

    @staticmethod
    def invalidate_permission_cache(user_id=None, role_id=None):
        """
        Invalidate permission cache

        Args:
            user_id: Optional user ID to invalidate cache for a specific user
            role_id: Optional role ID to invalidate cache for a specific role
        """
        # This is a simplified implementation that clears the entire cache
        # A more sophisticated implementation would target specific cache keys
        if user_id:
            pattern = f"permission_*_*{user_id}*"
            cache.delete_pattern(pattern)

        if role_id:
            pattern = f"permission_*_*{role_id}*"
            cache.delete_pattern(pattern)

        # If no specific user or role, clear all permission caches
        if not user_id and not role_id:
            pattern = "permission_*"
            cache.delete_pattern(pattern)
