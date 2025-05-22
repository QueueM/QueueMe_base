# apps/rolesapp/tests/test_models.py

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.authapp.models import User
from apps.rolesapp.models import Permission, Role, RolePermissionLog, UserRole


class PermissionModelTest(TestCase):
    """Test the Permission model"""

    def setUp(self):
        """Set up test data"""
        self.permission = Permission.objects.create(
            resource="shop", action="view", description="Can view shops"
        )

    def test_permission_creation(self):
        """Test creating a permission"""
        self.assertEqual(self.permission.resource, "shop")
        self.assertEqual(self.permission.action, "view")
        self.assertEqual(self.permission.description, "Can view shops")
        self.assertEqual(self.permission.code_name, "shop_view")
        self.assertEqual(str(self.permission), "View Shop")

    def test_wildcard_permission(self):
        """Test wildcard permission"""
        wildcard = Permission.objects.create(
            resource="*", action="*", description="All permissions"
        )
        self.assertEqual(wildcard.code_name, "*_*_wildcard")


class RoleModelTest(TestCase):
    """Test the Role model"""

    def setUp(self):
        """Set up test data"""
        # Create permissions
        self.view_shop = Permission.objects.create(
            resource="shop", action="view", description="Can view shops"
        )
        self.add_shop = Permission.objects.create(
            resource="shop", action="add", description="Can add shops"
        )

        # Create parent role
        self.parent_role = Role.objects.create(
            name="Base Role", role_type="custom", weight=100, is_active=True
        )
        self.parent_role.permissions.add(self.view_shop)

        # Create child role
        self.role = Role.objects.create(
            name="Test Role",
            description="Test description",
            role_type="custom",
            parent=self.parent_role,
            weight=50,
            is_active=True,
        )
        self.role.permissions.add(self.add_shop)

    def test_role_creation(self):
        """Test creating a role"""
        self.assertEqual(self.role.name, "Test Role")
        self.assertEqual(self.role.description, "Test description")
        self.assertEqual(self.role.role_type, "custom")
        self.assertEqual(self.role.parent, self.parent_role)
        self.assertEqual(self.role.weight, 50)
        self.assertTrue(self.role.is_active)
        self.assertFalse(self.role.is_system)

    def test_permission_inheritance(self):
        """Test permission inheritance from parent role"""
        # Role should have its own permission
        self.assertTrue(self.role.has_permission("shop", "add"))

        # Role should inherit parent's permission
        self.assertTrue(self.role.has_permission("shop", "view"))

        # Role should not have other permissions
        self.assertFalse(self.role.has_permission("shop", "edit"))

        # Test all_permissions property
        all_permissions = self.role.all_permissions
        self.assertEqual(len(all_permissions), 2)
        self.assertIn(self.view_shop, all_permissions)
        self.assertIn(self.add_shop, all_permissions)


class UserRoleModelTest(TestCase):
    """Test the UserRole model"""

    def setUp(self):
        """Set up test data"""
        # Create users
        self.user = User.objects.create(phone_number="1234567890", user_type="employee")
        self.assigner = User.objects.create(
            phone_number="0987654321", user_type="admin"
        )

        # Create roles
        self.role1 = Role.objects.create(
            name="Role 1", role_type="custom", is_active=True
        )

        self.role2 = Role.objects.create(
            name="Role 2", role_type="custom", is_active=True
        )

        # Create shop entity for context testing
        from apps.shopapp.models import Shop

        self.shop = Shop.objects.create(
            name="Test Shop", phone_number="5555555555", username="testshop"
        )

        # Create roles for the shop
        shop_ct = ContentType.objects.get_for_model(Shop)

        self.shop_role1 = Role.objects.create(
            name="Shop Role 1",
            role_type="custom",
            content_type=shop_ct,
            object_id=self.shop.id,
            is_active=True,
        )

        self.shop_role2 = Role.objects.create(
            name="Shop Role 2",
            role_type="custom",
            content_type=shop_ct,
            object_id=self.shop.id,
            is_active=True,
        )

        # Assign roles
        self.user_role = UserRole.objects.create(
            user=self.user, role=self.role1, assigned_by=self.assigner, is_primary=True
        )

        self.shop_user_role = UserRole.objects.create(
            user=self.user,
            role=self.shop_role1,
            assigned_by=self.assigner,
            is_primary=True,
        )

    def test_user_role_creation(self):
        """Test creating a user role"""
        self.assertEqual(self.user_role.user, self.user)
        self.assertEqual(self.user_role.role, self.role1)
        self.assertEqual(self.user_role.assigned_by, self.assigner)
        self.assertTrue(self.user_role.is_primary)

    def test_primary_role_exclusivity(self):
        """Test that only one role can be primary in a context"""
        # Create a second role for the same user in the same context
        # This should automatically set is_primary=False for existing primary role
        user_role2 = UserRole.objects.create(
            user=self.user,
            role=self.shop_role2,
            assigned_by=self.assigner,
            is_primary=True,
        )

        # Refresh from DB
        self.shop_user_role.refresh_from_db()

        # Original shop role should no longer be primary
        self.assertFalse(self.shop_user_role.is_primary)

        # New role should be primary
        self.assertTrue(user_role2.is_primary)

        # Global role should still be primary
        self.user_role.refresh_from_db()
        self.assertTrue(self.user_role.is_primary)


class RolePermissionLogModelTest(TestCase):
    """Test the RolePermissionLog model"""

    def setUp(self):
        """Set up test data"""
        # Create user, permission, and role
        self.user = User.objects.create(phone_number="1234567890", user_type="admin")

        self.permission = Permission.objects.create(
            resource="shop", action="view", description="Can view shops"
        )

        self.role = Role.objects.create(
            name="Test Role", role_type="custom", is_active=True
        )

        # Create log entry
        self.log = RolePermissionLog.objects.create(
            role=self.role,
            permission=self.permission,
            action_type="add",
            performed_by=self.user,
        )

    def test_log_creation(self):
        """Test creating a log entry"""
        self.assertEqual(self.log.role, self.role)
        self.assertEqual(self.log.permission, self.permission)
        self.assertEqual(self.log.action_type, "add")
        self.assertEqual(self.log.performed_by, self.user)

        # Test string representation
        expected_str = f"{self.permission} added to {self.role} by {self.user} at {self.log.timestamp}"
        self.assertEqual(str(self.log), expected_str)
