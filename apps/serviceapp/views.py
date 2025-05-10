import datetime

from django.db import models, transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.rolesapp.decorators import has_permission, has_shop_permission
from apps.rolesapp.permissions import IsAuthenticated, IsShopStaffOrAdmin

from .filters import ServiceFilter
from .models import (
    Service,
    ServiceAftercare,
    ServiceAvailability,
    ServiceException,
    ServiceFAQ,
    ServiceOverview,
    ServiceStep,
)
from .serializers import (
    AvailabilitySlotSerializer,
    ServiceAftercareCreateUpdateSerializer,
    ServiceAftercareSerializer,
    ServiceAvailabilityCreateUpdateSerializer,
    ServiceAvailabilitySerializer,
    ServiceCreateSerializer,
    ServiceDetailSerializer,
    ServiceExceptionCreateUpdateSerializer,
    ServiceExceptionSerializer,
    ServiceFAQCreateUpdateSerializer,
    ServiceFAQSerializer,
    ServiceListSerializer,
    ServiceOverviewCreateUpdateSerializer,
    ServiceOverviewSerializer,
    ServiceStepCreateUpdateSerializer,
    ServiceStepSerializer,
    ServiceUpdateSerializer,
)
from .services.availability_service import AvailabilityService
from .services.duration_refiner import DurationRefiner
from .services.service_matcher import ServiceMatcher


