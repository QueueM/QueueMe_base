"""
Specialists app views for QueueMe platform
Handles endpoints related to service specialists, their services, working hours, portfolio,
availability, and verification. Specialists are employees who provide services to customers.
"""

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import generics, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.specialistsapp.constants import SPECIALIST_TOP_RATED_CACHE_KEY
from apps.specialistsapp.filters import SpecialistFilter
from apps.specialistsapp.models import (
    PortfolioItem,
    Specialist,
    SpecialistService,
    SpecialistWorkingHours,
)
from apps.specialistsapp.permissions import (
    CanManagePortfolio,
    CanManageSpecialist,
    CanVerifySpecialist,
    CanViewSpecialist,
)
from apps.specialistsapp.serializers import (
    PortfolioItemCreateSerializer,
    PortfolioItemSerializer,
    PortfolioItemUpdateSerializer,
    SpecialistCreateSerializer,
    SpecialistDetailSerializer,
    SpecialistListSerializer,
    SpecialistServiceCreateSerializer,
    SpecialistServiceSerializer,
    SpecialistServiceUpdateSerializer,
    SpecialistUpdateSerializer,
    SpecialistWorkingHoursCreateUpdateSerializer,
    SpecialistWorkingHoursSerializer,
)
from apps.specialistsapp.services.availability_service import AvailabilityService
from apps.specialistsapp.services.specialist_ranker import SpecialistRanker
from apps.specialistsapp.services.specialist_recommender import SpecialistRecommender


class SpecialistViewSet(viewsets.ModelViewSet):
    """
    ViewSet for specialists.

    Provides CRUD operations for specialists, who are shop employees that provide services
    to customers. Specialists have skills, working hours, and portfolio items.

    Endpoints:
    - GET /api/specialists/ - List all specialists
    - POST /api/specialists/ - Create a new specialist
    - GET /api/specialists/{id}/ - Get a specific specialist
    - PUT/PATCH /api/specialists/{id}/ - Update a specialist
    - DELETE /api/specialists/{id}/ - Delete a specialist

    Permissions:
    - List/Retrieve: Anyone can view specialists
    - Create/Update/Delete: Requires appropriate permissions to manage specialists

    Filtering:
    - Multiple filters available via SpecialistFilter

    Search fields:
    - employee__first_name: Specialist's first name
    - employee__last_name: Specialist's last name
    - bio: Specialist's biography

    Ordering:
    - avg_rating: Average rating
    - total_bookings: Total number of bookings
    - experience_years: Years of experience
    - created_at: Creation date
    """

    filterset_class = SpecialistFilter
    search_fields = ["employee__first_name", "employee__last_name", "bio"]
    ordering_fields = ["avg_rating", "total_bookings", "experience_years", "created_at"]
    ordering = ["-avg_rating", "-total_bookings"]

    def get_queryset(self):
        """
        Get the queryset for specialists

        Returns specialists with related objects preloaded for performance,
        filtering only active specialists from active shops.

        Returns:
            QuerySet: Filtered specialists with related objects
        """
        queryset = (
            Specialist.objects.select_related(
                "employee", "employee__shop", "employee__user"
            )
            .prefetch_related(
                "specialist_services",
                "specialist_services__service",
                "specialist_services__service__category",
                "working_hours",
                "portfolio",
                "expertise",
            )
            .filter(employee__is_active=True, employee__shop__is_active=True)
        )

        return queryset

    def get_serializer_class(self):
        """
        Get the appropriate serializer for the action

        - list: SpecialistListSerializer (simplified for lists)
        - retrieve: SpecialistDetailSerializer (full details)
        - create: SpecialistCreateSerializer (for creation)
        - update: SpecialistUpdateSerializer (for updates)

        Returns:
            Serializer class: The appropriate serializer for the current action
        """
        if self.action == "list":
            return SpecialistListSerializer
        elif self.action == "retrieve":
            return SpecialistDetailSerializer
        elif self.action == "create":
            return SpecialistCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return SpecialistUpdateSerializer

        return SpecialistDetailSerializer

    def get_permissions(self):
        """
        Get the permissions for the action

        - list/retrieve: Can view specialist permission
        - create/update/delete: Authenticated + Can manage specialist permission
        - other actions: Authenticated

        Returns:
            list: Permission classes for the current action
        """
        if self.action in ["list", "retrieve"]:
            permission_classes = [CanViewSpecialist]
        elif self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [IsAuthenticated, CanManageSpecialist]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    def perform_destroy(self, instance):
        """
        Check if specialist can be deleted

        Prevents deletion of specialists who have bookings to maintain data integrity.

        Args:
            instance: The specialist instance to delete

        Raises:
            ValidationError: If specialist has bookings
        """
        if instance.total_bookings > 0:
            from rest_framework.exceptions import ValidationError

            raise ValidationError(_("Cannot delete specialist with existing bookings."))

        super().perform_destroy(instance)


