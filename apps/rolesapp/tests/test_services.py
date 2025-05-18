# apps/rolesapp/tests/test_services.py
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.authapp.models import User
from apps.rolesapp.models import Permission, Role, UserRole
from apps.rolesapp.services.permission_resolver import PermissionResolver
from apps.rolesapp.services.permission_service import PermissionService
from apps.rolesapp.services.role_service import RoleService


class PermissionServiceTest(TestCase):
    """Test the PermissionService"""

    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create(phone_number="1234567890", user_type="admin")

    def test_get_or_create_permission(self):
        """Test getting or creating a permission"""
        # Create a new permission
        permission = PermissionService.get_or_create_permission(
            "service", "edit", "Edit service details"
        )

        self.assertEqual(permission.resource, "service")
        self.assertEqual(permission.action, "edit")
        self.assertEqual(permission.description, "Edit service details")
        self.assertEqual(permission.code_name, "service_edit")

        # Get the same permission (should not create a new one)
        permission2 = PermissionService.get_or_create_permission(
            "service", "edit", "Different description"
        )

        self.assertEqual(permission.id, permission2.id)
        self.assertEqual(
            permission2.description, "Edit service details"
        )  # Description should not change

    def test_create_default_permissions(self):
        """Test creating default permissions"""
        # Clear any existing permissions
        Permission.objects.all().delete()

        # Create default permissions
        count = PermissionService.create_default_permissions()

        # Verify permissions were created
        self.assertGreater(count, 0)

        # Check for some key permissions
        self.assertTrue(Permission.objects.filter(resource="*", action="*").exists())
        self.assertTrue(Permission.objects.filter(resource="shop", action="view").exists())
        self.assertTrue(Permission.objects.filter(resource="service", action="add").exists())

    def test_create_default_role(self):
        """Test creating a default role"""
        # Create necessary permissions
        PermissionService.create_default_permissions()

        # Create a shop manager role
        role = PermissionService.create_default_role(
            "shop_manager",
            name="Test Manager",
            description="Test description",
            performed_by=self.user,
        )

        # Verify role properties
        self.assertEqual(role.name, "Test Manager")
        self.assertEqual(role.description, "Test description")
        self.assertEqual(role.role_type, "shop_manager")
        self.assertTrue(role.is_system)

        # Verify permissions were assigned
        self.assertTrue(role.has_permission("service", "add"))
        self.assertTrue(role.has_permission("specialist", "manage"))

    def test_create_default_roles_for_entity(self):
        """Test creating default roles for an entity"""
        # Create necessary permissions
        PermissionService.create_default_permissions()

        # Create a shop entity
        from apps.shopapp.models import Shop

        shop = Shop.objects.create(name="Test Shop", phone_number="5555555555", username="testshop")

        # Create default roles for the shop
        roles = PermissionService.create_default_roles_for_entity(
            shop, "shop", performed_by=self.user
        )

        # Verify roles were created
        # apps/rolesapp/tests/test_services.py (continued)
        # Verify roles were created
        self.assertIn("manager", roles)
        self.assertIn("employee", roles)

        # Verify roles have correct properties
        manager_role = roles["manager"]
        self.assertEqual(manager_role.name, f"{shop.name} Manager")
        self.assertEqual(manager_role.role_type, "shop_manager")
        self.assertEqual(manager_role.content_type, ContentType.objects.get_for_model(shop))
        self.assertEqual(manager_role.object_id, shop.id)

        # Verify employee role
        employee_role = roles["employee"]
        self.assertEqual(employee_role.name, f"{shop.name} Employee")
        self.assertEqual(employee_role.role_type, "shop_employee")

    def test_assign_role_to_user(self):
        """Test assigning a role to a user"""
        # Create a role
        role = Role.objects.create(name="Test Role", role_type="custom", is_active=True)

        # Assign role to user
        user_role = PermissionService.assign_role_to_user(
            self.user, role, assigned_by=self.user, is_primary=True
        )

        # Verify assignment
        self.assertEqual(user_role.user, self.user)
        self.assertEqual(user_role.role, role)
        self.assertEqual(user_role.assigned_by, self.user)
        self.assertTrue(user_role.is_primary)

        # Test assigning the same role again (should return existing)
        user_role2 = PermissionService.assign_role_to_user(
            self.user, role, assigned_by=self.user, is_primary=False
        )

        self.assertEqual(user_role.id, user_role2.id)

        # Primary status should be updated
        self.assertFalse(user_role2.is_primary)

    def test_revoke_role_from_user(self):
        """Test revoking a role from a user"""
        # Create a role
        role = Role.objects.create(name="Test Role", role_type="custom", is_active=True)

        # Assign role to user
        UserRole.objects.create(user=self.user, role=role, is_primary=True)

        # Verify role exists
        self.assertTrue(UserRole.objects.filter(user=self.user, role=role).exists())

        # Revoke role
        result = PermissionService.revoke_role_from_user(self.user, role)

        # Verify role was revoked
        self.assertTrue(result)
        self.assertFalse(UserRole.objects.filter(user=self.user, role=role).exists())

        # Try revoking again (should return False)
        result = PermissionService.revoke_role_from_user(self.user, role)
        self.assertFalse(result)


