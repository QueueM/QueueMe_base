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

    list:
    Return a list of all specialists.

    retrieve:
    Return a specific specialist.

    create:
    Create a new specialist.

    update:
    Update an existing specialist.

    partial_update:
    Partially update an existing specialist.

    destroy:
    Delete a specialist.
    """

    filterset_class = SpecialistFilter
    search_fields = ["employee__first_name", "employee__last_name", "bio"]
    ordering_fields = ["avg_rating", "total_bookings", "experience_years", "created_at"]
    ordering = ["-avg_rating", "-total_bookings"]

    def get_queryset(self):
        """Get the queryset for specialists"""
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
        """Get the appropriate serializer for the action"""
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
        """Get the permissions for the action"""
        if self.action in ["list", "retrieve"]:
            permission_classes = [CanViewSpecialist]
        elif self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [IsAuthenticated, CanManageSpecialist]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    def perform_destroy(self, instance):
        """Check if specialist can be deleted"""
        if instance.total_bookings > 0:
            from rest_framework.exceptions import ValidationError

            raise ValidationError(_("Cannot delete specialist with existing bookings."))

        super().perform_destroy(instance)


class ShopSpecialistsView(generics.ListAPIView):
    """View for listing specialists by shop"""

    serializer_class = SpecialistListSerializer
    filterset_class = SpecialistFilter

    def get_queryset(self):
        """Get specialists for a specific shop"""
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
    """View for listing specialists by service"""

    serializer_class = SpecialistListSerializer
    filterset_class = SpecialistFilter

    def get_queryset(self):
        """Get specialists for a specific service"""
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
    """View for listing top rated specialists"""

    serializer_class = SpecialistListSerializer
    permission_classes = [CanViewSpecialist]

    def get_queryset(self):
        """Get top rated specialists"""
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
    """View for getting specialist recommendations for a customer"""

    serializer_class = SpecialistListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get specialist recommendations"""
        category_id = self.request.query_params.get("category_id")
        limit = int(self.request.query_params.get("limit", 5))

        # Use the SpecialistRecommender service to get recommendations
        recommender = SpecialistRecommender()
        return recommender.get_recommendations(
            customer=self.request.user, category_id=category_id, limit=limit
        )