class ShopSpecialistsView(generics.ListAPIView):
    """
    View for listing specialists by shop

    Returns all specialists for a specific shop.

    Endpoint:
    - GET /api/shops/{shop_id}/specialists/ - List specialists for a shop

    URL parameters:
        shop_id: UUID of the shop

    Filtering:
    - Multiple filters available via SpecialistFilter

    Ordering:
    - Default: By average rating and total bookings (descending)
    """

    serializer_class = SpecialistListSerializer
    filterset_class = SpecialistFilter

    def get_queryset(self):
        """
        Get specialists for a specific shop

        Returns only active specialists from the specified shop,
        with related objects preloaded for performance.

        Returns:
            QuerySet: Filtered specialists for the shop
        """
        shop_id = self.kwargs.get("shop_id")
        return (
            Specialist.objects.filter(
                employee__shop_id=shop_id, employee__is_active=True
            )
            .select_related("employee", "employee__shop")
            .prefetch_related(
                "specialist_services",
                "specialist_services__service",
                "specialist_services__service__category",
                "expertise",
            )
            .order_by("-avg_rating", "-total_bookings")
        )


class ServiceSpecialistsView(generics.ListAPIView):
    """
    View for listing specialists by service

    Returns all specialists that provide a specific service.

    Endpoint:
    - GET /api/services/{service_id}/specialists/ - List specialists for a service

    URL parameters:
        service_id: UUID of the service

    Filtering:
    - Multiple filters available via SpecialistFilter

    Ordering:
    - Default: By average rating and total bookings (descending)
    """

    serializer_class = SpecialistListSerializer
    filterset_class = SpecialistFilter

    def get_queryset(self):
        """
        Get specialists for a specific service

        Returns only active specialists from active shops that provide
        the specified service, with related objects preloaded for performance.

        Returns:
            QuerySet: Filtered specialists for the service
        """
        service_id = self.kwargs.get("service_id")
        return (
            Specialist.objects.filter(
                specialist_services__service_id=service_id,
                employee__is_active=True,
                employee__shop__is_active=True,
            )
            .select_related("employee", "employee__shop")
            .prefetch_related(
                "specialist_services",
                "specialist_services__service",
                "specialist_services__service__category",
                "expertise",
            )
            .order_by("-avg_rating", "-total_bookings")
        )


class TopRatedSpecialistsView(generics.ListAPIView):
    """
    View for listing top rated specialists

    Returns the top-rated specialists based on ratings, booking counts,
    and other factors. Results are cached for performance.

    Endpoint:
    - GET /api/specialists/top-rated/ - List top rated specialists

    Query parameters:
        shop_id: Filter by shop (optional)
        limit: Maximum number of specialists to return (default: 10)

    Permissions:
    - Can view specialist permission
    """

    serializer_class = SpecialistListSerializer
    permission_classes = [CanViewSpecialist]

    def get_queryset(self):
        """
        Get top rated specialists

        Uses caching to improve performance. Returns only verified specialists
        from active shops, optionally filtered by shop ID.

        Returns:
            QuerySet: Top rated specialists
        """
        shop_id = self.request.query_params.get("shop_id")
        limit = int(self.request.query_params.get("limit", 10))

        # Try to get from cache
        cache_key = SPECIALIST_TOP_RATED_CACHE_KEY.format(
            shop_id=shop_id or "all", limit=limit
        )
        cached_results = cache.get(cache_key)

        if cached_results:
            return cached_results

        # Build query based on shop_id
        queryset = Specialist.objects.filter(
            employee__is_active=True, employee__shop__is_active=True, is_verified=True
        )

        if shop_id:
            queryset = queryset.filter(employee__shop_id=shop_id)

        # Use the SpecialistRanker service to rank specialists
        ranker = SpecialistRanker()
        top_specialists = ranker.get_top_rated_specialists(queryset, limit)

        # Cache results for 1 hour
        cache.set(cache_key, top_specialists, 60 * 60)

        return top_specialists


