"""
Ad Serving Service.

This module handles the logic for selecting and serving advertisements to users
based on targeting criteria.
"""

import logging
import random
from typing import Any, Dict, List, Optional

from django.db.models import F, Q

from apps.marketingapp.models import AdStatus, Advertisement, AdView, TargetingType

logger = logging.getLogger(__name__)


class AdServingService:
    """
    Service for selecting and serving advertisements to users
    """

    # Constants for ad serving
    MAX_ADS_PER_REQUEST = 5
    DEFAULT_AD_COUNT = 1

    @classmethod
    def get_ads_for_user(
        cls,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        city_id: Optional[str] = None,
        category_ids: Optional[List[str]] = None,
        count: int = DEFAULT_AD_COUNT,
    ) -> Dict[str, Any]:
        """
        Get advertisements for a specific user or session.

        Args:
            user_id: Optional ID of the user
            session_id: Optional session ID for anonymous users
            city_id: Optional city ID for location targeting
            category_ids: Optional list of category IDs for interest targeting
            count: Number of ads to retrieve (default 1)

        Returns:
            Dictionary with advertisements
        """
        try:
            # Validate parameters
            if not user_id and not session_id:
                return {
                    "success": False,
                    "message": "Either user_id or session_id must be provided",
                }

            # Limit count to avoid abuse
            if count > cls.MAX_ADS_PER_REQUEST:
                count = cls.MAX_ADS_PER_REQUEST

            # Start with active ads query
            ads_query = Advertisement.objects.filter(status=AdStatus.ACTIVE)

            # Apply targeting filters
            targeted_ads = cls._apply_targeting_filters(
                ads_query, user_id, city_id, category_ids
            )

            # If no targeted ads available, fall back to non-targeted ads
            if not targeted_ads.exists():
                targeted_ads = ads_query.filter(targeting_type=TargetingType.ALL)

            # Get the requested number of ads, or all if fewer available
            selected_ads = list(targeted_ads[:count])
            random.shuffle(selected_ads)  # Randomize order

            # Convert to dict form for response
            ad_list = []
            for ad in selected_ads:
                ad_list.append(cls._format_ad_for_response(ad))

                # Record the view
                cls._record_ad_view(ad.id, user_id, session_id, city_id)

            return {"success": True, "ads": ad_list, "count": len(ad_list)}

        except Exception as e:
            logger.error(f"Error serving ads: {str(e)}")
            return {"success": False, "message": f"Error serving ads: {str(e)}"}

    @classmethod
    def record_ad_click(
        cls,
        ad_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        city_id: Optional[str] = None,
        referrer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record a click on an advertisement.

        Args:
            ad_id: ID of the advertisement
            user_id: Optional ID of the user
            session_id: Optional session ID for anonymous users
            ip_address: Optional IP address
            city_id: Optional city ID
            referrer: Optional referrer URL

        Returns:
            Dictionary with success status and message
        """
        try:
            # Validate parameters
            if not user_id and not session_id:
                return {
                    "success": False,
                    "message": "Either user_id or session_id must be provided",
                }

            # Get advertisement
            try:
                ad = Advertisement.objects.get(id=ad_id)
            except Advertisement.DoesNotExist:
                return {
                    "success": False,
                    "message": f"Advertisement not found with ID: {ad_id}",
                }

            # Record click
            from apps.marketingapp.models import AdClick

            click = AdClick.objects.create(
                advertisement=ad,
                user_id=user_id,
                session_id=session_id,
                ip_address=ip_address,
                city_id=city_id,
                referrer=referrer,
            )

            # Update ad metrics
            ad.click_count = F("click_count") + 1
            ad.save(update_fields=["click_count"])

            # Update campaign budget spent if applicable
            if ad.campaign:
                ad.campaign.budget_spent = F("budget_spent") + ad.cost_per_click
                ad.campaign.save(update_fields=["budget_spent"])

            return {
                "success": True,
                "message": "Ad click recorded successfully",
                "click_id": str(click.id),
            }

        except Exception as e:
            logger.error(f"Error recording ad click: {str(e)}")
            return {"success": False, "message": f"Error recording ad click: {str(e)}"}

    @classmethod
    def record_conversion(
        cls,
        ad_id: str,
        booking_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record a conversion from an advertisement.

        Args:
            ad_id: ID of the advertisement
            booking_id: ID of the booking/appointment
            user_id: Optional ID of the user
            session_id: Optional session ID for anonymous users

        Returns:
            Dictionary with success status and message
        """
        try:
            # Validate parameters
            if not user_id and not session_id:
                return {
                    "success": False,
                    "message": "Either user_id or session_id must be provided",
                }

            # Get advertisement
            try:
                ad = Advertisement.objects.get(id=ad_id)
            except Advertisement.DoesNotExist:
                return {
                    "success": False,
                    "message": f"Advertisement not found with ID: {ad_id}",
                }

            # Find the most recent click for this ad from this user/session
            from apps.marketingapp.models import AdClick

            query = Q(advertisement=ad)
            if user_id:
                query &= Q(user_id=user_id)
            elif session_id:
                query &= Q(session_id=session_id)

            try:
                click = AdClick.objects.filter(query).latest("clicked_at")

                # Update click with conversion info
                click.led_to_booking = True
                click.booking_id = booking_id
                click.save(update_fields=["led_to_booking", "booking_id"])

                # Update ad metrics
                ad.conversion_count = F("conversion_count") + 1
                ad.save(update_fields=["conversion_count"])

                return {
                    "success": True,
                    "message": "Conversion recorded successfully",
                    "click_id": str(click.id),
                }

            except AdClick.DoesNotExist:
                # Create a synthetic click if none found
                click = AdClick.objects.create(
                    advertisement=ad,
                    user_id=user_id,
                    session_id=session_id,
                    led_to_booking=True,
                    booking_id=booking_id,
                )

                # Update ad metrics
                ad.click_count = F("click_count") + 1
                ad.conversion_count = F("conversion_count") + 1
                ad.save(update_fields=["click_count", "conversion_count"])

                return {
                    "success": True,
                    "message": "Conversion recorded successfully (synthetic click created)",
                    "click_id": str(click.id),
                }

        except Exception as e:
            logger.error(f"Error recording conversion: {str(e)}")
            return {
                "success": False,
                "message": f"Error recording conversion: {str(e)}",
            }

    # Private helper methods

    @staticmethod
    def _apply_targeting_filters(base_query, user_id, city_id, category_ids):
        """
        Apply targeting filters to the base query.
        """
        # Start with all targeting types
        targeting_query = Q()

        # Add location targeting if city provided
        if city_id:
            location_query = Q(
                targeting_type=TargetingType.LOCATION, target_cities__id=city_id
            )
            targeting_query |= location_query

        # Add category targeting if categories provided
        if category_ids and len(category_ids) > 0:
            category_query = Q(
                targeting_type=TargetingType.CATEGORY,
                target_categories__id__in=category_ids,
            )
            targeting_query |= category_query

        # Add interest targeting if user provided
        if user_id:
            # Interest targeting would be based on user preferences/history
            # This is a placeholder for more sophisticated targeting
            interest_query = Q(targeting_type=TargetingType.INTEREST)
            targeting_query |= interest_query

        # Add "all users" targeting as fallback
        all_users_query = Q(targeting_type=TargetingType.ALL)
        targeting_query |= all_users_query

        # Apply the combined targeting query
        return base_query.filter(targeting_query).distinct()

    @staticmethod
    def _format_ad_for_response(ad):
        """
        Format an advertisement for API response.
        """
        # Base ad data
        ad_data = {
            "id": str(ad.id),
            "title": ad.title,
            "description": ad.description,
            "ad_type": ad.ad_type,
        }

        # Add media URLs
        if ad.ad_type == "image" and ad.image:
            ad_data["image_url"] = ad.image.url
        elif ad.ad_type == "video" and ad.video:
            ad_data["video_url"] = ad.video.url

        # Add linked content info if available
        if ad.content_type and ad.object_id:
            ad_data["linked_content"] = {
                "type": ad.content_type.model,
                "id": str(ad.object_id),
            }

        return ad_data

    @classmethod
    def _record_ad_view(cls, ad_id, user_id, session_id, city_id):
        """
        Record a view of an advertisement.
        """
        try:
            # Get advertisement
            ad = Advertisement.objects.get(id=ad_id)

            # Create view record
            AdView.objects.create(
                advertisement=ad,
                user_id=user_id,
                session_id=session_id,
                city_id=city_id,
            )

            # Update ad metrics
            ad.impression_count = F("impression_count") + 1
            ad.save(update_fields=["impression_count"])

            # Update campaign budget spent if applicable
            if ad.campaign:
                ad.campaign.budget_spent = F("budget_spent") + ad.cost_per_view
                ad.campaign.save(update_fields=["budget_spent"])

            return True
        except Exception as e:
            logger.error(f"Error recording ad view: {str(e)}")
            return False
