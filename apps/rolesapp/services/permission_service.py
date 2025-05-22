# apps/rolesapp/services/permission_service.py
import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from apps.rolesapp.constants import DEFAULT_ROLE_PERMISSIONS, DEFAULT_WEIGHTS
from apps.rolesapp.models import Permission, Role, RolePermissionLog, UserRole
from apps.rolesapp.services.permission_resolver import PermissionResolver

logger = logging.getLogger(__name__)


class PermissionService:
    """
    Service for managing permissions and roles

    This service provides methods for creating, updating, and managing
    permissions, roles, and user-role assignments.
    """

    @staticmethod
    def get_or_create_permission(resource, action, description=None):
        """
        Get or create a permission

        Args:
            resource: The resource (e.g., 'shop', 'service')
            action: The action (e.g., 'view', 'add', 'edit')
            description: Optional description

        Returns:
            Permission object
        """
        code_name = f"{resource}_{action}"

        if resource == "*" or action == "*":
            code_name = f"{resource}_{action}_wildcard"

        permission, created = Permission.objects.get_or_create(
            resource=resource,
            action=action,
            defaults={
                "code_name": code_name,
                "description": description or f"{action.capitalize()} {resource}",
            },
        )

        return permission

    @staticmethod
    @transaction.atomic
    def create_default_permissions():
        """
        Create all default permissions

        This creates a full matrix of resource x action permissions,
        plus wildcard permissions.
        """
        # Resources and actions from RESOURCE_CHOICES and ACTION_CHOICES in Permission model
        resources = [choice[0] for choice in Permission.RESOURCE_CHOICES]
        actions = [choice[0] for choice in Permission.ACTION_CHOICES]

        # Create wildcard permissions
        PermissionService.get_or_create_permission("*", "*", "All permissions")

        # Create resource wildcards
        for resource in resources:
            PermissionService.get_or_create_permission(
                resource, "*", f"All actions on {resource}"
            )

        # Create action wildcards
        for action in actions:
            PermissionService.get_or_create_permission(
                "*", action, f"{action.capitalize()} all resources"
            )

        # Create all resource-action combinations
        for resource in resources:
            for action in actions:
                PermissionService.get_or_create_permission(resource, action)

        return Permission.objects.count()

    @staticmethod
    @transaction.atomic
    def create_default_role(
        role_type, name=None, description=None, entity=None, performed_by=None
    ):
        """
        Create a default role with standard permissions

        Args:
            role_type: The role type (e.g., 'queue_me_admin', 'shop_manager')
            name: Optional name (defaults to role_type)
            description: Optional description
            entity: Optional entity to associate with the role (e.g., a Shop instance)
            performed_by: Optional user who performed the action

        Returns:
            Role object
        """
        name = name or role_type.replace("_", " ").title()
        description = description or f"Default {name} role"

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
            role_type=role_type,
            content_type=content_type,
            object_id=object_id,
            weight=DEFAULT_WEIGHTS.get(role_type, 0),
            is_system=role_type
            in ["queue_me_admin", "queue_me_employee", "company", "shop_manager"],
        )

        # Add default permissions
        default_permissions = DEFAULT_ROLE_PERMISSIONS.get(role_type, [])
        for perm_data in default_permissions:
            resource = perm_data["resource"]
            action = perm_data["action"]

            try:
                if resource == "*" or action == "*":
                    # Handle wildcard permissions
                    if resource == "*" and action == "*":
                        # All permissions
                        permission = Permission.objects.get(resource="*", action="*")
                        role.permissions.add(permission)
                    elif resource == "*":
                        # All resources for specific action
                        permission = Permission.objects.get(resource="*", action=action)
                        role.permissions.add(permission)
                    elif action == "*":
                        # All actions for specific resource
                        permission = Permission.objects.get(
                            resource=resource, action="*"
                        )
                        role.permissions.add(permission)
                else:
                    # Regular permission
                    permission = Permission.objects.get(
                        resource=resource, action=action
                    )
                    role.permissions.add(permission)

                # Log permission addition
                if performed_by:
                    RolePermissionLog.objects.create(
                        role=role,
                        permission=permission,
                        action_type="add",
                        performed_by=performed_by,
                    )
            except Permission.DoesNotExist:
                logger.warning(f"Permission {resource}_{action} not found")

        return role

    @staticmethod
    @transaction.atomic
    def create_default_roles_for_entity(entity, entity_type, performed_by=None):
        """
        Create default roles for a new entity (e.g., Shop)

        Args:
            entity: The entity instance (e.g., Shop)
            entity_type: The entity type (e.g., 'shop')
            performed_by: Optional user who performed the action

        Returns:
            Dictionary of created roles
        """
        roles = {}

        if entity_type == "shop":
            # Create shop manager role
            manager_role = PermissionService.create_default_role(
                "shop_manager",
                name=f"{entity.name} Manager",
                description=f"Manager of {entity.name}",
                entity=entity,
                performed_by=performed_by,
            )
            roles["manager"] = manager_role

            # Create shop employee role
            employee_role = PermissionService.create_default_role(
                "shop_employee",
                name=f"{entity.name} Employee",
                description=f"Employee of {entity.name}",
                entity=entity,
                performed_by=performed_by,
            )
            roles["employee"] = employee_role

        elif entity_type == "company":
            # Create company owner role
            owner_role = PermissionService.create_default_role(
                "company",
                name=f"{entity.name} Owner",
                description=f"Owner of {entity.name}",
                entity=entity,
                performed_by=performed_by,
            )
            roles["owner"] = owner_role

        return roles

    @staticmethod
    @transaction.atomic
    def assign_role_to_user(user, role, assigned_by=None, is_primary=False):
        """
        Assign a role to a user

        Args:
            user: The user to assign the role to
            role: The role to assign
            assigned_by: Optional user who performed the assignment
            is_primary: Whether this is the primary role for the user in this context

        Returns:
            UserRole object
        """
        # Check if user already has this role
        existing = UserRole.objects.filter(user=user, role=role).first()
        if existing:
            # Update primary status if needed
            if existing.is_primary != is_primary:
                existing.is_primary = is_primary
                existing.save()
            return existing

        # Create new user role
        user_role = UserRole.objects.create(
            user=user, role=role, assigned_by=assigned_by, is_primary=is_primary
        )

        # Invalidate permission cache for this user
        PermissionResolver.invalidate_permission_cache(user_id=user.id)

        return user_role

    @staticmethod
    @transaction.atomic
    def revoke_role_from_user(user, role):
        """
        Revoke a role from a user

        Args:
            user: The user to revoke the role from
            role: The role to revoke

        Returns:
            bool: True if successful, False if user didn't have the role
        """
        deleted, _ = UserRole.objects.filter(user=user, role=role).delete()

        if deleted:
            # Invalidate permission cache for this user
            PermissionResolver.invalidate_permission_cache(user_id=user.id)
            return True

        return False

    @staticmethod
    def get_permissions_by_resource():
        """
        Get all permissions grouped by resource

        Returns:
            Dictionary of resources with their permissions
        """
        result = {}

        for permission in Permission.objects.all():
            if permission.resource not in result:
                result[permission.resource] = {
                    "resource": permission.resource,
                    "resource_display": permission.get_resource_display(),
                    "permissions": [],
                }

            result[permission.resource]["permissions"].append(
                {
                    "id": permission.id,
                    "action": permission.action,
                    "action_display": permission.get_action_display(),
                    "code_name": permission.code_name,
                    "description": permission.description,
                }
            )

        # Convert dict to list and sort by resource
        return sorted(result.values(), key=lambda x: x["resource"])