class SpecialistRecommendationsView(generics.ListAPIView):
    """
    View for getting specialist recommendations for a customer

    Returns personalized specialist recommendations for the current user,
    based on their preferences, booking history, and other factors.

    Endpoint:
    - GET /api/specialists/recommendations/ - Get specialist recommendations

    Query parameters:
        category_id: Filter by service category (optional)
        limit: Maximum number of specialists to return (default: 5)

    Permissions:
    - Authentication required
    """

    serializer_class = SpecialistListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Get specialist recommendations

        Uses the SpecialistRecommender service to generate personalized
        recommendations for the current user.

        Returns:
            QuerySet: Recommended specialists
        """
        category_id = self.request.query_params.get("category_id")
        limit = int(self.request.query_params.get("limit", 5))

        # Use the SpecialistRecommender service to get recommendations
        recommender = SpecialistRecommender()
        return recommender.get_recommendations(
            customer=self.request.user, category_id=category_id, limit=limit
        )


class SpecialistServicesView(generics.ListCreateAPIView):
    """
    View for listing and creating specialist services

    Manages the services that a specialist provides, including pricing,
    duration, and other service details.

    Endpoints:
    - GET /api/specialists/{specialist_id}/services/ - List services for a specialist
    - POST /api/specialists/{specialist_id}/services/ - Add a service to a specialist

    URL parameters:
        specialist_id: UUID of the specialist

    Permissions:
    - GET: Can view specialist permission
    - POST: Authenticated + Can manage specialist permission
    """

    serializer_class = SpecialistServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Get services for a specific specialist

        Returns services provided by the specialist, ordered by primary status
        and booking count, with related objects preloaded for performance.

        Returns:
            QuerySet: Services provided by the specialist
        """
        specialist_id = self.kwargs.get("specialist_id")
        return (
            SpecialistService.objects.filter(specialist_id=specialist_id)
            .select_related("service", "service__category")
            .order_by("-is_primary", "-booking_count")
        )

    def get_permissions(self):
        """
        Get the permissions based on method

        - GET: Can view specialist permission
        - Other methods: Authenticated + Can manage specialist permission

        Returns:
            list: Permission classes for the current method
        """
        if self.request.method == "GET":
            return [CanViewSpecialist()]
        return [IsAuthenticated(), CanManageSpecialist()]

    def get_serializer_class(self):
        """
        Get the serializer class based on method

        - POST: SpecialistServiceCreateSerializer (for creation)
        - Other methods: SpecialistServiceSerializer (standard representation)

        Returns:
            Serializer class: The appropriate serializer for the current method
        """
        if self.request.method == "POST":
            return SpecialistServiceCreateSerializer
        return SpecialistServiceSerializer

    def get_serializer_context(self):
        """
        Add specialist to serializer context

        Includes the specialist object in the serializer context for validation
        and association purposes.

        Returns:
            dict: Serializer context with specialist included
        """
        context = super().get_serializer_context()
        specialist_id = self.kwargs.get("specialist_id")
        if specialist_id:
            context["specialist"] = get_object_or_404(Specialist, id=specialist_id)
        return context

    def perform_create(self, serializer):
        """
        Create the specialist service

        Verifies the user has permission to manage the specialist before
        creating the service association.

        Args:
            serializer: The specialist service serializer instance

        Raises:
            PermissionDenied: If user doesn't have permission to manage this specialist
        """
        specialist_id = self.kwargs.get("specialist_id")
        specialist = get_object_or_404(Specialist, id=specialist_id)

        # Check if user has permission to manage this specialist
        if not CanManageSpecialist().has_object_permission(
            self.request, self, specialist
        ):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                _("You don't have permission to manage this specialist.")
            )

        serializer.save()


class SpecialistServiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View for retrieving, updating and deleting specialist services

    Manages individual service associations for a specialist.

    Endpoints:
    - GET /api/specialists/{specialist_id}/services/{id}/ - Get a specialist service
    - PUT/PATCH /api/specialists/{specialist_id}/services/{id}/ - Update a specialist service
    - DELETE /api/specialists/{specialist_id}/services/{id}/ - Remove a service from a specialist

    URL parameters:
        specialist_id: UUID of the specialist
        id: UUID of the specialist service

    Permissions:
    - GET: Can view specialist permission
    - Other methods: Authenticated + Can manage specialist permission
    """

    serializer_class = SpecialistServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Get specialist service queryset

        Returns services for the specified specialist with related
        objects preloaded for performance.

        Returns:
            QuerySet: Services for the specialist
        """
        specialist_id = self.kwargs.get("specialist_id")
        return SpecialistService.objects.filter(
            specialist_id=specialist_id
        ).select_related("service", "service__category")

    def get_permissions(self):
        """
        Get the permissions based on method

        - GET: Can view specialist permission
        - Other methods: Authenticated + Can manage specialist permission

        Returns:
            list: Permission classes for the current method
        """
        if self.request.method == "GET":
            return [CanViewSpecialist()]
        return [IsAuthenticated(), CanManageSpecialist()]

    def get_serializer_class(self):
        """
        Get the serializer class based on method

        - PUT/PATCH: SpecialistServiceUpdateSerializer (for updates)
        - Other methods: SpecialistServiceSerializer (standard representation)

        Returns:
            Serializer class: The appropriate serializer for the current method
        """
        if self.request.method in ["PUT", "PATCH"]:
            return SpecialistServiceUpdateSerializer
        return SpecialistServiceSerializer

    def perform_update(self, serializer):
        """
        Update the specialist service

        Verifies the user has permission to manage the specialist before
        updating the service association.

        Args:
            serializer: The specialist service serializer instance

        Raises:
            PermissionDenied: If user doesn't have permission to manage this specialist
        """
        specialist = serializer.instance.specialist

        # Check if user has permission to manage this specialist
        if not CanManageSpecialist().has_object_permission(
            self.request, self, specialist
        ):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                _("You don't have permission to manage this specialist.")
            )

        serializer.save()