class SpecialistServicesView(generics.ListCreateAPIView):
    """View for listing and creating specialist services"""

    serializer_class = SpecialistServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get services for a specific specialist"""
        specialist_id = self.kwargs.get("specialist_id")
        return (
            SpecialistService.objects.filter(specialist_id=specialist_id)
            .select_related("service", "service__category")
            .order_by("-is_primary", "-booking_count")
        )

    def get_permissions(self):
        """Get the permissions based on method"""
        if self.request.method == "GET":
            return [CanViewSpecialist()]
        return [IsAuthenticated(), CanManageSpecialist()]

    def get_serializer_class(self):
        """Get the serializer class based on method"""
        if self.request.method == "POST":
            return SpecialistServiceCreateSerializer
        return SpecialistServiceSerializer

    def get_serializer_context(self):
        """Add specialist to serializer context"""
        context = super().get_serializer_context()
        specialist_id = self.kwargs.get("specialist_id")
        if specialist_id:
            context["specialist"] = get_object_or_404(Specialist, id=specialist_id)
        return context

    def perform_create(self, serializer):
        """Create the specialist service"""
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
    """View for retrieving, updating and deleting specialist services"""

    serializer_class = SpecialistServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get specialist service queryset"""
        specialist_id = self.kwargs.get("specialist_id")
        return SpecialistService.objects.filter(
            specialist_id=specialist_id
        ).select_related("service", "service__category")

    def get_permissions(self):
        """Get the permissions based on method"""
        if self.request.method == "GET":
            return [CanViewSpecialist()]
        return [IsAuthenticated(), CanManageSpecialist()]

    def get_serializer_class(self):
        """Get the serializer class based on method"""
        if self.request.method in ["PUT", "PATCH"]:
            return SpecialistServiceUpdateSerializer
        return SpecialistServiceSerializer

    def perform_update(self, serializer):
        """Update the specialist service"""
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
    """View for listing and creating specialist working hours"""

    serializer_class = SpecialistWorkingHoursSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get working hours for a specific specialist"""
        specialist_id = self.kwargs.get("specialist_id")
        return SpecialistWorkingHours.objects.filter(
            specialist_id=specialist_id
        ).order_by("weekday", "from_hour")

    def get_permissions(self):
        """Get the permissions based on method"""
        if self.request.method == "GET":
            return [CanViewSpecialist()]
        return [IsAuthenticated(), CanManageSpecialist()]

    def get_serializer_class(self):
        """Get the serializer class based on method"""
        if self.request.method == "POST":
            return SpecialistWorkingHoursCreateUpdateSerializer
        return SpecialistWorkingHoursSerializer

    def get_serializer_context(self):
        """Add specialist to serializer context"""
        context = super().get_serializer_context()
        specialist_id = self.kwargs.get("specialist_id")
        if specialist_id:
            context["specialist"] = get_object_or_404(Specialist, id=specialist_id)
        return context

    def perform_create(self, serializer):
        """Create the specialist working hours"""
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
    """View for retrieving, updating and deleting specialist working hours"""

    serializer_class = SpecialistWorkingHoursSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get specialist working hours queryset"""
        specialist_id = self.kwargs.get("specialist_id")
        return SpecialistWorkingHours.objects.filter(specialist_id=specialist_id)

    def get_permissions(self):
        """Get the permissions based on method"""
        if self.request.method == "GET":
            return [CanViewSpecialist()]
        return [IsAuthenticated(), CanManageSpecialist()]

    def get_serializer_class(self):
        """Get the serializer class based on method"""
        if self.request.method in ["PUT", "PATCH"]:
            return SpecialistWorkingHoursCreateUpdateSerializer
        return SpecialistWorkingHoursSerializer

    def get_serializer_context(self):
        """Add specialist to serializer context"""
        context = super().get_serializer_context()
        specialist_id = self.kwargs.get("specialist_id")
        if specialist_id:
            context["specialist"] = get_object_or_404(Specialist, id=specialist_id)
        return context

    def perform_update(self, serializer):
        """Update the specialist working hours"""
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
    """View for listing and creating specialist portfolio items"""

    serializer_class = PortfolioItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get portfolio items for a specific specialist"""
        specialist_id = self.kwargs.get("specialist_id")
        return (
            PortfolioItem.objects.filter(specialist_id=specialist_id)
            .select_related("service", "category")
            .order_by("-is_featured", "-created_at")
        )

    def get_permissions(self):
        """Get the permissions based on method"""
        if self.request.method == "GET":
            return [CanViewSpecialist()]
        return [IsAuthenticated(), CanManagePortfolio()]

    def get_serializer_class(self):
        """Get the serializer class based on method"""
        if self.request.method == "POST":
            return PortfolioItemCreateSerializer
        return PortfolioItemSerializer

    def get_serializer_context(self):
        """Add specialist to serializer context"""
        context = super().get_serializer_context()
        specialist_id = self.kwargs.get("specialist_id")
        if specialist_id:
            context["specialist"] = get_object_or_404(Specialist, id=specialist_id)
        return context

    def perform_create(self, serializer):
        """Create the portfolio item"""
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
    """View for retrieving, updating and deleting specialist portfolio items"""

    serializer_class = PortfolioItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get specialist portfolio item queryset"""
        specialist_id = self.kwargs.get("specialist_id")
        return PortfolioItem.objects.filter(specialist_id=specialist_id).select_related(
            "service", "category"
        )

    def get_permissions(self):
        """Get the permissions based on method"""
        if self.request.method == "GET":
            return [CanViewSpecialist()]
        return [IsAuthenticated(), CanManagePortfolio()]

    def get_serializer_class(self):
        """Get the serializer class based on method"""
        if self.request.method in ["PUT", "PATCH"]:
            return PortfolioItemUpdateSerializer
        return PortfolioItemSerializer


class SpecialistAvailabilityView(APIView):
    """View for checking specialist availability on a specific date"""

    permission_classes = [CanViewSpecialist]

    def get(self, request, specialist_id, date):
        """Get specialist availability for a date"""
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
    """View for verifying a specialist"""

    permission_classes = [IsAuthenticated, CanVerifySpecialist]

    def post(self, request, pk):
        """Verify a specialist"""
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