class RoleServiceTest(TestCase):
    """Test the RoleService"""

    def setUp(self):
        """Set up test data"""
        # Create users
        self.admin_user = User.objects.create(phone_number="1234567890", user_type="admin")
        self.employee_user = User.objects.create(phone_number="0987654321", user_type="employee")

        # Create roles
        self.admin_role = Role.objects.create(
            name="Admin Role", role_type="queue_me_admin", weight=1000, is_active=True
        )
        self.employee_role = Role.objects.create(
            name="Employee Role",
            role_type="queue_me_employee",
            weight=800,
            is_active=True,
        )
        self.custom_role = Role.objects.create(
            name="Custom Role", role_type="custom", weight=100, is_active=True
        )

        # Assign roles
        UserRole.objects.create(user=self.admin_user, role=self.admin_role, is_primary=True)
        UserRole.objects.create(user=self.employee_user, role=self.employee_role, is_primary=True)
        UserRole.objects.create(user=self.employee_user, role=self.custom_role, is_primary=False)

        # Create a shop entity for context testing
        from apps.shopapp.models import Shop

        self.shop = Shop.objects.create(
            name="Test Shop", phone_number="5555555555", username="testshop"
        )

        # Create shop roles
        shop_ct = ContentType.objects.get_for_model(Shop)

        self.shop_manager_role = Role.objects.create(
            name="Shop Manager",
            role_type="shop_manager",
            content_type=shop_ct,
            object_id=self.shop.id,
            weight=400,
            is_active=True,
        )

        self.shop_employee_role = Role.objects.create(
            name="Shop Employee",
            role_type="shop_employee",
            content_type=shop_ct,
            object_id=self.shop.id,
            weight=200,
            is_active=True,
        )

        # Assign shop roles
        UserRole.objects.create(
            user=self.employee_user, role=self.shop_manager_role, is_primary=True
        )

    def test_get_highest_role(self):
        """Test getting the highest role for a user"""
        # Admin user's highest role should be admin_role
        highest_role = RoleService.get_highest_role(self.admin_user)
        self.assertEqual(highest_role, self.admin_role)

        # Employee user's highest role should be employee_role
        highest_role = RoleService.get_highest_role(self.employee_user)
        self.assertEqual(highest_role, self.employee_role)

    def test_get_primary_role_for_context(self):
        """Test getting the primary role for a user in a context"""
        # Get primary role for employee_user in shop context
        primary_role = RoleService.get_primary_role_for_context(
            self.employee_user, "shop", self.shop.id
        )

        self.assertEqual(primary_role, self.shop_manager_role)

        # Test with a user that has no roles in this context
        primary_role = RoleService.get_primary_role_for_context(
            self.admin_user, "shop", self.shop.id
        )

        self.assertIsNone(primary_role)

    def test_clone_role(self):
        """Test cloning a role"""
        # Create a permission and add to source role
        permission = Permission.objects.create(
            resource="shop", action="view", description="Can view shops"
        )
        self.custom_role.permissions.add(permission)

        # Clone the role
        cloned_role = RoleService.clone_role(
            self.custom_role,
            "Cloned Role",
            "Cloned description",
            performed_by=self.admin_user,
        )

        # Verify cloned role properties
        self.assertEqual(cloned_role.name, "Cloned Role")
        self.assertEqual(cloned_role.description, "Cloned description")
        self.assertEqual(cloned_role.role_type, self.custom_role.role_type)
        self.assertEqual(cloned_role.weight, self.custom_role.weight)
        self.assertFalse(cloned_role.is_system)  # Cloned roles are never system roles

        # Verify permissions were cloned
        self.assertEqual(cloned_role.permissions.count(), 1)
        self.assertTrue(cloned_role.permissions.filter(id=permission.id).exists())

    def test_create_custom_role(self):
        """Test creating a custom role with specific permissions"""
        # Create permissions
        permission1 = Permission.objects.create(
            resource="shop", action="view", description="Can view shops"
        )
        permission2 = Permission.objects.create(
            resource="service", action="add", description="Can add services"
        )

        # Create custom role
        custom_role = RoleService.create_custom_role(
            "New Custom Role",
            "Custom role description",
            [permission1, permission2],
            entity=self.shop,
            parent=self.custom_role,
            performed_by=self.admin_user,
        )

        # Verify role properties
        self.assertEqual(custom_role.name, "New Custom Role")
        self.assertEqual(custom_role.description, "Custom role description")
        self.assertEqual(custom_role.role_type, "custom")
        self.assertEqual(custom_role.parent, self.custom_role)
        self.assertEqual(custom_role.content_type, ContentType.objects.get_for_model(self.shop))
        self.assertEqual(custom_role.object_id, self.shop.id)

        # Verify permissions
        self.assertEqual(custom_role.permissions.count(), 2)
        self.assertTrue(custom_role.permissions.filter(id=permission1.id).exists())
        self.assertTrue(custom_role.permissions.filter(id=permission2.id).exists())

    def test_transfer_users_between_roles(self):
        """Test transferring users between roles"""
        # Create additional user and assign to source role
        user2 = User.objects.create(phone_number="5556667777", user_type="employee")

        UserRole.objects.create(user=user2, role=self.custom_role, is_primary=True)

        # Verify users have source role
        self.assertEqual(UserRole.objects.filter(role=self.custom_role).count(), 2)

        # Create target role
        target_role = Role.objects.create(name="Target Role", role_type="custom", is_active=True)

        # Transfer users
        count = RoleService.transfer_users_between_roles(
            self.custom_role, target_role, performed_by=self.admin_user
        )

        # Verify transfer
        self.assertEqual(count, 2)
        self.assertEqual(UserRole.objects.filter(role=self.custom_role).count(), 0)
        self.assertEqual(UserRole.objects.filter(role=target_role).count(), 2)

    def test_can_user_manage_role(self):
        """Test checking if a user can manage a role"""
        # Admin can manage any role
        self.assertTrue(RoleService.can_user_manage_role(self.admin_user, self.employee_role))
        self.assertTrue(RoleService.can_user_manage_role(self.admin_user, self.custom_role))
        self.assertTrue(RoleService.can_user_manage_role(self.admin_user, self.shop_employee_role))

        # Employee can manage shop_employee_role (lower in hierarchy) but not admin_role (higher)
        self.assertFalse(RoleService.can_user_manage_role(self.employee_user, self.admin_role))
        self.assertTrue(
            RoleService.can_user_manage_role(self.employee_user, self.shop_employee_role)
        )


