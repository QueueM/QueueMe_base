# apps/companiesapp/services/subscription_service.py
from django.db import transaction


class SubscriptionLinkService:
    @staticmethod
    @transaction.atomic
    def link_company_to_subscription(
        company, subscription_plan, payment_method=None, auto_renew=True
    ):
        """
        Link a company to a subscription plan

        This is a helper service that bridges companiesapp and subscriptionapp
        """
        try:
            # Import here to avoid circular imports
            from apps.subscriptionapp.models import Plan
            from apps.subscriptionapp.services.subscription_service import SubscriptionService

            # Get the plan
            if isinstance(subscription_plan, str):
                plan = Plan.objects.get(id=subscription_plan)
            else:
                plan = subscription_plan

            # Create subscription
            subscription = SubscriptionService.create_subscription(
                company=company,
                plan=plan,
                payment_method=payment_method,
                auto_renew=auto_renew,
            )

            # Update company's cached subscription status
            company.subscription_status = subscription.status
            company.subscription_end_date = subscription.end_date
            company.save(update_fields=["subscription_status", "subscription_end_date"])

            return subscription

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error linking company to subscription: {str(e)}")
            raise

    @staticmethod
    def get_recommended_plan(company):
        """
        Analyze company needs and recommend the best subscription plan
        """
        try:
            from apps.subscriptionapp.models import Plan

            # Get available plans
            plans = Plan.objects.filter(is_active=True)

            if not plans.exists():
                return None

            # Count existing shops and employees
            from apps.employeeapp.models import Employee
            from apps.shopapp.models import Shop

            shops = Shop.objects.filter(company=company)
            shop_count = shops.count()

            if shop_count == 0:
                # No shops yet, recommend smallest plan
                return plans.order_by("price").first()

            # Get shop IDs
            shop_ids = shops.values_list("id", flat=True)

            # Count employees/specialists
            employee_count = Employee.objects.filter(shop_id__in=shop_ids).count()
            specialist_count = Employee.objects.filter(
                shop_id__in=shop_ids, specialist__isnull=False
            ).count()

            # Calculate average specialists per shop
            avg_specialists = specialist_count / shop_count if shop_count > 0 else 0

            # Score each plan based on company needs
            scored_plans = []

            for plan in plans:
                score = 0

                # Shop count factor
                if plan.max_shops >= shop_count:
                    # Plan can accommodate current shops
                    shop_factor = 1 - (shop_count / plan.max_shops) if plan.max_shops > 0 else 0
                    # Higher score for closer match (not too much excess capacity)
                    score += shop_factor * 40  # 40% weight for shop match
                else:
                    # Plan can't accommodate current shops
                    continue  # Skip this plan

                # Specialist factor
                if plan.max_specialists_per_shop >= avg_specialists:
                    # Plan can accommodate specialists
                    specialist_factor = (
                        1 - (avg_specialists / plan.max_specialists_per_shop)
                        if plan.max_specialists_per_shop > 0
                        else 0
                    )
                    score += specialist_factor * 30  # 30% weight for specialist match
                else:
                    # Plan can't accommodate specialists
                    continue  # Skip this plan

                # Feature factor - give more score for more features
                feature_count = len(plan.features) if plan.features else 0
                max_features = max([len(p.features) if p.features else 0 for p in plans])
                feature_factor = feature_count / max_features if max_features > 0 else 0
                score += feature_factor * 20  # 20% weight for features

                # Price factor - give more score for lower price (value)
                min_price = min([p.price for p in plans])
                max_price = max([p.price for p in plans])
                price_range = max_price - min_price
                price_factor = (max_price - plan.price) / price_range if price_range > 0 else 0
                score += price_factor * 10  # 10% weight for price value

                scored_plans.append((plan, score))

            # Sort by score (descending)
            scored_plans.sort(key=lambda x: x[1], reverse=True)

            # Return the highest scoring plan
            return scored_plans[0][0] if scored_plans else plans.order_by("price").first()

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error finding recommended plan: {str(e)}")

            # Fallback to the cheapest plan
            from apps.subscriptionapp.models import Plan

            return Plan.objects.filter(is_active=True).order_by("price").first()

    @staticmethod
    def check_subscription_usage(company):
        """
        Check if company is within subscription limits
        """
        try:
            # Get active subscription
            from apps.subscriptionapp.models import Subscription

            subscription = (
                Subscription.objects.filter(company=company, status="active")
                .select_related("plan")
                .first()
            )

            if not subscription:
                return {
                    "status": "no_subscription",
                    "within_limits": False,
                    "message": "No active subscription found",
                }

            plan = subscription.plan

            # Check shop limits
            from apps.shopapp.models import Shop

            shop_count = Shop.objects.filter(company=company).count()

            if plan.max_shops > 0 and shop_count > plan.max_shops:
                return {
                    "status": "exceeded",
                    "within_limits": False,
                    "type": "shops",
                    "current": shop_count,
                    "limit": plan.max_shops,
                    "message": f"Exceeded maximum shops: {shop_count}/{plan.max_shops}",
                }

            # Check specialist limits
            if plan.max_specialists_per_shop > 0:
                from apps.employeeapp.models import Employee

                # Get all shops
                shops = Shop.objects.filter(company=company)

                for shop in shops:
                    specialist_count = Employee.objects.filter(
                        shop=shop, specialist__isnull=False
                    ).count()

                    if specialist_count > plan.max_specialists_per_shop:
                        return {
                            "status": "exceeded",
                            "within_limits": False,
                            "type": "specialists",
                            "shop": shop.name,
                            "current": specialist_count,
                            "limit": plan.max_specialists_per_shop,
                            "message": f"Shop {shop.name} exceeds specialist limit: {specialist_count}/{plan.max_specialists_per_shop}",
                        }

            # Check service limits
            if plan.max_services_per_shop > 0:
                from apps.serviceapp.models import Service

                shops = Shop.objects.filter(company=company)

                for shop in shops:
                    service_count = Service.objects.filter(shop=shop).count()

                    if service_count > plan.max_services_per_shop:
                        return {
                            "status": "exceeded",
                            "within_limits": False,
                            "type": "services",
                            "shop": shop.name,
                            "current": service_count,
                            "limit": plan.max_services_per_shop,
                            "message": f"Shop {shop.name} exceeds service limit: {service_count}/{plan.max_services_per_shop}",
                        }

            # All checks passed
            return {
                "status": "active",
                "within_limits": True,
                "message": "Company is within subscription limits",
            }

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error checking subscription usage: {str(e)}")

            return {
                "status": "error",
                "within_limits": False,
                "message": f"Error checking subscription: {str(e)}",
            }
