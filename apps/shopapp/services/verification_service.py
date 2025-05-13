from django.db import transaction
from django.utils import timezone

from apps.authapp.models import User
from apps.notificationsapp.services.notification_service import NotificationService
from apps.shopapp.models import Shop, ShopVerification
from apps.specialistsapp.models import Specialist


class VerificationService:
    @staticmethod
    @transaction.atomic
    def request_verification(shop_id, documents=None):
        """Request verification for a shop"""
        shop = Shop.objects.get(id=shop_id)

        # Check if there's an active verification request
        existing_request = ShopVerification.objects.filter(shop=shop, status="pending").first()

        if existing_request:
            return existing_request

        # Create verification request
        verification = ShopVerification.objects.create(
            shop=shop, status="pending", documents=documents or []
        )

        # Notify Queue Me admins
        admin_users = User.objects.filter(user_type="admin")
        for admin in admin_users:
            NotificationService.send_notification(
                user_id=admin.id,
                notification_type="verification_requested",
                data={
                    "shop_name": shop.name,
                    "shop_id": str(shop.id),
                    "company_name": shop.company.name,
                    "verification_id": str(verification.id),
                },
            )

        return verification

    @staticmethod
    @transaction.atomic
    def approve_verification(verification_id, processed_by_id):
        """Approve shop verification"""
        verification = ShopVerification.objects.get(id=verification_id)
        processed_by = User.objects.get(id=processed_by_id)

        # Update verification record
        verification.status = "approved"
        verification.processed_by = processed_by
        verification.processed_at = timezone.now()
        verification.save()

        # Update shop
        shop = verification.shop
        shop.is_verified = True
        shop.verification_date = timezone.now()
        shop.save()

        # Also verify all specialists in this shop
        specialists = Specialist.objects.filter(employee__shop=shop)
        specialists.update(is_verified=True)

        # Notify shop manager
        if shop.manager:
            NotificationService.send_notification(
                user_id=shop.manager.id,
                notification_type="verification_approved",
                data={
                    "shop_name": shop.name,
                    "verification_date": shop.verification_date.strftime("%d %b, %Y"),
                },
            )

        # Notify company owner
        company_owner = shop.company.owner
        if company_owner:
            NotificationService.send_notification(
                user_id=company_owner.id,
                notification_type="verification_approved",
                data={
                    "shop_name": shop.name,
                    "company_name": shop.company.name,
                    "verification_date": shop.verification_date.strftime("%d %b, %Y"),
                },
            )

        return verification

    @staticmethod
    @transaction.atomic
    def reject_verification(verification_id, processed_by_id, reason):
        """Reject shop verification"""
        verification = ShopVerification.objects.get(id=verification_id)
        processed_by = User.objects.get(id=processed_by_id)

        # Update verification record
        verification.status = "rejected"
        verification.processed_by = processed_by
        verification.processed_at = timezone.now()
        verification.rejection_reason = reason
        verification.save()

        # Notify shop manager
        shop = verification.shop
        if shop.manager:
            NotificationService.send_notification(
                user_id=shop.manager.id,
                notification_type="verification_rejected",
                data={"shop_name": shop.name, "rejection_reason": reason},
            )

        # Notify company owner
        company_owner = shop.company.owner
        if company_owner:
            NotificationService.send_notification(
                user_id=company_owner.id,
                notification_type="verification_rejected",
                data={
                    "shop_name": shop.name,
                    "company_name": shop.company.name,
                    "rejection_reason": reason,
                },
            )

        return verification

    @staticmethod
    def get_verification_requirements():
        """Get verification requirements for shops"""
        requirements = [
            {
                "type": "business_license",
                "name": "Business License",
                "description": "Valid business license issued by the appropriate government authority",
                "required": True,
            },
            {
                "type": "national_id",
                "name": "National ID",
                "description": "Valid national ID of the shop owner or manager",
                "required": True,
            },
            {
                "type": "commercial_register",
                "name": "Commercial Register",
                "description": "Commercial registration certificate",
                "required": True,
            },
            {
                "type": "tax_certificate",
                "name": "Tax Certificate",
                "description": "VAT registration certificate",
                "required": False,
            },
            {
                "type": "shop_photos",
                "name": "Shop Photos",
                "description": "Photos of the shop interior and exterior",
                "required": True,
            },
            {
                "type": "specialist_certifications",
                "name": "Specialist Certifications",
                "description": "Professional certifications for specialists (if applicable)",
                "required": False,
            },
        ]

        return requirements

    @staticmethod
    def get_pending_verifications_count():
        """Get count of pending verifications"""
        return ShopVerification.objects.filter(status="pending").count()
