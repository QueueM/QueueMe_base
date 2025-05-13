# apps/subscriptionapp/services/feature_service.py

from apps.subscriptionapp.constants import FEATURE_CATEGORY_CHOICES
from apps.subscriptionapp.models import Plan, PlanFeature


class FeatureService:
    """Service for managing plan features"""

    @staticmethod
    def get_features_by_category(plan_id):
        """Get plan features organized by category"""
        features = PlanFeature.objects.filter(plan_id=plan_id).order_by("category", "tier")

        # Organize features by category
        categorized_features = {}
        for category_code, category_name in FEATURE_CATEGORY_CHOICES:
            categorized_features[category_code] = {
                "name": category_name,
                "features": [],
            }

        # Add features to their categories
        for feature in features:
            if feature.category in categorized_features:
                categorized_features[feature.category]["features"].append(
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

        return categorized_features

    @staticmethod
    def create_feature_set(plan_id, features_data):
        """Create a set of features for a plan"""
        plan = Plan.objects.get(id=plan_id)

        created_features = []
        for feature_data in features_data:
            feature = PlanFeature.objects.create(plan=plan, **feature_data)
            created_features.append(feature)

        return created_features

    @staticmethod
    def update_feature_set(plan_id, features_data):
        """Update the feature set for a plan"""
        plan = Plan.objects.get(id=plan_id)

        # Clear existing features
        plan.features.all().delete()

        # Create new features
        return FeatureService.create_feature_set(plan_id, features_data)

    @staticmethod
    def check_feature_availability(subscription, feature_category, value=None):
        """Check if a specific feature is available for the subscription"""
        if not subscription:
            return False

        # Get the plan for this subscription
        plan = subscription.plan
        if not plan:
            return False

        # Check plan features
        feature = PlanFeature.objects.filter(
            plan=plan, category=feature_category, is_available=True
        ).first()

        if not feature:
            return False

        # If value is provided, check if the feature supports this value
        if value and feature.value:
            # Handle numeric comparisons
            try:
                feature_value = int(feature.value)
                check_value = int(value)
                return check_value <= feature_value
            except (ValueError, TypeError):
                # Handle string values (e.g., "basic", "premium")
                return feature.value == value or feature.value == "unlimited"

        return True

    @staticmethod
    def get_feature_comparison(plans):
        """Compare features across multiple plans"""
        plan_ids = [plan.id for plan in plans]

        # Get all features for these plans
        all_features = PlanFeature.objects.filter(plan_id__in=plan_ids).order_by("category", "tier")

        # Organize features by category
        comparison = {}
        for category_code, category_name in FEATURE_CATEGORY_CHOICES:
            comparison[category_code] = {"name": category_name, "features": []}

        # Create unique feature list
        unique_features = {}
        for feature in all_features:
            key = f"{feature.category}_{feature.name}"
            if key not in unique_features:
                unique_features[key] = {
                    "name": feature.name,
                    "name_ar": feature.name_ar,
                    "category": feature.category,
                    "plans": {},
                }

            # Add plan-specific value
            unique_features[key]["plans"][str(feature.plan_id)] = {
                "value": feature.value,
                "is_available": feature.is_available,
                "tier": feature.tier,
            }

        # Arrange features by category
        for key, feature in unique_features.items():
            if feature["category"] in comparison:
                comparison[feature["category"]]["features"].append(
                    {
                        "name": feature["name"],
                        "name_ar": feature["name_ar"],
                        "plans": feature["plans"],
                    }
                )

        return comparison
