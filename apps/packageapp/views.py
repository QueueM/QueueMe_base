"""
Package app views for QueueMe platform
Handles endpoints related to service packages, pricing, and FAQs
"""

from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.documentation.api_doc_decorators import document_api_endpoint, document_api_viewset

from .filters import PackageFilter
from .models import Package, PackageFAQ
from .permissions import PackageFAQPermission, PackagePermission
from .serializers import (
    PackageCreateSerializer,
    PackageDetailSerializer,
    PackageFAQSerializer,
    PackageListSerializer,
)
from .services.package_availability import PackageAvailabilityService
from .services.package_service import PackageService


@document_api_viewset(
    summary="Package",
    description="API endpoints for managing service packages including CRUD operations, availability, and recommendations",
    tags=["Packages"],
)
class PackageViewSet(viewsets.ModelViewSet):
    """
    API endpoint for packages management.

    Provides CRUD operations for packages, with additional endpoints for:
    - Availability: Get available time slots for a package
    - Recommended: Get recommended packages based on user preferences
    - Popular: Get popular packages based on booking frequency
    """

    queryset = Package.objects.all()
    permission_classes = [IsAuthenticated, PackagePermission]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = PackageFilter
    search_fields = ["name", "description", "shop__name"]
    ordering_fields = [
        "name",
        "created_at",
        "discounted_price",
        "discount_percentage",
        "total_duration",
    ]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "list":
            return PackageListSerializer
        elif self.action == "create":
            return PackageCreateSerializer
        return PackageDetailSerializer

    def get_queryset(self):
        """
        Filter packages based on user role:
        - Customers see active packages in their city
        - Shop staff see packages for their shop
        - Queue Me admins see all packages
        """
        queryset = super().get_queryset()

        user = self.request.user

        # For Queue Me admins, return all packages
        if user.is_superuser or user.user_type == "admin":
            return queryset

        # For shop managers/employees, return packages for their shops
        if user.user_type in ["employee"]:
            from apps.rolesapp.services.permission_resolver import PermissionResolver

            shops = PermissionResolver.get_user_shops(user)
            return queryset.filter(shop__in=shops)

        # For customers, return only active packages in their city
        if user.user_type == "customer":
            from apps.customersapp.models import Customer

            try:
                customer = Customer.objects.get(user=user)
                city = customer.city

                # Filter by status and city
                return queryset.filter(Q(status="active") & Q(shop__location__city=city))
            except Customer.DoesNotExist:
                # If customer profile doesn't exist, just filter by status
                return queryset.filter(status="active")

        return queryset

    @document_api_endpoint(
        summary="List packages",
        description="Retrieve packages filtered based on user role",
        responses={200: "Success - Returns list of packages"},
        tags=["Packages"],
    )
    def list(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().list(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Create package",
        description="Create a new service package",
        responses={
            201: "Created - Package created successfully",
            400: "Bad Request - Invalid data",
            403: "Forbidden - User doesn't have permission",
        },
        tags=["Packages"],
    )
    def create(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().create(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Retrieve package",
        description="Get detailed information about a specific package",
        responses={
            200: "Success - Returns package details",
            404: "Not Found - Package not found",
        },
        path_params=[{"name": "pk", "description": "Package ID", "type": "string"}],
        tags=["Packages"],
    )
    def retrieve(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().retrieve(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Update package",
        description="Update an existing service package",
        responses={
            200: "Success - Package updated successfully",
            400: "Bad Request - Invalid data",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Package not found",
        },
        path_params=[{"name": "pk", "description": "Package ID", "type": "string"}],
        tags=["Packages"],
    )
    def update(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().update(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Delete package",
        description="Delete a service package",
        responses={
            204: "No Content - Package deleted successfully",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Package not found",
        },
        path_params=[{"name": "pk", "description": "Package ID", "type": "string"}],
        tags=["Packages"],
    )
    def destroy(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().destroy(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Get package availability",
        description="Get available time slots for a package on a specific date",
        responses={
            200: "Success - Returns available time slots",
            400: "Bad Request - Missing or invalid date parameter",
            404: "Not Found - Package not found",
        },
        path_params=[{"name": "pk", "description": "Package ID", "type": "string"}],
        query_params=[
            {
                "name": "date",
                "description": "Date to check availability (YYYY-MM-DD)",
                "required": True,
                "type": "string",
            }
        ],
        tags=["Packages", "Availability"],
    )
    @action(detail=True, methods=["get"])
    def availability(self, request, pk=None):
        """
        Get available time slots for a package on a specific date.

        Query Parameters:
            date: The date to check availability (YYYY-MM-DD)
        """
        package = self.get_object()
        date_str = request.query_params.get("date")

        if not date_str:
            return Response(
                {"detail": _("Date parameter is required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            available_slots = PackageAvailabilityService.get_package_availability(
                package.id, date_str
            )
            return Response(available_slots)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @document_api_endpoint(
        summary="Get recommended packages",
        description="Get personalized package recommendations for the current user",
        responses={200: "Success - Returns list of recommended packages"},
        tags=["Packages", "Recommendations"],
    )
    @action(detail=False, methods=["get"])
    def recommended(self, request):
        """
        Get personalized package recommendations for the current user.

        Uses customer preferences, booking history, and service interests
        to recommend relevant packages.
        """
        user = request.user

        # Get recommended packages from recommendation engine
        recommended_packages = PackageService.get_recommended_packages(user.id)

        # Serialize and return results
        serializer = PackageListSerializer(recommended_packages, many=True)
        return Response(serializer.data)

    @document_api_endpoint(
        summary="Get popular packages",
        description="Get most popular packages based on booking frequency and ratings",
        responses={200: "Success - Returns list of popular packages"},
        query_params=[
            {
                "name": "shop_id",
                "description": "Optional shop ID to filter by",
                "required": False,
                "type": "string",
            },
            {
                "name": "category_id",
                "description": "Optional category ID to filter by",
                "required": False,
                "type": "string",
            },
            {
                "name": "limit",
                "description": "Maximum number of packages to return (default: 10)",
                "required": False,
                "type": "integer",
            },
        ],
        tags=["Packages", "Popular"],
    )
    @action(detail=False, methods=["get"])
    def popular(self, request):
        """
        Get most popular packages based on booking frequency and ratings.

        Query Parameters:
            shop_id: Optional shop ID to filter by
            category_id: Optional category ID to filter by
            limit: Maximum number of packages to return (default: 10)
        """
        shop_id = request.query_params.get("shop_id")
        category_id = request.query_params.get("category_id")
        limit = int(request.query_params.get("limit", 10))

        # Get popular packages from service
        popular_packages = PackageService.get_popular_packages(
            shop_id=shop_id, category_id=category_id, limit=limit
        )

        # Serialize and return results
        serializer = PackageListSerializer(popular_packages, many=True)
        return Response(serializer.data)


@document_api_viewset(
    summary="Package FAQ",
    description="API endpoints for managing frequently asked questions for packages",
    tags=["Packages", "FAQs"],
)
class PackageFAQViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing package FAQs.
    """

    queryset = PackageFAQ.objects.all()
    serializer_class = PackageFAQSerializer
    permission_classes = [IsAuthenticated, PackageFAQPermission]

    @document_api_endpoint(
        summary="List package FAQs",
        description="Retrieve FAQs, optionally filtered by package",
        responses={200: "Success - Returns list of package FAQs"},
        query_params=[
            {
                "name": "package_id",
                "description": "Package ID to filter FAQs by",
                "required": False,
                "type": "string",
            }
        ],
        tags=["Packages", "FAQs"],
    )
    def get_queryset(self):
        """Filter FAQs by package"""
        queryset = super().get_queryset()

        package_id = self.request.query_params.get("package_id")
        if package_id:
            queryset = queryset.filter(package_id=package_id)

        return queryset

    @document_api_endpoint(
        summary="Create package FAQ",
        description="Create a new FAQ for a package",
        responses={
            201: "Created - FAQ created successfully",
            400: "Bad Request - Invalid data",
            403: "Forbidden - User doesn't have permission",
        },
        tags=["Packages", "FAQs"],
    )
    def create(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().create(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Retrieve package FAQ",
        description="Get a specific package FAQ by ID",
        responses={
            200: "Success - Returns FAQ details",
            404: "Not Found - FAQ not found",
        },
        path_params=[{"name": "pk", "description": "FAQ ID", "type": "string"}],
        tags=["Packages", "FAQs"],
    )
    def retrieve(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().retrieve(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Update package FAQ",
        description="Update an existing package FAQ",
        responses={
            200: "Success - FAQ updated successfully",
            400: "Bad Request - Invalid data",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - FAQ not found",
        },
        path_params=[{"name": "pk", "description": "FAQ ID", "type": "string"}],
        tags=["Packages", "FAQs"],
    )
    def update(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().update(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Delete package FAQ",
        description="Delete a package FAQ",
        responses={
            204: "No Content - FAQ deleted successfully",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - FAQ not found",
        },
        path_params=[{"name": "pk", "description": "FAQ ID", "type": "string"}],
        tags=["Packages", "FAQs"],
    )
    def destroy(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().destroy(request, *args, **kwargs)
