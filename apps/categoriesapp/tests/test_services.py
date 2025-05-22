from django.core.cache import cache
from django.test import TestCase
from django.utils import translation

from ..models import Category, CategoryRelation
from ..services.category_service import CategoryService
from ..services.hierarchy_service import HierarchyService


class CategoryServiceTest(TestCase):
    """
    Test case for the CategoryService
    """

    def setUp(self):
        """Set up test data"""
        # Clear cache
        cache.clear()

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
            name="Inactive Category",
            name_en="Inactive Category",
            name_ar="تصنيف غير نشط",
            is_active=False,
            position=3,
        )

        # Create category relation
        self.category_relation = CategoryRelation.objects.create(
            from_category=self.parent_category1,
            to_category=self.parent_category2,
            relation_type="related",
            weight=1.5,
        )

    def test_get_all_categories(self):
        """Test getting all categories"""
        # Test with active_only=True (default)
        categories = CategoryService.get_all_categories()
        self.assertEqual(len(categories), 4)  # 4 active categories
        self.assertIn(self.parent_category1, categories)
        self.assertIn(self.child_category1, categories)
        self.assertNotIn(self.inactive_category, categories)

        # Test with active_only=False
        all_categories = CategoryService.get_all_categories(active_only=False)
        self.assertEqual(len(all_categories), 5)  # All 5 categories
        self.assertIn(self.inactive_category, all_categories)

    def test_get_category_by_id(self):
        """Test getting a category by ID"""
        category = CategoryService.get_category_by_id(self.parent_category1.id)
        self.assertEqual(category, self.parent_category1)

        # Test caching
        with self.assertNumQueries(0):
            CategoryService.get_category_by_id(self.parent_category1.id)

        # Test non-existent category
        non_existent = CategoryService.get_category_by_id(
            "00000000-0000-0000-0000-000000000000"
        )
        self.assertIsNone(non_existent)

    def test_get_category_by_slug(self):
        """Test getting a category by slug"""
        category = CategoryService.get_category_by_slug(self.parent_category1.slug)
        self.assertEqual(category, self.parent_category1)

        # Test caching
        with self.assertNumQueries(0):
            CategoryService.get_category_by_slug(self.parent_category1.slug)

        # Test non-existent slug
        non_existent = CategoryService.get_category_by_slug("non-existent-slug")
        self.assertIsNone(non_existent)

    def test_get_parent_categories(self):
        """Test getting parent categories"""
        parents = CategoryService.get_parent_categories()
        self.assertEqual(len(parents), 2)  # 2 active parent categories
        self.assertIn(self.parent_category1, parents)
        self.assertIn(self.parent_category2, parents)

        # Test with inactive parent
        inactive_parent = Category.objects.create(
            name="Inactive Parent", is_active=False
        )

        # Refresh parents
        CategoryService._clear_category_caches()

        parents = CategoryService.get_parent_categories()
        self.assertEqual(len(parents), 2)  # Still 2 active parent categories
        self.assertNotIn(inactive_parent, parents)

        # Test with active_only=False
        all_parents = CategoryService.get_parent_categories(active_only=False)
        self.assertEqual(len(all_parents), 3)  # All 3 parent categories
        self.assertIn(inactive_parent, all_parents)

    def test_get_child_categories(self):
        """Test getting child categories"""
        children = CategoryService.get_child_categories(self.parent_category1.id)
        self.assertEqual(len(children), 2)  # 2 active child categories
        self.assertIn(self.child_category1, children)
        self.assertIn(self.child_category2, children)

        # Test with inactive child
        inactive_child = Category.objects.create(
            name="Inactive Child", parent=self.parent_category1, is_active=False
        )

        # Refresh children
        CategoryService._clear_category_caches()

        children = CategoryService.get_child_categories(self.parent_category1.id)
        self.assertEqual(len(children), 2)  # Still 2 active child categories
        self.assertNotIn(inactive_child, children)

        # Test with active_only=False
        all_children = CategoryService.get_child_categories(
            self.parent_category1.id, active_only=False
        )
        self.assertEqual(len(all_children), 3)  # All 3 child categories
        self.assertIn(inactive_child, all_children)

    def test_get_category_with_children(self):
        """Test getting a category with its children"""
        category = CategoryService.get_category_with_children(self.parent_category1.id)
        self.assertEqual(category, self.parent_category1)
        self.assertTrue(hasattr(category, "_children"))
        self.assertEqual(len(category._children), 2)
        self.assertIn(self.child_category1, category._children)
        self.assertIn(self.child_category2, category._children)

    def test_get_category_hierarchy(self):
        """Test getting the category hierarchy"""
        hierarchy = CategoryService.get_category_hierarchy()
        self.assertEqual(len(hierarchy), 2)  # 2 parent categories

        # Check that children are loaded
        for parent in hierarchy:
            if parent.id == self.parent_category1.id:
                self.assertTrue(hasattr(parent, "_children"))
                self.assertEqual(len(parent._children), 2)

        # Test caching
        with self.assertNumQueries(0):
            CategoryService.get_category_hierarchy()

    def test_get_featured_categories(self):
        """Test getting featured categories"""
        featured = CategoryService.get_featured_categories()
        self.assertEqual(len(featured), 1)  # Only parent_category1 is featured
        self.assertIn(self.parent_category1, featured)

        # Make another category featured
        self.child_category1.is_featured = True
        self.child_category1.save()

        # Refresh featured categories
        CategoryService._clear_category_caches()

        featured = CategoryService.get_featured_categories()
        self.assertEqual(len(featured), 2)  # Now 2 featured categories
        self.assertIn(self.parent_category1, featured)
        self.assertIn(self.child_category1, featured)

        # Test limit
        featured = CategoryService.get_featured_categories(limit=1)
        self.assertEqual(len(featured), 1)

    def test_create_category(self):
        """Test creating a category"""
        category_data = {
            "name": "Test New Category",
            "name_en": "Test New Category",
            "name_ar": "تصنيف جديد",
            "description": "Test new category description",
            "is_active": True,
            "position": 4,
        }

        category = CategoryService.create_category(category_data)
        self.assertEqual(category.name, "Test New Category")
        self.assertEqual(category.name_ar, "تصنيف جديد")
        self.assertEqual(category.position, 4)
        self.assertTrue(category.is_active)

        # Verify it's in the database
        db_category = Category.objects.get(id=category.id)
        self.assertEqual(db_category.name, "Test New Category")

    def test_update_category(self):
        """Test updating a category"""
        update_data = {
            "name": "Updated Parent Category",
            "name_ar": "تصنيف الأصل محدث",
            "is_featured": False,
        }

        updated = CategoryService.update_category(self.parent_category1.id, update_data)
        self.assertEqual(updated.name, "Updated Parent Category")
        self.assertEqual(updated.name_ar, "تصنيف الأصل محدث")
        self.assertFalse(updated.is_featured)

        # Verify changes in database
        db_category = Category.objects.get(id=self.parent_category1.id)
        self.assertEqual(db_category.name, "Updated Parent Category")
        self.assertEqual(db_category.name_ar, "تصنيف الأصل محدث")
        self.assertFalse(db_category.is_featured)

    def test_delete_category(self):
        """Test deleting a category"""
        # Create a test category to delete
        category_to_delete = Category.objects.create(
            name="Category To Delete", is_active=True
        )

        # Delete the category
        result = CategoryService.delete_category(category_to_delete.id)
        self.assertTrue(result)

        # Verify it's deleted
        with self.assertRaises(Category.DoesNotExist):
            Category.objects.get(id=category_to_delete.id)

    def test_delete_category_with_services(self):
        """Test deleting a category that has services"""
        # We'll simulate services by setting service_count > 0
        # In a real implementation, we'd check actual service associations
        category = Category.objects.create(
            name="Category With Services", is_active=True
        )

        # Mock service_count property
        original_property = Category.service_count
        try:
            Category.service_count = property(
                lambda self: 5 if self.id == category.id else 0
            )

            # Try to delete
            result = CategoryService.delete_category(category.id)
            self.assertTrue(result)

            # Verify it's soft-deleted (marked inactive), not hard-deleted
            db_category = Category.objects.get(id=category.id)
            self.assertFalse(db_category.is_active)
        finally:
            # Restore original property
            Category.service_count = original_property

    def test_delete_category_with_children(self):
        """Test deleting a category that has children"""
        # Create a parent with children
        parent = Category.objects.create(name="Parent To Delete", is_active=True)

        child1 = Category.objects.create(name="Child 1", parent=parent, is_active=True)

        child2 = Category.objects.create(name="Child 2", parent=parent, is_active=True)

        # Delete the parent
        result = CategoryService.delete_category(parent.id)
        self.assertTrue(result)

        # Verify parent is deleted
        with self.assertRaises(Category.DoesNotExist):
            Category.objects.get(id=parent.id)

        # Verify children are now top-level
        updated_child1 = Category.objects.get(id=child1.id)
        updated_child2 = Category.objects.get(id=child2.id)

        self.assertIsNone(updated_child1.parent)
        self.assertIsNone(updated_child2.parent)

    def test_reorder_categories(self):
        """Test reordering categories"""
        # Get initial positions
        initial_pos1 = self.parent_category1.position
        initial_pos2 = self.parent_category2.position

        # Swap positions
        ordering_data = [
            {"id": str(self.parent_category1.id), "position": initial_pos2},
            {"id": str(self.parent_category2.id), "position": initial_pos1},
        ]

        result = CategoryService.reorder_categories(ordering_data)
        self.assertTrue(result)

        # Verify positions are updated
        updated_cat1 = Category.objects.get(id=self.parent_category1.id)
        updated_cat2 = Category.objects.get(id=self.parent_category2.id)

        self.assertEqual(updated_cat1.position, initial_pos2)
        self.assertEqual(updated_cat2.position, initial_pos1)

    def test_create_category_relation(self):
        """Test creating a category relation"""
        # Create a relation
        relation = CategoryService.create_category_relation(
            self.parent_category2.id, self.child_category1.id, "alternative", 2.0
        )

        self.assertEqual(relation.from_category, self.parent_category2)
        self.assertEqual(relation.to_category, self.child_category1)
        self.assertEqual(relation.relation_type, "alternative")
        self.assertEqual(relation.weight, 2.0)

        # Verify it's in the database
        db_relation = CategoryRelation.objects.get(
            from_category=self.parent_category2, to_category=self.child_category1
        )
        self.assertEqual(db_relation.relation_type, "alternative")

    def test_get_related_categories(self):
        """Test getting related categories"""
        related = CategoryService.get_related_categories(self.parent_category1.id)
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0], self.parent_category2)

        # Add another relation with different type
        CategoryService.create_category_relation(
            self.parent_category1.id, self.child_category2.id, "alternative", 1.0
        )

        # Test getting all related categories
        CategoryService._clear_category_caches()
        all_related = CategoryService.get_related_categories(self.parent_category1.id)
        self.assertEqual(len(all_related), 2)

        # Test filtering by relation type
        related_alt = CategoryService.get_related_categories(
            self.parent_category1.id, relation_type="alternative"
        )
        self.assertEqual(len(related_alt), 1)
        self.assertEqual(related_alt[0], self.child_category2)

    def test_get_category_breadcrumbs(self):
        """Test generating category breadcrumbs"""
        # Create a deeper hierarchy
        grandchild = Category.objects.create(
            name="Test Grandchild",
            name_en="Test Grandchild",
            name_ar="تصنيف الحفيد",
            parent=self.child_category1,
            is_active=True,
        )

        # Test with English language
        with translation.override("en"):
            breadcrumbs = CategoryService.get_category_breadcrumbs(grandchild.id)
            self.assertEqual(len(breadcrumbs), 3)
            self.assertEqual(breadcrumbs[0]["name"], "Test Parent Category 1")
            self.assertEqual(breadcrumbs[1]["name"], "Test Child Category 1")
            self.assertEqual(breadcrumbs[2]["name"], "Test Grandchild")

        # Test with Arabic language
        with translation.override("ar"):
            breadcrumbs = CategoryService.get_category_breadcrumbs(grandchild.id)
            self.assertEqual(len(breadcrumbs), 3)
            self.assertEqual(breadcrumbs[0]["name"], "تصنيف الأصل 1")
            self.assertEqual(breadcrumbs[1]["name"], "تصنيف الفرعي 1")
            self.assertEqual(breadcrumbs[2]["name"], "تصنيف الحفيد")


