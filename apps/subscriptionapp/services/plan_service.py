# apps/subscriptionapp/services/plan_service.py
import logging

from apps.subscriptionapp.constants import (
    FEATURE_CATEGORY_CHOICES,
    SUBSCRIPTION_PERIOD_CHOICES,
)
from apps.subscriptionapp.models import Plan, PlanFeature

logger = logging.getLogger(__name__)


class PlanService:
    """Service for managing subscription plans"""

    @staticmethod
    def create_plan(plan_data, features_data=None):
        """Create a new subscription plan with features"""
        # Create the plan
        plan = Plan.objects.create(**plan_data)

        # Add features if provided
        if features_data:
            for feature_data in features_data:
                PlanFeature.objects.create(plan=plan, **feature_data)

        return plan

    @staticmethod
    def update_plan(plan_id, plan_data, features_data=None):
        """Update a subscription plan and its features"""
        plan = Plan.objects.get(id=plan_id)

        # Update plan fields
        for key, value in plan_data.items():
            setattr(plan, key, value)

        plan.save()

        # Update features if provided
        if features_data is not None:  # Allow empty list to clear features
            # Delete existing features
            plan.features.all().delete()

            # Create new features
            for feature_data in features_data:
                PlanFeature.objects.create(plan=plan, **feature_data)

        return plan

    @staticmethod
    def get_active_plans():
        """Get all active subscription plans"""
        return Plan.objects.filter(is_active=True).order_by("position", "monthly_price")

    @staticmethod
    def get_plan_details(plan_id):
        """Get detailed information about a plan"""
        plan = Plan.objects.get(id=plan_id)

        # Get features grouped by category
        features_by_category = {}
        for category_code, category_name in FEATURE_CATEGORY_CHOICES:
            features_by_category[category_code] = {
                "name": category_name,
                "features": [],
            }

        for feature in plan.features.all():
            features_by_category[feature.category]["features"].append(
                {
                    "id": str(feature.id),
                    "name": feature.name,
                    "name_ar": feature.name_ar,
                    "description": feature.description,
                    "description_ar": feature.description_ar,
                    "tier": feature.tier,
                    "value": feature.value,
                    "is_available": feature.is_available,
                }
            )

        # Get pricing options
        pricing_options = []
        for period_code, period_name in SUBSCRIPTION_PERIOD_CHOICES:
            from apps.subscriptionapp.utils.billing_utils import calculate_period_price

            price = calculate_period_price(plan.monthly_price, period_code)

            pricing_options.append(
                {
                    "period": period_code,
                    "name": period_name,
                    "price": price,
                    "display_price": f"{price} SAR",
                }
            )

        return {
            "id": str(plan.id),
            "name": plan.name,
            "name_ar": plan.name_ar,
            "description": plan.description,
            "description_ar": plan.description_ar,
            "is_featured": plan.is_featured,
            "limits": {
                "shops": plan.max_shops,
                "services_per_shop": plan.max_services_per_shop,
                "specialists_per_shop": plan.max_specialists_per_shop,
            },
            "pricing_options": pricing_options,
            "features": features_by_category,
        }

    @staticmethod
    def compare_plans(plans):
        """Compare multiple plans side by side"""
        if not plans:
            return {}

        plan_details = []
        for plan in plans:
            plan_details.append(
                {
                    "id": str(plan.id),
                    "name": plan.name,
                    "name_ar": plan.name_ar,
                    "monthly_price": plan.monthly_price,
                    "is_featured": plan.is_featured,
                    "max_shops": plan.max_shops,
                    "max_services_per_shop": plan.max_services_per_shop,
                    "max_specialists_per_shop": plan.max_specialists_per_shop,
                }
            )

        # Get features comparison
        features_comparison = {}
        for category_code, category_name in FEATURE_CATEGORY_CHOICES:
            features_comparison[category_code] = {"name": category_name, "features": []}

        # For each plan, get its features
        feature_matrix = {}
        for plan in plans:
            plan_id = str(plan.id)
            features = plan.features.all()

            for feature in features:
                feature_key = f"{feature.category}_{feature.name}"

                if feature_key not in feature_matrix:
                    feature_matrix[feature_key] = {
                        "name": feature.name,
                        "name_ar": feature.name_ar,
                        "category": feature.category,
                        "plans": {},
                    }

                feature_matrix[feature_key]["plans"][plan_id] = {
                    "value": feature.value,
                    "is_available": feature.is_available,
                    "tier": feature.tier,
                }

        # Organize features by category
        for feature_key, feature_data in feature_matrix.items():
            category = feature_data["category"]
            if category in features_comparison:
                features_comparison[category]["features"].append(
                    {
                        "name": feature_data["name"],
                        "name_ar": feature_data["name_ar"],
                        "plans": feature_data["plans"],
                    }
                )

        return {"plans": plan_details, "features": features_comparison}

    @staticmethod
    def get_plan_recommendations(company_id):
        """Get plan recommendations for a company"""
        from apps.subscriptionapp.services.plan_recommender import PlanRecommender

        # Get recommendations
        recommendations = PlanRecommender.recommend_multiple_plans(company_id, count=3)

        result = []
        for recommendation in recommendations:
            plan = recommendation["plan"]
            analysis = recommendation["fit_analysis"]

            result.append(
                {
                    "id": str(plan.id),
                    "name": plan.name,
                    "name_ar": plan.name_ar,
                    "monthly_price": plan.monthly_price,
                    "is_featured": plan.is_featured,
                    "max_shops": plan.max_shops,
                    "max_services_per_shop": plan.max_services_per_shop,
                    "max_specialists_per_shop": plan.max_specialists_per_shop,
                    "score": recommendation["score"],
                    "analysis": analysis,
                }
            )

        return result
