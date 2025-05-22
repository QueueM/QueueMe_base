from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.authapp.models import User
from apps.bookingapp.models import Appointment
from apps.notificationsapp.services.notification_service import NotificationService
from apps.specialistsapp.models import Specialist

from ..models import Package, PackageService
from .package_availability import PackageAvailabilityService


class PackageBookingService:
    """
    Service for booking package appointments.
    Handles the complex workflow of booking multiple services as part of a package.
    """

    @staticmethod
    @transaction.atomic
    def book_package(
        customer_id, package_id, date_str, time_str, specialist_assignments=None
    ):
        """
        Book all services in a package as sequential appointments.

        Args:
            customer_id: ID of the customer making the booking
            package_id: ID of the package being booked
            date_str: Date string in YYYY-MM-DD format
            time_str: Time string in HH:MM format for the package start time
            specialist_assignments: Optional dict mapping service IDs to specialist IDs
                                  If not provided, available specialists will be assigned

        Returns:
            list: List of created appointment objects
        """
        # Validate inputs
        customer = User.objects.get(id=customer_id)
        package = Package.objects.get(id=package_id)

        # Check if package is available
        if not package.is_available:
            raise ValueError(_("This package is not currently available for booking"))

        # Parse date and time
        booking_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        start_time = datetime.strptime(time_str, "%H:%M").time()

        # Make timezone-aware
        tz = timezone.get_default_timezone()
        current_datetime = timezone.make_aware(
            datetime.combine(booking_date, start_time), tz
        )

        # If specialist assignments not provided, check availability and get assignments
        if specialist_assignments is None:
            specialist_assignments = (
                PackageAvailabilityService.check_package_service_availability(
                    package_id, date_str, time_str
                )
            )

        if not specialist_assignments:
            raise ValueError(_("Package is not available at the selected time"))

        # Get package services in sequence order
        package_services = PackageService.objects.filter(package=package).order_by(
            "sequence"
        )

        # Create appointments for each service
        appointments = []

        for ps in package_services:
            service = ps.service
            service_duration = ps.effective_duration

            # Get specialist for this service
            specialist_id = specialist_assignments.get(str(service.id))
            if not specialist_id:
                raise ValueError(
                    _("No specialist assigned for service: {0}").format(service.name)
                )

            specialist = Specialist.objects.get(id=specialist_id)

            # Calculate end time
            end_datetime = current_datetime + timedelta(minutes=service_duration)

            # Create appointment
            appointment = Appointment.objects.create(
                customer=customer,
                service=service,
                specialist=specialist,
                shop=package.shop,
                start_time=current_datetime,
                end_time=end_datetime,
                status="scheduled",
                # Add reference to package
                package_id=package.id,
                # Store special package pricing
                notes=f"Part of package: {package.name}",
                # Payment will be handled at the package level
                payment_status="pending",
            )

            # Add to list
            appointments.append(appointment)

            # Update current datetime for next service
            current_datetime = end_datetime

        # After creating all appointments, update package purchase count
        package.current_purchases += 1
        package.save(update_fields=["current_purchases"])

        # Send confirmation notifications
        PackageBookingService._send_package_booking_notifications(
            customer.id, package.id, appointments
        )

        return appointments

    @staticmethod
    def _send_package_booking_notifications(customer_id, package_id, appointments):
        """
        Send confirmation notifications for a package booking.

        Args:
            customer_id: ID of the customer who made the booking
            package_id: ID of the booked package
            appointments: List of created appointment objects
        """
        package = Package.objects.get(id=package_id)
        first_appt = appointments[0] if appointments else None

        if first_appt:
            # Send package booking confirmation
            NotificationService.send_notification(
                user_id=customer_id,
                notification_type="package_confirmation",
                data={
                    "package_name": package.name,
                    "shop_name": package.shop.name,
                    "service_count": len(appointments),
                    "start_date": first_appt.start_time.strftime("%d %b, %Y"),
                    "start_time": first_appt.start_time.strftime("%I:%M %p"),
                    "package_id": str(package.id),
                },
            )

            # Notify shop about new package booking
            from apps.employeeapp.models import Employee

            shop_manager = Employee.objects.filter(
                shop=package.shop, position="manager"
            ).first()

            if shop_manager and shop_manager.user:
                NotificationService.send_notification(
                    user_id=shop_manager.user.id,
                    notification_type="new_package_booking",
                    data={
                        "customer_name": f"{first_appt.customer.phone_number}",
                        "package_name": package.name,
                        "service_count": len(appointments),
                        "start_date": first_appt.start_time.strftime("%d %b, %Y"),
                        "start_time": first_appt.start_time.strftime("%I:%M %p"),
                    },
                )

    @staticmethod
    @transaction.atomic
    def cancel_package_booking(customer_id, package_id, reason=""):
        """
        Cancel all appointments related to a package booking.

        Args:
            customer_id: ID of the customer who made the booking
            package_id: ID of the booked package
            reason: Optional reason for cancellation

        Returns:
            int: Number of appointments cancelled
        """
        customer = User.objects.get(id=customer_id)

        # Find all related appointments
        appointments = Appointment.objects.filter(
            customer=customer,
            package_id=package_id,
            status__in=["scheduled", "confirmed"],
        )

        if not appointments.exists():
            raise ValueError(_("No active package bookings found"))

        # Cancel all appointments
        cancel_count = 0
        for appointment in appointments:
            appointment.status = "cancelled"
            appointment.cancelled_by = customer
            appointment.cancellation_reason = reason
            appointment.save(
                update_fields=["status", "cancelled_by", "cancellation_reason"]
            )
            cancel_count += 1

        # If at least one appointment was cancelled, decrement package purchase count
        if cancel_count > 0:
            package = Package.objects.get(id=package_id)
            if package.current_purchases > 0:
                package.current_purchases -= 1
                package.save(update_fields=["current_purchases"])

            # Send cancellation notification
            NotificationService.send_notification(
                user_id=customer_id,
                notification_type="package_cancellation",
                data={
                    "package_name": package.name,
                    "shop_name": package.shop.name,
                    "service_count": cancel_count,
                },
            )

        return cancel_count

    @staticmethod
    @transaction.atomic
    def reschedule_package_booking(customer_id, package_id, new_date_str, new_time_str):
        """
        Reschedule all appointments related to a package booking to a new date/time.

        Args:
            customer_id: ID of the customer who made the booking
            package_id: ID of the booked package
            new_date_str: New date string in YYYY-MM-DD format
            new_time_str: New time string in HH:MM format

        Returns:
            list: List of updated appointment objects
        """
        # Validate inputs
        customer = User.objects.get(id=customer_id)
        package = Package.objects.get(id=package_id)

        # Find all related appointments
        appointments = Appointment.objects.filter(
            customer=customer,
            package_id=package_id,
            status__in=["scheduled", "confirmed"],
        ).order_by("start_time")

        if not appointments.exists():
            raise ValueError(_("No active package bookings found"))

        # Check availability for new date/time
        specialist_assignments = (
            PackageAvailabilityService.check_package_service_availability(
                package_id, new_date_str, new_time_str
            )
        )

        if not specialist_assignments:
            raise ValueError(_("Package is not available at the selected new time"))

        # Parse new date and time
        new_date = datetime.strptime(new_date_str, "%Y-%m-%d").date()
        new_start_time = datetime.strptime(new_time_str, "%H:%M").time()

        # Make timezone-aware
        tz = timezone.get_default_timezone()
        new_datetime = timezone.make_aware(
            datetime.combine(new_date, new_start_time), tz
        )

        # Get time difference between old and new start time
        old_first_appointment = appointments.first()
        time_shift = new_datetime - old_first_appointment.start_time

        # Update all appointments
        updated_appointments = []

        for appointment in appointments:
            service_id = str(appointment.service.id)
            specialist_id = specialist_assignments.get(service_id)

            if not specialist_id:
                raise ValueError(_("Could not find specialist for one of the services"))

            # Calculate new times
            new_start = appointment.start_time + time_shift
            new_end = appointment.end_time + time_shift

            # Update appointment
            appointment.start_time = new_start
            appointment.end_time = new_end
            appointment.specialist_id = specialist_id
            appointment.save(update_fields=["start_time", "end_time", "specialist_id"])

            updated_appointments.append(appointment)

        # Send rescheduling notification
        if updated_appointments:
            NotificationService.send_notification(
                user_id=customer_id,
                notification_type="package_reschedule",
                data={
                    "package_name": package.name,
                    "shop_name": package.shop.name,
                    "service_count": len(updated_appointments),
                    "new_date": new_date_str,
                    "new_time": new_time_str,
                },
            )

        return updated_appointments

    @staticmethod
    def get_package_bookings(customer_id, package_id=None, status=None):
        """
        Get package bookings for a customer.

        Args:
            customer_id: ID of the customer
            package_id: Optional package ID to filter by
            status: Optional booking status to filter by

        Returns:
            dict: Dictionary grouping appointments by package booking
        """
        # Get base queryset
        query = Appointment.objects.filter(
            customer_id=customer_id, package_id__isnull=False
        ).select_related("service", "specialist", "shop")

        # Apply filters
        if package_id:
            query = query.filter(package_id=package_id)

        if status:
            query = query.filter(status=status)

        # Group by package_id
        package_bookings = {}

        for appointment in query:
            package_id = str(appointment.package_id)

            if package_id not in package_bookings:
                try:
                    package = Package.objects.get(id=package_id)
                    package_name = package.name
                except Package.DoesNotExist:
                    package_name = "Unknown Package"

                package_bookings[package_id] = {
                    "package_id": package_id,
                    "package_name": package_name,
                    "shop_name": appointment.shop.name,
                    "first_appointment_time": appointment.start_time,
                    "appointments": [],
                }

            package_bookings[package_id]["appointments"].append(appointment)

        # Sort appointments within each package
        for pkg_id in package_bookings:
            package_bookings[pkg_id]["appointments"].sort(key=lambda x: x.start_time)

            # Update first appointment time
            if package_bookings[pkg_id]["appointments"]:
                package_bookings[pkg_id]["first_appointment_time"] = package_bookings[
                    pkg_id
                ]["appointments"][0].start_time

        return package_bookings