class ServiceViewSet(viewsets.ModelViewSet):
    """API endpoint for services"""

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ServiceFilter
    search_fields = ["name", "description", "short_description"]
    ordering_fields = ["name", "price", "duration", "order", "created_at"]
    ordering = ["order", "name"]

    def get_queryset(self):
        """Filter queryset based on user role and permissions"""
        queryset = Service.objects.all()

        # Standard filtering for customers - only active services
        if not self.request.user.is_authenticated:
            return queryset.filter(status="active")

        user = self.request.user

        # For customers, only active services
        if user.user_type == "customer":
            return queryset.filter(status="active")

        # For shop staff, only their shop's services
        if user.user_type == "employee":
            from apps.employeeapp.models import Employee

            try:
                employee = Employee.objects.get(user=user)
                return queryset.filter(shop=employee.shop)
            except Employee.DoesNotExist:
                return Service.objects.none()

        # For Queue Me admins, all services
        if user.user_type == "admin":
            return queryset

        return Service.objects.none()

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "list":
            return ServiceListSerializer
        elif self.action == "retrieve":
            return ServiceDetailSerializer
        elif self.action == "create":
            return ServiceCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return ServiceUpdateSerializer

        return ServiceDetailSerializer

    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ["list", "retrieve", "availability_slots"]:
            permission_classes = [permissions.AllowAny]
        elif self.action in ["create"]:
            permission_classes = [IsAuthenticated, IsShopStaffOrAdmin]
        else:
            permission_classes = [IsAuthenticated, IsShopStaffOrAdmin]

        return [permission() for permission in permission_classes]

    @transaction.atomic
    @has_permission("service", "add")
    def create(self, request, *args, **kwargs):
        """Create a new service"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        # Return detailed representation
        detail_serializer = ServiceDetailSerializer(serializer.instance)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    @has_shop_permission("service", "edit")
    def update(self, request, *args, **kwargs):
        """Update a service"""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Return detailed representation
        detail_serializer = ServiceDetailSerializer(instance)
        return Response(detail_serializer.data)

    @transaction.atomic
    @has_shop_permission("service", "delete")
    def destroy(self, request, *args, **kwargs):
        """Delete a service"""
        instance = self.get_object()

        # Check if service has appointments
        from apps.bookingapp.models import Appointment

        has_appointments = Appointment.objects.filter(service=instance).exists()

        if has_appointments:
            # Instead of deleting, mark as archived
            instance.status = "archived"
            instance.save()
            return Response(
                {
                    "detail": _(
                        "Service has appointments and cannot be deleted. It has been archived instead."
                    )
                },
                status=status.HTTP_200_OK,
            )

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def availability_slots(self, request, pk=None):
        """
        Get available time slots for a service on a specific date

        Query parameters:
        - date: Date to check (YYYY-MM-DD)
        """
        service = self.get_object()
        date_str = request.query_params.get("date")

        if not date_str:
            return Response(
                {"detail": _("Date parameter is required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"detail": _("Invalid date format. Use YYYY-MM-DD")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        slots = AvailabilityService.get_service_availability(service.id, date)
        serializer = AvailabilitySlotSerializer(slots, many=True)

        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def available_specialists(self, request, pk=None):
        """
        Get available specialists for a service at a specific time

        Query parameters:
        - date: Date to check (YYYY-MM-DD)
        - start_time: Start time (HH:MM)
        - end_time: End time (HH:MM)
        """
        service = self.get_object()
        date_str = request.query_params.get("date")
        start_time = request.query_params.get("start_time")
        end_time = request.query_params.get("end_time")

        if not date_str or not start_time:
            return Response(
                {"detail": _("Date and start_time parameters are required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            start = datetime.datetime.strptime(start_time, "%H:%M").time()

            if end_time:
                end = datetime.datetime.strptime(end_time, "%H:%M").time()
            else:
                # Calculate end time based on service duration
                start_dt = datetime.datetime.combine(date, start)
                end_dt = start_dt + datetime.timedelta(minutes=service.duration)
                end = end_dt.time()
        except ValueError:
            return Response(
                {"detail": _("Invalid date or time format. Use YYYY-MM-DD and HH:MM")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        specialist_ids = AvailabilityService.get_available_specialists(
            service.id, date, start, end
        )

        # Get specialist details
        from apps.specialistsapp.models import Specialist
        from apps.specialistsapp.serializers import SpecialistListSerializer

        specialists = Specialist.objects.filter(id__in=specialist_ids)
        serializer = SpecialistListSerializer(
            specialists, many=True, context={"request": request}
        )

        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def recommended_specialists(self, request, pk=None):
        """
        Get recommended specialists for a service, ranked by suitability

        Query parameters:
        - date: Optional date for specific time slot (YYYY-MM-DD)
        - start_time: Optional start time (HH:MM)
        - end_time: Optional end time (HH:MM)
        """
        service = self.get_object()
        date_str = request.query_params.get("date")
        start_time = request.query_params.get("start_time")
        end_time = request.query_params.get("end_time")

        time_slot = None
        if date_str and start_time:
            try:
                date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                start = datetime.datetime.strptime(start_time, "%H:%M").time()

                if end_time:
                    end = datetime.datetime.strptime(end_time, "%H:%M").time()
                else:
                    # Calculate end time based on service duration
                    start_dt = datetime.datetime.combine(date, start)
                    end_dt = start_dt + datetime.timedelta(minutes=service.duration)
                    end = end_dt.time()

                time_slot = {"date": date, "start_time": start, "end_time": end}
            except ValueError:
                return Response(
                    {
                        "detail": _(
                            "Invalid date or time format. Use YYYY-MM-DD and HH:MM"
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Get customer ID if authenticated
        customer_id = None
        if request.user.is_authenticated and request.user.user_type == "customer":
            customer_id = request.user.id

        specialists = ServiceMatcher.find_optimal_specialist(
            service.id, time_slot, customer_id
        )

        return Response(specialists)

    @action(detail=True, methods=["get"])
    def complementary_services(self, request, pk=None):
        """
        Get services that complement this service

        These are services that are frequently booked together or logically related
        """
        service = self.get_object()

        # Get customer ID if authenticated
        customer_id = None
        if request.user.is_authenticated and request.user.user_type == "customer":
            customer_id = request.user.id

        complementary = ServiceMatcher.find_complementary_services(
            service.id, customer_id
        )

        return Response(complementary)

    @action(detail=True, methods=["get"])
    @has_shop_permission("service", "view")
    def analyze_duration(self, request, pk=None):
        """
        Analyze historical service durations to suggest optimizations

        This provides insights on whether the service duration should be adjusted
        based on actual service delivery times.
        """
        service = self.get_object()

        # Get lookback period from query params (default 30 days)
        lookback_days = int(request.query_params.get("lookback_days", 30))

        analysis = DurationRefiner.analyze_service_duration(service.id, lookback_days)

        return Response(analysis)

    @action(detail=True, methods=["get"])
    @has_shop_permission("service", "view")
    def analyze_buffers(self, request, pk=None):
        """
        Analyze buffer times (before/after) to suggest optimizations

        This provides insights on whether buffer times should be adjusted
        based on actual preparation and cleanup times.
        """
        service = self.get_object()

        # Get lookback period from query params (default 30 days)
        lookback_days = int(request.query_params.get("lookback_days", 30))

        analysis = DurationRefiner.analyze_buffer_times(service.id, lookback_days)

        return Response(analysis)

    @action(detail=True, methods=["post"])
    @has_shop_permission("service", "edit")
    def apply_recommended_duration(self, request, pk=None):
        """Apply a recommended duration to the service"""
        service = self.get_object()
        new_duration = request.data.get("duration")

        if not new_duration:
            return Response(
                {"detail": _("Duration is required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            new_duration = int(new_duration)
            if new_duration < 1 or new_duration > 1440:
                return Response(
                    {"detail": _("Duration must be between 1 and 1440 minutes")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError:
            return Response(
                {"detail": _("Duration must be a number")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_service = DurationRefiner.apply_recommended_duration(
            service.id, new_duration
        )
        serializer = ServiceDetailSerializer(updated_service)

        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    @has_shop_permission("service", "edit")
    def apply_recommended_buffers(self, request, pk=None):
        """Apply recommended buffer times to the service"""
        service = self.get_object()
        buffer_before = request.data.get("buffer_before")
        buffer_after = request.data.get("buffer_after")

        if buffer_before is None and buffer_after is None:
            return Response(
                {"detail": _("At least one buffer time is required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            if buffer_before is not None:
                buffer_before = int(buffer_before)
                if buffer_before < 0 or buffer_before > 120:
                    return Response(
                        {
                            "detail": _(
                                "Buffer before must be between 0 and 120 minutes"
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            if buffer_after is not None:
                buffer_after = int(buffer_after)
                if buffer_after < 0 or buffer_after > 120:
                    return Response(
                        {"detail": _("Buffer after must be between 0 and 120 minutes")},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        except ValueError:
            return Response(
                {"detail": _("Buffer times must be numbers")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_service = DurationRefiner.apply_recommended_buffer_times(
            service.id, buffer_before, buffer_after
        )
        serializer = ServiceDetailSerializer(updated_service)

        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    @has_shop_permission("service", "edit")
    def duplicate(self, request, pk=None):
        """
        Duplicate a service with all its associated data

        Query parameters:
        - new_name: Optional new name for the duplicate
        - include_specialists: Whether to duplicate specialist assignments (default True)
        """
        service = self.get_object()
        new_name = request.data.get("new_name")
        include_specialists = request.data.get("include_specialists", True)

        from .services.service_service import ServiceService

        duplicated = ServiceService.duplicate_service(
            service.id, new_name, include_specialists
        )

        serializer = ServiceDetailSerializer(duplicated)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="assign-specialists")
    @has_shop_permission("service", "edit")
    def assign_specialists(self, request, pk=None):
        """
        Assign specialists to a service

        Body:
        - specialist_ids: List of specialist IDs to assign
        - replace: Whether to replace existing specialists (default False)
        """
        service = self.get_object()
        specialist_ids = request.data.get("specialist_ids", [])
        replace = request.data.get("replace", False)

        if not specialist_ids:
            return Response(
                {"detail": _("Specialist IDs are required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .services.service_service import ServiceService

        unused_unused_updated_service = ServiceService.manage_specialists(
            service.id, specialist_ids, replace
        )

        return Response({"detail": _("Specialists assigned successfully")})

    @action(detail=True, methods=["get"], url_path="available-days")
    def available_days(self, request, pk=None):
        """
        Get a list of dates when the service has at least one available slot

        Query parameters:
        - start_date: Start date (YYYY-MM-DD, default: today)
        - end_date: End date (YYYY-MM-DD, default: 30 days from start)
        """
        service = self.get_object()

        # Parse dates
        try:
            start_date_str = request.query_params.get("start_date")
            if start_date_str:
                start_date = datetime.datetime.strptime(
                    start_date_str, "%Y-%m-%d"
                ).date()
            else:
                start_date = datetime.date.today()

            end_date_str = request.query_params.get("end_date")
            if end_date_str:
                end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date()
            else:
                end_date = start_date + datetime.timedelta(days=30)
        except ValueError:
            return Response(
                {"detail": _("Invalid date format. Use YYYY-MM-DD")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get available days
        available_days = AvailabilityService.get_service_available_days(
            service.id, start_date, end_date
        )

        # Format dates as strings
        available_days_str = [date.strftime("%Y-%m-%d") for date in available_days]

        return Response(available_days_str)


class ServiceAvailabilityViewSet(viewsets.ModelViewSet):
    """API endpoint for service availability"""

    serializer_class = ServiceAvailabilitySerializer
    permission_classes = [IsAuthenticated, IsShopStaffOrAdmin]

    def get_queryset(self):
        service_id = self.kwargs.get("service_id")
        return ServiceAvailability.objects.filter(service_id=service_id)

    def get_service(self):
        service_id = self.kwargs.get("service_id")
        return get_object_or_404(Service, id=service_id)

    def check_permissions(self, request):
        super().check_permissions(request)
        service = self.get_service()

        # Check if user has permission for this shop
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        if not PermissionResolver.has_shop_permission(
            request.user, service.shop_id, "service", "edit"
        ):
            self.permission_denied(request)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        service = self.get_service()
        serializer = ServiceAvailabilityCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create availability
        availability = ServiceAvailability.objects.create(
            service=service, **serializer.validated_data
        )

        # Update service flag
        service.has_custom_availability = True
        service.save()

        return Response(
            ServiceAvailabilitySerializer(availability).data,
            status=status.HTTP_201_CREATED,
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        availability = self.get_object()
        serializer = ServiceAvailabilityCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Update availability
        for key, value in serializer.validated_data.items():
            setattr(availability, key, value)

        availability.save()

        return Response(ServiceAvailabilitySerializer(availability).data)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        availability = self.get_object()
        availability.delete()

        # Check if service still has any availability records
        service = self.get_service()
        if not ServiceAvailability.objects.filter(service=service).exists():
            service.has_custom_availability = False
            service.save()

        return Response(status=status.HTTP_204_NO_CONTENT)


class ServiceExceptionViewSet(viewsets.ModelViewSet):
    """API endpoint for service exceptions (holidays, special days)"""

    serializer_class = ServiceExceptionSerializer
    permission_classes = [IsAuthenticated, IsShopStaffOrAdmin]

    def get_queryset(self):
        service_id = self.kwargs.get("service_id")
        return ServiceException.objects.filter(service_id=service_id)

    def get_service(self):
        service_id = self.kwargs.get("service_id")
        return get_object_or_404(Service, id=service_id)

    def check_permissions(self, request):
        super().check_permissions(request)
        service = self.get_service()

        # Check if user has permission for this shop
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        if not PermissionResolver.has_shop_permission(
            request.user, service.shop_id, "service", "edit"
        ):
            self.permission_denied(request)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        service = self.get_service()
        serializer = ServiceExceptionCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Check if exception already exists for this date
        date = serializer.validated_data.get("date")
        existing = ServiceException.objects.filter(service=service, date=date).first()

        if existing:
            # Update existing
            for key, value in serializer.validated_data.items():
                setattr(existing, key, value)

            existing.save()
            return Response(ServiceExceptionSerializer(existing).data)

        # Create new exception
        exception = ServiceException.objects.create(
            service=service, **serializer.validated_data
        )

        return Response(
            ServiceExceptionSerializer(exception).data, status=status.HTTP_201_CREATED
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        exception = self.get_object()
        serializer = ServiceExceptionCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Update exception
        for key, value in serializer.validated_data.items():
            setattr(exception, key, value)

        exception.save()

        return Response(ServiceExceptionSerializer(exception).data)


class ServiceFAQViewSet(viewsets.ModelViewSet):
    """API endpoint for service FAQs"""

    serializer_class = ServiceFAQSerializer
    permission_classes = [IsAuthenticated, IsShopStaffOrAdmin]

    def get_queryset(self):
        service_id = self.kwargs.get("service_id")
        return ServiceFAQ.objects.filter(service_id=service_id)

    def get_service(self):
        service_id = self.kwargs.get("service_id")
        return get_object_or_404(Service, id=service_id)

    def check_permissions(self, request):
        super().check_permissions(request)
        service = self.get_service()

        # Check if user has permission for this shop
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        if not PermissionResolver.has_shop_permission(
            request.user, service.shop_id, "service", "edit"
        ):
            self.permission_denied(request)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        service = self.get_service()
        serializer = ServiceFAQCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get next order if not provided
        data = serializer.validated_data.copy()
        if "order" not in data or data["order"] is None:
            max_order = (
                ServiceFAQ.objects.filter(service=service).aggregate(
                    max_order=models.Max("order")
                )["max_order"]
                or 0
            )
            data["order"] = max_order + 1

        # Create FAQ
        faq = ServiceFAQ.objects.create(service=service, **data)

        return Response(ServiceFAQSerializer(faq).data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        faq = self.get_object()
        serializer = ServiceFAQCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Update FAQ
        for key, value in serializer.validated_data.items():
            setattr(faq, key, value)

        faq.save()

        return Response(ServiceFAQSerializer(faq).data)

    @action(detail=False, methods=["post"], url_path="reorder")
    @transaction.atomic
    def reorder(self, request, service_id=None):
        """
        Reorder FAQs

        Body:
        - faq_order: List of FAQ IDs in the desired order
        """
        service = self.get_service()
        faq_order = request.data.get("faq_order", [])

        if not faq_order:
            return Response(
                {"detail": _("FAQ order is required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify all FAQs belong to this service
        service_faqs = set(
            ServiceFAQ.objects.filter(service=service).values_list("id", flat=True)
        )

        for faq_id in faq_order:
            if str(faq_id) not in map(str, service_faqs):
                return Response(
                    {"detail": _("All FAQ IDs must belong to this service")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Update order
        for i, faq_id in enumerate(faq_order):
            ServiceFAQ.objects.filter(id=faq_id).update(order=i)

        # Return updated FAQs
        updated_faqs = ServiceFAQ.objects.filter(service=service).order_by("order")
        serializer = ServiceFAQSerializer(updated_faqs, many=True)

        return Response(serializer.data)


class ServiceOverviewViewSet(viewsets.ModelViewSet):
    """API endpoint for service overviews"""

    serializer_class = ServiceOverviewSerializer
    permission_classes = [IsAuthenticated, IsShopStaffOrAdmin]

    def get_queryset(self):
        service_id = self.kwargs.get("service_id")
        return ServiceOverview.objects.filter(service_id=service_id)

    def get_service(self):
        service_id = self.kwargs.get("service_id")
        return get_object_or_404(Service, id=service_id)

    def check_permissions(self, request):
        super().check_permissions(request)
        service = self.get_service()

        # Check if user has permission for this shop
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        if not PermissionResolver.has_shop_permission(
            request.user, service.shop_id, "service", "edit"
        ):
            self.permission_denied(request)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        service = self.get_service()
        serializer = ServiceOverviewCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get next order if not provided
        data = serializer.validated_data.copy()
        if "order" not in data or data["order"] is None:
            max_order = (
                ServiceOverview.objects.filter(service=service).aggregate(
                    max_order=models.Max("order")
                )["max_order"]
                or 0
            )
            data["order"] = max_order + 1

        # Create overview
        overview = ServiceOverview.objects.create(service=service, **data)

        return Response(
            ServiceOverviewSerializer(overview).data, status=status.HTTP_201_CREATED
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        overview = self.get_object()
        serializer = ServiceOverviewCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Update overview
        for key, value in serializer.validated_data.items():
            setattr(overview, key, value)

        overview.save()

        return Response(ServiceOverviewSerializer(overview).data)

    @action(detail=False, methods=["post"], url_path="reorder")
    @transaction.atomic
    def reorder(self, request, service_id=None):
        """
        Reorder overviews

        Body:
        - overview_order: List of overview IDs in the desired order
        """
        service = self.get_service()
        overview_order = request.data.get("overview_order", [])

        if not overview_order:
            return Response(
                {"detail": _("Overview order is required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify all overviews belong to this service
        service_overviews = set(
            ServiceOverview.objects.filter(service=service).values_list("id", flat=True)
        )

        for overview_id in overview_order:
            if str(overview_id) not in map(str, service_overviews):
                return Response(
                    {"detail": _("All overview IDs must belong to this service")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Update order
        for i, overview_id in enumerate(overview_order):
            ServiceOverview.objects.filter(id=overview_id).update(order=i)

        # Return updated overviews
        updated_overviews = ServiceOverview.objects.filter(service=service).order_by(
            "order"
        )
        serializer = ServiceOverviewSerializer(updated_overviews, many=True)

        return Response(serializer.data)


class ServiceStepViewSet(viewsets.ModelViewSet):
    """API endpoint for service steps (How It Works)"""

    serializer_class = ServiceStepSerializer
    permission_classes = [IsAuthenticated, IsShopStaffOrAdmin]

    def get_queryset(self):
        service_id = self.kwargs.get("service_id")
        return ServiceStep.objects.filter(service_id=service_id)

    def get_service(self):
        service_id = self.kwargs.get("service_id")
        return get_object_or_404(Service, id=service_id)

    def check_permissions(self, request):
        super().check_permissions(request)
        service = self.get_service()

        # Check if user has permission for this shop
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        if not PermissionResolver.has_shop_permission(
            request.user, service.shop_id, "service", "edit"
        ):
            self.permission_denied(request)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        service = self.get_service()
        serializer = ServiceStepCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get next order if not provided
        data = serializer.validated_data.copy()
        if "order" not in data or data["order"] is None:
            max_order = (
                ServiceStep.objects.filter(service=service).aggregate(
                    max_order=models.Max("order")
                )["max_order"]
                or 0
            )
            data["order"] = max_order + 1

        # Create step
        step = ServiceStep.objects.create(service=service, **data)

        return Response(
            ServiceStepSerializer(step).data, status=status.HTTP_201_CREATED
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        step = self.get_object()
        serializer = ServiceStepCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Update step
        for key, value in serializer.validated_data.items():
            setattr(step, key, value)

        step.save()

        return Response(ServiceStepSerializer(step).data)

    @action(detail=False, methods=["post"], url_path="reorder")
    @transaction.atomic
    def reorder(self, request, service_id=None):
        """
        Reorder steps

        Body:
        - step_order: List of step IDs in the desired order
        """
        service = self.get_service()
        step_order = request.data.get("step_order", [])

        if not step_order:
            return Response(
                {"detail": _("Step order is required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify all steps belong to this service
        service_steps = set(
            ServiceStep.objects.filter(service=service).values_list("id", flat=True)
        )

        for step_id in step_order:
            if str(step_id) not in map(str, service_steps):
                return Response(
                    {"detail": _("All step IDs must belong to this service")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Update order
        for i, step_id in enumerate(step_order):
            ServiceStep.objects.filter(id=step_id).update(order=i)

        # Return updated steps
        updated_steps = ServiceStep.objects.filter(service=service).order_by("order")
        serializer = ServiceStepSerializer(updated_steps, many=True)

        return Response(serializer.data)


class ServiceAftercareViewSet(viewsets.ModelViewSet):
    """API endpoint for service aftercare tips"""

    serializer_class = ServiceAftercareSerializer
    permission_classes = [IsAuthenticated, IsShopStaffOrAdmin]

    def get_queryset(self):
        service_id = self.kwargs.get("service_id")
        return ServiceAftercare.objects.filter(service_id=service_id)

    def get_service(self):
        service_id = self.kwargs.get("service_id")
        return get_object_or_404(Service, id=service_id)

    def check_permissions(self, request):
        super().check_permissions(request)
        service = self.get_service()

        # Check if user has permission for this shop
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        if not PermissionResolver.has_shop_permission(
            request.user, service.shop_id, "service", "edit"
        ):
            self.permission_denied(request)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        service = self.get_service()
        serializer = ServiceAftercareCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get next order if not provided
        data = serializer.validated_data.copy()
        if "order" not in data or data["order"] is None:
            max_order = (
                ServiceAftercare.objects.filter(service=service).aggregate(
                    max_order=models.Max("order")
                )["max_order"]
                or 0
            )
            data["order"] = max_order + 1

        # Create aftercare tip
        tip = ServiceAftercare.objects.create(service=service, **data)

        return Response(
            ServiceAftercareSerializer(tip).data, status=status.HTTP_201_CREATED
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        tip = self.get_object()
        serializer = ServiceAftercareCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Update aftercare tip
        for key, value in serializer.validated_data.items():
            setattr(tip, key, value)

        tip.save()

        return Response(ServiceAftercareSerializer(tip).data)

    @action(detail=False, methods=["post"], url_path="reorder")
    @transaction.atomic
    def reorder(self, request, service_id=None):
        """
        Reorder aftercare tips

        Body:
        - tip_order: List of tip IDs in the desired order
        """
        service = self.get_service()
        tip_order = request.data.get("tip_order", [])

        if not tip_order:
            return Response(
                {"detail": _("Tip order is required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify all tips belong to this service
        service_tips = set(
            ServiceAftercare.objects.filter(service=service).values_list(
                "id", flat=True
            )
        )

        for tip_id in tip_order:
            if str(tip_id) not in map(str, service_tips):
                return Response(
                    {"detail": _("All tip IDs must belong to this service")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Update order
        for i, tip_id in enumerate(tip_order):
            ServiceAftercare.objects.filter(id=tip_id).update(order=i)

        # Return updated tips
        updated_tips = ServiceAftercare.objects.filter(service=service).order_by(
            "order"
        )
        serializer = ServiceAftercareSerializer(updated_tips, many=True)

        return Response(serializer.data)
