from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.notificationsapp.services.notification_service import NotificationService
from apps.specialistsapp.models import Specialist

from ..constants import VERIFICATION_STATUS_APPROVED, VERIFICATION_STATUS_REJECTED
from ..models import VerificationRequest


class VerificationService:
    """
    Service for managing shop verification process.
    """

    @staticmethod
    @transaction.atomic
    def create_verification_request(shop, documents=None):
        """
        Create a new verification request for a shop.

        Args:
            shop: The shop to verify
            documents: Verification documents (optional)

        Returns:
            VerificationRequest: The created verification request
        """
        # Check if there's already a pending request
        existing = VerificationRequest.objects.filter(
            shop=shop, status="pending"
        ).first()

        if existing:
            return existing

        # Create new request
        request = VerificationRequest.objects.create(
            shop=shop, documents=documents or []
        )

        return request

    @staticmethod
    @transaction.atomic
    def approve_verification(verification_request, admin_user, notes=""):
        """
        Approve a verification request.

        Args:
            verification_request: The verification request
            admin_user: The admin approving the request
            notes: Admin notes (optional)

        Returns:
            VerificationRequest: The updated verification request
        """
        # Update verification request
        verification_request.status = VERIFICATION_STATUS_APPROVED
        verification_request.verified_by = admin_user
        verification_request.verified_at = timezone.now()
        verification_request.notes = notes
        verification_request.save()

        # Update shop verification status
        shop = verification_request.shop
        shop.is_verified = True
        shop.verification_date = timezone.now()
        shop.save()

        # Also mark all specialists in this shop as verified
        specialists = Specialist.objects.filter(employee__shop=shop)
        specialists.update(is_verified=True)

        # Send notification to shop owner/manager
        VerificationService._send_verification_notifications(verification_request, True)

        return verification_request

    @staticmethod
    @transaction.atomic
    def reject_verification(
        verification_request, admin_user, rejection_reason, notes=""
    ):
        """
        Reject a verification request.

        Args:
            verification_request: The verification request
            admin_user: The admin rejecting the request
            rejection_reason: Reason for rejection
            notes: Admin notes (optional)

        Returns:
            VerificationRequest: The updated verification request
        """
        # Update verification request
        verification_request.status = VERIFICATION_STATUS_REJECTED
        verification_request.verified_by = admin_user
        verification_request.verified_at = timezone.now()
        verification_request.rejection_reason = rejection_reason
        verification_request.notes = notes
        verification_request.save()

        # Send notification to shop owner/manager
        VerificationService._send_verification_notifications(
            verification_request, False
        )

        return verification_request

    @staticmethod
    def _send_verification_notifications(verification_request, approved):
        """
        Send notifications for verification status change.

        Args:
            verification_request: The verification request
            approved: Whether the request was approved
        """
        shop = verification_request.shop

        # Get shop manager
        manager = shop.manager
        if not manager:
            return

        # Send email if manager has email
        if manager.email:
            if approved:
                subject = _("Your shop has been verified")
                template = "queueMeAdminApp/email/verification_approved.html"
            else:
                subject = _("Your verification request has been rejected")
                template = "queueMeAdminApp/email/verification_rejected.html"

            context = {
                "shop_name": shop.name,
                "verification_date": verification_request.verified_at,
                "rejection_reason": (
                    verification_request.rejection_reason if not approved else None
                ),
            }

            html_message = render_to_string(template, context)

            send_mail(
                subject,
                "",  # Plain text version (empty)
                "noreply@queueme.net",
                [manager.email],
                html_message=html_message,
            )

        # Send in-app and SMS notification
        if approved:
            notification_type = "verification_approved"
            unused_message = _(f"Congratulations! Your shop {shop.name} has been verified.")
        else:
            notification_type = "verification_rejected"
            unused_unused_message = _(
                f"Your verification request for {shop.name} has been rejected. Reason: {verification_request.rejection_reason}"
            )

        # Send notification via NotificationService
        NotificationService.send_notification(
            user_id=manager.id,
            notification_type=notification_type,
            data={
                "shop_id": str(shop.id),
                "shop_name": shop.name,
                "status": verification_request.status,
                "rejection_reason": (
                    verification_request.rejection_reason if not approved else None
                ),
            },
            channels=[
                "push",
                "sms",
                "in_app",
            ],  # Use all channels for important notification
        )

    @staticmethod
    def get_pending_verifications():
        """
        Get all pending verification requests.

        Returns:
            QuerySet: Pending verification requests
        """
        return VerificationRequest.objects.filter(status="pending").order_by(
            "submitted_at"
        )

    @staticmethod
    def get_verification_stats():
        """
        Get verification statistics.

        Returns:
            dict: Verification statistics
        """
        total = VerificationRequest.objects.count()
        pending = VerificationRequest.objects.filter(status="pending").count()
        approved = VerificationRequest.objects.filter(status="approved").count()
        rejected = VerificationRequest.objects.filter(status="rejected").count()

        # Get average verification time for approved requests
        avg_verification_time = None
        approved_requests = VerificationRequest.objects.filter(status="approved")

        if approved_requests.exists():
            from django.db.models import Avg, ExpressionWrapper, F, fields

            time_diff = ExpressionWrapper(
                F("verified_at") - F("submitted_at"),
                output_field=fields.DurationField(),
            )

            avg_time_seconds = approved_requests.annotate(
                time_diff=time_diff
            ).aggregate(avg_time=Avg("time_diff"))["avg_time"]

            if avg_time_seconds:
                avg_verification_time = (
                    avg_time_seconds.total_seconds() / 3600
                )  # Convert to hours

        return {
            "total": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "approval_rate": (approved / total * 100) if total > 0 else 0,
            "avg_verification_time_hours": avg_verification_time,
        }
