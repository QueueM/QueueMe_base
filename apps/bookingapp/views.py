# apps/bookingapp/views.py
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, permissions, status, viewsets, generics
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.bookingapp.filters import AppointmentFilter, MultiServiceBookingFilter
from apps.bookingapp.models import (
    Appointment,
    AppointmentNote,
    MultiServiceBooking,
)
from apps.bookingapp.permissions import (
    AppointmentPermission,
    MultiServiceBookingPermission,
)
from apps.bookingapp.serializers import (
    AppointmentNoteSerializer,
    AppointmentSerializer,
    BookingCancelSerializer,
    BookingCreateSerializer,
    BookingRescheduleSerializer,
    MultiServiceBookingCreateSerializer,
    MultiServiceBookingSerializer,
    AppointmentCreateSerializer,
    AppointmentDetailSerializer,
)
from apps.bookingapp.services.availability_service import AvailabilityService
from apps.bookingapp.services.booking_service import BookingService
from apps.bookingapp.services.multi_service_booker import MultiServiceBooker
from apps.bookingapp.services.specialist_matcher import SpecialistMatcher
from utils.request_validators import validate_request_schema, InputSanitizer, RequestValidationError
from django.db import transaction
from datetime import datetime, timedelta
from typing import Dict, List, Optional


# Define JSON Schema for appointment creation
CREATE_APPOINTMENT_SCHEMA = {
    "type": "object",
    "required": ["service_id", "specialist_id", "date", "start_time"],
    "properties": {
        "service_id": {
            "type": "string",
            "format": "uuid",
            "description": "UUID of the service"
        },
        "specialist_id": {
            "type": "string",
            "format": "uuid",
            "description": "UUID of the specialist"
        },
        "date": {
            "type": "string",
            "format": "date",
            "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
            "description": "Appointment date (YYYY-MM-DD)"
        },
        "start_time": {
            "type": "string",
            "pattern": "^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
            "description": "Appointment start time (HH:MM)"
        },
        "notes": {
            "type": "string",
            "maxLength": 1000,
            "description": "Optional notes for the appointment"
        }
    },
    "additionalProperties": False
}

# Define JSON Schema for appointment cancellation
CANCEL_APPOINTMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "reason": {
            "type": "string",
            "maxLength": 500,
            "description": "Optional reason for cancellation"
        }
    },
    "additionalProperties": False
}


class AppointmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing appointments.

    Provides CRUD operations for appointments with additional actions for:
    - Canceling appointments
    - Rescheduling appointments
    - Adding notes to appointments
    - Getting availability for dates

    Permissions are enforced based on user role:
    - Customers can only manage their own appointments
    - Staff can manage appointments for their shop
    - Admins have full access
    """

    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated, AppointmentPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = AppointmentFilter
    search_fields = [
        "customer__phone_number",
        "service__name",
        "specialist__employee__first_name",
        "specialist__employee__last_name",
    ]
    ordering_fields = ["start_time", "created_at", "status", "total_price"]
    ordering = ["-start_time"]

    def get_queryset(self):
        """Filter appointments based on user role"""
        user = self.request.user

        if user.user_type == "customer":
            # Customers can only see their own appointments
            return super().get_queryset().filter(customer=user)
        elif user.user_type == "employee":
            # Employees can see appointments for their shop
            from apps.employeeapp.models import Employee

            try:
                employee = Employee.objects.get(user=user)
                return super().get_queryset().filter(shop=employee.shop)
            except Employee.DoesNotExist:
                return Appointment.objects.none()

        # Admins can see all appointments
        return super().get_queryset()

    @validate_request_schema(CREATE_APPOINTMENT_SCHEMA, schema_id="create_appointment")
    def create(self, request, *args, **kwargs):
        """Create appointment with JSON schema validation"""
        try:
            # Data has already been validated by the schema validator
            # Get validated and sanitized data from request
            data = request.validated_data
            
            # Parse date and time
            from datetime import datetime
            
            try:
                date_obj = datetime.strptime(data["date"], "%Y-%m-%d").date()
                time_obj = datetime.strptime(data["start_time"], "%H:%M").time()
            except ValueError as e:
                return Response(
                    {"detail": f"Date/time parsing error: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Use booking service to create appointment
            appointment = BookingService.create_appointment(
                customer_id=request.user.id,
                service_id=data["service_id"],
                specialist_id=data["specialist_id"],
                start_time_str=data["start_time"],
                date_str=data["date"],
                notes=data.get("notes", ""),
            )

            # Return created appointment
            response_serializer = self.get_serializer(appointment)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=["post"])
    @validate_request_schema(CANCEL_APPOINTMENT_SCHEMA, schema_id="cancel_appointment")
    def cancel(self, request, pk=None):
        """Cancel an appointment"""
        appointment = self.get_object()

        try:
            # Use booking service to cancel appointment
            cancelled_appointment = BookingService.cancel_appointment(
                appointment_id=appointment.id,
                cancelled_by_id=request.user.id,
                reason=request.validated_data.get("reason", ""),
            )

            # Return updated appointment
            response_serializer = self.get_serializer(cancelled_appointment)
            return Response(response_serializer.data)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def reschedule(self, request, pk=None):
        """Reschedule an appointment"""
        appointment = self.get_object()

        serializer = BookingRescheduleSerializer(
            data=request.data, context={"appointment": appointment}
        )
        serializer.is_valid(raise_exception=True)

        try:
            # Use booking service to reschedule appointment
            specialist_id = None
            if "specialist" in serializer.validated_data:
                specialist_id = serializer.validated_data["specialist"].id

            rescheduled_appointment = BookingService.reschedule_appointment(
                appointment_id=appointment.id,
                new_date_str=serializer.validated_data["date"].strftime("%Y-%m-%d"),
                new_start_time_str=serializer.validated_data["start_time"].strftime(
                    "%H:%M"
                ),
                new_specialist_id=specialist_id,
            )

            # Return updated appointment
            response_serializer = self.get_serializer(rescheduled_appointment)
            return Response(response_serializer.data)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def add_note(self, request, pk=None):
        """Add a note to an appointment"""
        appointment = self.get_object()

        serializer = AppointmentNoteSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        # Create note
        note = AppointmentNote.objects.create(
            appointment=appointment,
            user=request.user,
            note=serializer.validated_data["note"],
            is_private=serializer.validated_data.get("is_private", False),
        )

        # Return created note
        return Response(
            AppointmentNoteSerializer(note, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def availability(self, request):
        """Get service availability for a date"""
        service_id = request.query_params.get("service_id")
        date_str = request.query_params.get("date")

        if not service_id or not date_str:
            return Response(
                {"detail": _("service_id and date are required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Parse date
            from datetime import datetime

            date = datetime.strptime(date_str, "%Y-%m-%d").date()

            # Get availability
            availability = AvailabilityService.get_service_availability(
                service_id, date
            )

            return Response(availability)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def specialists(self, request):
        """Get available specialists for a service/time"""
        service_id = request.query_params.get("service_id")
        date_str = request.query_params.get("date")
        start_time_str = request.query_params.get("start_time")
        end_time_str = request.query_params.get("end_time")

        if not all([service_id, date_str, start_time_str, end_time_str]):
            return Response(
                {
                    "detail": _(
                        "service_id, date, start_time, and end_time are required"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Parse date and times
            from datetime import datetime

            date = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
            end_time = datetime.strptime(end_time_str, "%H:%M").time()

            # Get available specialists
            specialists = AvailabilityService.get_available_specialists(
                service_id, date, start_time, end_time
            )

            return Response(specialists)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def recommend_specialist(self, request):
        """Get recommended specialist for a service/time"""
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Get necessary data
            service_id = serializer.validated_data["service_id"]
            date = serializer.validated_data["date"]
            start_time = serializer.validated_data["start_time"]

            # Combine date and time
            import datetime

            from django.utils import timezone

            start_datetime = datetime.datetime.combine(date, start_time)
            start_datetime = timezone.make_aware(start_datetime)

            # Calculate end time (with fixed 1-hour duration for now)
            end_datetime = start_datetime + datetime.timedelta(hours=1)

            # Get recommended specialist
            specialist = SpecialistMatcher.find_best_specialist(
                service_id, request.user.id, (start_datetime, end_datetime)
            )

            if not specialist:
                return Response(
                    {"detail": _("No specialists available")},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Get serialized specialist
            from apps.specialistsapp.serializers import SpecialistSerializer

            return Response(SpecialistSerializer(specialist).data)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MultiServiceBookingViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    API endpoint for managing multi-service bookings.

    Provides operations for:
    - Creating multi-service bookings
    - Retrieving multi-service bookings
    - Listing multi-service bookings
    """

    queryset = MultiServiceBooking.objects.all()
    serializer_class = MultiServiceBookingSerializer
    permission_classes = [permissions.IsAuthenticated, MultiServiceBookingPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = MultiServiceBookingFilter
    ordering_fields = ["created_at", "total_price"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter bookings based on user role"""
        user = self.request.user

        if user.user_type == "customer":
            # Customers can only see their own bookings
            return super().get_queryset().filter(customer=user)
        elif user.user_type == "employee":
            # Employees can see bookings for their shop
            from apps.employeeapp.models import Employee

            try:
                employee = Employee.objects.get(user=user)
                return super().get_queryset().filter(shop=employee.shop)
            except Employee.DoesNotExist:
                return MultiServiceBooking.objects.none()

        # Admins can see all bookings
        return super().get_queryset()

    def create(self, request, *args, **kwargs):
        """Create multi-service booking"""
        serializer = MultiServiceBookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Extract list of bookings
            bookings_data = serializer.validated_data["services"]

            # Get first booking's shop (all bookings should be for the same shop)
            shop_id = bookings_data[0]["shop"].id

            # Use booking service to create multi-service booking
            multi_booking = BookingService.create_multi_service_booking(
                customer_id=request.user.id,
                bookings_data=bookings_data,
                shop_id=shop_id,
            )

            # Return created booking
            response_serializer = self.get_serializer(multi_booking)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def suggest_sequence(self, request):
        """Suggest optimal sequence for multiple services"""
        # Validate input
        service_ids = request.data.get("service_ids", [])
        date_str = request.data.get("date")
        shop_id = request.data.get("shop_id")

        if not service_ids or not date_str or not shop_id:
            return Response(
                {"detail": _("service_ids, date, and shop_id are required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Parse date
            from datetime import datetime

            date = datetime.strptime(date_str, "%Y-%m-%d").date()

            # Get optimal sequence
            suggested_bookings = MultiServiceBooker.suggest_optimal_sequence(
                service_ids=service_ids,
                date=date,
                shop_id=shop_id,
                customer_id=request.user.id,
            )

            if not suggested_bookings:
                return Response(
                    {"detail": _("Could not find suitable slots for all services")},
                    status=status.HTTP_404_NOT_FOUND,
                )

            return Response(suggested_bookings)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AppointmentCreateView(generics.CreateAPIView):
    """Create a new appointment with conflict detection"""
    
    serializer_class = AppointmentCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create appointment with atomic transaction to prevent race conditions.
        Uses SELECT FOR UPDATE to lock rows while checking for availability.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Extract data for conflict check
        service_id = serializer.validated_data['service'].id
        specialist_id = serializer.validated_data['specialist'].id
        shop_id = serializer.validated_data['shop'].id
        start_time = serializer.validated_data['start_time']
        
        # Calculate end time
        service = serializer.validated_data['service']
        end_time = start_time + timedelta(minutes=service.duration)
        
        # Check for conflicts using FOR UPDATE to lock rows
        # This prevents race conditions where multiple users try to book the same slot
        conflicts = Appointment.objects.select_for_update().filter(
            specialist_id=specialist_id,
            status__in=['scheduled', 'confirmed', 'in_progress'],
            start_time__lt=end_time,
            end_time__gt=start_time
        ).exists()
        
        if conflicts:
            return Response(
                {"detail": "This time slot is no longer available. Please select another."},
                status=status.HTTP_409_CONFLICT
            )
        
        # No conflicts, save the appointment
        appointment = serializer.save(customer=request.user)
        
        # Return the created appointment
        output_serializer = AppointmentDetailSerializer(appointment)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class MultiServiceBookingCreateView(generics.CreateAPIView):
    """Create a multi-service booking with multiple appointments"""
    
    serializer_class = MultiServiceBookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create multiple appointments and group them in a booking.
        Uses transaction to ensure all appointments are created or none.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Extract appointments data for conflict check
        appointments_data = serializer.validated_data.get('appointments_data', [])
        
        # Check for conflicts in all appointments
        for appt_data in appointments_data:
            specialist_id = appt_data['specialist_id']
            start_time = appt_data['start_time']
            duration = appt_data.get('duration', 30)  # Default 30 minutes
            end_time = start_time + timedelta(minutes=duration)
            
            # Check for conflicts
            conflicts = Appointment.objects.select_for_update().filter(
                specialist_id=specialist_id,
                status__in=['scheduled', 'confirmed', 'in_progress'],
                start_time__lt=end_time,
                end_time__gt=start_time
            ).exists()
            
            if conflicts:
                return Response(
                    {"detail": f"Conflict detected for appointment at {start_time}. Please select another time."},
                    status=status.HTTP_409_CONFLICT
                )
        
        # No conflicts, create the booking
        booking = serializer.save(customer=request.user)
        
        return Response(
            MultiServiceBookingSerializer(booking).data,
            status=status.HTTP_201_CREATED
        )
