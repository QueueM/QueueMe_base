"""
Ad Management Service.

This module handles the creation, updating, and management of advertisements
and campaigns.
"""

import logging
from typing import Any, Dict, List, Optional

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from apps.marketingapp.models import (
    AdStatus,
    AdType,
    Advertisement,
    Campaign,
    TargetingType,
)

logger = logging.getLogger(__name__)


class AdManagementService:
    """
    Service for managing advertisements and campaigns
    """

    @classmethod
    def create_campaign(
        cls,
        company_id: str,
        shop_id: str,
        name: str,
        start_date: timezone.datetime,
        end_date: timezone.datetime,
        budget: float,
        is_active: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a new advertising campaign.

        Args:
            company_id: ID of the company
            shop_id: ID of the shop
            name: Campaign name
            start_date: Start date of the campaign
            end_date: End date of the campaign
            budget: Total budget for the campaign in SAR
            is_active: Whether the campaign is active

        Returns:
            Dictionary with campaign details or error message
        """
        try:
            # Validate dates
            if start_date >= end_date:
                return {
                    "success": False,
                    "message": "End date must be after start date",
                }

            # Validate budget
            if budget <= 0:
                return {"success": False, "message": "Budget must be greater than zero"}

            # Create campaign
            with transaction.atomic():
                campaign = Campaign.objects.create(
                    company_id=company_id,
                    shop_id=shop_id,
                    name=name,
                    start_date=start_date,
                    end_date=end_date,
                    budget=budget,
                    is_active=is_active,
                )

            return {
                "success": True,
                "campaign_id": str(campaign.id),
                "message": "Campaign created successfully",
            }

        except Exception as e:
            logger.error(f"Error creating campaign: {str(e)}")
            return {"success": False, "message": f"Error creating campaign: {str(e)}"}

    @classmethod
    def create_advertisement(
        cls,
        title: str,
        description: str,
        ad_type: str,
        campaign_id: Optional[str] = None,
        targeting_type: str = TargetingType.ALL,
        target_cities: Optional[List[str]] = None,
        target_categories: Optional[List[str]] = None,
        linked_object_type: Optional[str] = None,
        linked_object_id: Optional[str] = None,
        cost_per_view: float = 0.10,
        cost_per_click: float = 1.00,
        image=None,
        video=None,
    ) -> Dict[str, Any]:
        """
        Create a new advertisement.

        Args:
            title: Advertisement title
            description: Advertisement description
            ad_type: Type of ad (image or video)
            campaign_id: Optional ID of the campaign
            targeting_type: Type of targeting
            target_cities: List of city IDs to target
            target_categories: List of category IDs to target
            linked_object_type: Type of linked object (shop, service, specialist)
            linked_object_id: ID of linked object
            cost_per_view: Cost per view in SAR
            cost_per_click: Cost per click in SAR
            image: Image file for image ads
            video: Video file for video ads

        Returns:
            Dictionary with advertisement details or error message
        """
        try:
            # Validate ad type and content
            if ad_type not in [choice[0] for choice in AdType.choices]:
                return {"success": False, "message": f"Invalid ad type: {ad_type}"}

            if ad_type == AdType.IMAGE and not image:
                return {"success": False, "message": "Image is required for image ads"}

            if ad_type == AdType.VIDEO and not video:
                return {"success": False, "message": "Video is required for video ads"}

            # Validate targeting
            if targeting_type not in [choice[0] for choice in TargetingType.choices]:
                return {
                    "success": False,
                    "message": f"Invalid targeting type: {targeting_type}",
                }

            if targeting_type == TargetingType.LOCATION and not target_cities:
                return {
                    "success": False,
                    "message": "Target cities are required for location-based targeting",
                }

            if targeting_type == TargetingType.CATEGORY and not target_categories:
                return {
                    "success": False,
                    "message": "Target categories are required for category-based targeting",
                }

            # Get content type for linked object
            content_type = None
            if linked_object_type and linked_object_id:
                try:
                    content_type = ContentType.objects.get(
                        model=linked_object_type.lower()
                    )
                except ContentType.DoesNotExist:
                    return {
                        "success": False,
                        "message": f"Invalid linked object type: {linked_object_type}",
                    }

            # Create advertisement
            with transaction.atomic():
                ad = Advertisement.objects.create(
                    title=title,
                    description=description,
                    ad_type=ad_type,
                    campaign_id=campaign_id,
                    targeting_type=targeting_type,
                    content_type=content_type,
                    object_id=linked_object_id,
                    cost_per_view=cost_per_view,
                    cost_per_click=cost_per_click,
                    status=AdStatus.DRAFT,
                    image=image,
                    video=video,
                )

                # Add targeting relationships
                if target_cities:
                    ad.target_cities.set(target_cities)

                if target_categories:
                    ad.target_categories.set(target_categories)

            return {
                "success": True,
                "advertisement_id": str(ad.id),
                "message": "Advertisement created successfully",
            }

        except Exception as e:
            logger.error(f"Error creating advertisement: {str(e)}")
            return {
                "success": False,
                "message": f"Error creating advertisement: {str(e)}",
            }

    @classmethod
    def update_advertisement_status(cls, ad_id: str, status: str) -> Dict[str, Any]:
        """
        Update the status of an advertisement.

        Args:
            ad_id: ID of the advertisement
            status: New status

        Returns:
            Dictionary with success status and message
        """
        try:
            # Validate status
            if status not in [choice[0] for choice in AdStatus.choices]:
                return {"success": False, "message": f"Invalid status: {status}"}

            # Get advertisement
            try:
                ad = Advertisement.objects.get(id=ad_id)
            except Advertisement.DoesNotExist:
                return {
                    "success": False,
                    "message": f"Advertisement not found with ID: {ad_id}",
                }

            # Update status
            prev_status = ad.status
            ad.status = status

            # Additional logic based on status change
            if status == AdStatus.ACTIVE and prev_status != AdStatus.ACTIVE:
                # Check if ad has been paid for
                if not ad.payment_date:
                    return {
                        "success": False,
                        "message": "Cannot activate advertisement that hasn't been paid for",
                    }

                # Check if campaign is active
                if ad.campaign and not ad.campaign.is_active:
                    return {
                        "success": False,
                        "message": "Cannot activate advertisement for inactive campaign",
                    }

            ad.save()

            return {
                "success": True,
                "message": f"Advertisement status updated to {status}",
            }

        except Exception as e:
            logger.error(f"Error updating advertisement status: {str(e)}")
            return {
                "success": False,
                "message": f"Error updating advertisement status: {str(e)}",
            }

    @classmethod
    def delete_advertisement(cls, ad_id: str) -> Dict[str, Any]:
        """
        Delete an advertisement.

        Args:
            ad_id: ID of the advertisement

        Returns:
            Dictionary with success status and message
        """
        try:
            # Get advertisement
            try:
                ad = Advertisement.objects.get(id=ad_id)
            except Advertisement.DoesNotExist:
                return {
                    "success": False,
                    "message": f"Advertisement not found with ID: {ad_id}",
                }

            # Can only delete in draft or rejected status
            if ad.status not in [AdStatus.DRAFT, AdStatus.REJECTED]:
                return {
                    "success": False,
                    "message": f"Cannot delete advertisement in {ad.status} status",
                }

            # Delete advertisement
            ad.delete()

            return {"success": True, "message": "Advertisement deleted successfully"}

        except Exception as e:
            logger.error(f"Error deleting advertisement: {str(e)}")
            return {
                "success": False,
                "message": f"Error deleting advertisement: {str(e)}",
            }

    @classmethod
    def get_campaign_stats(cls, campaign_id: str) -> Dict[str, Any]:
        """
        Get statistics for a campaign.

        Args:
            campaign_id: ID of the campaign

        Returns:
            Dictionary with campaign statistics
        """
        try:
            # Get campaign
            try:
                campaign = Campaign.objects.get(id=campaign_id)
            except Campaign.DoesNotExist:
                return {
                    "success": False,
                    "message": f"Campaign not found with ID: {campaign_id}",
                }

            # Get campaign advertisements
            ads = Advertisement.objects.filter(campaign=campaign)

            # Calculate statistics
            total_impressions = sum(ad.impression_count for ad in ads)
            total_clicks = sum(ad.click_count for ad in ads)
            total_conversions = sum(ad.conversion_count for ad in ads)

            # Calculate rates
            ctr = (
                (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            )
            conversion_rate = (
                (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
            )

            # Calculate spending
            total_spent = campaign.budget_spent
            budget_remaining = campaign.budget - total_spent

            return {
                "success": True,
                "campaign_id": str(campaign.id),
                "campaign_name": campaign.name,
                "total_ads": ads.count(),
                "active_ads": ads.filter(status=AdStatus.ACTIVE).count(),
                "total_impressions": total_impressions,
                "total_clicks": total_clicks,
                "total_conversions": total_conversions,
                "click_through_rate": round(ctr, 2),
                "conversion_rate": round(conversion_rate, 2),
                "total_spent": float(total_spent),
                "budget_remaining": float(budget_remaining),
                "budget_percentage_used": (
                    round((total_spent / campaign.budget * 100), 2)
                    if campaign.budget > 0
                    else 0
                ),
                "days_remaining": (
                    (campaign.end_date - timezone.now()).days
                    if campaign.end_date > timezone.now()
                    else 0
                ),
            }

        except Exception as e:
            logger.error(f"Error getting campaign stats: {str(e)}")
            return {
                "success": False,
                "message": f"Error getting campaign stats: {str(e)}",
            }