class SpecialistWorkingHoursView(generics.ListCreateAPIView):
    """
    View for listing and creating specialist working hours

    Manages the working hours for a specialist on different days of the week.

    Endpoints:
    - GET /api/specialists/{specialist_id}/working-hours/ - List working hours for a specialist
    - POST /api/specialists/{specialist_id}/working-hours/ - Add working hours for a specialist

    URL parameters:
        specialist_id: UUID of the specialist

    Permissions:
    - GET: Can view specialist permission
    - POST: Authenticated + Can manage specialist permission
    """

    serializer_class = SpecialistWorkingHoursSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Get working hours for a specific specialist

        Returns working hours for the specialist, ordered by weekday and start time.

        Returns:
            QuerySet: Working hours for the specialist
        """
        specialist_id = self.kwargs.get("specialist_id")
        return SpecialistWorkingHours.objects.filter(
            specialist_id=specialist_id
        ).order_by("weekday", "from_hour")

    def get_permissions(self):
        """
        Get the permissions based on method

        - GET: Can view specialist permission
        - Other methods: Authenticated + Can manage specialist permission

        Returns:
            list: Permission classes for the current method
        """
        if self.request.method == "GET":
            return [CanViewSpecialist()]
        return [IsAuthenticated(), CanManageSpecialist()]

    def get_serializer_class(self):
        """
        Get the serializer class based on method

        - POST: SpecialistWorkingHoursCreateUpdateSerializer (for creation)
        - Other methods: SpecialistWorkingHoursSerializer (standard representation)

        Returns:
            Serializer class: The appropriate serializer for the current method
        """
        if self.request.method == "POST":
            return SpecialistWorkingHoursCreateUpdateSerializer
        return SpecialistWorkingHoursSerializer

    def get_serializer_context(self):
        """
        Add specialist to serializer context

        Includes the specialist object in the serializer context for validation
        and association purposes.

        Returns:
            dict: Serializer context with specialist included
        """
        context = super().get_serializer_context()
        specialist_id = self.kwargs.get("specialist_id")
        if specialist_id:
            context["specialist"] = get_object_or_404(Specialist, id=specialist_id)
        return context

    def perform_create(self, serializer):
        """
        Create the specialist working hours

        Verifies the user has permission to manage the specialist. If working hours
        already exist for the weekday, updates them instead of creating new ones.

        Args:
            serializer: The working hours serializer instance

        Raises:
            PermissionDenied: If user doesn't have permission to manage this specialist
        """
        specialist_id = self.kwargs.get("specialist_id")
        specialist = get_object_or_404(Specialist, id=specialist_id)

        # Check if user has permission to manage this specialist
        if not CanManageSpecialist().has_object_permission(
            self.request, self, specialist
        ):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                _("You don't have permission to manage this specialist.")
            )

        # Check if working hours already exist for this weekday
        weekday = serializer.validated_data.get("weekday")
        existing = SpecialistWorkingHours.objects.filter(
            specialist=specialist, weekday=weekday
        ).first()

        if existing:
            # Update existing instead of creating new
            existing.from_hour = serializer.validated_data.get("from_hour")
            existing.to_hour = serializer.validated_data.get("to_hour")
            existing.is_off = serializer.validated_data.get("is_off", False)
            existing.save()
            return existing

        serializer.save(specialist=specialist)


class SpecialistWorkingHoursDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View for retrieving, updating and deleting specialist working hours

    Manages individual working hour records for a specialist.

    Endpoints:
    - GET /api/specialists/{specialist_id}/working-hours/{id}/ - Get specific working hours
    - PUT/PATCH /api/specialists/{specialist_id}/working-hours/{id}/ - Update working hours
    - DELETE /api/specialists/{specialist_id}/working-hours/{id}/ - Delete working hours

    URL parameters:
        specialist_id: UUID of the specialist
        id: UUID of the working hours record

    Permissions:
    - GET: Can view specialist permission
    - Other methods: Authenticated + Can manage specialist permission
    """

    serializer_class = SpecialistWorkingHoursSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Get specialist working hours queryset

        Returns working hours for the specified specialist.

        Returns:
            QuerySet: Working hours for the specialist
        """
        specialist_id = self.kwargs.get("specialist_id")
        return SpecialistWorkingHours.objects.filter(specialist_id=specialist_id)

    def get_permissions(self):
        """
        Get the permissions based on method

        - GET: Can view specialist permission
        - Other methods: Authenticated + Can manage specialist permission

        Returns:
            list: Permission classes for the current method
        """
        if self.request.method == "GET":
            return [CanViewSpecialist()]
        return [IsAuthenticated(), CanManageSpecialist()]

    def get_serializer_class(self):
        """
        Get the serializer class based on method

        - PUT/PATCH: SpecialistWorkingHoursCreateUpdateSerializer (for updates)
        - Other methods: SpecialistWorkingHoursSerializer (standard representation)

        Returns:
            Serializer class: The appropriate serializer for the current method
        """
        if self.request.method in ["PUT", "PATCH"]:
            return SpecialistWorkingHoursCreateUpdateSerializer
        return SpecialistWorkingHoursSerializer

    def get_serializer_context(self):
        """
        Add specialist to serializer context

        Includes the specialist object in the serializer context for validation
        and association purposes.

        Returns:
            dict: Serializer context with specialist included
        """
        context = super().get_serializer_context()
        specialist_id = self.kwargs.get("specialist_id")
        if specialist_id:
            context["specialist"] = get_object_or_404(Specialist, id=specialist_id)
        return context

    def perform_update(self, serializer):
        """
        Update the specialist working hours

        Verifies the user has permission to manage the specialist before
        updating the working hours.

        Args:
            serializer: The working hours serializer instance

        Raises:
            PermissionDenied: If user doesn't have permission to manage this specialist
        """
        specialist = serializer.instance.specialist

        # Check if user has permission to manage this specialist
        if not CanManageSpecialist().has_object_permission(
            self.request, self, specialist
        ):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                _("You don't have permission to manage this specialist.")
            )

        serializer.save()


class SpecialistPortfolioView(generics.ListCreateAPIView):
    """
    View for listing and creating specialist portfolio items

    Manages the portfolio of work samples for a specialist, showcasing
    their skills and previous work.

    Endpoints:
    - GET /api/specialists/{specialist_id}/portfolio/ - List portfolio items for a specialist
    - POST /api/specialists/{specialist_id}/portfolio/ - Add a portfolio item

    URL parameters:
        specialist_id: UUID of the specialist

    Permissions:
    - GET: Can view specialist permission
    - POST: Authenticated + Can manage portfolio permission
    """

    serializer_class = PortfolioItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Get portfolio items for a specific specialist

        Returns portfolio items for the specialist, ordered by featured status
        and creation date, with related objects preloaded for performance.

        Returns:
            QuerySet: Portfolio items for the specialist
        """
        specialist_id = self.kwargs.get("specialist_id")
        return (
            PortfolioItem.objects.filter(specialist_id=specialist_id)
            .select_related("service", "category")
            .order_by("-is_featured", "-created_at")
        )

    def get_permissions(self):
        """
        Get the permissions based on method

        - GET: Can view specialist permission
        - Other methods: Authenticated + Can manage portfolio permission

        Returns:
            list: Permission classes for the current method
        """
        if self.request.method == "GET":
            return [CanViewSpecialist()]
        return [IsAuthenticated(), CanManagePortfolio()]

    def get_serializer_class(self):
        """
        Get the serializer class based on method

        - POST: PortfolioItemCreateSerializer (for creation)
        - Other methods: PortfolioItemSerializer (standard representation)

        Returns:
            Serializer class: The appropriate serializer for the current method
        """
        if self.request.method == "POST":
            return PortfolioItemCreateSerializer
        return PortfolioItemSerializer

    def get_serializer_context(self):
        """
        Add specialist to serializer context

        Includes the specialist object in the serializer context for validation
        and association purposes.

        Returns:
            dict: Serializer context with specialist included
        """
        context = super().get_serializer_context()
        specialist_id = self.kwargs.get("specialist_id")
        if specialist_id:
            context["specialist"] = get_object_or_404(Specialist, id=specialist_id)
        return context

    def perform_create(self, serializer):
        """
        Create the portfolio item

        Verifies the user has permission to manage the specialist's portfolio
        before creating the item.

        Args:
            serializer: The portfolio item serializer instance

        Raises:
            PermissionDenied: If user doesn't have permission to manage this portfolio
        """
        specialist_id = self.kwargs.get("specialist_id")
        specialist = get_object_or_404(Specialist, id=specialist_id)

        # Check if user has permission to manage this specialist's portfolio
        permission = CanManagePortfolio()
        if not permission.has_object_permission(self.request, self, specialist):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                _("You don't have permission to manage this specialist's portfolio.")
            )

        serializer.save()


class SpecialistPortfolioItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View for retrieving, updating and deleting specialist portfolio items

    Manages individual portfolio items for a specialist.

    Endpoints:
    - GET /api/specialists/{specialist_id}/portfolio/{id}/ - Get a portfolio item
    - PUT/PATCH /api/specialists/{specialist_id}/portfolio/{id}/ - Update a portfolio item
    - DELETE /api/specialists/{specialist_id}/portfolio/{id}/ - Delete a portfolio item

    URL parameters:
        specialist_id: UUID of the specialist
        id: UUID of the portfolio item

    Permissions:
    - GET: Can view specialist permission
    - Other methods: Authenticated + Can manage portfolio permission
    """

    serializer_class = PortfolioItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Get specialist portfolio item queryset

        Returns portfolio items for the specified specialist with related
        objects preloaded for performance.

        Returns:
            QuerySet: Portfolio items for the specialist
        """
        specialist_id = self.kwargs.get("specialist_id")
        return PortfolioItem.objects.filter(specialist_id=specialist_id).select_related(
            "service", "category"
        )

    def get_permissions(self):
        """
        Get the permissions based on method

        - GET: Can view specialist permission
        - Other methods: Authenticated + Can manage portfolio permission

        Returns:
            list: Permission classes for the current method
        """
        if self.request.method == "GET":
            return [CanViewSpecialist()]
        return [IsAuthenticated(), CanManagePortfolio()]

    def get_serializer_class(self):
        """
        Get the serializer class based on method

        - PUT/PATCH: PortfolioItemUpdateSerializer (for updates)
        - Other methods: PortfolioItemSerializer (standard representation)

        Returns:
            Serializer class: The appropriate serializer for the current method
        """
        if self.request.method in ["PUT", "PATCH"]:
            return PortfolioItemUpdateSerializer
        return PortfolioItemSerializer


