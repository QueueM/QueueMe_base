# apps/subscriptionapp/services/usage_monitor.py
import logging

from django.utils import timezone

from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist
from apps.subscriptionapp.constants import (
    FEATURE_CATEGORY_CHOICES,
    FEATURE_CATEGORY_SERVICES,
    FEATURE_CATEGORY_SHOPS,
    FEATURE_CATEGORY_SPECIALISTS,
)
from apps.subscriptionapp.models import FeatureUsage, Subscription

logger = logging.getLogger(__name__)


class UsageMonitor:
    """Service for monitoring and enforcing feature usage limits"""

    @staticmethod
    def initialize_usage_tracking(subscription_id):
        """Initialize usage tracking for a new subscription"""
        subscription = Subscription.objects.get(id=subscription_id)

        # Create feature usage records
        FeatureUsage.objects.create(
            subscription=subscription,
            feature_category=FEATURE_CATEGORY_SHOPS,
            limit=subscription.max_shops,
            current_usage=0,
        )

        FeatureUsage.objects.create(
            subscription=subscription,
            feature_category=FEATURE_CATEGORY_SERVICES,
            limit=subscription.max_services_per_shop,
            current_usage=0,
        )

        FeatureUsage.objects.create(
            subscription=subscription,
            feature_category=FEATURE_CATEGORY_SPECIALISTS,
            limit=subscription.max_specialists_per_shop,
            current_usage=0,
        )

        # Update actual usage
        company_id = subscription.company_id
        UsageMonitor.update_all_usage(company_id)

    @staticmethod
    def update_usage_limits(subscription_id):
        """Update feature usage limits based on subscription plan"""
        subscription = Subscription.objects.get(id=subscription_id)

        # Update shop limit
        shop_usage = FeatureUsage.objects.get(
            subscription=subscription, feature_category=FEATURE_CATEGORY_SHOPS
        )
        shop_usage.limit = subscription.max_shops
        shop_usage.save()

        # Update service limit
        service_usage = FeatureUsage.objects.get(
            subscription=subscription, feature_category=FEATURE_CATEGORY_SERVICES
        )
        service_usage.limit = subscription.max_services_per_shop
        service_usage.save()

        # Update specialist limit
        specialist_usage = FeatureUsage.objects.get(
            subscription=subscription, feature_category=FEATURE_CATEGORY_SPECIALISTS
        )
        specialist_usage.limit = subscription.max_specialists_per_shop
        specialist_usage.save()

    @staticmethod
    def update_all_usage(company_id):
        """Update all usage statistics for a company"""
        # Get active subscription
        subscription = Subscription.objects.filter(
            company_id=company_id, status__in=["active", "trial"]
        ).first()

        if not subscription:
            logger.warning(f"No active subscription found for company {company_id}")
            return False

        # Update shop usage
        UsageMonitor.update_shop_usage(company_id)

        # Update service usage for each shop
        shops = Shop.objects.filter(company_id=company_id)
        for shop in shops:
            UsageMonitor.update_service_usage(company_id, shop.id)
            UsageMonitor.update_specialist_usage(company_id, shop.id)

        return True

    @staticmethod
    def update_shop_usage(company_id):
        """Update shop count for a company"""
        # Get active subscription
        subscription = Subscription.objects.filter(
            company_id=company_id, status__in=["active", "trial"]
        ).first()

        if not subscription:
            logger.warning(f"No active subscription found for company {company_id}")
            return False

        # Count shops
        shop_count = Shop.objects.filter(company_id=company_id).count()

        # Update usage
        shop_usage, created = FeatureUsage.objects.get_or_create(
            subscription=subscription,
            feature_category=FEATURE_CATEGORY_SHOPS,
            defaults={"limit": subscription.max_shops},
        )

        shop_usage.current_usage = shop_count
        shop_usage.last_updated = timezone.now()
        shop_usage.save()

        return shop_usage

    @staticmethod
    def update_service_usage(company_id, shop_id):
        """Update service count for a shop"""
        # Get active subscription
        subscription = Subscription.objects.filter(
            company_id=company_id, status__in=["active", "trial"]
        ).first()

        if not subscription:
            logger.warning(f"No active subscription found for company {company_id}")
            return False

        # Count services for this shop
        service_count = Service.objects.filter(shop_id=shop_id).count()

        # Get the usage record
        service_usage, created = FeatureUsage.objects.get_or_create(
            subscription=subscription,
            feature_category=FEATURE_CATEGORY_SERVICES,
            defaults={"limit": subscription.max_services_per_shop},
        )

        # We don't update current_usage directly since it's the max count per shop
        # Instead, we check if this shop's count exceeds the current max
        if service_count > service_usage.current_usage:
            service_usage.current_usage = service_count
            service_usage.last_updated = timezone.now()
            service_usage.save()

        return service_usage

    @staticmethod
    def update_specialist_usage(company_id, shop_id):
        """Update specialist count for a shop"""
        # Get active subscription
        subscription = Subscription.objects.filter(
            company_id=company_id, status__in=["active", "trial"]
        ).first()

        if not subscription:
            logger.warning(f"No active subscription found for company {company_id}")
            return False

        # Count specialists for this shop
        specialist_count = Specialist.objects.filter(employee__shop_id=shop_id).count()

        # Get the usage record
        specialist_usage, created = FeatureUsage.objects.get_or_create(
            subscription=subscription,
            feature_category=FEATURE_CATEGORY_SPECIALISTS,
            defaults={"limit": subscription.max_specialists_per_shop},
        )

        # We don't update current_usage directly since it's the max count per shop
        # Instead, we check if this shop's count exceeds the current max
        if specialist_count > specialist_usage.current_usage:
            specialist_usage.current_usage = specialist_count
            specialist_usage.last_updated = timezone.now()
            specialist_usage.save()

        return specialist_usage

    @staticmethod
    def check_shop_limit(company_id):
        """Check if company has reached shop limit"""
        # Get active subscription
        subscription = Subscription.objects.filter(
            company_id=company_id, status__in=["active", "trial"]
        ).first()

        if not subscription:
            logger.warning(f"No active subscription found for company {company_id}")
            return False, 0, 0

        # Get shop usage
        shop_usage = FeatureUsage.objects.filter(
            subscription=subscription, feature_category=FEATURE_CATEGORY_SHOPS
        ).first()

        if not shop_usage:
            # Create usage record if it doesn't exist
            shop_count = Shop.objects.filter(company_id=company_id).count()

            shop_usage = FeatureUsage.objects.create(
                subscription=subscription,
                feature_category=FEATURE_CATEGORY_SHOPS,
                limit=subscription.max_shops,
                current_usage=shop_count,
            )

        # Check if limit is reached
        limit_reached = shop_usage.current_usage >= shop_usage.limit

        return not limit_reached, shop_usage.current_usage, shop_usage.limit

    @staticmethod
    def check_service_limit(shop_id):
        """Check if shop has reached service limit"""
        shop = Shop.objects.get(id=shop_id)
        company_id = shop.company_id

        # Get active subscription
        subscription = Subscription.objects.filter(
            company_id=company_id, status__in=["active", "trial"]
        ).first()

        if not subscription:
            logger.warning(f"No active subscription found for company {company_id}")
            return False, 0, 0

        # Count services for this shop
        service_count = Service.objects.filter(shop_id=shop_id).count()

        # Get service usage
        service_usage = FeatureUsage.objects.filter(
            subscription=subscription, feature_category=FEATURE_CATEGORY_SERVICES
        ).first()

        if not service_usage:
            # Create usage record if it doesn't exist
            service_usage = FeatureUsage.objects.create(
                subscription=subscription,
                feature_category=FEATURE_CATEGORY_SERVICES,
                limit=subscription.max_services_per_shop,
                current_usage=service_count,
            )

        # Check if limit is reached
        limit_reached = service_count >= service_usage.limit

        return not limit_reached, service_count, service_usage.limit

    @staticmethod
    def check_specialist_limit(shop_id):
        """Check if shop has reached specialist limit"""
        shop = Shop.objects.get(id=shop_id)
        company_id = shop.company_id

        # Get active subscription
        subscription = Subscription.objects.filter(
            company_id=company_id, status__in=["active", "trial"]
        ).first()

        if not subscription:
            logger.warning(f"No active subscription found for company {company_id}")
            return False, 0, 0

        # Count specialists for this shop
        specialist_count = Specialist.objects.filter(employee__shop_id=shop_id).count()

        # Get specialist usage
        specialist_usage = FeatureUsage.objects.filter(
            subscription=subscription, feature_category=FEATURE_CATEGORY_SPECIALISTS
        ).first()

        if not specialist_usage:
            # Create usage record if it doesn't exist
            specialist_usage = FeatureUsage.objects.create(
                subscription=subscription,
                feature_category=FEATURE_CATEGORY_SPECIALISTS,
                limit=subscription.max_specialists_per_shop,
                current_usage=specialist_count,
            )

        # Check if limit is reached
        limit_reached = specialist_count >= specialist_usage.limit

        return not limit_reached, specialist_count, specialist_usage.limit

    @staticmethod
    def get_usage_summary(company_id):
        """Get a summary of feature usage for a company"""
        # Get active subscription
        subscription = Subscription.objects.filter(
            company_id=company_id, status__in=["active", "trial"]
        ).first()

        if not subscription:
            logger.warning(f"No active subscription found for company {company_id}")
            return None

        # Get usage records
        usage_records = FeatureUsage.objects.filter(subscription=subscription)

        # Format into summary
        summary = {
            "subscription_id": str(subscription.id),
            "plan_name": subscription.plan_name or subscription.plan.name,
            "status": subscription.status,
            "current_period_end": subscription.current_period_end,
            "usage": {},
        }

        for record in usage_records:
            category_name = dict(FEATURE_CATEGORY_CHOICES).get(
                record.feature_category, record.feature_category
            )

            summary["usage"][record.feature_category] = {
                "name": category_name,
                "current": record.current_usage,
                "limit": record.limit,
                "usage_percent": round(
                    (
                        (record.current_usage / record.limit * 100)
                        if record.limit > 0
                        else 0
                    ),
                    1,
                ),
                "is_limit_reached": record.is_limit_reached(),
                "last_updated": record.last_updated,
            }

        # Get shop-level usage
        shops = Shop.objects.filter(company_id=company_id)
        shop_usage = []

        for shop in shops:
            service_count = Service.objects.filter(shop_id=shop.id).count()
            specialist_count = Specialist.objects.filter(
                employee__shop_id=shop.id
            ).count()

            shop_usage.append(
                {
                    "id": str(shop.id),
                    "name": shop.name,
                    "services": {
                        "count": service_count,
                        "limit": subscription.max_services_per_shop,
                        "percent": round(
                            (
                                (
                                    service_count
                                    / subscription.max_services_per_shop
                                    * 100
                                )
                                if subscription.max_services_per_shop > 0
                                else 0
                            ),
                            1,
                        ),
                        "is_limit_reached": service_count
                        >= subscription.max_services_per_shop,
                    },
                    "specialists": {
                        "count": specialist_count,
                        "limit": subscription.max_specialists_per_shop,
                        "percent": round(
                            (
                                (
                                    specialist_count
                                    / subscription.max_specialists_per_shop
                                    * 100
                                )
                                if subscription.max_specialists_per_shop > 0
                                else 0
                            ),
                            1,
                        ),
                        "is_limit_reached": specialist_count
                        >= subscription.max_specialists_per_shop,
                    },
                }
            )

        summary["shops"] = shop_usage

        return summary