class HierarchyServiceTest(TestCase):
    """
    Test case for the HierarchyService
    """

    def setUp(self):
        """Set up test data"""
        # Clear cache
        cache.clear()

        # Create parent categories
        self.parent_category1 = Category.objects.create(
            name="Test Parent Category 1",
            name_en="Test Parent Category 1",
            name_ar="تصنيف الأصل 1",
            description="Test parent category description",
            is_active=True,
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

        # Create grandchild category for deeper hierarchy
        self.grandchild_category = Category.objects.create(
            name="Test Grandchild Category",
            name_en="Test Grandchild Category",
            name_ar="تصنيف الحفيد",
            description="Test grandchild category description",
            parent=self.child_category1,
            is_active=True,
            position=1,
        )

        # Create inactive category
        self.inactive_category = Category.objects.create(
            name="Inactive Category",
            name_en="Inactive Category",
            name_ar="تصنيف غير نشط",
            parent=self.parent_category2,
            is_active=False,
            position=1,
        )

    def test_build_category_tree(self):
        """Test building the category tree"""
        with translation.override("en"):
            tree = HierarchyService.build_category_tree()

            # Should be 2 parent categories
            self.assertEqual(len(tree), 2)

            # Find parent_category1 in the tree
            parent1_node = next(
                (item for item in tree if item["id"] == str(self.parent_category1.id)),
                None,
            )
            self.assertIsNotNone(parent1_node)
            self.assertEqual(parent1_node["name"], "Test Parent Category 1")

            # Check children of parent_category1
            self.assertEqual(len(parent1_node["children"]), 2)

            # Find parent_category2 in the tree
            parent2_node = next(
                (item for item in tree if item["id"] == str(self.parent_category2.id)),
                None,
            )
            self.assertIsNotNone(parent2_node)

            # parent_category2 should have no active children
            self.assertEqual(len(parent2_node["children"]), 0)

            # Test with inactive categories included
            tree_with_inactive = HierarchyService.build_category_tree(
                include_inactive=True
            )

            # Find parent_category2 in the tree
            parent2_node = next(
                (
                    item
                    for item in tree_with_inactive
                    if item["id"] == str(self.parent_category2.id)
                ),
                None,
            )
            self.assertIsNotNone(parent2_node)

            # Now it should have 1 inactive child
            self.assertEqual(len(parent2_node["children"]), 1)
            self.assertEqual(parent2_node["children"][0]["name"], "Inactive Category")

    def test_get_category_path(self):
        """Test getting a category path"""
        # Test with grandchild
        path = HierarchyService.get_category_path(self.grandchild_category.id)
        self.assertEqual(len(path), 3)
        self.assertEqual(path[0], self.parent_category1)
        self.assertEqual(path[1], self.child_category1)
        self.assertEqual(path[2], self.grandchild_category)

        # Test with child
        path = HierarchyService.get_category_path(self.child_category1.id)
        self.assertEqual(len(path), 2)
        self.assertEqual(path[0], self.parent_category1)
        self.assertEqual(path[1], self.child_category1)

        # Test with parent
        path = HierarchyService.get_category_path(self.parent_category1.id)
        self.assertEqual(len(path), 1)
        self.assertEqual(path[0], self.parent_category1)

        # Test with non-existent ID
        path = HierarchyService.get_category_path(
            "00000000-0000-0000-0000-000000000000"
        )
        self.assertEqual(len(path), 0)

    def test_flatten_category_tree(self):
        """Test flattening the category tree"""
        # Test full tree
        flattened = HierarchyService.flatten_category_tree()

        # Should have 5 active categories
        self.assertEqual(len(flattened), 5)

        # Verify levels
        for item in flattened:
            if item["id"] == str(self.parent_category1.id) or item["id"] == str(
                self.parent_category2.id
            ):
                self.assertEqual(item["level"], 0)
            elif item["id"] == str(self.child_category1.id) or item["id"] == str(
                self.child_category2.id
            ):
                self.assertEqual(item["level"], 1)
            elif item["id"] == str(self.grandchild_category.id):
                self.assertEqual(item["level"], 2)

        # Test subtree for parent_category1
        subtree = HierarchyService.flatten_category_tree(self.parent_category1.id)

        # Should have 4 items: parent_category1 + 2 children + 1 grandchild
        self.assertEqual(len(subtree), 4)

        # First item should be parent_category1
        self.assertEqual(subtree[0]["id"], str(self.parent_category1.id))
        self.assertEqual(subtree[0]["level"], 0)

        # Last item should be grandchild
        self.assertEqual(subtree[3]["id"], str(self.grandchild_category.id))
        self.assertEqual(subtree[3]["level"], 2)

    def test_move_category(self):
        """Test moving a category"""
        # Move child_category2 to be under parent_category2
        result = HierarchyService.move_category(
            self.child_category2.id, self.parent_category2.id
        )
        self.assertTrue(result)

        # Verify the move
        updated_child = Category.objects.get(id=self.child_category2.id)
        self.assertEqual(updated_child.parent, self.parent_category2)

        # Test moving to root level
        result = HierarchyService.move_category(self.child_category1.id)
        self.assertTrue(result)

        # Verify the move to root
        updated_child = Category.objects.get(id=self.child_category1.id)
        self.assertIsNone(updated_child.parent)

        # Test preventing circular references
        # Trying to set grandchild as parent of parent_category1 should fail
        result = HierarchyService.move_category(
            self.parent_category1.id, self.grandchild_category.id
        )
        self.assertFalse(result)

        # Verify parent_category1 hasn't changed
        updated_parent = Category.objects.get(id=self.parent_category1.id)
        self.assertIsNone(updated_parent.parent)

    def test_reorganize_category_positions(self):
        """Test reorganizing category positions"""
        # Change positions to non-sequential values
        self.parent_category1.position = 5
        self.parent_category1.save()

        self.parent_category2.position = 10
        self.parent_category2.save()

        # Reorganize parent positions
        result = HierarchyService.reorganize_category_positions()
        self.assertTrue(result)

        # Verify positions are now sequential
        updated_parent1 = Category.objects.get(id=self.parent_category1.id)
        updated_parent2 = Category.objects.get(id=self.parent_category2.id)

        self.assertEqual(updated_parent1.position, 1)
        self.assertEqual(updated_parent2.position, 2)

        # Test reorganizing children positions
        self.child_category1.position = 3
        self.child_category1.save()

        self.child_category2.position = 7
        self.child_category2.save()

        result = HierarchyService.reorganize_category_positions(
            self.parent_category1.id
        )
        self.assertTrue(result)

        # Verify child positions are sequential
        updated_child1 = Category.objects.get(id=self.child_category1.id)
        updated_child2 = Category.objects.get(id=self.child_category2.id)

        self.assertEqual(updated_child1.position, 1)
        self.assertEqual(updated_child2.position, 2)

    def test_check_hierarchy_integrity(self):
        """Test checking hierarchy integrity"""
        # Normal hierarchy should have no issues
        issues = HierarchyService.check_hierarchy_integrity()
        self.assertEqual(len(issues["circular_references"]), 0)
        self.assertEqual(len(issues["orphaned_categories"]), 0)
        self.assertEqual(len(issues["invalid_parent_refs"]), 0)

        # To test circular reference detection, we need to bypass model validation
        # by directly manipulating the database
        child = Category.objects.get(id=self.child_category1.id)
        parent = Category.objects.get(id=self.parent_category1.id)

        # Make parent a child of its child (circular)
        parent.parent = child
        parent.save()

        # Check integrity again
        issues = HierarchyService.check_hierarchy_integrity()
        self.assertEqual(len(issues["circular_references"]), 1)

    def test_get_category_statistics(self):
        """Test getting category statistics"""
        stats = HierarchyService.get_category_statistics()

        # Verify basic counts
        self.assertEqual(stats["total_categories"], 6)  # Total categories
        self.assertEqual(stats["parent_categories"], 2)  # Top-level categories
        self.assertEqual(stats["child_categories"], 4)  # Non-top-level categories
        self.assertEqual(stats["inactive_categories"], 1)  # Inactive category

        # Verify depth calculation
        self.assertEqual(stats["max_depth"], 2)  # Deepest level is grandchild (depth 2)

        # Verify categories by depth
        self.assertEqual(stats["categories_by_depth"][0], 2)  # 2 parent categories
        self.assertEqual(stats["categories_by_depth"][1], 3)  # 3 child categories
        self.assertEqual(stats["categories_by_depth"][2], 1)  # 1 grandchild category
