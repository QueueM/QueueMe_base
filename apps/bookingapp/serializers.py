# apps/bookingapp/serializers.py
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.authapp.serializers import UserSerializer
from apps.bookingapp.models import (
    Appointment,
    AppointmentNote,
    AppointmentReminder,
    MultiServiceBooking,
)
from apps.serviceapp.serializers import ServiceSerializer
from apps.shopapp.serializers import ShopSerializer
from apps.specialistsapp.serializers import SpecialistSerializer


class AppointmentReminderSerializer(serializers.ModelSerializer):
    """Serializer for appointment reminders"""

    reminder_type_display = serializers.CharField(
        source="get_reminder_type_display", read_only=True
    )

    class Meta:
        model = AppointmentReminder
        fields = [
            "id",
            "reminder_type",
            "reminder_type_display",
            "scheduled_time",
            "sent_at",
            "is_sent",
            "content",
        ]
        read_only_fields = ["id", "sent_at", "is_sent"]


class AppointmentNoteSerializer(serializers.ModelSerializer):
    """Serializer for appointment notes"""

    user_details = UserSerializer(source="user", read_only=True)

    class Meta:
        model = AppointmentNote
        fields = ["id", "user", "user_details", "note", "is_private", "created_at"]
        read_only_fields = ["id", "created_at", "user_details"]

    def validate(self, data):
        """Validate that only staff can create private notes"""
        user = self.context["request"].user
        is_private = data.get("is_private", False)

        if is_private and user.user_type == "customer":
            raise serializers.ValidationError(
                _("Customers cannot create private notes")
            )

        return data


class AppointmentSerializer(serializers.ModelSerializer):
    """Serializer for appointments"""

    customer_details = UserSerializer(source="customer", read_only=True)
    service_details = ServiceSerializer(source="service", read_only=True)
    specialist_details = SpecialistSerializer(source="specialist", read_only=True)
    shop_details = ShopSerializer(source="shop", read_only=True)
    cancelled_by_details = UserSerializer(source="cancelled_by", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True
    )
    reminders = AppointmentReminderSerializer(many=True, read_only=True)
    notes = AppointmentNoteSerializer(source="notes_history", many=True, read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "customer",
            "customer_details",
            "service",
            "service_details",
            "specialist",
            "specialist_details",
            "shop",
            "shop_details",
            "start_time",
            "end_time",
            "status",
            "status_display",
            "notes",
            "transaction_id",
            "payment_status",
            "payment_status_display",
            "is_reminder_sent",
            "cancelled_by",
            "cancelled_by_details",
            "cancellation_reason",
            "created_at",
            "updated_at",
            "total_price",
            "buffer_before",
            "buffer_after",
            "duration",
            "is_reviewed",
            "reminders",
        ]
        read_only_fields = [
            "id",
            "status_display",
            "payment_status_display",
            "is_reminder_sent",
            "cancelled_by_details",
            "created_at",
            "updated_at",
            "customer_details",
            "service_details",
            "specialist_details",
            "shop_details",
            "is_reviewed",
            "reminders",
        ]

    def validate(self, data):
        """Validate appointment data ensuring no scheduling conflicts"""
        # Get service, specialist, and shop either from data or instance if updating
        service = data.get("service", getattr(self.instance, "service", None))
        specialist = data.get("specialist", getattr(self.instance, "specialist", None))
        shop = data.get("shop", getattr(self.instance, "shop", None))
        start_time = data.get("start_time", getattr(self.instance, "start_time", None))
        end_time = data.get("end_time", getattr(self.instance, "end_time", None))

        if not all([service, specialist, shop, start_time, end_time]):
            return data  # Partial update without all required fields

        # Validate that end time is after start time
        if end_time <= start_time:
            raise serializers.ValidationError(_("End time must be after start time"))

        # Validate that appointment is in the future
        if start_time < timezone.now():
            raise serializers.ValidationError(_("Cannot book appointments in the past"))

        # Validate specialist can provide this service
        from apps.specialistsapp.models import SpecialistService

        specialist_service = SpecialistService.objects.filter(
            specialist=specialist, service=service
        ).exists()

        if not specialist_service:
            raise serializers.ValidationError(
                _("Specialist does not provide this service")
            )

        # Validate that service belongs to the shop
        if service.shop != shop:
            raise serializers.ValidationError(
                _("Service does not belong to the selected shop")
            )

        # Validate specialist belongs to the shop
        if specialist.employee.shop != shop:
            raise serializers.ValidationError(
                _("Specialist does not belong to the selected shop")
            )

        # Check for scheduling conflicts using conflict service
        from apps.bookingapp.services.conflict_service import ConflictService

        # If updating, exclude current appointment from conflict check
        exclude_id = None
        if self.instance:
            exclude_id = self.instance.id

        conflict = ConflictService.check_appointment_conflict(
            specialist.id, start_time, end_time, exclude_appointment_id=exclude_id
        )

        if conflict:
            raise serializers.ValidationError(
                _("The specialist is not available at this time")
            )

        return data

    def create(self, validated_data):
        """Create appointment with customer from request"""
        validated_data["customer"] = self.context["request"].user

        # Set calculated fields
        service = validated_data.get("service")
        if service:
            if "buffer_before" not in validated_data:
                validated_data["buffer_before"] = service.buffer_before
            if "buffer_after" not in validated_data:
                validated_data["buffer_after"] = service.buffer_after
            if "duration" not in validated_data:
                validated_data["duration"] = service.duration
            if "total_price" not in validated_data:
                validated_data["total_price"] = service.price

        return super().create(validated_data)


