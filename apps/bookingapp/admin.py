# apps/bookingapp/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.bookingapp.models import (
    Appointment,
    AppointmentNote,
    AppointmentReminder,
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


@admin.register(MultiServiceBooking)
class MultiServiceBookingAdmin(admin.ModelAdmin):
    """Admin configuration for multi-service bookings"""

    list_display = [
        "id",
        "customer_name",
        "shop_name",
        "appointment_count",
        "total_price",
        "payment_status",
    ]
    list_filter = ["payment_status", "created_at", "shop"]
    search_fields = ["customer__phone_number", "shop__name"]
    readonly_fields = ["created_at", "updated_at"]
    filter_horizontal = ["appointments"]

    def customer_name(self, obj):
        """Get customer name/phone for display"""
        return obj.customer.phone_number

    customer_name.short_description = _("Customer")

    def shop_name(self, obj):
        """Get shop name for display"""
        return obj.shop.name

    shop_name.short_description = _("Shop")

    def appointment_count(self, obj):
        """Get count of appointments in this booking"""
        return obj.appointments.count()

    appointment_count.short_description = _("# Appointments")


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
