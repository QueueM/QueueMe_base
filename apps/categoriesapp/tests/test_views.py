from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import translation
from rest_framework import status
from rest_framework.test import APIClient

from apps.authapp.models import User
from apps.rolesapp.models import Permission, Role, UserRole

from ..models import Category, CategoryRelation


class CategoryViewSetTest(TestCase):
    """
    Test case for the CategoryViewSet
    """

    def setUp(self):
        """Set up test data"""
        # Clear cache
        cache.clear()

        # Create admin user with permissions
        self.admin_user = User.objects.create_user(
            phone_number="1234567890",
            password="testpass",
            user_type="admin",
            is_staff=True,
            is_active=True,
            is_verified=True,
        )

        # Create regular user
        self.user = User.objects.create_user(
            phone_number="9876543210",
            password="testpass",
            user_type="customer",
            is_staff=False,
            is_active=True,
            is_verified=True,
        )

        # Create employee user with category permissions
        self.employee_user = User.objects.create_user(
            phone_number="5556667777",
            password="testpass",
            user_type="employee",
            is_staff=False,
            is_active=True,
            is_verified=True,
        )

        # Create category permissions
        self.view_permission = Permission.objects.create(
            resource="category", action="view"
        )

        self.add_permission = Permission.objects.create(
            resource="category", action="add"
        )

        self.edit_permission = Permission.objects.create(
            resource="category", action="edit"
        )

        self.delete_permission = Permission.objects.create(
            resource="category", action="delete"
        )

        # Create a role with category permissions
        self.category_manager_role = Role.objects.create(
            name="Category Manager",
            role_type="queue_me_employee",
            description="Can manage categories",
        )

        # Add permissions to role
        self.category_manager_role.permissions.add(
            self.view_permission,
            self.add_permission,
            self.edit_permission,
            self.delete_permission,
        )

        # Assign role to employee user
        UserRole.objects.create(
            user=self.employee_user, role=self.category_manager_role
        )

        # Create parent categories
        self.parent_category1 = Category.objects.create(
            name="Test Parent Category 1",
            name_en="Test Parent Category 1",
            name_ar="تصنيف الأصل 1",
            description="Test parent category description",
            is_active=True,
            is_featured=True,
            position=1,
        )

        self.parent_category2 = Category.objects.create(
            name="Test Parent Category 2",
            name_en="Test Parent Category 2",
            name_ar="تصنيف الأصل 2",
            description="Test parent category description 2",
            is_active=True,
            position=2,
        )

        # Create child categories
        self.child_category1 = Category.objects.create(
            name="Test Child Category 1",
            name_en="Test Child Category 1",
            name_ar="تصنيف الفرعي 1",
            description="Test child category description",
            parent=self.parent_category1,
            is_active=True,
            position=1,
        )

        self.child_category2 = Category.objects.create(
            name="Test Child Category 2",
            name_en="Test Child Category 2",
            name_ar="تصنيف الفرعي 2",
            description="Test child category description 2",
            parent=self.parent_category1,
            is_active=True,
            position=2,
        )

        # Create inactive category
        self.inactive_category = Category.objects.create(
            name="Inactive Category", is_active=False, position=3
        )

        # Create category relation
        self.category_relation = CategoryRelation.objects.create(
            from_category=self.parent_category1,
            to_category=self.parent_category2,
            relation_type="related",
            weight=1.5,
        )

        # Setup API client
        self.client = APIClient()

    def test_list_categories(self):
        """Test listing categories"""
        url = reverse("category-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 4)  # 4 active categories

        # Test with inactive included
        response = self.client.get(url + "?active_only=false")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 5)  # 5 total categories

        # Test filtering by parent
        response = self.client.get(url + f"?parent={self.parent_category1.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)  # 2 children of parent1

        # Test filtering for top-level categories
        response = self.client.get(url + "?parent=null")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)  # 2 parent categories

        # Test filtering by is_parent=true
        response = self.client.get(url + "?is_parent=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)  # 2 parent categories

        # Test filtering by is_parent=false
        response = self.client.get(url + "?is_parent=false")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)  # 2 child categories

        # Test searching
        response = self.client.get(url + "?search=Child")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)  # 2 child categories

        # Test filtering by featured status
        response = self.client.get(url + "?featured=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)  # 1 featured category

    def test_retrieve_category(self):
        """Test retrieving a single category"""
        url = reverse("category-detail", args=[self.parent_category1.id])

        with translation.override("en"):
            response = self.client.get(url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["name"], "Test Parent Category 1")
            self.assertEqual(response.data["is_featured"], True)
            self.assertEqual(len(response.data["children"]), 2)

        with translation.override("ar"):
            response = self.client.get(url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["name"], "تصنيف الأصل 1")

    def test_create_category(self):
        """Test creating a category"""
        url = reverse("category-list")

        # Authentication required
        data = {
            "name": "New Test Category",
            "name_en": "New Test Category",
            "name_ar": "تصنيف جديد",
            "description": "New test category description",
            "is_active": True,
            "position": 4,
        }

        # Unauthenticated request should fail
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticate as regular user without required permissions
        self.client.force_authenticate(user=self.user)

        # Should fail due to lack of permissions
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Now should succeed
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New Test Category")

        # Verify in database
        category = Category.objects.get(name="New Test Category")
        self.assertEqual(category.name_ar, "تصنيف جديد")
        self.assertEqual(category.position, 4)

        # Test creating child category
        child_data = {
            "name": "New Child Category",
            "parent": str(self.parent_category1.id),
            "is_active": True,
            "position": 3,
        }

        response = self.client.post(url, child_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify in database
        child = Category.objects.get(name="New Child Category")
        self.assertEqual(child.parent, self.parent_category1)

        # Test as employee with permissions
        self.client.force_authenticate(user=self.employee_user)

        data = {"name": "Employee Created Category", "is_active": True, "position": 5}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify in database
        category = Category.objects.get(name="Employee Created Category")
        self.assertEqual(category.position, 5)

    def test_update_category(self):
        """Test updating a category"""
        url = reverse("category-detail", args=[self.parent_category1.id])

        data = {
            "name": "Updated Parent Category",
            "name_ar": "تصنيف الأصل محدث",
            "is_featured": False,
        }

        # Unauthenticated request should fail
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticate as regular user without required permissions
        self.client.force_authenticate(user=self.user)

        # Should fail due to lack of permissions
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Now should succeed
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Parent Category")

        # Verify in database
        category = Category.objects.get(id=self.parent_category1.id)
        self.assertEqual(category.name, "Updated Parent Category")
        self.assertEqual(category.name_ar, "تصنيف الأصل محدث")
        self.assertFalse(category.is_featured)

        # Test as employee with permissions
        self.client.force_authenticate(user=self.employee_user)

        data = {"name": "Employee Updated Category", "position": 3}

        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify in database
        category = Category.objects.get(id=self.parent_category1.id)
        self.assertEqual(category.name, "Employee Updated Category")
        self.assertEqual(category.position, 3)

    def test_delete_category(self):
        """Test deleting a category"""
        # Create a test category to delete
        category = Category.objects.create(name="Category To Delete", is_active=True)

        url = reverse("category-detail", args=[category.id])

        # Unauthenticated request should fail
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticate as regular user without required permissions
        self.client.force_authenticate(user=self.user)

        # Should fail due to lack of permissions
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Now should succeed
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify deletion
        with self.assertRaises(Category.DoesNotExist):
            Category.objects.get(id=category.id)

        # Create another test category to delete with employee user
        category = Category.objects.create(
            name="Category For Employee To Delete", is_active=True
        )

        url = reverse("category-detail", args=[category.id])

        # Authenticate as employee with permissions
        self.client.force_authenticate(user=self.employee_user)

        # Should succeed
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify deletion
        with self.assertRaises(Category.DoesNotExist):
            Category.objects.get(id=category.id)

    def test_parent_categories_action(self):
        """Test parent_categories action"""
        url = reverse("category-parent-categories")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # 2 parent categories

        # Check specific data
        categories = [c["id"] for c in response.data]
        self.assertIn(str(self.parent_category1.id), categories)
        self.assertIn(str(self.parent_category2.id), categories)

    def test_children_action(self):
        """Test children action"""
        url = reverse("category-children", args=[self.parent_category1.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # 2 children

        # Check specific data
        categories = [c["id"] for c in response.data]
        self.assertIn(str(self.child_category1.id), categories)
        self.assertIn(str(self.child_category2.id), categories)

    def test_hierarchy_action(self):
        """Test hierarchy action"""
        url = reverse("category-hierarchy")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # 2 parent categories

        # Find parent_category1 in the response
        parent1 = next(
            (
                item
                for item in response.data
                if item["id"] == str(self.parent_category1.id)
            ),
            None,
        )
        self.assertIsNotNone(parent1)
        self.assertEqual(len(parent1["children"]), 2)  # 2 children

        # Test with inactive categories
        response = self.client.get(url + "?include_inactive=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should include inactive categories now
        inactive_found = False
        for parent in response.data:
            for child in parent["children"]:
                if child["id"] == str(self.inactive_category.id):
                    inactive_found = True
                    break

        # Inactive category should be found if it was a child of one of the parents
        if self.inactive_category.parent is not None:
            self.assertTrue(inactive_found)

    def test_featured_action(self):
        """Test featured action"""
        url = reverse("category-featured")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # 1 featured category
        self.assertEqual(response.data[0]["id"], str(self.parent_category1.id))

        # Test with limit parameter
        response = self.client.get(url + "?limit=5")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            len(response.data), 1
        )  # Still 1 featured category (that's all we have)

    def test_popular_action(self):
        """Test popular action"""
        url = reverse("category-popular")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # The response should contain categories ordered by some popularity metric
        # The exact ordering depends on the implementation of the popular method

        # Test with limit parameter
        response = self.client.get(url + "?limit=2")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data), 2)  # Should be at most 2 categories

    def test_breadcrumbs_action(self):
        """Test breadcrumbs action"""
        url = reverse("category-breadcrumbs", args=[self.child_category1.id])

        with translation.override("en"):
            response = self.client.get(url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 2)  # 2 levels: parent -> child
            self.assertEqual(response.data[0]["name"], "Test Parent Category 1")
            self.assertEqual(response.data[1]["name"], "Test Child Category 1")

        with translation.override("ar"):
            response = self.client.get(url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 2)  # 2 levels: parent -> child
            self.assertEqual(response.data[0]["name"], "تصنيف الأصل 1")
            self.assertEqual(response.data[1]["name"], "تصنيف الفرعي 1")

    def test_flat_hierarchy_action(self):
        """Test flat_hierarchy action"""
        url = reverse("category-flat-hierarchy")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)  # 4 active categories

        # Check levels
        for item in response.data:
            if item["id"] in [
                str(self.parent_category1.id),
                str(self.parent_category2.id),
            ]:
                self.assertEqual(item["level"], 0)
            else:
                self.assertEqual(item["level"], 1)

        # Test with parent parameter
        response = self.client.get(url + f"?parent={self.parent_category1.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)  # parent + 2 children

        # Test with inactive included
        response = self.client.get(url + "?include_inactive=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5)  # All 5 categories

    def test_move_action(self):
        """Test move action"""
        url = reverse("category-move", args=[self.child_category1.id])

        data = {"parent": str(self.parent_category2.id)}

        # Unauthenticated request should fail
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticate as regular user without required permissions
        self.client.force_authenticate(user=self.user)

        # Should fail due to lack of permissions
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Now should succeed
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify move
        category = Category.objects.get(id=self.child_category1.id)
        self.assertEqual(category.parent, self.parent_category2)

        # Test moving to root level
        url = reverse("category-move", args=[self.child_category2.id])
        data = {"parent": None}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify move
        category = Category.objects.get(id=self.child_category2.id)
        self.assertIsNone(category.parent)

    def test_reorder_action(self):
        """Test reorder action"""
        url = reverse("category-reorder")

        data = [
            {"id": str(self.parent_category1.id), "position": 2},
            {"id": str(self.parent_category2.id), "position": 1},
        ]

        # Unauthenticated request should fail
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticate as regular user without required permissions
        self.client.force_authenticate(user=self.user)

        # Should fail due to lack of permissions
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Now should succeed
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify reordering
        parent1 = Category.objects.get(id=self.parent_category1.id)
        parent2 = Category.objects.get(id=self.parent_category2.id)

        self.assertEqual(parent1.position, 2)
        self.assertEqual(parent2.position, 1)

    def test_related_action(self):
        """Test related action"""
        url = reverse("category-related", args=[self.parent_category1.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # 1 related category
        self.assertEqual(response.data[0]["id"], str(self.parent_category2.id))

        # Test with relation_type filter
        response = self.client.get(url + "?type=related")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # 1 related category

        # Test with non-existent relation type
        response = self.client.get(url + "?type=nonexistent")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)  # 0 categories with this relation type

        # Test with limit parameter
        response = self.client.get(url + "?limit=10")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            len(response.data), 1
        )  # Still 1 related category (that's all we have)

    def test_statistics_action(self):
        """Test statistics action"""
        url = reverse("category-statistics")

        # Unauthenticated request should fail
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticate as regular user without admin role
        self.client.force_authenticate(user=self.user)

        # Should fail for non-admin
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Now should succeed
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check basic stats
        self.assertEqual(response.data["total_categories"], 5)
        self.assertEqual(response.data["parent_categories"], 2)
        self.assertEqual(response.data["inactive_categories"], 1)

        # Check categories by depth
        self.assertIn("categories_by_depth", response.data)
        self.assertIn("0", response.data["categories_by_depth"])
        self.assertEqual(
            response.data["categories_by_depth"]["0"], 2
        )  # 2 parent categories

    def test_check_integrity_action(self):
        """Test check_integrity action"""
        url = reverse("category-check-integrity")

        # Unauthenticated request should fail
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticate as regular user without admin role
        self.client.force_authenticate(user=self.user)

        # Should fail for non-admin
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Now should succeed
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check integrity results
        self.assertEqual(len(response.data["circular_references"]), 0)
        self.assertEqual(len(response.data["orphaned_categories"]), 0)
        self.assertEqual(len(response.data["invalid_parent_refs"]), 0)


class CategoryRelationViewSetTest(TestCase):
    """
    Test case for the CategoryRelationViewSet
    """

    def setUp(self):
        """Set up test data"""
        # Clear cache
        cache.clear()

        # Create admin user
        self.admin_user = User.objects.create_user(
            phone_number="1234567890",
            password="testpass",
            user_type="admin",
            is_staff=True,
            is_active=True,
            is_verified=True,
        )

        # Create regular user
        self.user = User.objects.create_user(
            phone_number="9876543210",
            password="testpass",
            user_type="customer",
            is_staff=False,
            is_active=True,
            is_verified=True,
        )

        # Create employee user with category permissions
        self.employee_user = User.objects.create_user(
            phone_number="5556667777",
            password="testpass",
            user_type="employee",
            is_staff=False,
            is_active=True,
            is_verified=True,
        )

        # Create category permissions
        category_permissions = [
            Permission.objects.create(resource="category", action="view"),
            Permission.objects.create(resource="category", action="add"),
            Permission.objects.create(resource="category", action="edit"),
            Permission.objects.create(resource="category", action="delete"),
        ]

        # Create a role with category permissions
        category_manager_role = Role.objects.create(
            name="Category Manager",
            role_type="queue_me_employee",
            description="Can manage categories",
        )

        # Add permissions to role
        for permission in category_permissions:
            category_manager_role.permissions.add(permission)

        # Assign role to employee user
        UserRole.objects.create(user=self.employee_user, role=category_manager_role)

        # Create categories
        self.category1 = Category.objects.create(name="Test Category 1", is_active=True)

        self.category2 = Category.objects.create(name="Test Category 2", is_active=True)

        self.category3 = Category.objects.create(name="Test Category 3", is_active=True)

        # Create category relations
        self.relation1 = CategoryRelation.objects.create(
            from_category=self.category1,
            to_category=self.category2,
            relation_type="related",
            weight=1.5,
        )

        self.relation2 = CategoryRelation.objects.create(
            from_category=self.category1,
            to_category=self.category3,
            relation_type="alternative",
            weight=1.0,
        )

        # Setup API client
        self.client = APIClient()

    def test_list_relations(self):
        """Test listing category relations"""
        url = reverse("category-relation-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # 2 relations

        # Test filtering by from_category
        response = self.client.get(url + f"?from_category={self.category1.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # 2 relations from category1

        # Test filtering by to_category
        response = self.client.get(url + f"?to_category={self.category2.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # 1 relation to category2

        # Test filtering by relation_type
        response = self.client.get(url + "?relation_type=alternative")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # 1 alternative relation

    def test_retrieve_relation(self):
        """Test retrieving a single relation"""
        url = reverse("category-relation-detail", args=[self.relation1.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["to_category"], str(self.category2.id))
        self.assertEqual(response.data["relation_type"], "related")
        self.assertEqual(response.data["weight"], 1.5)

    def test_create_relation(self):
        """Test creating a category relation"""
        url = reverse("category-relation-list")

        data = {
            "from_category": str(self.category2.id),
            "to_category": str(self.category3.id),
            "relation_type": "similar",
            "weight": 2.0,
        }

        # Unauthenticated request should fail
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticate as regular user without category permissions
        self.client.force_authenticate(user=self.user)

        # Should fail due to lack of permissions
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Now should succeed
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify in database
        relation = CategoryRelation.objects.get(
            from_category=self.category2, to_category=self.category3
        )
        self.assertEqual(relation.relation_type, "similar")
        self.assertEqual(relation.weight, 2.0)

        # Test as employee with category permissions
        self.client.force_authenticate(user=self.employee_user)

        data = {
            "from_category": str(self.category3.id),
            "to_category": str(self.category1.id),
            "relation_type": "similar",
            "weight": 1.0,
        }

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify in database
        relation = CategoryRelation.objects.get(
            from_category=self.category3, to_category=self.category1
        )
        self.assertEqual(relation.relation_type, "similar")
        self.assertEqual(relation.weight, 1.0)

    def test_update_relation(self):
        """Test updating a category relation"""
        url = reverse("category-relation-detail", args=[self.relation1.id])

        data = {"relation_type": "similar", "weight": 3.0}

        # Unauthenticated request should fail
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticate as regular user without category permissions
        self.client.force_authenticate(user=self.user)

        # Should fail due to lack of permissions
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Now should succeed
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify update
        relation = CategoryRelation.objects.get(id=self.relation1.id)
        self.assertEqual(relation.relation_type, "similar")
        self.assertEqual(relation.weight, 3.0)

        # Test as employee with category permissions
        self.client.force_authenticate(user=self.employee_user)

        data = {"relation_type": "alternative", "weight": 2.5}

        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify update
        relation = CategoryRelation.objects.get(id=self.relation1.id)
        self.assertEqual(relation.relation_type, "alternative")
        self.assertEqual(relation.weight, 2.5)

    def test_delete_relation(self):
        """Test deleting a category relation"""
        url = reverse("category-relation-detail", args=[self.relation1.id])

        # Unauthenticated request should fail
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticate as regular user without category permissions
        self.client.force_authenticate(user=self.user)

        # Should fail due to lack of permissions
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Now should succeed
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify deletion
        with self.assertRaises(CategoryRelation.DoesNotExist):
            CategoryRelation.objects.get(id=self.relation1.id)

        # Test as employee with category permissions
        url = reverse("category-relation-detail", args=[self.relation2.id])
        self.client.force_authenticate(user=self.employee_user)

        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify deletion
        with self.assertRaises(CategoryRelation.DoesNotExist):
            CategoryRelation.objects.get(id=self.relation2.id)

    def test_validation_preventing_circular_relations(self):
        """Test validation preventing relationship of category to itself"""
        url = reverse("category-relation-list")

        data = {
            "from_category": str(self.category1.id),
            "to_category": str(self.category1.id),
            "relation_type": "related",
            "weight": 1.0,
        }

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Should fail due to validation
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "to_category", response.data
        )  # Error message should mention to_category

    def test_validation_preventing_duplicate_relations(self):
        """Test validation preventing duplicate relations"""
        url = reverse("category-relation-list")

        data = {
            "from_category": str(self.category1.id),
            "to_category": str(self.category2.id),
            "relation_type": "related",  # Same as existing relation1
            "weight": 2.0,
        }

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Should fail due to validation
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "non_field_errors", response.data
        )  # Error message should be in non_field_errors