class BookingCreateSerializer(serializers.Serializer):
    """Serializer for creating a booking with simplified input"""

    service_id = serializers.UUIDField()
    specialist_id = serializers.UUIDField()
    date = serializers.DateField()
    start_time = serializers.TimeField()
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        """Validate booking data and check availability"""
        import datetime

        from django.utils import timezone

        from apps.serviceapp.models import Service
        from apps.specialistsapp.models import Specialist

        # Get service and specialist
        try:
            service = Service.objects.get(id=data["service_id"])
            specialist = Specialist.objects.get(id=data["specialist_id"])
        except (Service.DoesNotExist, Specialist.DoesNotExist):
            raise serializers.ValidationError(_("Service or specialist not found"))

        # Check if specialist provides this service
        from apps.specialistsapp.models import SpecialistService

        specialist_service = SpecialistService.objects.filter(
            specialist=specialist, service=service
        ).exists()

        if not specialist_service:
            raise serializers.ValidationError(
                _("Specialist does not provide this service")
            )

        # Combine date and time
        date = data["date"]
        time = data["start_time"]
        start_datetime = datetime.datetime.combine(date, time)

        # Make timezone-aware
        tz = timezone.get_default_timezone()
        start_datetime = timezone.make_aware(start_datetime, tz)

        # Calculate end time
        end_datetime = start_datetime + datetime.timedelta(minutes=service.duration)

        # Validate date is in the future
        if start_datetime < timezone.now():
            raise serializers.ValidationError(_("Cannot book appointments in the past"))

        # Check availability using availability service
        from apps.bookingapp.services.availability_service import AvailabilityService

        is_available = AvailabilityService.check_time_slot_available(
            service.id, specialist.id, start_datetime, end_datetime
        )

        if not is_available:
            raise serializers.ValidationError(
                _("The selected time slot is not available")
            )

        # Add shop to validated data
        data["shop"] = service.shop

        # Add end time to validated data
        data["end_datetime"] = end_datetime
        data["start_datetime"] = start_datetime

        return data


class BookingCancelSerializer(serializers.Serializer):
    """Serializer for cancelling an appointment"""

    reason = serializers.CharField(required=False, allow_blank=True)


class BookingRescheduleSerializer(serializers.Serializer):
    """Serializer for rescheduling an appointment"""

    date = serializers.DateField()
    start_time = serializers.TimeField()
    specialist_id = serializers.UUIDField(required=False)

    def validate(self, data):
        """Validate reschedule data and check availability"""
        import datetime

        from django.utils import timezone

        from apps.specialistsapp.models import Specialist

        # Get appointment from context
        appointment = self.context.get("appointment")
        if not appointment:
            raise serializers.ValidationError(_("Appointment not provided"))

        # Get specialist if provided, otherwise use current
        specialist = appointment.specialist
        if "specialist_id" in data:
            try:
                new_specialist = Specialist.objects.get(id=data["specialist_id"])

                # Check if new specialist provides this service
                from apps.specialistsapp.models import SpecialistService

                specialist_service = SpecialistService.objects.filter(
                    specialist=new_specialist, service=appointment.service
                ).exists()

                if not specialist_service:
                    raise serializers.ValidationError(
                        _("Selected specialist does not provide this service")
                    )

                specialist = new_specialist
            except Specialist.DoesNotExist:
                raise serializers.ValidationError(_("Specialist not found"))

        # Combine date and time
        date = data["date"]
        time = data["start_time"]
        start_datetime = datetime.datetime.combine(date, time)

        # Make timezone-aware
        tz = timezone.get_default_timezone()
        start_datetime = timezone.make_aware(start_datetime, tz)

        # Calculate end time
        end_datetime = start_datetime + datetime.timedelta(minutes=appointment.duration)

        # Validate date is in the future
        if start_datetime < timezone.now():
            raise serializers.ValidationError(_("Cannot reschedule to past time"))

        # Check availability using availability service
        from apps.bookingapp.services.availability_service import AvailabilityService

        is_available = AvailabilityService.check_time_slot_available(
            appointment.service.id,
            specialist.id,
            start_datetime,
            end_datetime,
            exclude_appointment_id=appointment.id,
        )

        if not is_available:
            raise serializers.ValidationError(
                _("The selected time slot is not available")
            )

        # Add to validated data
        data["specialist"] = specialist
        data["end_datetime"] = end_datetime
        data["start_datetime"] = start_datetime

        return data


