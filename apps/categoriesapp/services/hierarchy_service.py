import logging

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils.translation import get_language

from ..models import Category

logger = logging.getLogger(__name__)

CACHE_TTL = getattr(settings, "CATEGORY_CACHE_TTL", 3600)  # 1 hour default


class HierarchyService:
    """
    Service class for managing and analyzing category hierarchies.
    Provides advanced methods for tree manipulation, validation,
    and optimization of hierarchical structures.
    """

    @staticmethod
    def build_category_tree(include_inactive=False):
        """
        Build a complete hierarchical tree structure of all categories.
        Optimized to minimize database queries through prefetching.

        Returns:
            list: A nested list of dictionaries representing the category tree
        """
        cache_key = f"category_tree_{include_inactive}"
        tree = cache.get(cache_key)

        if tree is None:
            # Get all categories in a single query with parent relations
            queryset = Category.objects.select_related("parent")

            if not include_inactive:
                queryset = queryset.filter(is_active=True)

            all_categories = list(queryset.order_by("position", "name"))

            # Organize by parent
            category_map = {}
            root_categories = []

            # First pass: map all categories by ID
            for category in all_categories:
                category_id = str(category.id)

                # Prepare translation fields based on current language
                lang = get_language()
                name_field = "name_ar" if lang == "ar" else "name_en"
                desc_field = "description_ar" if lang == "ar" else "description_en"

                # Create a dict representation of the category
                category_dict = {
                    "id": category_id,
                    "name": getattr(category, name_field),
                    "slug": category.slug,
                    "description": getattr(category, desc_field) or "",
                    "icon": category.icon.url if category.icon else None,
                    "image": category.image.url if category.image else None,
                    "is_active": category.is_active,
                    "is_featured": category.is_featured,
                    "position": category.position,
                    "children": [],  # Will be populated in second pass
                }

                category_map[category_id] = category_dict

                # Root categories have no parent
                if category.parent is None:
                    root_categories.append(category_dict)

            # Second pass: build the tree structure
            for category in all_categories:
                if category.parent:
                    parent_id = str(category.parent.id)
                    if parent_id in category_map:
                        category_id = str(category.id)
                        if category_id in category_map:
                            category_map[parent_id]["children"].append(category_map[category_id])

            # Sort children by position
            for category_dict in category_map.values():
                category_dict["children"].sort(key=lambda x: (x["position"], x["name"]))

            # Sort root categories by position
            root_categories.sort(key=lambda x: (x["position"], x["name"]))

            tree = root_categories
            cache.set(cache_key, tree, CACHE_TTL)

        return tree

    @staticmethod
    def get_category_path(category_id):
        """
        Get the full path of a category from root to the specified category.

        Args:
            category_id: UUID of the category

        Returns:
            list: List of Category objects from root to the target category
        """
        try:
            cache_key = f"category_path_{category_id}"
            path = cache.get(cache_key)

            if path is None:
                category = Category.objects.get(id=category_id)

                # Start with the target category
                path = [category]

                # Navigate up to the root
                current = category
                while current.parent:
                    current = current.parent
                    path.append(current)

                # Reverse to get root->target order
                path = path[::-1]

                cache.set(cache_key, path, CACHE_TTL)

            return path
        except Category.DoesNotExist:
            logger.error(f"Category not found: {category_id}")
            return []
        except Exception as e:
            logger.error(f"Error getting category path: {str(e)}")
            return []

    @staticmethod
    def flatten_category_tree(category_id=None, include_inactive=False):
        """
        Get a flattened list of all categories under a given parent (or all if no parent specified)
        with proper indentation level information to show hierarchy.

        Useful for admin interfaces to display hierarchies in a flat select/list.

        Args:
            category_id: Optional parent category UUID
            include_inactive: Whether to include inactive categories

        Returns:
            list: List of dicts with category info and level indicators
        """
        cache_key = f"flattened_tree_{category_id}_{include_inactive}"
        flattened = cache.get(cache_key)

        if flattened is None:
            flattened = []

            # Get base queryset
            queryset = Category.objects.select_related("parent")

            if not include_inactive:
                queryset = queryset.filter(is_active=True)

            if category_id:
                # Get the subtree
                try:
                    parent = queryset.get(id=category_id)
                    # Add the parent first
                    flattened.append(
                        {
                            "id": str(parent.id),
                            "name": parent.name,
                            "slug": parent.slug,
                            "level": 0,
                            "is_active": parent.is_active,
                            "has_children": parent.children.exists(),
                        }
                    )

                    # Helper function to recursively add children with level info
                    def add_children(parent_id, level):
                        children = queryset.filter(parent_id=parent_id).order_by("position", "name")
                        for child in children:
                            has_children = queryset.filter(parent=child).exists()
                            flattened.append(
                                {
                                    "id": str(child.id),
                                    "name": child.name,
                                    "slug": child.slug,
                                    "level": level,
                                    "is_active": child.is_active,
                                    "has_children": has_children,
                                }
                            )
                            # Recursively add this child's children
                            add_children(child.id, level + 1)

                    # Add all children recursively
                    add_children(parent.id, 1)

                except Category.DoesNotExist:
                    pass
            else:
                # Get all categories with hierarchy information
                # First, get all root categories
                root_categories = queryset.filter(parent__isnull=True).order_by("position", "name")

                for root in root_categories:
                    flattened.append(
                        {
                            "id": str(root.id),
                            "name": root.name,
                            "slug": root.slug,
                            "level": 0,
                            "is_active": root.is_active,
                            "has_children": queryset.filter(parent=root).exists(),
                        }
                    )

                    # Helper function to recursively add children with level info
                    def add_children(parent_id, level):
                        children = queryset.filter(parent_id=parent_id).order_by("position", "name")
                        for child in children:
                            has_children = queryset.filter(parent=child).exists()
                            flattened.append(
                                {
                                    "id": str(child.id),
                                    "name": child.name,
                                    "slug": child.slug,
                                    "level": level,
                                    "is_active": child.is_active,
                                    "has_children": has_children,
                                }
                            )
                            # Recursively add this child's children
                            add_children(child.id, level + 1)

                    # Add all children recursively
                    add_children(root.id, 1)

            cache.set(cache_key, flattened, CACHE_TTL)

        return flattened

    @staticmethod
    @transaction.atomic
    def move_category(category_id, new_parent_id=None):
        """
        Move a category to a new parent (or to root level if new_parent_id is None)

        Args:
            category_id: UUID of the category to move
            new_parent_id: UUID of the new parent, or None for root level

        Returns:
            bool: Success indicator
        """
        try:
            category = Category.objects.get(id=category_id)

            # If new parent is specified, check that it exists and wouldn't create a cycle
            if new_parent_id:
                new_parent = Category.objects.get(id=new_parent_id)

                # Check if new_parent is the same as current category
                if new_parent.id == category.id:
                    logger.error("Cannot set a category as its own parent")
                    return False

                # Check if new_parent is a descendant of the category
                # (which would create a cycle)
                current = new_parent
                while current.parent:
                    if current.parent.id == category.id:
                        logger.error("Cannot move category: would create a circular reference")
                        return False
                    current = current.parent

                category.parent = new_parent
            else:
                # Moving to root level
                category.parent = None

            category.save()

            # Clear relevant caches
            HierarchyService._clear_hierarchy_caches(category_id)

            return True
        except Category.DoesNotExist:
            logger.error(
                f"Category not found during move operation: {category_id} or {new_parent_id}"
            )
            return False
        except Exception as e:
            logger.error(f"Error moving category: {str(e)}")
            return False

    @staticmethod
    @transaction.atomic
    def reorganize_category_positions(parent_id=None):
        """
        Reorganize category positions to be sequential (1, 2, 3...)
        for all children of a given parent (or all root categories if parent_id is None)

        Args:
            parent_id: UUID of the parent category, or None for root level

        Returns:
            bool: Success indicator
        """
        try:
            # Get categories to reorganize
            if parent_id:
                categories = Category.objects.filter(parent_id=parent_id).order_by(
                    "position", "name"
                )
            else:
                categories = Category.objects.filter(parent__isnull=True).order_by(
                    "position", "name"
                )

            # Update positions to be sequential
            for index, category in enumerate(categories):
                if category.position != index + 1:
                    category.position = index + 1
                    category.save(update_fields=["position"])

            # Clear caches
            HierarchyService._clear_hierarchy_caches(parent_id)

            return True
        except Exception as e:
            logger.error(f"Error reorganizing category positions: {str(e)}")
            return False

    @staticmethod
    def check_hierarchy_integrity():
        """
        Check the integrity of the category hierarchy:
        - No circular references
        - No orphaned categories (except root level)
        - No invalid parent references

        Returns:
            dict: Report of any issues found
        """
        issues = {
            "circular_references": [],
            "orphaned_categories": [],
            "invalid_parent_refs": [],
        }

        try:
            # Check for invalid parent references
            categories = Category.objects.select_related("parent").all()

            # Build a dictionary mapping category IDs to their parent IDs
            parent_map = {}
            all_ids = set()

            for category in categories:
                all_ids.add(str(category.id))
                if category.parent:
                    parent_map[str(category.id)] = str(category.parent.id)

            # Check for invalid parent references
            for category_id, parent_id in parent_map.items():
                if parent_id not in all_ids:
                    cat = Category.objects.get(id=category_id)
                    issues["invalid_parent_refs"].append(
                        {"id": category_id, "name": cat.name, "parent_id": parent_id}
                    )

            # Check for circular references
            for category_id in parent_map:
                visited = set()
                current = category_id

                while current in parent_map:
                    if current in visited:
                        # Found a cycle
                        cycle = [current]
                        next_id = parent_map[current]
                        while next_id != current:
                            cycle.append(next_id)
                            next_id = parent_map[next_id]
                        cycle.append(current)  # Complete the cycle

                        # Get names for the report
                        cycle_with_names = []
                        for c_id in cycle:
                            try:
                                cat = Category.objects.get(id=c_id)
                                cycle_with_names.append({"id": c_id, "name": cat.name})
                            except Exception:
                                cycle_with_names.append({"id": c_id, "name": "Unknown"})

                        issues["circular_references"].append(cycle_with_names)
                        break

                    visited.add(current)
                    current = parent_map[current]

            # No need to check for orphans as every category is either a root or has a parent

            return issues
        except Exception as e:
            logger.error(f"Error checking hierarchy integrity: {str(e)}")
            return issues

    @staticmethod
    def get_category_statistics():
        """
        Get statistics about the category hierarchy

        Returns:
            dict: Various statistics about the category structure
        """
        try:
            stats = {
                "total_categories": 0,
                "parent_categories": 0,
                "child_categories": 0,
                "max_depth": 0,
                "inactive_categories": 0,
                "featured_categories": 0,
                "avg_children_per_parent": 0,
                "categories_by_depth": {},
            }

            # Basic counts
            all_categories = Category.objects.all()
            stats["total_categories"] = all_categories.count()
            stats["parent_categories"] = all_categories.filter(parent__isnull=True).count()
            stats["child_categories"] = all_categories.filter(parent__isnull=False).count()
            stats["inactive_categories"] = all_categories.filter(is_active=False).count()
            stats["featured_categories"] = all_categories.filter(is_featured=True).count()

            # Calculate average children per parent
            if stats["parent_categories"] > 0:
                stats["avg_children_per_parent"] = (
                    stats["child_categories"] / stats["parent_categories"]
                )

            # Calculate max depth and distribution by depth
            parent_categories = Category.objects.filter(parent__isnull=True)

            # Initialize depth tracking
            stats["categories_by_depth"] = {0: stats["parent_categories"]}
            max_depth = 0

            # Helper function to recursively calculate depth
            def calculate_depth(parent_id, current_depth):
                nonlocal max_depth
                children = Category.objects.filter(parent_id=parent_id)

                if not children:
                    return current_depth

                # Update max depth if needed
                if current_depth > max_depth:
                    max_depth = current_depth

                # Update depth distribution
                if current_depth in stats["categories_by_depth"]:
                    stats["categories_by_depth"][current_depth] += children.count()
                else:
                    stats["categories_by_depth"][current_depth] = children.count()

                # Recursively check children's depth
                max_child_depth = current_depth
                for child in children:
                    child_depth = calculate_depth(child.id, current_depth + 1)
                    if child_depth > max_child_depth:
                        max_child_depth = child_depth

                return max_child_depth

            # Calculate for each parent category
            for parent in parent_categories:
                depth = calculate_depth(parent.id, 1)
                if depth > max_depth:
                    max_depth = depth

            stats["max_depth"] = max_depth

            return stats
        except Exception as e:
            logger.error(f"Error getting category statistics: {str(e)}")
            return {}

    @staticmethod
    def _clear_hierarchy_caches(category_id=None):
        """
        Clear all hierarchy-related caches, or just for a specific category

        Args:
            category_id: Optional category ID to focus cache clearing
        """
        # Clear general hierarchy caches
        cache.delete("category_tree_True")
        cache.delete("category_tree_False")

        if category_id:
            # Clear specific category caches
            cache.delete(f"category_path_{category_id}")
            cache.delete(f"flattened_tree_{category_id}_True")
            cache.delete(f"flattened_tree_{category_id}_False")
        else:
            # Clear all flattened tree caches
            cache.delete("flattened_tree_None_True")
            cache.delete("flattened_tree_None_False")
