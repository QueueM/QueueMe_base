from django.test import TestCase
from django.utils.text import slugify

from ..models import Category, CategoryRelation


class CategoryModelTest(TestCase):
    """
    Test case for the Category model
    """

    def setUp(self):
        """Set up test data"""
        # Create parent categories
        self.parent_category1 = Category.objects.create(
            name="Test Parent Category 1",
            name_en="Test Parent Category 1",
            name_ar="تصنيف الأصل 1",
            description="Test parent category description",
            description_en="Test parent category description",
            description_ar="وصف تصنيف الأصل",
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

        # Create category relation
        self.category_relation = CategoryRelation.objects.create(
            from_category=self.parent_category1,
            to_category=self.parent_category2,
            relation_type="related",
            weight=1.5,
        )

    def test_category_creation(self):
        """Test that categories are created correctly"""
        self.assertEqual(self.parent_category1.name, "Test Parent Category 1")
        self.assertEqual(self.parent_category1.name_ar, "تصنيف الأصل 1")
        self.assertEqual(
            self.parent_category1.slug,
            slugify("Test Parent Category 1", allow_unicode=True),
        )
        self.assertTrue(self.parent_category1.is_active)
        self.assertTrue(self.parent_category1.is_featured)
        self.assertEqual(self.parent_category1.position, 1)

        self.assertEqual(self.child_category1.parent, self.parent_category1)
        self.assertEqual(self.child_category1.name, "Test Child Category 1")
        self.assertEqual(self.child_category1.position, 1)

    def test_is_parent_property(self):
        """Test the is_parent property"""
        self.assertTrue(self.parent_category1.is_parent)
        self.assertFalse(self.child_category1.is_parent)

    def test_is_child_property(self):
        """Test the is_child property"""
        self.assertFalse(self.parent_category1.is_child)
        self.assertTrue(self.child_category1.is_child)

    def test_str_representation(self):
        """Test the string representation of categories"""
        self.assertEqual(str(self.parent_category1), "Test Parent Category 1")
        self.assertEqual(
            str(self.child_category1), "Test Child Category 1 (Test Parent Category 1)"
        )

    def test_get_all_children(self):
        """Test getting all children of a category"""
        children = self.parent_category1.get_all_children()
        self.assertEqual(len(children), 2)
        self.assertIn(self.child_category1, children)
        self.assertIn(self.child_category2, children)

    def test_get_parent_hierarchy(self):
        """Test getting the parent hierarchy of a category"""
        # Create a deeper hierarchy
        grandchild = Category.objects.create(
            name="Test Grandchild Category", parent=self.child_category1, is_active=True
        )

        hierarchy = grandchild.get_parent_hierarchy()
        self.assertEqual(len(hierarchy), 2)
        self.assertEqual(hierarchy[0], self.parent_category1)
        self.assertEqual(hierarchy[1], self.child_category1)

    def test_automatic_slug_generation(self):
        """Test that slugs are automatically generated"""
        category = Category.objects.create(name="Test Slug Generation", is_active=True)

        self.assertEqual(category.slug, "test-slug-generation")

        # Test duplicate slug handling
        category2 = Category.objects.create(name="Test Slug Generation", is_active=True)

        self.assertNotEqual(category2.slug, category.slug)
        self.assertTrue(category2.slug.startswith("test-slug-generation-"))

    def test_multilingual_fields(self):
        """Test that multilingual fields are handled correctly"""
        # Test initialization of multilingual fields from main field
        category = Category.objects.create(
            name="Test Multilingual", description="Test description", is_active=True
        )

        self.assertEqual(category.name_en, "Test Multilingual")
        self.assertEqual(category.name_ar, "Test Multilingual")
        self.assertEqual(category.description_en, "Test description")
        self.assertEqual(category.description_ar, "Test description")

        # Test custom values for multilingual fields
        category = Category.objects.create(
            name="Test Custom Multilingual",
            name_en="English Name",
            name_ar="Arabic Name",
            description="Default description",
            description_en="English description",
            description_ar="Arabic description",
            is_active=True,
        )

        self.assertEqual(category.name, "Test Custom Multilingual")
        self.assertEqual(category.name_en, "English Name")
        self.assertEqual(category.name_ar, "Arabic Name")
        self.assertEqual(category.description, "Default description")
        self.assertEqual(category.description_en, "English description")
        self.assertEqual(category.description_ar, "Arabic description")

    def test_category_relation(self):
        """Test category relations"""
        self.assertEqual(self.category_relation.from_category, self.parent_category1)
        self.assertEqual(self.category_relation.to_category, self.parent_category2)
        self.assertEqual(self.category_relation.relation_type, "related")
        self.assertEqual(self.category_relation.weight, 1.5)

        # Test string representation
        expected_str = f"{self.parent_category1} → {self.parent_category2} (related)"
        self.assertEqual(str(self.category_relation), expected_str)