class PermissionResolverTest(TestCase):
    """Test the PermissionResolver"""

    def setUp(self):
        """Set up test data"""
        # Create permissions
        self.view_shop = Permission.objects.create(
            resource="shop", action="view", description="Can view shops"
        )
        self.add_shop = Permission.objects.create(
            resource="shop", action="add", description="Can add shops"
        )
        self.view_service = Permission.objects.create(
            resource="service", action="view", description="Can view services"
        )
        self.all_permissions = Permission.objects.create(
            resource="*",
            action="*",
            description="All permissions",
            code_name="*_*_wildcard",
        )

        # Create users
        self.admin_user = User.objects.create_user(
            phone_number="1234567890", user_type="admin", is_superuser=True
        )
        self.normal_user = User.objects.create_user(phone_number="0987654321", user_type="employee")

        # Create roles
        self.admin_role = Role.objects.create(
            name="Admin Role", role_type="queue_me_admin", is_active=True
        )
        self.admin_role.permissions.add(self.all_permissions)

        self.employee_role = Role.objects.create(
            name="Employee Role", role_type="custom", is_active=True
        )
        self.employee_role.permissions.add(self.view_shop)
        self.employee_role.permissions.add(self.view_service)

        # Create a shop entity for context testing
        from apps.shopapp.models import Shop

        self.shop = Shop.objects.create(
            name="Test Shop", phone_number="5555555555", username="testshop"
        )

        # Create shop-specific role
        shop_ct = ContentType.objects.get_for_model(Shop)

        self.shop_role = Role.objects.create(
            name="Shop Role",
            role_type="custom",
            content_type=shop_ct,
            object_id=self.shop.id,
            is_active=True,
        )
        self.shop_role.permissions.add(self.add_shop)

        # Assign roles to users
        UserRole.objects.create(user=self.normal_user, role=self.employee_role, is_primary=True)
        UserRole.objects.create(user=self.normal_user, role=self.shop_role, is_primary=True)

    def test_get_user_permissions(self):
        """Test getting user permissions"""
        # Admin user should have all permissions
        admin_permissions = PermissionResolver.get_user_permissions(self.admin_user)
        self.assertEqual(admin_permissions.count(), Permission.objects.count())

        # Normal user should have specific permissions
        normal_permissions = PermissionResolver.get_user_permissions(self.normal_user)
        self.assertEqual(normal_permissions.count(), 2)
        self.assertIn(self.view_shop, normal_permissions)
        self.assertIn(self.view_service, normal_permissions)

        # Test context-specific permissions
        shop_permissions = PermissionResolver.get_user_permissions(
            self.normal_user, "shop", self.shop.id
        )
        self.assertEqual(shop_permissions.count(), 1)
        self.assertIn(self.add_shop, shop_permissions)

    def test_has_permission(self):
        """Test checking if user has a permission"""
        # Admin user should have all permissions
        self.assertTrue(PermissionResolver.has_permission(self.admin_user, "shop", "view"))
        self.assertTrue(PermissionResolver.has_permission(self.admin_user, "shop", "add"))
        self.assertTrue(PermissionResolver.has_permission(self.admin_user, "service", "delete"))

        # Normal user should have specific permissions
        self.assertTrue(PermissionResolver.has_permission(self.normal_user, "shop", "view"))
        self.assertTrue(PermissionResolver.has_permission(self.normal_user, "service", "view"))
        self.assertFalse(PermissionResolver.has_permission(self.normal_user, "shop", "delete"))

    def test_has_context_permission(self):
        """Test checking if user has a permission in a specific context"""
        # Normal user should have add_shop permission in shop context
        self.assertTrue(
            PermissionResolver.has_context_permission(
                self.normal_user, "shop", self.shop.id, "shop", "add"
            )
        )

        # Normal user should still have global permissions in context
        self.assertTrue(
            PermissionResolver.has_context_permission(
                self.normal_user, "shop", self.shop.id, "shop", "view"
            )
        )

        # Normal user should not have delete permission in any context
        self.assertFalse(
            PermissionResolver.has_context_permission(
                self.normal_user, "shop", self.shop.id, "shop", "delete"
            )
        )

    def test_role_type_checks(self):
        """Test role type checking methods"""
        # Add queue_me_admin role to normal_user
        UserRole.objects.create(user=self.normal_user, role=self.admin_role)

        # Test is_queue_me_admin
        self.assertTrue(PermissionResolver.is_queue_me_admin(self.admin_user))
        self.assertTrue(PermissionResolver.is_queue_me_admin(self.normal_user))

        # Test is_queue_me_employee (should be true if admin)
        self.assertTrue(PermissionResolver.is_queue_me_employee(self.admin_user))
        self.assertTrue(PermissionResolver.is_queue_me_employee(self.normal_user))

        # Test has_role_type with multiple types
        self.assertTrue(
            PermissionResolver.has_role_type(self.normal_user, ["queue_me_admin", "custom"])
        )

        # Test with non-existent role type
        self.assertFalse(PermissionResolver.has_role_type(self.normal_user, "non_existent_type"))