class MultiServiceBookingSerializer(serializers.ModelSerializer):
    # ──────────────────────────────────────────────────────────────────────────
    # manual fields so DRF won't look for DB columns
    transaction_id = serializers.CharField(read_only=True, allow_null=True)
    payment_status = serializers.CharField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    # ──────────────────────────────────────────────────────────────────────────

    appointments = AppointmentSerializer(many=True, read_only=True)
    shop_details = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    payment_status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True
    )

    class Meta:
        model = MultiServiceBooking
        fields = [
            "id",
            "shop_details",
            "appointments",
            "total_price",
            "transaction_id",
            "payment_status",
            "payment_status_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields  # everything is read-only


class MultiServiceBookingCreateSerializer(serializers.Serializer):
    """Serializer for creating multiple appointments in one booking"""

    services = serializers.ListField(child=BookingCreateSerializer(), min_length=1)

    def validate(self, data):
        """Validate that all services can be booked without conflicts"""
        services = data["services"]

        # Check that all services are from the same shop
        shops = set()
        for service_data in services:
            shops.add(service_data["shop"].id)

        if len(shops) > 1:
            raise serializers.ValidationError(
                _("All services must be from the same shop")
            )

        # Check for conflicts between the services
        from apps.bookingapp.services.multi_service_booker import MultiServiceBooker

        # Prepare booking requests
        booking_requests = []
        for service_data in services:
            booking_requests.append(
                {
                    "service_id": service_data["service_id"],
                    "specialist_id": service_data["specialist_id"],
                    "start_time": service_data["start_datetime"],
                    "end_time": service_data["end_datetime"],
                }
            )

        # Check conflicts
        conflicts = MultiServiceBooker.check_multi_service_conflicts(booking_requests)
        if conflicts:
            raise serializers.ValidationError(
                _("There are conflicts between the selected services: {}").format(
                    conflicts
                )
            )

        return data


class AppointmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating appointments through the more optimized endpoint"""

    class Meta:
        model = Appointment
        fields = ["service", "specialist", "shop", "start_time", "notes"]

    def validate(self, data):
        """Validate appointment data ensuring no scheduling conflicts"""
        service = data.get("service")
        specialist = data.get("specialist")
        shop = data.get("shop")
        start_time = data.get("start_time")

        if not all([service, specialist, shop, start_time]):
            raise serializers.ValidationError(_("Missing required fields"))

        # Validate that appointment is in the future
        if start_time < timezone.now():
            raise serializers.ValidationError(_("Cannot book appointments in the past"))

        # Validate specialist can provide this service
        from apps.specialistsapp.models import SpecialistService

        specialist_service = SpecialistService.objects.filter(
            specialist=specialist, service=service
        ).exists()

        if not specialist_service:
            raise serializers.ValidationError(
                _("Specialist does not provide this service")
            )

        # Validate that service belongs to the shop
        if service.shop != shop:
            raise serializers.ValidationError(
                _("Service does not belong to the selected shop")
            )

        # Validate specialist belongs to the shop
        if specialist.employee.shop != shop:
            raise serializers.ValidationError(
                _("Specialist does not belong to the selected shop")
            )

        # Calculate end time
        end_time = start_time + timezone.timedelta(minutes=service.duration)
        data["end_time"] = end_time

        return data

    def create(self, validated_data):
        """Create appointment with additional fields from service"""
        service = validated_data.get("service")

        # Set calculated fields from service
        validated_data["buffer_before"] = service.buffer_before
        validated_data["buffer_after"] = service.buffer_after
        validated_data["duration"] = service.duration
        validated_data["total_price"] = service.price

        # Create appointment
        return super().create(validated_data)


class AppointmentDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for appointments with all related details"""

    customer_details = UserSerializer(source="customer", read_only=True)
    service_details = ServiceSerializer(source="service", read_only=True)
    specialist_details = SpecialistSerializer(source="specialist", read_only=True)
    shop_details = ShopSerializer(source="shop", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True
    )

    class Meta:
        model = Appointment
        fields = [
            "id",
            "customer",
            "customer_details",
            "service",
            "service_details",
            "specialist",
            "specialist_details",
            "shop",
            "shop_details",
            "start_time",
            "end_time",
            "status",
            "status_display",
            "notes",
            "payment_status",
            "payment_status_display",
            "total_price",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "customer_details",
            "service_details",
            "specialist_details",
            "shop_details",
            "status_display",
            "payment_status_display",
            "created_at",
            "updated_at",
        ]
