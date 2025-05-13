"""
Categories app views for QueueMe platform
Handles endpoints related to category management, hierarchies, and relationships.
Categories are used to organize services, shops, and other entities across the platform.
"""

from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from apps.rolesapp.decorators import has_permission

from .models import Category, CategoryRelation
from .permissions import CategoryPermission
from .serializers import (
    CategoryCreateUpdateSerializer,
    CategoryHierarchySerializer,
    CategoryListSerializer,
    CategoryRelationCreateSerializer,
    CategoryRelationSerializer,
    CategorySerializer,
)
from .services.category_service import CategoryService
from .services.hierarchy_service import HierarchyService


class CategoryPagination(PageNumberPagination):
    """
    Pagination class for category listings

    Controls the page size and maximum page size for category listings.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class CategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing categories.

    Provides CRUD operations and additional actions for managing
    the category hierarchy and relationships. Categories form a tree structure
    with parent-child relationships and can be used to organize services,
    shops, and other entities.

    Endpoints:
    - GET /api/categories/ - List categories with filtering options
    - POST /api/categories/ - Create a new category
    - GET /api/categories/{id}/ - Get category details
    - PUT/PATCH /api/categories/{id}/ - Update a category
    - DELETE /api/categories/{id}/ - Delete a category
    - GET /api/categories/parent_categories/ - Get top-level categories
    - GET /api/categories/{id}/children/ - Get child categories
    - GET /api/categories/hierarchy/ - Get complete category tree
    - GET /api/categories/featured/ - Get featured categories
    - GET /api/categories/popular/ - Get popular categories
    - GET /api/categories/{id}/breadcrumbs/ - Get category breadcrumbs
    - GET /api/categories/flat_hierarchy/ - Get flattened category tree
    - POST /api/categories/{id}/move/ - Move a category to a new parent
    - POST /api/categories/reorder/ - Reorder categories
    - GET /api/categories/{id}/related/ - Get related categories
    - GET /api/categories/statistics/ - Get category statistics (admin only)
    - GET /api/categories/check_integrity/ - Check hierarchy integrity (admin only)

    Permissions:
    - Most read operations allow anonymous access
    - Write operations require authentication and specific permissions
    """

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    pagination_class = CategoryPagination
    permission_classes = [CategoryPermission]
    lookup_field = "id"

    def get_queryset(self):
        """
        Get base queryset with optional filtering

        Applies filters based on query parameters:
        - active_only: Show only active categories (default: true)
        - parent: Filter by parent category ID or 'null' for top-level categories
        - featured: Filter by featured status
        - is_parent: Filter for parent or child categories
        - search: Search in category names (includes translations)

        Returns:
            QuerySet: Filtered categories ordered by position and name
        """
        queryset = Category.objects.all()

        # Apply filter for active status
        active_only = self.request.query_params.get("active_only", "true").lower() == "true"
        if active_only:
            queryset = queryset.filter(is_active=True)

        # Filter by parent
        parent_id = self.request.query_params.get("parent")
        if parent_id:
            if parent_id.lower() == "null":
                queryset = queryset.filter(parent__isnull=True)
            else:
                queryset = queryset.filter(parent_id=parent_id)

        # Filter by featured status
        featured = self.request.query_params.get("featured")
        if featured and featured.lower() == "true":
            queryset = queryset.filter(is_featured=True)

        # Filter by is_parent/is_child
        is_parent = self.request.query_params.get("is_parent")
        if is_parent:
            if is_parent.lower() == "true":
                queryset = queryset.filter(parent__isnull=True)
            elif is_parent.lower() == "false":
                queryset = queryset.filter(parent__isnull=False)

        # Search by name
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(name_en__icontains=search)
                | Q(name_ar__icontains=search)
            )

        # Order by position and name
        queryset = queryset.order_by("position", "name")

        return queryset

    def get_serializer_class(self):
        """
        Return appropriate serializer class based on action and parameters

        - list: CategoryListSerializer (simpler representation for lists)
        - create/update: CategoryCreateUpdateSerializer (validates hierarchy)
        - hierarchy: CategoryHierarchySerializer (specialized for tree structure)
        - other actions: CategorySerializer (standard representation)

        Returns:
            Serializer class: The appropriate serializer for the current action
        """
        if self.action == "list":
            return CategoryListSerializer
        elif self.action == "create" or self.action == "update" or self.action == "partial_update":
            return CategoryCreateUpdateSerializer
        elif self.action == "hierarchy":
            return CategoryHierarchySerializer
        return CategorySerializer

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def parent_categories(self, request):
        """
        Get all parent categories (categories without a parent)

        Returns all top-level categories in the hierarchy, which can be used
        as starting points for navigating the category tree.

        Returns:
            Response: List of parent categories
        """
        parent_categories = CategoryService.get_parent_categories()
        serializer = CategorySerializer(parent_categories, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def children(self, request, id=None):
        """
        Get all child categories for a parent category

        Returns all immediate children of the specified category.

        Returns:
            Response: List of child categories
        """
        children = CategoryService.get_child_categories(id)
        serializer = CategorySerializer(children, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def hierarchy(self, request):
        """
        Get complete category hierarchy as a nested structure

        Returns the full category tree with parent-child relationships
        represented as nested objects. Useful for building category
        navigation menus.

        Query parameters:
            include_inactive: Include inactive categories (default: false)

        Returns:
            Response: Nested category hierarchy
        """
        include_inactive = request.query_params.get("include_inactive", "false").lower() == "true"
        tree = HierarchyService.build_category_tree(include_inactive)
        return Response(tree)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def featured(self, request):
        """
        Get featured categories

        Returns categories marked as featured, which are typically
        highlighted in the UI and receive special promotion.

        Query parameters:
            limit: Maximum number of categories to return (default: 10)

        Returns:
            Response: List of featured categories
        """
        limit = int(request.query_params.get("limit", 10))
        featured = CategoryService.get_featured_categories(limit)
        serializer = CategorySerializer(featured, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def popular(self, request):
        """
        Get popular categories based on service count and interactions

        Returns categories that have the most services and user interactions,
        which are useful for highlighting trending categories.

        Query parameters:
            limit: Maximum number of categories to return (default: 10)

        Returns:
            Response: List of popular categories
        """
        limit = int(request.query_params.get("limit", 10))
        popular = CategoryService.get_popular_categories(limit)
        serializer = CategorySerializer(popular, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def breadcrumbs(self, request, id=None):
        """
        Get breadcrumb navigation data for a category

        Returns the path from the root category to the specified category,
        useful for creating breadcrumb navigation in the UI.

        Returns:
            Response: List of categories in the breadcrumb path
                [
                    {"id": "uuid", "name": "Category 1"},
                    {"id": "uuid", "name": "Category 2"},
                    ...
                ]
        """
        breadcrumbs = CategoryService.get_category_breadcrumbs(id)
        return Response(breadcrumbs)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def flat_hierarchy(self, request):
        """
        Get a flattened representation of the category hierarchy

        Returns the category tree in a flat list with indentation information,
        useful for dropdown selects with proper visual hierarchy.

        Query parameters:
            parent: Filter by parent category ID (optional)
            include_inactive: Include inactive categories (default: false)

        Returns:
            Response: Flattened category hierarchy with indentation levels
                [
                    {"id": "uuid", "name": "Category 1", "level": 0},
                    {"id": "uuid", "name": "Subcategory", "level": 1},
                    ...
                ]
        """
        parent_id = request.query_params.get("parent")
        include_inactive = request.query_params.get("include_inactive", "false").lower() == "true"
        flattened = HierarchyService.flatten_category_tree(parent_id, include_inactive)
        return Response(flattened)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    @has_permission("category", "edit")
    def move(self, request, id=None):
        """
        Move a category to a new parent

        Changes the parent of a category, effectively moving it in the hierarchy.
        Validates that the move won't create circular references.

        Request body:
            {
                "parent": "parent_id" or null (for root level)
            }

        Returns:
            Response: Success message or error

        Status codes:
            200: Category moved successfully
            400: Failed to move category (circular reference or other issue)
        """
        new_parent_id = request.data.get("parent")
        success = HierarchyService.move_category(id, new_parent_id)

        if success:
            return Response({"status": "success"})
        else:
            return Response(
                {"status": "error", "message": _("Failed to move category")},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated])
    @has_permission("category", "edit")
    def reorder(self, request):
        """
        Reorder categories by updating position values

        Updates the position values of multiple categories at once,
        allowing for bulk reordering of categories.

        Request body:
            [
                {"id": "category_id", "position": integer},
                {"id": "category_id", "position": integer},
                ...
            ]

        Returns:
            Response: Success message or error

        Status codes:
            200: Categories reordered successfully
            400: Failed to reorder categories
        """
        ordering_data = request.data
        if not isinstance(ordering_data, list):
            return Response(
                {"status": "error", "message": _("Expected a list of ordering data")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        success = CategoryService.reorder_categories(ordering_data)

        if success:
            return Response({"status": "success"})
        else:
            return Response(
                {"status": "error", "message": _("Failed to reorder categories")},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def related(self, request, id=None):
        """
        Get categories related to the current category

        Returns categories that have a relationship with the specified category,
        optionally filtered by relationship type.

        Query parameters:
            type: Relationship type (optional)
            limit: Maximum number of categories to return (default: 5)

        Returns:
            Response: List of related categories
        """
        relation_type = request.query_params.get("type")
        limit = int(request.query_params.get("limit", 5))

        related = CategoryService.get_related_categories(id, relation_type, limit)
        serializer = CategorySerializer(related, many=True)

        return Response(serializer.data)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated, IsAdminUser])
    def statistics(self, request):
        """
        Get statistics about the category structure

        Returns aggregate statistics about the category structure,
        including counts of categories at different levels, average
        children per parent, etc.

        Admin-only endpoint.

        Returns:
            Response: Category statistics
                {
                    "total_categories": integer,
                    "active_categories": integer,
                    "top_level_categories": integer,
                    "max_depth": integer,
                    "avg_children_per_parent": float,
                    ...
                }
        """
        stats = HierarchyService.get_category_statistics()
        return Response(stats)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated, IsAdminUser])
    def check_integrity(self, request):
        """
        Check category hierarchy integrity

        Validates the category hierarchy for issues like circular references,
        orphaned categories, and other integrity problems.

        Admin-only endpoint.

        Returns:
            Response: List of integrity issues found
                [
                    {"type": "circular_reference", "categories": [...], "message": "..."},
                    {"type": "orphaned_category", "category_id": "uuid", "message": "..."},
                    ...
                ]
        """
        issues = HierarchyService.check_hierarchy_integrity()
        return Response(issues)

    def create(self, request, *args, **kwargs):
        """
        Create a new category using the CategoryService

        Validates and creates a new category with the provided data.
        Uses the service layer for business logic validation.

        Returns:
            Response: Created category data

        Status codes:
            201: Category created successfully
            400: Invalid request data
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            category = CategoryService.create_category(serializer.validated_data)
            response_serializer = CategorySerializer(category)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def update(self, request, *args, **kwargs):
        """
        Update a category using the CategoryService

        Validates and updates an existing category with the provided data.
        Uses the service layer for business logic validation.

        Returns:
            Response: Updated category data

        Status codes:
            200: Category updated successfully
            400: Invalid request data
            404: Category not found
        """
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        try:
            category = CategoryService.update_category(instance.id, serializer.validated_data)
            if not category:
                return Response(
                    {"status": "error", "message": _("Category not found")},
                    status=status.HTTP_404_NOT_FOUND,
                )

            response_serializer = CategorySerializer(category)
            return Response(response_serializer.data)
        except Exception as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def destroy(self, request, *args, **kwargs):
        """
        Delete a category using the CategoryService

        Deletes a category and handles any cleanup required,
        such as reassigning child categories.

        Returns:
            Response: No content on success, error details on failure

        Status codes:
            204: Category deleted successfully
            400: Failed to delete category
        """
        instance = self.get_object()

        try:
            success = CategoryService.delete_category(instance.id)
            if success:
                return Response(status=status.HTTP_204_NO_CONTENT)
            else:
                return Response(
                    {"status": "error", "message": _("Failed to delete category")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class CategoryRelationViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing category relations

    Handles the creation, retrieval, update, and deletion of relationships
    between categories. These relationships can be used to establish connections
    between categories that aren't directly in a parent-child relationship.

    Endpoints:
    - GET /api/category-relations/ - List relations with filtering options
    - POST /api/category-relations/ - Create a new relation
    - GET /api/category-relations/{id}/ - Get relation details
    - PUT/PATCH /api/category-relations/{id}/ - Update a relation
    - DELETE /api/category-relations/{id}/ - Delete a relation

    Permissions:
    - Requires authentication and specific permissions
    """

    queryset = CategoryRelation.objects.all()
    serializer_class = CategoryRelationSerializer
    permission_classes = [CategoryPermission]

    def get_queryset(self):
        """
        Filter relations based on query parameters

        Applies filters for:
        - from_category: Source category ID
        - to_category: Target category ID
        - relation_type: Type of relationship

        Returns:
            QuerySet: Filtered relations ordered by weight (descending)
        """
        queryset = CategoryRelation.objects.all()

        # Filter by from_category
        from_category = self.request.query_params.get("from_category")
        if from_category:
            queryset = queryset.filter(from_category_id=from_category)

        # Filter by to_category
        to_category = self.request.query_params.get("to_category")
        if to_category:
            queryset = queryset.filter(to_category_id=to_category)

        # Filter by relation_type
        relation_type = self.request.query_params.get("relation_type")
        if relation_type:
            queryset = queryset.filter(relation_type=relation_type)

        return queryset.order_by("-weight")

    def get_serializer_class(self):
        """
        Return appropriate serializer based on action

        - create/update: CategoryRelationCreateSerializer (validates IDs)
        - other actions: CategoryRelationSerializer (standard representation)

        Returns:
            Serializer class: The appropriate serializer for the current action
        """
        if self.action in ["create", "update", "partial_update"]:
            return CategoryRelationCreateSerializer
        return CategoryRelationSerializer

    def create(self, request, *args, **kwargs):
        """
        Create a new category relation

        Creates a relationship between two categories with the specified
        relation type and weight.

        Request body:
            {
                "from_category": "source_category_id",
                "to_category": "target_category_id",
                "relation_type": "related|alternative|complementary" (optional, default: "related"),
                "weight": float (optional, default: 1.0)
            }

        Returns:
            Response: Created relation data

        Status codes:
            201: Relation created successfully
            400: Invalid request data
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            relation = CategoryService.create_category_relation(
                serializer.validated_data["from_category"].id,
                serializer.validated_data["to_category"].id,
                serializer.validated_data.get("relation_type", "related"),
                serializer.validated_data.get("weight", 1.0),
            )

            if relation:
                response_serializer = CategoryRelationSerializer(relation)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {"status": "error", "message": _("Failed to create relation")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
