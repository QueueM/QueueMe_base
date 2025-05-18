# apps/subscriptionapp/services/plan_recommender.py
import logging

from django.utils.translation import gettext_lazy as _

from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist
from apps.subscriptionapp.models import Plan

logger = logging.getLogger(__name__)


class PlanRecommender:
    """Intelligent service for recommending subscription plans based on company needs"""

    # Weights for different factors
    WEIGHTS = {"shops": 0.35, "services": 0.25, "specialists": 0.25, "pricing": 0.15}

    @staticmethod
    def recommend_plan(company_id):
        """Recommend the optimal plan for a company based on their needs"""
        # Get company usage data
        usage_data = PlanRecommender._get_company_usage(company_id)

        # Get all active plans
        plans = Plan.objects.filter(is_active=True).order_by("monthly_price")

        if not plans:
            logger.warning("No active plans found for recommendation")
            return None

        # Calculate scores for each plan
        scored_plans = []
        for plan in plans:
            score = PlanRecommender._calculate_plan_score(plan, usage_data)

            scored_plans.append(
                {
                    "plan": plan,
                    "score": score,
                    "fit_analysis": PlanRecommender._analyze_plan_fit(plan, usage_data),
                }
            )

        # Sort by score (descending)
        scored_plans.sort(key=lambda x: x["score"], reverse=True)

        # Return the top recommendation
        return scored_plans[0] if scored_plans else None

    @staticmethod
    def recommend_multiple_plans(company_id, count=3):
        """Recommend multiple plans for a company"""
        # Get company usage data
        usage_data = PlanRecommender._get_company_usage(company_id)

        # Get all active plans
        plans = Plan.objects.filter(is_active=True).order_by("monthly_price")

        if not plans:
            logger.warning("No active plans found for recommendation")
            return []

        # Calculate scores for each plan
        scored_plans = []
        for plan in plans:
            score = PlanRecommender._calculate_plan_score(plan, usage_data)

            scored_plans.append(
                {
                    "plan": plan,
                    "score": score,
                    "fit_analysis": PlanRecommender._analyze_plan_fit(plan, usage_data),
                }
            )

        # Sort by score (descending)
        scored_plans.sort(key=lambda x: x["score"], reverse=True)

        # Return the top recommendations
        return scored_plans[:count]

    @staticmethod
    def _get_company_usage(company_id):
        """Get current usage data for a company"""
        # Count shops
        shop_count = Shop.objects.filter(company_id=company_id).count()

        # Count services per shop
        shops = Shop.objects.filter(company_id=company_id)
        services_per_shop = {}
        total_services = 0

        for shop in shops:
            service_count = Service.objects.filter(shop=shop).count()
            services_per_shop[str(shop.id)] = service_count
            total_services += service_count

        avg_services_per_shop = total_services / shop_count if shop_count > 0 else 0
        max_services_per_shop = max(services_per_shop.values()) if services_per_shop else 0

        # Count specialists per shop
        specialists_per_shop = {}
        total_specialists = 0

        for shop in shops:
            specialist_count = Specialist.objects.filter(employee__shop=shop).count()
            specialists_per_shop[str(shop.id)] = specialist_count
            total_specialists += specialist_count

        avg_specialists_per_shop = total_specialists / shop_count if shop_count > 0 else 0
        max_specialists_per_shop = max(specialists_per_shop.values()) if specialists_per_shop else 0

        # Estimate growth (basic - could be more sophisticated in a real implementation)
        growth_factor = 1.2  # Assume 20% growth

        return {
            "shop_count": shop_count,
            "avg_services_per_shop": avg_services_per_shop,
            "max_services_per_shop": max_services_per_shop,
            "avg_specialists_per_shop": avg_specialists_per_shop,
            "max_specialists_per_shop": max_specialists_per_shop,
            "projected_shop_count": int(shop_count * growth_factor),
            "projected_max_services": int(max_services_per_shop * growth_factor),
            "projected_max_specialists": int(max_specialists_per_shop * growth_factor),
            "services_per_shop": services_per_shop,
            "specialists_per_shop": specialists_per_shop,
        }

    @staticmethod
    def _calculate_plan_score(plan, usage_data):
        """Calculate a score for how well a plan fits the company's needs"""
        # Shop score: penalize if plan doesn't support enough shops
        if plan.max_shops < usage_data["shop_count"]:
            shop_score = 0  # Plan doesn't support current needs
        elif plan.max_shops < usage_data["projected_shop_count"]:
            shop_score = 0.5  # Plan supports current but not projected growth
        else:
            # Plan has enough capacity
            # Optimize for not over-provisioning too much
            over_provision_factor = plan.max_shops / max(usage_data["projected_shop_count"], 1)
            if over_provision_factor > 3:
                shop_score = 0.7  # Too much wasted capacity
            else:
                shop_score = 1.0

        # Service score
        if plan.max_services_per_shop < usage_data["max_services_per_shop"]:
            service_score = 0  # Plan doesn't support current needs
        elif plan.max_services_per_shop < usage_data["projected_max_services"]:
            service_score = 0.5  # Plan supports current but not projected growth
        else:
            # Calculate optimal fit
            over_provision_factor = plan.max_services_per_shop / max(
                usage_data["projected_max_services"], 1
            )
            if over_provision_factor > 3:
                service_score = 0.7  # Too much wasted capacity
            else:
                service_score = 1.0

        # Specialist score
        if plan.max_specialists_per_shop < usage_data["max_specialists_per_shop"]:
            specialist_score = 0  # Plan doesn't support current needs
        elif plan.max_specialists_per_shop < usage_data["projected_max_specialists"]:
            specialist_score = 0.5  # Plan supports current but not projected growth
        else:
            # Calculate optimal fit
            over_provision_factor = plan.max_specialists_per_shop / max(
                usage_data["projected_max_specialists"], 1
            )
            if over_provision_factor > 3:
                specialist_score = 0.7  # Too much wasted capacity
            else:
                specialist_score = 1.0

        # Pricing score (lower is better)
        # Get min and max prices from active plans for normalization
        min_price = (
            Plan.objects.filter(is_active=True).order_by("monthly_price").first().monthly_price
        )
        max_price = (
            Plan.objects.filter(is_active=True).order_by("-monthly_price").first().monthly_price
        )

        # Normalize price between 0 and 1, then invert so lower price = higher score
        if max_price == min_price:
            price_score = 1.0  # Only one price point
        else:
            price_normalized = (plan.monthly_price - min_price) / (max_price - min_price)
            price_score = 1.0 - price_normalized

        # Combined weighted score
        final_score = (
            shop_score * PlanRecommender.WEIGHTS["shops"]
            + service_score * PlanRecommender.WEIGHTS["services"]
            + specialist_score * PlanRecommender.WEIGHTS["specialists"]
            + price_score * PlanRecommender.WEIGHTS["pricing"]
        )

        return final_score

    @staticmethod
    def _analyze_plan_fit(plan, usage_data):
        """Provide detailed analysis of why a plan fits or doesn't fit"""
        analysis = {
            "shops": {
                "current": usage_data["shop_count"],
                "projected": usage_data["projected_shop_count"],
                "plan_limit": plan.max_shops,
                "sufficient": plan.max_shops >= usage_data["shop_count"],
                "future_proof": plan.max_shops >= usage_data["projected_shop_count"],
            },
            "services": {
                "current_max": usage_data["max_services_per_shop"],
                "projected_max": usage_data["projected_max_services"],
                "plan_limit": plan.max_services_per_shop,
                "sufficient": plan.max_services_per_shop >= usage_data["max_services_per_shop"],
                "future_proof": plan.max_services_per_shop >= usage_data["projected_max_services"],
            },
            "specialists": {
                "current_max": usage_data["max_specialists_per_shop"],
                "projected_max": usage_data["projected_max_specialists"],
                "plan_limit": plan.max_specialists_per_shop,
                "sufficient": plan.max_specialists_per_shop
                >= usage_data["max_specialists_per_shop"],
                "future_proof": plan.max_specialists_per_shop
                >= usage_data["projected_max_specialists"],
            },
        }

        # Generate strengths and weaknesses
        strengths = []
        weaknesses = []

        # Shops analysis
        if analysis["shops"]["sufficient"] and analysis["shops"]["future_proof"]:
            strengths.append(_("Fully supports your current and projected shop count"))
        elif analysis["shops"]["sufficient"]:
            weaknesses.append(
                _("Supports your current shops but may not accommodate future growth")
            )
        else:
            weaknesses.append(_("Insufficient shops limit for your current needs"))

        # Services analysis
        if analysis["services"]["sufficient"] and analysis["services"]["future_proof"]:
            strengths.append(_("Fully supports your service offerings across all shops"))
        elif analysis["services"]["sufficient"]:
            weaknesses.append(_("Supports your current services but may limit future expansion"))
        else:
            weaknesses.append(_("Insufficient services limit for your needs"))

        # Specialists analysis
        if analysis["specialists"]["sufficient"] and analysis["specialists"]["future_proof"]:
            strengths.append(_("Fully supports your specialist team size"))
        elif analysis["specialists"]["sufficient"]:
            weaknesses.append(_("Supports your current specialists but may limit future hiring"))
        else:
            weaknesses.append(_("Insufficient specialists limit for your needs"))

        # Value analysis
        if plan.is_featured:
            strengths.append(_("Popular plan with optimal price-to-feature ratio"))

        analysis["summary"] = {"strengths": strengths, "weaknesses": weaknesses}

        return analysis
