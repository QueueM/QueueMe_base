# apps/rolesapp/services/role_service.py
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from apps.rolesapp.constants import ROLE_HIERARCHY
from apps.rolesapp.models import Permission, Role, RolePermissionLog, UserRole
from apps.rolesapp.services.permission_resolver import PermissionResolver


class RoleService:
    """
    Service for managing roles

    This service provides methods for creating, updating, and managing roles.
    """

    @staticmethod
    def get_highest_role(user):
        """
        Get the highest role a user has based on role hierarchy

        Args:
            user: The user to check

        Returns:
            Role: The highest role the user has, or None
        """
        # Get all active roles
        user_roles = UserRole.objects.filter(user=user, role__is_active=True).select_related("role")

        if not user_roles:
            return None

        # Find the highest role
        highest_rank = -1
        highest_role = None

        for user_role in user_roles:
            role_type = user_role.role.role_type
            rank = ROLE_HIERARCHY.get(role_type, 0)

            if rank > highest_rank:
                highest_rank = rank
                highest_role = user_role.role

        return highest_role

    @staticmethod
    def get_primary_role_for_context(user, context_type, context_id):
        """
        Get the user's primary role in a specific context

        Args:
            user: The user to check
            context_type: The context type (e.g., 'shop', 'company')
            context_id: The context ID

        Returns:
            Role: The primary role, or None
        """
        content_type = ContentType.objects.get(app_label="apps", model=context_type.lower())

        # Try to find primary role first
        primary_user_role = UserRole.objects.filter(
            user=user,
            role__content_type=content_type,
            role__object_id=context_id,
            role__is_active=True,
            is_primary=True,
        ).first()

        if primary_user_role:
            return primary_user_role.role

        # If no primary role, return the highest role
        user_roles = UserRole.objects.filter(
            user=user,
            role__content_type=content_type,
            role__object_id=context_id,
            role__is_active=True,
        ).select_related("role")

        if not user_roles:
            return None

        # Find the highest role in this context
        highest_rank = -1
        highest_role = None

        for user_role in user_roles:
            role_type = user_role.role.role_type
            rank = ROLE_HIERARCHY.get(role_type, 0)

            if rank > highest_rank:
                highest_rank = rank
                highest_role = user_role.role

        return highest_role

    @staticmethod
    @transaction.atomic
    def clone_role(role, new_name, new_description=None, performed_by=None):
        """
        Clone a role with its permissions

        Args:
            role: The role to clone
            new_name: Name for the new role
            new_description: Optional description for the new role
            performed_by: Optional user who performed the action

        Returns:
            Role: The new role
        """
        # Create new role
        new_role = Role.objects.create(
            name=new_name,
            description=new_description or f"Cloned from {role.name}",
            role_type=role.role_type,
            content_type=role.content_type,
            object_id=role.object_id,
            parent=role.parent,
            weight=role.weight,
            is_active=role.is_active,
            is_system=False,  # Cloned roles are never system roles
        )

        # Clone permissions
        permissions = role.permissions.all()
        new_role.permissions.set(permissions)

        # Log permission additions
        if performed_by:
            for permission in permissions:
                RolePermissionLog.objects.create(
                    role=new_role,
                    permission=permission,
                    action_type="add",
                    performed_by=performed_by,
                )

        return new_role

    @staticmethod
    @transaction.atomic
    def create_custom_role(
        name, description, permissions, entity=None, parent=None, performed_by=None
    ):
        """
        Create a custom role with specific permissions

        Args:
            name: Role name
            description: Role description
            permissions: List of Permission objects or IDs
            entity: Optional entity to associate with role
            parent: Optional parent role
            performed_by: Optional user who performed the action

        Returns:
            Role: The new role
        """
        # Set content_type and object_id if entity is provided
        content_type = None
        object_id = None

        if entity:
            content_type = ContentType.objects.get_for_model(entity)
            object_id = entity.id

        # Create the role
        role = Role.objects.create(
            name=name,
            description=description,
            role_type="custom",
            content_type=content_type,
            object_id=object_id,
            parent=parent,
            is_active=True,
            is_system=False,
        )

        # Add permissions
        if isinstance(permissions[0], Permission) if permissions else False:
            role.permissions.set(permissions)
        else:
            role.permissions.set(Permission.objects.filter(id__in=permissions))

        # Log permission additions
        if performed_by:
            for permission in role.permissions.all():
                RolePermissionLog.objects.create(
                    role=role,
                    permission=permission,
                    action_type="add",
                    performed_by=performed_by,
                )

        return role

    @staticmethod
    def get_user_count_by_role():
        """
        Get count of users for each role

        Returns:
            Dictionary mapping role IDs to user counts
        """
        result = {}
        roles = Role.objects.all()

        for role in roles:
            result[str(role.id)] = role.user_roles.count()

        return result

    @staticmethod
    @transaction.atomic
    def transfer_users_between_roles(from_role, to_role, performed_by=None):
        """
        Transfer all users from one role to another

        Args:
            from_role: Source role
            to_role: Destination role
            performed_by: Optional user who performed the action

        Returns:
            int: Number of users transferred
        """
        # Get all users with the source role
        user_roles = UserRole.objects.filter(role=from_role)
        count = user_roles.count()

        # Create list of users to transfer
        users_to_transfer = [ur.user for ur in user_roles]

        # Delete old user roles
        user_roles.delete()

        # Create new user roles
        for user in users_to_transfer:
            UserRole.objects.create(
                user=user,
                role=to_role,
                assigned_by=performed_by,
                is_primary=False,  # Default to non-primary
            )

            # Invalidate permission cache for this user
            PermissionResolver.invalidate_permission_cache(user_id=user.id)

        return count

    @staticmethod
    def can_user_manage_role(user, role):
        """
        Check if a user can manage a specific role

        Args:
            user: The user to check
            role: The role to check

        Returns:
            bool: True if user can manage the role
        """
        # Admin users can manage all roles
        if user.is_superuser or PermissionResolver.is_queue_me_admin(user):
            return True

        # Get the user's highest role
        user_highest_role = RoleService.get_highest_role(user)

        if not user_highest_role:
            return False

        # Check role hierarchy
        user_role_rank = ROLE_HIERARCHY.get(user_highest_role.role_type, 0)
        target_role_rank = ROLE_HIERARCHY.get(role.role_type, 0)

        # Users can only manage roles below them in hierarchy
        if user_role_rank <= target_role_rank:
            return False

        # For entity-specific roles, check if user has management permission
        if role.content_type and role.object_id:
            entity_type = role.content_type.model
            entity_id = role.object_id

            # Check if user can manage roles in this context
            return PermissionResolver.has_context_permission(
                user, entity_type, entity_id, "roles", "manage"
            )

        return False
