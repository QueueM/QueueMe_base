import logging

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils.text import slugify
from django.utils.translation import get_language

from ..models import Category, CategoryRelation

logger = logging.getLogger(__name__)

CACHE_TTL = getattr(settings, "CATEGORY_CACHE_TTL", 3600)  # 1 hour default


class CategoryService:
    """
    Service class for category-related business logic and operations.
    Includes advanced functionality for category management, optimization,
    and smart traversal of category hierarchies.
    """

    @staticmethod
    def get_all_categories(active_only=True):
        """Get all categories with optional filtering by active status"""
        query = Category.objects.all()
        if active_only:
            query = query.filter(is_active=True)
        return query.order_by("position", "name")

    @staticmethod
    def get_category_by_id(category_id):
        """Get category by ID with optimized queries for related data"""
        try:
            # Get from cache first
            cache_key = f"category_{category_id}"
            category = cache.get(cache_key)
            if category:
                return category

            # If not in cache, fetch from DB with optimized query
            category = Category.objects.select_related("parent").get(id=category_id)

            # Store in cache
            cache.set(cache_key, category, CACHE_TTL)

            return category
        except Category.DoesNotExist:
            return None

    @staticmethod
    def get_category_by_slug(slug):
        """Get category by slug with optimized queries for related data"""
        try:
            cache_key = f"category_slug_{slug}"
            category = cache.get(cache_key)
            if category:
                return category

            category = Category.objects.select_related("parent").get(slug=slug)
            cache.set(cache_key, category, CACHE_TTL)

            return category
        except Category.DoesNotExist:
            return None

    @staticmethod
    def get_parent_categories(active_only=True):
        """Get all parent categories (those without a parent)"""
        cache_key = f"parent_categories_{active_only}"
        categories = cache.get(cache_key)

        if categories is None:
            query = Category.objects.filter(parent__isnull=True)
            if active_only:
                query = query.filter(is_active=True)
            categories = list(query.order_by("position", "name"))
            cache.set(cache_key, categories, CACHE_TTL)

        return categories

    @staticmethod
    def get_child_categories(parent_id, active_only=True):
        """Get child categories for a given parent"""
        cache_key = f"child_categories_{parent_id}_{active_only}"
        children = cache.get(cache_key)

        if children is None:
            query = Category.objects.filter(parent_id=parent_id)
            if active_only:
                query = query.filter(is_active=True)
            children = list(query.order_by("position", "name"))
            cache.set(cache_key, children, CACHE_TTL)

        return children

    @staticmethod
    def get_category_with_children(category_id):
        """Get a category with all its immediate children"""
        try:
            category = CategoryService.get_category_by_id(category_id)
            if not category:
                return None

            children = CategoryService.get_child_categories(category_id)

            # Add children to the category object (this doesn't alter the DB)
            # It's just a convenience for the caller
            category._children = children

            return category
        except Exception as e:
            logger.error(f"Error getting category with children: {str(e)}")
            return None

    @staticmethod
    def get_category_hierarchy():
        """
        Get the complete category hierarchy as a nested structure
        Returns parent categories with their children preloaded
        """
        cache_key = "category_hierarchy"
        hierarchy = cache.get(cache_key)

        if hierarchy is None:
            # Get all parent categories
            parent_categories = CategoryService.get_parent_categories()

            # For each parent, preload its children
            hierarchy = []
            for parent in parent_categories:
                children = CategoryService.get_child_categories(parent.id)
                parent._children = children
                hierarchy.append(parent)

            cache.set(cache_key, hierarchy, CACHE_TTL)

        return hierarchy

    @staticmethod
    def get_featured_categories(limit=10):
        """Get featured categories for homepage or special promotion"""
        cache_key = f"featured_categories_{limit}"
        featured = cache.get(cache_key)

        if featured is None:
            featured = Category.objects.filter(
                is_active=True, is_featured=True
            ).order_by("position")[:limit]

            cache.set(cache_key, list(featured), CACHE_TTL)

        return featured

    @staticmethod
    def get_popular_categories(limit=10):
        """
        Get popular categories based on service count and specialist count
        This is a more complex query that ranks categories by their popularity
        """
        cache_key = f"popular_categories_{limit}"
        popular = cache.get(cache_key)

        if popular is None:
            # This calculation would normally involve joins with service and specialist tables
            # For simplicity, we'll just get active categories and would sort by metrics in a real implementation
            # In production, this would be a more complex query with annotations

            # Simplified example - in a real implementation we'd join with services and count
            popular = Category.objects.filter(
                is_active=True, parent__isnull=False  # Only child categories
            ).order_by("-service_count", "position")[:limit]

            cache.set(cache_key, list(popular), CACHE_TTL)

        return popular

    @staticmethod
    @transaction.atomic
    def create_category(data):
        """
        Create a new category with all necessary validations and processing
        """
        try:
            # Generate slug if not provided
            if "slug" not in data or not data["slug"]:
                name = data.get("name", "")
                data["slug"] = slugify(name, allow_unicode=True)

            # Create category
            category = Category.objects.create(**data)

            # Clear relevant caches
            CategoryService._clear_category_caches()

            return category
        except Exception as e:
            logger.error(f"Error creating category: {str(e)}")
            raise

    @staticmethod
    @transaction.atomic
    def update_category(category_id, data):
        """
        Update an existing category with validations
        """
        try:
            category = CategoryService.get_category_by_id(category_id)
            if not category:
                return None

            # Update fields
            for key, value in data.items():
                setattr(category, key, value)

            # Special handling for slug if name changed
            if "name" in data and ("slug" not in data or not data["slug"]):
                category.slug = slugify(data["name"], allow_unicode=True)

            category.save()

            # Clear caches
            CategoryService._clear_category_caches(category_id)

            return category
        except Exception as e:
            logger.error(f"Error updating category: {str(e)}")
            raise

    @staticmethod
    @transaction.atomic
    def delete_category(category_id):
        """
        Delete a category after validating it can be safely removed
        """
        try:
            category = CategoryService.get_category_by_id(category_id)
            if not category:
                return False

            # Check if category has services (in production you'd check real service counts)
            # For now, let's assume we have direct access to related services
            if hasattr(category, "services") and category.services.count() > 0:
                # Instead of hard delete, we'll soft delete by marking inactive
                category.is_active = False
                category.save()
                CategoryService._clear_category_caches(category_id)
                return True

            # If it has children, we'll need special handling
            if category.children.exists():
                # Option 1: Reassign children to category's parent (if any)
                if category.parent:
                    category.children.update(parent=category.parent)
                else:
                    # Option 2: Make children top-level categories
                    category.children.update(parent=None)

            # Now we can delete the category
            category.delete()

            # Clear caches
            CategoryService._clear_category_caches(category_id)

            return True
        except Exception as e:
            logger.error(f"Error deleting category: {str(e)}")
            raise

    @staticmethod
    def reorder_categories(ordering_data):
        """
        Update the position field of categories based on provided ordering data
        ordering_data should be a list of dicts with 'id' and 'position' keys
        """
        with transaction.atomic():
            for item in ordering_data:
                Category.objects.filter(id=item["id"]).update(position=item["position"])

            # Clear caches that might be affected by reordering
            CategoryService._clear_category_caches()

        return True

    @staticmethod
    @transaction.atomic
    def create_category_relation(
        from_category_id, to_category_id, relation_type="related", weight=1.0
    ):
        """Create a relation between two categories"""
        try:
            # Check if categories exist
            from_category = CategoryService.get_category_by_id(from_category_id)
            to_category = CategoryService.get_category_by_id(to_category_id)

            if not from_category or not to_category:
                return None

            # Check for existing relation
            existing = CategoryRelation.objects.filter(
                from_category=from_category,
                to_category=to_category,
                relation_type=relation_type,
            ).first()

            if existing:
                # Update weight if relation exists
                existing.weight = weight
                existing.save()
                return existing

            # Create new relation
            relation = CategoryRelation.objects.create(
                from_category=from_category,
                to_category=to_category,
                relation_type=relation_type,
                weight=weight,
            )

            # Optionally create reciprocal relation if needed
            # (Uncomment if you want bidirectional relationships)
            # CategoryRelation.objects.get_or_create(
            #     from_category=to_category,
            #     to_category=from_category,
            #     relation_type=relation_type,
            #     defaults={'weight': weight}
            # )

            # Clear relevant cache
            cache_key = f"related_categories_{from_category_id}"
            cache.delete(cache_key)

            return relation
        except Exception as e:
            logger.error(f"Error creating category relation: {str(e)}")
            raise

    @staticmethod
    def get_related_categories(category_id, relation_type=None, limit=5):
        """Get related categories for a given category"""
        cache_key = f"related_categories_{category_id}_{relation_type}_{limit}"
        related = cache.get(cache_key)

        if related is None:
            query = CategoryRelation.objects.filter(from_category_id=category_id)

            if relation_type:
                query = query.filter(relation_type=relation_type)

            # Order by weight descending to get strongest relationships first
            relations = query.order_by("-weight")[:limit]

            # Extract the related categories
            related = [rel.to_category for rel in relations]

            cache.set(cache_key, related, CACHE_TTL)

        return related

    @staticmethod
    def get_category_breadcrumbs(category_id):
        """
        Generate breadcrumb data for a category, showing its position in the hierarchy
        """
        try:
            category = CategoryService.get_category_by_id(category_id)
            if not category:
                return []

            breadcrumbs = []
            current = category

            # Add the current category first
            lang = get_language()
            name_field = "name_ar" if lang == "ar" else "name_en"

            breadcrumbs.append(
                {
                    "id": str(current.id),
                    "name": getattr(current, name_field),
                    "slug": current.slug,
                }
            )

            # Then traverse up the parent chain
            while current.parent:
                current = current.parent
                breadcrumbs.append(
                    {
                        "id": str(current.id),
                        "name": getattr(current, name_field),
                        "slug": current.slug,
                    }
                )

            # Reverse to get root->leaf order
            return breadcrumbs[::-1]
        except Exception as e:
            logger.error(f"Error generating breadcrumbs: {str(e)}")
            return []

    @staticmethod
    def _clear_category_caches(category_id=None):
        """Clear all category-related caches, or just for a specific category"""
        if category_id:
            # Clear specific category caches
            cache.delete(f"category_{category_id}")
            cache.delete(f"child_categories_{category_id}_True")
            cache.delete(f"child_categories_{category_id}_False")
            cache.delete(f"related_categories_{category_id}")

            # Also try to find and clear the slug cache
            try:
                category = Category.objects.get(id=category_id)
                cache.delete(f"category_slug_{category.slug}")
            except Exception:
                pass

        # Clear general category caches
        cache.delete("parent_categories_True")
        cache.delete("parent_categories_False")
        cache.delete("category_hierarchy")
        cache.delete("featured_categories_10")  # Common default
        cache.delete("popular_categories_10")  # Common default
