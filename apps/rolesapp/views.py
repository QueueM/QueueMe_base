"""
Roles app views for QueueMe platform
Handles endpoints related to user roles, permissions, and user-role assignments.
This module implements a full RBAC (Role-Based Access Control) system for the QueueMe platform,
allowing fine-grained control over what actions users can perform in different contexts.
"""

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.rolesapp.decorators import has_permission
from apps.rolesapp.models import Permission, Role, RolePermissionLog, UserRole
from apps.rolesapp.permissions import HasResourcePermission
from apps.rolesapp.serializers import (
    ContentTypeSerializer,
    PermissionGroupSerializer,
    PermissionSerializer,
    RoleDetailSerializer,
    RolePermissionLogSerializer,
    RoleSerializer,
    UserRoleSerializer,
)
from apps.rolesapp.services.permission_resolver import PermissionResolver
from apps.rolesapp.services.permission_service import PermissionService
from apps.rolesapp.services.role_service import RoleService


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for system permissions

    Permissions are read-only as they are system-defined capabilities that users can be granted.
    Each permission represents a specific action on a specific resource.

    Permissions:
    - Requires authentication
    - User must have 'view' permission on the 'roles' resource

    Filters:
    - resource: Filter by resource name
    - action: Filter by action type (view, manage, etc.)

    Search:
    - code_name: Permission code name
    - description: Permission description

    Ordering:
    - resource: Resource name
    - action: Action type
    - code_name: Permission code name
    """

    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        HasResourcePermission("roles", "view"),
    ]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["resource", "action"]
    search_fields = ["code_name", "description"]
    ordering_fields = ["resource", "action", "code_name"]
    ordering = ["resource", "action"]

    @action(detail=False, methods=["get"])
    @has_permission("roles", "view")
    def grouped(self, request):
        """
        Get permissions grouped by resource

        Returns a list of resources, each with its associated permissions.
        This endpoint is useful for UI representations of permissions where
        they are grouped by resource for easier management.

        Returns:
            Response: JSON array of resource objects, each containing a list of permissions
        """
        permissions = PermissionService.get_permissions_by_resource()
        serializer = PermissionGroupSerializer(permissions, many=True)
        return Response(serializer.data)


class ContentTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for content types

    Content types represent the different entity types in the system that can have roles.
    This is used for selecting entity types when creating roles.

    Permissions:
    - Requires authentication
    - User must have 'view' permission on the 'roles' resource
    """

    queryset = ContentType.objects.filter(app_label="apps")
    serializer_class = ContentTypeSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        HasResourcePermission("roles", "view"),
    ]

    @action(detail=False, methods=["get"])
    def for_roles(self, request):
        """
        Get content types that can be assigned roles

        Returns only the subset of content types that support role assignment,
        such as shops and companies. This filters out content types that don't
        make sense in the context of role assignment.

        Returns:
            Response: JSON array of valid content types for role assignment
        """
        # Only include models that support roles (e.g., shop, company)
        allowed_models = ["shop", "company"]
        queryset = self.queryset.filter(model__in=allowed_models)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class RoleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for roles

    Roles define sets of permissions that can be assigned to users. Each role can
    be associated with a specific entity (like a shop or company) to provide
    context-specific permissions.

    Permissions:
    - Requires authentication
    - 'view' permission for listing and retrieving
    - 'manage' permission for creating, updating and deleting

    Filters:
    - role_type: Filter by role type (e.g., shop, company)
    - is_active: Filter by active status
    - is_system: Filter by system role status

    Search:
    - name: Role name
    - description: Role description

    Ordering:
    - name: Role name
    - weight: Role priority weight
    - created_at: Role creation date
    """

    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        HasResourcePermission("roles", "view"),
    ]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["role_type", "is_active", "is_system"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "weight", "created_at"]
    ordering = ["-weight", "name"]

    def get_queryset(self):
        """
        Filter roles based on user permissions

        Returns different subsets of roles based on the user's permissions:
        - Admins can see all roles
        - Company owners see roles for their companies and associated shops
        - Shop managers see roles for their shops
        - Others see no roles by default

        Returns:
            QuerySet: Filtered queryset of roles the user can access
        """
        user = self.request.user

        # Admins can see all roles
        if user.is_superuser or PermissionResolver.is_queue_me_admin(user):
            return self.queryset

        # For others, restrict to roles they can manage
        if PermissionResolver.has_permission(user, "roles", "view"):
            # Company owners can see roles for their company and shops
            if PermissionResolver.is_company_owner(user):
                # Get the user's companies
                from apps.companiesapp.models import Company

                company_ids = Company.objects.filter(owner=user).values_list(
                    "id", flat=True
                )

                # Get the company content type
                company_ct = ContentType.objects.get(app_label="apps", model="company")

                # Get user's company roles and their companies
                user_role_companies = UserRole.objects.filter(
                    user=user, role__role_type="company", role__is_active=True
                ).values_list("role__object_id", flat=True)

                all_company_ids = list(company_ids) + list(user_role_companies)

                # Get the shop content type
                shop_ct = ContentType.objects.get(app_label="apps", model="shop")

                # Get shops from these companies
                from apps.shopapp.models import Shop

                shop_ids = Shop.objects.filter(
                    company__id__in=all_company_ids
                ).values_list("id", flat=True)

                # Return roles for these companies and shops
                return self.queryset.filter(
                    Q(content_type=company_ct, object_id__in=all_company_ids)
                    | Q(content_type=shop_ct, object_id__in=shop_ids)
                )

            # Shop managers can see roles for their shops
            if PermissionResolver.is_shop_manager(user):
                # Get the shop content type
                shop_ct = ContentType.objects.get(app_label="apps", model="shop")

                # Get user's managed shops
                from apps.shopapp.models import Shop

                managed_shop_ids = Shop.objects.filter(manager=user).values_list(
                    "id", flat=True
                )

                # Get user's shop manager roles and their shops
                user_role_shops = UserRole.objects.filter(
                    user=user, role__role_type="shop_manager", role__is_active=True
                ).values_list("role__object_id", flat=True)

                all_shop_ids = list(managed_shop_ids) + list(user_role_shops)

                # Return roles for these shops
                return self.queryset.filter(
                    content_type=shop_ct, object_id__in=all_shop_ids
                )

        # Default: empty queryset
        return self.queryset.none()

    def get_serializer_class(self):
        """
        Use detailed serializer for retrieve action

        Returns:
            Serializer class: The appropriate serializer for the current action
        """
        if self.action == "retrieve":
            return RoleDetailSerializer
        return super().get_serializer_class()

    def get_permissions(self):
        """
        Set permissions based on action

        Requires higher permissions (manage) for modifying actions.

        Returns:
            list: List of permission classes
        """
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [
                permissions.IsAuthenticated(),
                HasResourcePermission("roles", "manage"),
            ]
        return super().get_permissions()

    def perform_create(self, serializer):
        """
        Record the user who created the role

        Args:
            serializer: The role serializer instance
        """
        serializer.save()

    def perform_destroy(self, instance):
        """
        Prevent deletion of system roles

        Validates that:
        1. The role is not a system role
        2. The current user has permission to manage the role

        Args:
            instance: The role instance to delete

        Returns:
            Response: Error response if deletion is not allowed
        """
        if instance.is_system:
            return Response(
                {"detail": _("System roles cannot be deleted.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if this user can manage this role
        if not RoleService.can_user_manage_role(self.request.user, instance):
            return Response(
                {"detail": _("You don't have permission to manage this role.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        instance.delete()

    @action(detail=True, methods=["post"])
    @has_permission("roles", "manage")
    def clone(self, request, pk=None):
        """
        Clone a role with its permissions

        Creates a new role with the same permissions as the source role,
        but with a new name and optionally a new description.

        Request body:
            {
                "name": "New Role Name", (required)
                "description": "New role description" (optional)
            }

        Returns:
            Response: The newly created role
        """
        role = self.get_object()

        # Check if this user can manage this role
        if not RoleService.can_user_manage_role(request.user, role):
            return Response(
                {"detail": _("You don't have permission to manage this role.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get parameters
        name = request.data.get("name")
        description = request.data.get("description")

        if not name:
            return Response(
                {"detail": _("Name is required.")}, status=status.HTTP_400_BAD_REQUEST
            )

        # Clone the role
        new_role = RoleService.clone_role(
            role, name, description, performed_by=request.user
        )

        serializer = RoleSerializer(new_role)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    @has_permission("roles", "manage")
    def add_users(self, request, pk=None):
        """
        Add multiple users to a role

        Request body:
            {
                "user_ids": ["uuid1", "uuid2", ...] (required)
            }

        Returns:
            Response: Success message with the number of users added
        """
        role = self.get_object()

        # Check if this user can manage this role
        if not RoleService.can_user_manage_role(request.user, role):
            return Response(
                {"detail": _("You don't have permission to manage this role.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get user IDs from request
        user_ids = request.data.get("user_ids", [])

        if not user_ids:
            return Response(
                {"detail": _("No users specified.")}, status=status.HTTP_400_BAD_REQUEST
            )

        # Add users to role
        from apps.authapp.models import User

        added_count = 0

        with transaction.atomic():
            for user_id in user_ids:
                try:
                    user = User.objects.get(id=user_id)
                    PermissionService.assign_role_to_user(
                        user, role, assigned_by=request.user
                    )
                    added_count += 1
                except User.DoesNotExist:
                    pass  # Skip non-existent users

        return Response({"detail": _("{} users added to role.").format(added_count)})

    @action(detail=True, methods=["post"])
    @has_permission("roles", "manage")
    def transfer_users(self, request, pk=None):
        """
        Transfer users from this role to another role

        Moves all users from the current role to another role.

        Request body:
            {
                "to_role_id": "uuid" (required)
            }

        Returns:
            Response: Success message with the number of users transferred
        """
        from_role = self.get_object()

        # Check if this user can manage this role
        if not RoleService.can_user_manage_role(request.user, from_role):
            return Response(
                {"detail": _("You don't have permission to manage this role.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get target role ID
        to_role_id = request.data.get("to_role_id")

        if not to_role_id:
            return Response(
                {"detail": _("Target role ID is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            to_role = Role.objects.get(id=to_role_id)

            # Check if user can manage target role
            if not RoleService.can_user_manage_role(request.user, to_role):
                return Response(
                    {
                        "detail": _(
                            "You don't have permission to manage the target role."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Transfer users
            transferred = RoleService.transfer_users_between_roles(
                from_role, to_role, performed_by=request.user
            )

            return Response(
                {
                    "detail": _("{} users transferred to {}.").format(
                        transferred, to_role.name
                    )
                }
            )

        except Role.DoesNotExist:
            return Response(
                {"detail": _("Target role not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )


class UserRoleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for user role assignments

    This manages the many-to-many relationship between users and roles,
    allowing users to be assigned to roles and given specific permissions.

    Permissions:
    - Requires authentication
    - 'view' permission for listing and retrieving
    - 'manage' permission for creating, updating and deleting

    Filters:
    - user: Filter by user ID
    - role: Filter by role ID
    - is_primary: Filter by primary role status

    Search:
    - user__phone_number: User's phone number
    - role__name: Role name

    Ordering:
    - assigned_at: Assignment date
    - is_primary: Primary role status
    """

    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        HasResourcePermission("roles", "view"),
    ]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["user", "role", "is_primary"]
    search_fields = ["user__phone_number", "role__name"]
    ordering_fields = ["assigned_at", "is_primary"]
    ordering = ["-assigned_at"]

    def get_queryset(self):
        """
        Filter user roles based on user permissions

        Returns different subsets of user roles based on the user's permissions:
        - Admins can see all user roles
        - Others see only user roles for roles they can manage

        Returns:
            QuerySet: Filtered queryset of user roles the user can access
        """
        user = self.request.user

        # Admins can see all user roles
        if user.is_superuser or PermissionResolver.is_queue_me_admin(user):
            return self.queryset

        # For others, restrict to roles they can manage
        managed_roles = []

        for role in Role.objects.all():
            if RoleService.can_user_manage_role(user, role):
                managed_roles.append(role.id)

        return self.queryset.filter(role__id__in=managed_roles)

    def get_permissions(self):
        """
        Set permissions based on action

        Requires higher permissions (manage) for modifying actions.

        Returns:
            list: List of permission classes
        """
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [
                permissions.IsAuthenticated(),
                HasResourcePermission("roles", "manage"),
            ]
        return super().get_permissions()

    def perform_create(self, serializer):
        """
        Record the user who made the assignment

        Args:
            serializer: The user role serializer instance
        """
        serializer.save(assigned_by=self.request.user)

    def perform_destroy(self, instance):
        """
        Check if user can manage this role before deleting

        Args:
            instance: The user role instance to delete

        Returns:
            Response: Error response if deletion is not allowed
        """
        if not RoleService.can_user_manage_role(self.request.user, instance.role):
            return Response(
                {"detail": _("You don't have permission to manage this role.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        instance.delete()

    @action(detail=False, methods=["get"])
    def my_roles(self, request):
        """
        Get roles for the current user

        Returns all active roles assigned to the current authenticated user.

        Returns:
            Response: List of role assignments for the current user
        """
        user_roles = UserRole.objects.filter(user=request.user, role__is_active=True)
        serializer = self.get_serializer(user_roles, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_user(self, request):
        """
        Get roles for a specific user

        Query parameters:
            user_id: UUID of the user (required)

        Returns:
            Response: List of role assignments for the specified user
        """
        user_id = request.query_params.get("user_id")

        if not user_id:
            return Response(
                {"detail": _("User ID is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check permission to view this user's roles
        from apps.authapp.models import User

        try:
            target_user = User.objects.get(id=user_id)

            # Check permission: can see roles of users they can manage
            if (
                not request.user.is_superuser
                and not PermissionResolver.is_queue_me_admin(request.user)
            ):
                # If users are in entities we manage, we can see their roles
                # This is a simplified check - in a real app, you'd check entities more carefully
                if not self._can_manage_user(request.user, target_user):
                    return Response(
                        {
                            "detail": _(
                                "You don't have permission to view this user's roles."
                            )
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )

            user_roles = UserRole.objects.filter(user=target_user, role__is_active=True)
            serializer = self.get_serializer(user_roles, many=True)
            return Response(serializer.data)

        except User.DoesNotExist:
            return Response(
                {"detail": _("User not found.")}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=["get"])
    def by_role(self, request):
        """
        Get users for a specific role

        Query parameters:
            role_id: UUID of the role (required)

        Returns:
            Response: List of user assignments for the specified role
        """
        role_id = request.query_params.get("role_id")

        if not role_id:
            return Response(
                {"detail": _("Role ID is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            role = Role.objects.get(id=role_id)

            # Check if user can manage this role
            if not RoleService.can_user_manage_role(request.user, role):
                return Response(
                    {"detail": _("You don't have permission to manage this role.")},
                    status=status.HTTP_403_FORBIDDEN,
                )

            user_roles = UserRole.objects.filter(role=role)
            serializer = self.get_serializer(user_roles, many=True)
            return Response(serializer.data)

        except Role.DoesNotExist:
            return Response(
                {"detail": _("Role not found.")}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=["get"])
    def by_entity(self, request):
        """
        Get roles for a specific entity (e.g., shop, company)

        Query parameters:
            entity_type: Type of entity (e.g., 'shop', 'company') (required)
            entity_id: UUID of the entity (required)

        Returns:
            Response: List of user role assignments for the specified entity
        """
        entity_type = request.query_params.get("entity_type")
        entity_id = request.query_params.get("entity_id")

        if not entity_type or not entity_id:
            return Response(
                {"detail": _("Entity type and ID are required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Get the content type
            content_type = ContentType.objects.get(
                app_label="apps", model=entity_type.lower()
            )

            # Check if the entity exists
            model_class = content_type.model_class()
            # unused_unused_entity = model_class.objects.get(id=entity_id)

            # Check if user has permission to manage roles for this entity
            has_permission = False

            if request.user.is_superuser or PermissionResolver.is_queue_me_admin(
                request.user
            ):
                has_permission = True
            elif entity_type == "shop":
                has_permission = PermissionResolver.has_context_permission(
                    request.user, "shop", entity_id, "roles", "view"
                )
            elif entity_type == "company":
                has_permission = PermissionResolver.has_context_permission(
                    request.user, "company", entity_id, "roles", "view"
                )

            if not has_permission:
                return Response(
                    {
                        "detail": _(
                            "You don't have permission to view roles for this entity."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Get roles for this entity
            roles = Role.objects.filter(
                content_type=content_type, object_id=entity_id, is_active=True
            )

            # Get user roles for these roles
            user_roles = UserRole.objects.filter(role__in=roles)
            serializer = self.get_serializer(user_roles, many=True)
            return Response(serializer.data)

        except (ContentType.DoesNotExist, model_class.DoesNotExist):
            return Response(
                {"detail": _("Entity not found.")}, status=status.HTTP_404_NOT_FOUND
            )

    def _can_manage_user(self, manager, user):
        """
        Check if a manager can manage a user

        This is a helper method to determine if a manager has permission
        to view or manage a specific user's roles.

        Args:
            manager: The user who is trying to manage another user
            user: The user being managed

        Returns:
            bool: True if the manager can manage the user, False otherwise
        """
        # Get entities (shops, companies) manager can manage
        manager_shops = []
        manager_companies = []

        # If manager is company owner, they can manage all employees in their company shops
        if PermissionResolver.is_company_owner(manager):
            from apps.companiesapp.models import Company

            manager_companies = list(
                Company.objects.filter(owner=manager).values_list("id", flat=True)
            )

            # Add companies from roles
            company_roles = UserRole.objects.filter(
                user=manager, role__role_type="company", role__is_active=True
            )
            for role in company_roles:
                if role.role.object_id not in manager_companies:
                    manager_companies.append(role.role.object_id)

            # Get shops from these companies
            from apps.shopapp.models import Shop

            manager_shops = list(
                Shop.objects.filter(company__id__in=manager_companies).values_list(
                    "id", flat=True
                )
            )

        # If manager is shop manager, they can manage employees in their shops
        if PermissionResolver.is_shop_manager(manager):
            from apps.shopapp.models import Shop

            direct_shops = list(
                Shop.objects.filter(manager=manager).values_list("id", flat=True)
            )

            # Add shops from roles
            shop_roles = UserRole.objects.filter(
                user=manager, role__role_type="shop_manager", role__is_active=True
            )
            for role in shop_roles:
                if (
                    role.role.object_id not in manager_shops
                    and role.role.object_id not in direct_shops
                ):
                    manager_shops.append(role.role.object_id)

        # Check if user is an employee in any of these shops
        if manager_shops:
            from apps.employeeapp.models import Employee

            is_employee = Employee.objects.filter(
                user=user, shop__id__in=manager_shops
            ).exists()

            if is_employee:
                return True

        # If user has roles in entities manager can manage, manager can manage user
        user_entity_roles = (
            UserRole.objects.filter(user=user, role__is_active=True)
            .exclude(role__content_type__isnull=True)
            .exclude(role__object_id__isnull=True)
        )

        for user_role in user_entity_roles:
            if (
                user_role.role.content_type.model == "shop"
                and user_role.role.object_id in manager_shops
            ):
                return True
            elif (
                user_role.role.content_type.model == "company"
                and user_role.role.object_id in manager_companies
            ):
                return True

        return False


class RolePermissionLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for role permission audit logs

    These are read-only records of changes to role permissions,
    providing an audit trail of who changed what permissions and when.

    Permissions:
    - Requires authentication
    - User must have 'view' permission on the 'roles' resource

    Filters:
    - role: Filter by role ID
    - permission: Filter by permission ID
    - action_type: Filter by action type (add, remove)
    - performed_by: Filter by the user who performed the action

    Search:
    - role__name: Role name
    - permission__code_name: Permission code name

    Ordering:
    - timestamp: When the action occurred
    """

    queryset = RolePermissionLog.objects.all()
    serializer_class = RolePermissionLogSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        HasResourcePermission("roles", "view"),
    ]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["role", "permission", "action_type", "performed_by"]
    search_fields = ["role__name", "permission__code_name"]
    ordering_fields = ["timestamp"]
    ordering = ["-timestamp"]

    def get_queryset(self):
        """
        Filter logs based on user permissions

        Returns different subsets of logs based on the user's permissions:
        - Admins can see all logs
        - Others see only logs for roles they can manage

        Returns:
            QuerySet: Filtered queryset of logs the user can access
        """
        user = self.request.user

        # Admins can see all logs
        if user.is_superuser or PermissionResolver.is_queue_me_admin(user):
            return self.queryset

        # For others, restrict to roles they can manage
        managed_roles = []

        for role in Role.objects.all():
            if RoleService.can_user_manage_role(user, role):
                managed_roles.append(role.id)

        return self.queryset.filter(role__id__in=managed_roles)
