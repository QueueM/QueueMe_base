from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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
                return queryset.filter(
                    Q(status="active") & Q(shop__location__city=city)
                )
            except Customer.DoesNotExist:
                # If customer profile doesn't exist, just filter by status
                return queryset.filter(status="active")

        return queryset

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


class PackageFAQViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing package FAQs.
    """

    queryset = PackageFAQ.objects.all()
    serializer_class = PackageFAQSerializer
    permission_classes = [IsAuthenticated, PackageFAQPermission]

    def get_queryset(self):
        """Filter FAQs by package"""
        queryset = super().get_queryset()

        package_id = self.request.query_params.get("package_id")
        if package_id:
            queryset = queryset.filter(package_id=package_id)

        return queryset