class SpecialistAvailabilityView(APIView):
    """
    View for checking specialist availability on a specific date

    Returns the available time slots for a specialist on a given date,
    taking into account working hours, existing bookings, and leaves.

    Endpoint:
    - GET /api/specialists/{specialist_id}/availability/{date}/ - Get availability

    URL parameters:
        specialist_id: UUID of the specialist
        date: Date in YYYY-MM-DD or YYYYMMDD format

    Permissions:
    - Can view specialist permission
    """

    permission_classes = [CanViewSpecialist]

    def get(self, request, specialist_id, date):
        """
        Get specialist availability for a date

        Parses the date parameter and uses the AvailabilityService to
        calculate available time slots for the specialist.

        Args:
            request: The HTTP request
            specialist_id: UUID of the specialist
            date: Date string

        Returns:
            Response: List of available time slots
                [
                    {
                        "start_time": "HH:MM:SS",
                        "end_time": "HH:MM:SS",
                        "duration_minutes": integer
                    },
                    ...
                ]

        Status codes:
            200: Availability retrieved successfully
            400: Invalid date format
            404: Specialist not found
        """
        from datetime import datetime

        try:
            # Parse date string to date object
            if "-" in date:
                # Format: YYYY-MM-DD
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            else:
                # Format: YYYYMMDD
                date_obj = datetime.strptime(date, "%Y%m%d").date()

            specialist = get_object_or_404(
                Specialist.objects.select_related("employee__shop"),
                id=specialist_id,
                employee__is_active=True,
                employee__shop__is_active=True,
            )

            # Use availability service to get available slots
            availability_service = AvailabilityService()
            available_slots = availability_service.get_specialist_availability(
                specialist_id=specialist_id, date=date_obj
            )

            return Response(available_slots)

        except ValueError:
            return Response(
                {"error": _("Invalid date format. Use YYYY-MM-DD.")},
                status=status.HTTP_400_BAD_REQUEST,
            )


class SpecialistVerificationView(APIView):
    """
    View for verifying a specialist

    Allows authorized users to mark a specialist as verified,
    indicating they have been reviewed and approved.

    Endpoint:
    - POST /api/specialists/{pk}/verify/ - Verify a specialist

    URL parameters:
        pk: UUID of the specialist

    Permissions:
    - Authenticated + Can verify specialist permission
    """

    permission_classes = [IsAuthenticated, CanVerifySpecialist]

    def post(self, request, pk):
        """
        Verify a specialist

        Updates the specialist's verification status and sends a
        notification to the specialist.

        Args:
            request: The HTTP request
            pk: UUID of the specialist

        Returns:
            Response: Success message
                {
                    "message": "Specialist has been verified."
                }

        Status codes:
            200: Specialist verified successfully
            404: Specialist not found
        """
        specialist = get_object_or_404(Specialist, id=pk)

        # Update verification status
        specialist.is_verified = True
        specialist.verified_at = timezone.now()
        specialist.save()

        # Send notification to specialist's user
        from apps.notificationsapp.services.notification_service import (
            NotificationService,
        )

        NotificationService.send_notification(
            user_id=specialist.employee.user.id,
            notification_type="specialist_verified",
            data={
                "specialist_id": str(specialist.id),
                "specialist_name": f"{specialist.employee.first_name} {specialist.employee.last_name}",
                "shop_name": specialist.employee.shop.name,
            },
        )

        return Response(
            {"message": _("Specialist has been verified.")}, status=status.HTTP_200_OK
        )
