from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authapp.models import User
from apps.bookingapp.models import Appointment
from apps.queueapp.models import QueueTicket
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist
from apps.subscriptionapp.models import Subscription

from .constants import (
    AUDIT_ACTION_REJECT,
    AUDIT_ACTION_UPDATE,
    AUDIT_ACTION_VERIFY,
)
from .filters import (
    AdminNotificationFilter,
    AuditLogFilter,
    MaintenanceScheduleFilter,
    SupportTicketFilter,
    VerificationRequestFilter,
)
from .models import (
    AdminNotification,
    AuditLog,
    MaintenanceSchedule,
    PlatformStatus,
    SupportMessage,
    SupportTicket,
    SystemSetting,
    VerificationRequest,
)
from .permissions import (
    CanManageSupportTickets,
    CanManageSystemSettings,
    CanManageVerifications,
    CanViewAuditLogs,
    CanViewSystemMetrics,
    IsQueueMeAdmin,
)
from .serializers import (
    AdminNotificationReadSerializer,
    AdminNotificationSerializer,
    AuditLogSerializer,
    MaintenanceScheduleSerializer,
    PlatformStatusSerializer,
    SupportMessageSerializer,
    SupportTicketSerializer,
    SystemOverviewSerializer,
    SystemSettingSerializer,
    VerificationActionSerializer,
    VerificationRequestSerializer,
)
from .services.admin_service import AdminService
from .services.analytics_service import AnalyticsService
from .services.monitoring_service import MonitoringService
from .services.support_service import SupportService
from .services.verification_service import VerificationService


class SystemSettingViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing system settings.
    """

    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer
    permission_classes = [IsQueueMeAdmin & CanManageSystemSettings]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["category", "is_public"]

    def perform_create(self, serializer):
        setting = serializer.save()

        # Log the action
        AdminService.log_audit(
            self.request.user,
            AUDIT_ACTION_UPDATE,
            "SystemSetting",
            str(setting.id),
            {"key": setting.key, "action": "create"},
        )

    def perform_update(self, serializer):
        original = self.get_object()
        setting = serializer.save()

        # Log the action
        AdminService.log_audit(
            self.request.user,
            AUDIT_ACTION_UPDATE,
            "SystemSetting",
            str(setting.id),
            {
                "key": setting.key,
                "action": "update",
                "old_value": original.value,
                "new_value": setting.value,
            },
        )

    @action(detail=False, methods=["get"])
    def public(self, request):
        """Get only public settings (available to all users)"""
        public_settings = SystemSetting.objects.filter(is_public=True)
        serializer = self.get_serializer(public_settings, many=True)
        return Response(serializer.data)


class AdminNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for admin notifications.
    """

    queryset = AdminNotification.objects.all()
    serializer_class = AdminNotificationSerializer
    permission_classes = [IsQueueMeAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_class = AdminNotificationFilter

    @action(detail=True, methods=["patch"])
    def mark_read(self, request, pk=None):
        """Mark a notification as read"""
        notification = self.get_object()
        serializer = AdminNotificationReadSerializer(
            notification, data={"is_read": True}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        count = AdminNotification.objects.filter(is_read=False).update(is_read=True)
        return Response({"status": "success", "count": count})

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        """Get count of unread notifications"""
        count = AdminNotification.objects.filter(is_read=False).count()
        return Response({"unread_count": count})


class VerificationRequestViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing shop verification requests.
    """

    queryset = VerificationRequest.objects.all()
    serializer_class = VerificationRequestSerializer
    permission_classes = [IsQueueMeAdmin & CanManageVerifications]
    filter_backends = [DjangoFilterBackend]
    filterset_class = VerificationRequestFilter

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        """Approve or reject a verification request"""
        verification_request = self.get_object()
        serializer = VerificationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data["action"]
        notes = serializer.validated_data.get("notes", "")
        rejection_reason = serializer.validated_data.get("rejection_reason", "")

        if action == "approve":
            result = VerificationService.approve_verification(
                verification_request, request.user, notes
            )

            # Log the action
            AdminService.log_audit(
                request.user,
                AUDIT_ACTION_VERIFY,
                "Shop",
                str(verification_request.shop.id),
                {"verification_id": str(verification_request.id), "notes": notes},
            )

            return Response(
                {
                    "status": "success",
                    "message": _("Verification request approved successfully."),
                    "data": self.get_serializer(result).data,
                }
            )

        elif action == "reject":
            result = VerificationService.reject_verification(
                verification_request, request.user, rejection_reason, notes
            )

            # Log the action
            AdminService.log_audit(
                request.user,
                AUDIT_ACTION_REJECT,
                "Shop",
                str(verification_request.shop.id),
                {
                    "verification_id": str(verification_request.id),
                    "rejection_reason": rejection_reason,
                    "notes": notes,
                },
            )

            return Response(
                {
                    "status": "success",
                    "message": _("Verification request rejected."),
                    "data": self.get_serializer(result).data,
                }
            )

    @action(detail=False, methods=["get"])
    def pending(self, request):
        """Get all pending verification requests"""
        pending = VerificationRequest.objects.filter(status="pending")
        page = self.paginate_queryset(pending)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)


class SupportTicketViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing support tickets.
    """

    queryset = SupportTicket.objects.all()
    serializer_class = SupportTicketSerializer
    permission_classes = [IsQueueMeAdmin & CanManageSupportTickets]
    filter_backends = [DjangoFilterBackend]
    filterset_class = SupportTicketFilter

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        """Assign a ticket to a specific admin"""
        ticket = self.get_object()
        admin_id = request.data.get("admin_id")

        try:
            admin = User.objects.get(id=admin_id)
            result = SupportService.assign_ticket(ticket, admin, request.user)

            return Response(
                {
                    "status": "success",
                    "message": _("Ticket assigned successfully."),
                    "data": self.get_serializer(result).data,
                }
            )
        except User.DoesNotExist:
            return Response(
                {"status": "error", "message": _("Admin user not found.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"])
    def change_status(self, request, pk=None):
        """Change the status of a ticket"""
        ticket = self.get_object()
        new_status = request.data.get("status")

        if new_status not in dict(TICKET_STATUS_CHOICES).keys():
            return Response(
                {"status": "error", "message": _("Invalid status.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = SupportService.update_ticket_status(ticket, new_status, request.user)

        return Response(
            {
                "status": "success",
                "message": _("Ticket status updated successfully."),
                "data": self.get_serializer(result).data,
            }
        )

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get support ticket statistics"""
        stats = SupportService.get_ticket_stats()
        return Response(stats)

    @action(detail=False, methods=["get"])
    def my_assigned(self, request):
        """Get tickets assigned to the current admin"""
        my_tickets = SupportTicket.objects.filter(assigned_to=request.user)
        page = self.paginate_queryset(my_tickets)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(my_tickets, many=True)
        return Response(serializer.data)


class SupportMessageViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing support ticket messages.
    """

    queryset = SupportMessage.objects.all()
    serializer_class = SupportMessageSerializer
    permission_classes = [IsQueueMeAdmin & CanManageSupportTickets]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by ticket if provided
        ticket_id = self.request.query_params.get("ticket", None)
        if ticket_id:
            queryset = queryset.filter(ticket_id=ticket_id)

        return queryset

    def perform_create(self, serializer):
        # Mark as from admin and set sender to current user if not specified
        serializer.save(
            is_from_admin=True,
            sender_id=serializer.validated_data.get("sender_id", self.request.user.id),
        )

        # Update ticket when new message is added
        ticket_id = serializer.validated_data.get("ticket").id
        SupportService.update_ticket_on_new_message(ticket_id, self.request.user)


class PlatformStatusViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing platform component status.
    """

    queryset = PlatformStatus.objects.all()
    serializer_class = PlatformStatusSerializer
    permission_classes = [IsQueueMeAdmin & CanViewSystemMetrics]

    @action(detail=False, methods=["get"])
    def overall(self, request):
        """Get overall platform status summary"""
        overall_status = MonitoringService.get_overall_status()
        return Response(overall_status)

    @action(detail=False, methods=["post"])
    def refresh(self, request):
        """Trigger a refresh of component status checks"""
        MonitoringService.refresh_status()
        return Response(
            {"status": "success", "message": _("Status refresh initiated.")}
        )


class MaintenanceScheduleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing maintenance schedules.
    """

    queryset = MaintenanceSchedule.objects.all()
    serializer_class = MaintenanceScheduleSerializer
    permission_classes = [IsQueueMeAdmin & CanManageSystemSettings]
    filter_backends = [DjangoFilterBackend]
    filterset_class = MaintenanceScheduleFilter

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a scheduled maintenance"""
        maintenance = self.get_object()
        result = MonitoringService.cancel_maintenance(maintenance, request.user)

        return Response(
            {
                "status": "success",
                "message": _("Maintenance cancelled."),
                "data": self.get_serializer(result).data,
            }
        )

    @action(detail=False, methods=["get"])
    def upcoming(self, request):
        """Get all upcoming maintenance events"""
        now = timezone.now()
        upcoming = MaintenanceSchedule.objects.filter(
            Q(status="scheduled") | Q(status="in_progress"), start_time__gte=now
        ).order_by("start_time")

        serializer = self.get_serializer(upcoming, many=True)
        return Response(serializer.data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing audit logs.
    """

    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsQueueMeAdmin & CanViewAuditLogs]
    filter_backends = [DjangoFilterBackend]
    filterset_class = AuditLogFilter

    @action(detail=False, methods=["get"])
    def actions(self, request):
        """Get distinct actions for filtering"""
        actions = AuditLog.objects.values_list("action", flat=True).distinct()
        return Response(list(actions))

    @action(detail=False, methods=["get"])
    def entity_types(self, request):
        """Get distinct entity types for filtering"""
        entity_types = AuditLog.objects.values_list("entity_type", flat=True).distinct()
        return Response(list(entity_types))


class SystemOverviewView(APIView):
    """
    API endpoint for getting a system-wide overview.
    """

    permission_classes = [IsQueueMeAdmin]

    def get(self, request):
        """Get system overview statistics"""
        # Get counts of various entities
        total_shops = Shop.objects.count()
        total_users = User.objects.count()
        total_specialists = Specialist.objects.count()
        total_services = Service.objects.count()
        pending_verifications = VerificationRequest.objects.filter(
            status="pending"
        ).count()
        open_support_tickets = SupportTicket.objects.filter(status="open").count()

        # Get system health overview
        system_health = MonitoringService.get_overall_status()

        # Get today's activity
        today = timezone.now().date()
        today_start = timezone.datetime.combine(today, timezone.datetime.min.time())
        today_end = timezone.datetime.combine(today, timezone.datetime.max.time())

        today_bookings = Appointment.objects.filter(
            created_at__range=(today_start, today_end)
        ).count()
        today_queue_tickets = QueueTicket.objects.filter(
            join_time__range=(today_start, today_end)
        ).count()

        # Get subscription info
        active_subscriptions = Subscription.objects.filter(status="active").count()

        # Combine all data
        data = {
            "total_shops": total_shops,
            "total_users": total_users,
            "total_specialists": total_specialists,
            "total_services": total_services,
            "pending_verifications": pending_verifications,
            "open_support_tickets": open_support_tickets,
            "system_health": system_health,
            "today_bookings": today_bookings,
            "today_queue_tickets": today_queue_tickets,
            "active_subscriptions": active_subscriptions,
        }

        serializer = SystemOverviewSerializer(data)
        return Response(serializer.data)


class DashboardStatsView(APIView):
    """
    API endpoint for getting dashboard statistics.
    """

    permission_classes = [IsQueueMeAdmin]

    def get(self, request):
        """Get dashboard statistics with time-based data"""
        # Get time range parameters (default to last 30 days)
        days = int(request.query_params.get("days", 30))

        # Use analytics service to get time-series data
        stats = AnalyticsService.get_dashboard_stats(days)
        return Response(stats)


class SystemHealthView(APIView):
    """
    API endpoint for checking system health (accessible without authentication).
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        """Simple health check endpoint"""
        health = MonitoringService.get_basic_health_check()
        return Response(health)
