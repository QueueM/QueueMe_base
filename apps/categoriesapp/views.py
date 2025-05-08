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
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class CategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing categories.

    Provides CRUD operations and additional actions for managing
    the category hierarchy and relationships.
    """

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    pagination_class = CategoryPagination
    permission_classes = [CategoryPermission]
    lookup_field = "id"

    def get_queryset(self):
        """
        Get base queryset with optional filtering
        """
        queryset = Category.objects.all()

        # Apply filter for active status
        active_only = (
            self.request.query_params.get("active_only", "true").lower() == "true"
        )
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
        """
        if self.action == "list":
            return CategoryListSerializer
        elif (
            self.action == "create"
            or self.action == "update"
            or self.action == "partial_update"
        ):
            return CategoryCreateUpdateSerializer
        elif self.action == "hierarchy":
            return CategoryHierarchySerializer
        return CategorySerializer

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def parent_categories(self, request):
        """
        Get all parent categories (categories without a parent)
        """
        parent_categories = CategoryService.get_parent_categories()
        serializer = CategorySerializer(parent_categories, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def children(self, request, id=None):
        """
        Get all child categories for a parent category
        """
        children = CategoryService.get_child_categories(id)
        serializer = CategorySerializer(children, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def hierarchy(self, request):
        """
        Get complete category hierarchy as a nested structure
        """
        include_inactive = (
            request.query_params.get("include_inactive", "false").lower() == "true"
        )
        tree = HierarchyService.build_category_tree(include_inactive)
        return Response(tree)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def featured(self, request):
        """
        Get featured categories
        """
        limit = int(request.query_params.get("limit", 10))
        featured = CategoryService.get_featured_categories(limit)
        serializer = CategorySerializer(featured, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def popular(self, request):
        """
        Get popular categories based on service count and interactions
        """
        limit = int(request.query_params.get("limit", 10))
        popular = CategoryService.get_popular_categories(limit)
        serializer = CategorySerializer(popular, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def breadcrumbs(self, request, id=None):
        """
        Get breadcrumb navigation data for a category
        """
        breadcrumbs = CategoryService.get_category_breadcrumbs(id)
        return Response(breadcrumbs)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def flat_hierarchy(self, request):
        """
        Get a flattened representation of the category hierarchy
        Useful for dropdown selects with proper indentation
        """
        parent_id = request.query_params.get("parent")
        include_inactive = (
            request.query_params.get("include_inactive", "false").lower() == "true"
        )
        flattened = HierarchyService.flatten_category_tree(parent_id, include_inactive)
        return Response(flattened)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    @has_permission("category", "edit")
    def move(self, request, id=None):
        """
        Move a category to a new parent
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
        Expects a list of {id, position} objects
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
        """
        relation_type = request.query_params.get("type")
        limit = int(request.query_params.get("limit", 5))

        related = CategoryService.get_related_categories(id, relation_type, limit)
        serializer = CategorySerializer(related, many=True)

        return Response(serializer.data)

    @action(
        detail=False, methods=["get"], permission_classes=[IsAuthenticated, IsAdminUser]
    )
    def statistics(self, request):
        """
        Get statistics about the category structure
        Admin-only endpoint
        """
        stats = HierarchyService.get_category_statistics()
        return Response(stats)

    @action(
        detail=False, methods=["get"], permission_classes=[IsAuthenticated, IsAdminUser]
    )
    def check_integrity(self, request):
        """
        Check category hierarchy integrity (circular references, etc.)
        Admin-only endpoint
        """
        issues = HierarchyService.check_hierarchy_integrity()
        return Response(issues)

    def create(self, request, *args, **kwargs):
        """
        Create a new category using the CategoryService
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
        """
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        try:
            category = CategoryService.update_category(
                instance.id, serializer.validated_data
            )
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
    """

    queryset = CategoryRelation.objects.all()
    serializer_class = CategoryRelationSerializer
    permission_classes = [CategoryPermission]

    def get_queryset(self):
        """Filter relations based on query parameters"""
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
        """Return appropriate serializer based on action"""
        if self.action in ["create", "update", "partial_update"]:
            return CategoryRelationCreateSerializer
        return CategoryRelationSerializer

    def create(self, request, *args, **kwargs):
        """Create a new category relation"""
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
                return Response(
                    response_serializer.data, status=status.HTTP_201_CREATED
                )
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
