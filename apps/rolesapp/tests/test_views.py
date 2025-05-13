# apps/rolesapp/tests/test_views.py

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.authapp.models import User
from apps.rolesapp.models import Permission, Role, UserRole
from apps.rolesapp.serializers import PermissionSerializer, RoleSerializer, UserRoleSerializer


class PermissionViewSetTest(TestCase):
    """Test the PermissionViewSet"""

    def setUp(self):
        """Set up test data"""
        # Create admin user
        self.admin_user = User.objects.create_user(
            phone_number="1234567890", user_type="admin", is_superuser=True
        )

        # Create permissions
        self.permission1 = Permission.objects.create(
            resource="shop", action="view", description="Can view shops"
        )
        self.permission2 = Permission.objects.create(
            resource="service", action="add", description="Can add services"
        )

        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

        # API endpoints
        self.list_url = reverse("rolesapp:permission-list")
        self.detail_url = reverse("rolesapp:permission-detail", args=[self.permission1.id])
        self.grouped_url = reverse("rolesapp:permission-grouped")

    def test_get_permissions_list(self):
        """Test getting list of permissions"""
        response = self.client.get(self.list_url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get permissions from DB
        permissions = Permission.objects.all()
        serializer = PermissionSerializer(permissions, many=True)

        # Compare response with expected data
        self.assertEqual(response.data["results"], serializer.data)

    def test_get_permission_detail(self):
        """Test getting permission detail"""
        response = self.client.get(self.detail_url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get permission from DB
        serializer = PermissionSerializer(self.permission1)

        # Compare response with expected data
        self.assertEqual(response.data, serializer.data)

    def test_permissions_read_only(self):
        """Test that permissions are read-only"""
        # Try to create a permission
        data = {"resource": "test", "action": "test", "description": "Test permission"}
        response = self.client.post(self.list_url, data, format="json")

        # Verify request was rejected
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # Try to update a permission
        response = self.client.put(
            self.detail_url, {"description": "Updated description"}, format="json"
        )

        # Verify request was rejected
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # Try to delete a permission
        response = self.client.delete(self.detail_url)

        # Verify request was rejected
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_get_grouped_permissions(self):
        """Test getting permissions grouped by resource"""
        response = self.client.get(self.grouped_url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify structure
        self.assertTrue(isinstance(response.data, list))
        self.assertEqual(len(response.data), 2)  # One group for each resource

        # Verify content
        resources = set(item["resource"] for item in response.data)
        self.assertIn("shop", resources)
        self.assertIn("service", resources)

        # Get shop group
        shop_group = next(item for item in response.data if item["resource"] == "shop")

        # Verify permissions in group
        self.assertEqual(len(shop_group["permissions"]), 1)
        self.assertEqual(shop_group["permissions"][0]["id"], str(self.permission1.id))


class RoleViewSetTest(TestCase):
    """Test the RoleViewSet"""

    def setUp(self):
        """Set up test data"""
        # Create users
        self.admin_user = User.objects.create_user(
            phone_number="1234567890", user_type="admin", is_superuser=True
        )
        self.normal_user = User.objects.create_user(phone_number="0987654321", user_type="employee")

        # Create permissions
        self.permission1 = Permission.objects.create(
            resource="shop", action="view", description="Can view shops"
        )
        self.permission2 = Permission.objects.create(
            resource="service", action="add", description="Can add services"
        )
        self.roles_manage = Permission.objects.create(
            resource="roles", action="manage", description="Can manage roles"
        )

        # Create roles
        self.role1 = Role.objects.create(
            name="Admin Role",
            description="For administrators",
            role_type="queue_me_admin",
            weight=1000,
            is_active=True,
            is_system=True,
        )
        self.role1.permissions.add(self.permission1, self.permission2, self.roles_manage)

        self.role2 = Role.objects.create(
            name="Custom Role",
            description="For testing",
            role_type="custom",
            weight=100,
            is_active=True,
        )
        self.role2.permissions.add(self.permission1)

        # Assign roles
        UserRole.objects.create(user=self.normal_user, role=self.role2, is_primary=True)

        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

        # API endpoints
        self.list_url = reverse("rolesapp:role-list")
        self.detail_url = reverse("rolesapp:role-detail", args=[self.role1.id])
        self.clone_url = reverse("rolesapp:role-clone", args=[self.role1.id])

    def test_get_roles_list(self):
        """Test getting list of roles"""
        response = self.client.get(self.list_url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get roles from DB
        roles = Role.objects.all()
        serializer = RoleSerializer(roles, many=True)

        # Compare response with expected data
        self.assertEqual(response.data["results"], serializer.data)

    def test_get_role_detail(self):
        """Test getting role detail"""
        response = self.client.get(self.detail_url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify data structure
        self.assertIn("permissions", response.data)
        self.assertIn("users", response.data)

    def test_create_role(self):
        """Test creating a role"""
        # Prepare data
        data = {
            "name": "New Role",
            "description": "New role description",
            "role_type": "custom",
            "permission_ids": [str(self.permission1.id)],
            "weight": 50,
            "is_active": True,
        }

        response = self.client.post(self.list_url, data, format="json")

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify role was created
        self.assertTrue(Role.objects.filter(name="New Role").exists())

        # Verify permissions were assigned
        new_role = Role.objects.get(name="New Role")
        self.assertEqual(new_role.permissions.count(), 1)
        self.assertIn(self.permission1, new_role.permissions.all())

    def test_update_role(self):
        """Test updating a role"""
        # Prepare data
        data = {
            "name": "Updated Role",
            "description": "Updated description",
            "permission_ids": [str(self.permission2.id)],
        }

        response = self.client.patch(self.detail_url, data, format="json")

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh role from DB
        self.role1.refresh_from_db()

        # Verify changes
        self.assertEqual(self.role1.name, "Updated Role")
        self.assertEqual(self.role1.description, "Updated description")

        # Verify permissions were updated
        self.assertEqual(self.role1.permissions.count(), 1)
        self.assertIn(self.permission2, self.role1.permissions.all())

    def test_delete_role(self):
        """Test deleting a role"""
        # Try to delete system role (should fail)
        response = self.client.delete(self.detail_url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Verify role was not deleted
        self.assertTrue(Role.objects.filter(id=self.role1.id).exists())

        # Try deleting non-system role
        non_system_url = reverse("rolesapp:role-detail", args=[self.role2.id])
        response = self.client.delete(non_system_url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify role was deleted
        self.assertFalse(Role.objects.filter(id=self.role2.id).exists())

    def test_clone_role(self):
        """Test cloning a role"""
        # Prepare data
        data = {"name": "Cloned Role", "description": "Cloned description"}

        response = self.client.post(self.clone_url, data, format="json")

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify role was cloned
        self.assertTrue(Role.objects.filter(name="Cloned Role").exists())

        # Verify cloned role properties
        cloned_role = Role.objects.get(name="Cloned Role")
        self.assertEqual(cloned_role.description, "Cloned description")
        self.assertEqual(cloned_role.role_type, self.role1.role_type)
        self.assertFalse(cloned_role.is_system)

        # Verify permissions were cloned
        self.assertEqual(cloned_role.permissions.count(), self.role1.permissions.count())
        for perm in self.role1.permissions.all():
            self.assertIn(perm, cloned_role.permissions.all())


class UserRoleViewSetTest(TestCase):
    """Test the UserRoleViewSet"""

    def setUp(self):
        """Set up test data"""
        # Create users
        self.admin_user = User.objects.create_user(
            phone_number="1234567890", user_type="admin", is_superuser=True
        )
        self.user1 = User.objects.create_user(phone_number="1111111111", user_type="employee")
        self.user2 = User.objects.create_user(phone_number="2222222222", user_type="employee")

        # Create permissions
        self.roles_manage = Permission.objects.create(
            resource="roles", action="manage", description="Can manage roles"
        )

        # Create roles
        self.role1 = Role.objects.create(name="Role 1", role_type="custom", is_active=True)
        self.role2 = Role.objects.create(name="Role 2", role_type="custom", is_active=True)

        # Create user roles
        self.user_role = UserRole.objects.create(
            user=self.user1,
            role=self.role1,
            assigned_by=self.admin_user,
            is_primary=True,
        )

        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

        # API endpoints
        self.list_url = reverse("rolesapp:userrole-list")
        self.detail_url = reverse("rolesapp:userrole-detail", args=[self.user_role.id])
        self.my_roles_url = reverse("rolesapp:userrole-my-roles")
        self.by_user_url = reverse("rolesapp:userrole-by-user")
        self.by_role_url = reverse("rolesapp:userrole-by-role")

    def test_get_user_roles_list(self):
        """Test getting list of user roles"""
        response = self.client.get(self.list_url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get user roles from DB
        user_roles = UserRole.objects.all()
        serializer = UserRoleSerializer(user_roles, many=True)

        # Compare response with expected data
        self.assertEqual(response.data["results"], serializer.data)

    def test_get_user_role_detail(self):
        """Test getting user role detail"""
        response = self.client.get(self.detail_url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get user role from DB
        serializer = UserRoleSerializer(self.user_role)

        # Compare response with expected data
        self.assertEqual(response.data, serializer.data)

    def test_create_user_role(self):
        """Test creating a user role"""
        # Prepare data
        data = {
            "user": str(self.user2.id),
            "role": str(self.role2.id),
            "is_primary": True,
        }

        response = self.client.post(self.list_url, data, format="json")

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify user role was created
        self.assertTrue(UserRole.objects.filter(user=self.user2, role=self.role2).exists())

        # Verify assigned_by was set to the current user
        user_role = UserRole.objects.get(user=self.user2, role=self.role2)
        self.assertEqual(user_role.assigned_by, self.admin_user)

    def test_update_user_role(self):
        """Test updating a user role"""
        # Prepare data
        data = {"is_primary": False}

        response = self.client.patch(self.detail_url, data, format="json")

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh user role from DB
        self.user_role.refresh_from_db()

        # Verify changes
        self.assertFalse(self.user_role.is_primary)

    def test_delete_user_role(self):
        """Test deleting a user role"""
        response = self.client.delete(self.detail_url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify user role was deleted
        self.assertFalse(UserRole.objects.filter(id=self.user_role.id).exists())

    def test_get_my_roles(self):
        """Test getting current user's roles"""
        # Create a role for admin_user
        admin_role = UserRole.objects.create(user=self.admin_user, role=self.role1, is_primary=True)

        response = self.client.get(self.my_roles_url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify data
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], str(admin_role.id))

    def test_get_by_user(self):
        """Test getting roles for a specific user"""
        # Add URL parameter
        url = f"{self.by_user_url}?user_id={self.user1.id}"

        response = self.client.get(url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify data
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], str(self.user_role.id))

        # Test with missing user_id
        response = self.client.get(self.by_user_url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_by_role(self):
        """Test getting users for a specific role"""
        # Add URL parameter
        url = f"{self.by_role_url}?role_id={self.role1.id}"

        response = self.client.get(url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify data
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], str(self.user_role.id))

        # Test with missing role_id
        response = self.client.get(self.by_role_url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
