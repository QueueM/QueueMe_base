# apps/bookingapp/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.bookingapp.models import (
    Appointment,
    AppointmentNote,
    AppointmentReminder,
    Booking,
    MultiServiceBooking,
)


class AppointmentReminderInline(admin.TabularInline):
    """Inline admin for appointment reminders"""

    model = AppointmentReminder
    extra = 0
    readonly_fields = ["is_sent", "sent_at"]


class AppointmentNoteInline(admin.TabularInline):
    """Inline admin for appointment notes"""

    model = AppointmentNote
    extra = 0
    readonly_fields = ["created_at"]


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    """Admin configuration for appointments"""

    list_display = [
        "id",
        "customer_name",
        "service_name",
        "specialist_name",
        "shop_name",
        "start_time",
        "status",
        "payment_status",
    ]
    list_filter = [
        "status",
        "payment_status",
        "start_time",
        "shop",
        "is_reminder_sent",
        "is_reviewed",
    ]
    search_fields = [
        "customer__phone_number",
        "service__name",
        "specialist__employee__first_name",
        "specialist__employee__last_name",
        "shop__name",
    ]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "start_time"
    inlines = [AppointmentReminderInline, AppointmentNoteInline]

    def customer_name(self, obj):
        """Get customer name/phone for display"""
        return obj.customer.phone_number

    customer_name.short_description = _("Customer")

    def service_name(self, obj):
        """Get service name for display"""
        return obj.service.name

    service_name.short_description = _("Service")

    def specialist_name(self, obj):
        """Get specialist name for display"""
        return f"{obj.specialist.employee.first_name} {obj.specialist.employee.last_name}"

    specialist_name.short_description = _("Specialist")

    def shop_name(self, obj):
        """Get shop name for display"""
        return obj.shop.name

    shop_name.short_description = _("Shop")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """Admin configuration for bookings"""

    list_display = [
        "id",
        "customer_name",
        "service",
        "booking_date",
        "booking_time",
        "price",
    ]
    list_filter = [
        "booking_date",
        "status",
        "created_at",
    ]
    search_fields = [
        "customer_name",
        "customer_phone",
        "service",
    ]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "booking_date"


@admin.register(MultiServiceBooking)
class MultiServiceBookingAdmin(admin.ModelAdmin):
    """Admin configuration for multi-service bookings"""

    list_display = [
        "id",
        "booking_customer",
        "service_name",
        "duration",
        "price",
    ]
    list_filter = ["booking__booking_date", "booking__status"]
    search_fields = [
        "booking__customer_name",
        "booking__customer_phone",
        "service_name",
    ]
    readonly_fields = ["booking"]

    def booking_customer(self, obj):
        """Get customer name from the parent booking"""
        if obj.booking:
            return obj.booking.customer_name
        return "Unassigned"

    booking_customer.short_description = _("Customer")


@admin.register(AppointmentReminder)
class AppointmentReminderAdmin(admin.ModelAdmin):
    """Admin configuration for appointment reminders"""

    list_display = [
        "id",
        "appointment_info",
        "reminder_type",
        "scheduled_time",
        "is_sent",
        "sent_at",
    ]
    list_filter = ["reminder_type", "is_sent", "scheduled_time"]
    search_fields = [
        "appointment__customer__phone_number",
        "appointment__service__name",
    ]
    readonly_fields = ["sent_at"]

    def appointment_info(self, obj):
        """Get appointment info for display"""
        return f"{obj.appointment.customer.phone_number} - {obj.appointment.start_time.strftime('%Y-%m-%d %H:%M')}"

    appointment_info.short_description = _("Appointment")
