"""
Ad Analytics Service.

This module provides analysis and reporting of advertisement performance.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from django.db import models, transaction
from django.db.models import Case, Count, F, Sum, When
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone

from apps.marketingapp.models import AdClick, Advertisement, AdView, Campaign

logger = logging.getLogger(__name__)


class AdAnalyticsService:
    """
    Service for analyzing advertisement performance and generating reports
    """

    @classmethod
    def get_ad_performance(
        cls,
        ad_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get performance metrics for a specific advertisement.

        Args:
            ad_id: ID of the advertisement
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering

        Returns:
            Dictionary with performance metrics
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

            # Set default date range if not provided
            if not start_date:
                start_date = timezone.now() - timedelta(days=30)
            if not end_date:
                end_date = timezone.now()

            # Validate date range
            if end_date < start_date:
                return {
                    "success": False,
                    "message": "End date must be after start date",
                }

            # Query views within date range
            views = AdView.objects.filter(
                advertisement=ad, viewed_at__gte=start_date, viewed_at__lte=end_date
            )

            # Query clicks within date range
            clicks = AdClick.objects.filter(
                advertisement=ad, clicked_at__gte=start_date, clicked_at__lte=end_date
            )

            # Calculate core metrics
            total_views = views.count()
            total_clicks = clicks.count()
            total_conversions = clicks.filter(led_to_booking=True).count()

            # Calculate rates
            ctr = (total_clicks / total_views * 100) if total_views > 0 else 0
            conversion_rate = (
                (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
            )

            # Calculate costs
            view_cost = total_views * ad.cost_per_view
            click_cost = total_clicks * ad.cost_per_click
            total_cost = view_cost + click_cost

            # Cost per acquisition (CPA)
            cpa = (total_cost / total_conversions) if total_conversions > 0 else 0

            # Get daily breakdown
            daily_metrics = cls._get_daily_metrics(
                ad, views, clicks, start_date, end_date
            )

            # Get audience breakdown
            audience_metrics = cls._get_audience_metrics(views, clicks)

            return {
                "success": True,
                "ad_id": str(ad.id),
                "ad_title": ad.title,
                "status": ad.status,
                "ad_type": ad.ad_type,
                "date_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": (end_date - start_date).days,
                },
                "overall_metrics": {
                    "impressions": total_views,
                    "clicks": total_clicks,
                    "conversions": total_conversions,
                    "ctr": round(ctr, 2),
                    "conversion_rate": round(conversion_rate, 2),
                    "view_cost": round(view_cost, 2),
                    "click_cost": round(click_cost, 2),
                    "total_cost": round(total_cost, 2),
                    "cost_per_acquisition": round(cpa, 2),
                },
                "daily_metrics": daily_metrics,
                "audience_metrics": audience_metrics,
            }

        except Exception as e:
            logger.error(f"Error getting ad performance: {str(e)}")
            return {
                "success": False,
                "message": f"Error getting ad performance: {str(e)}",
            }

    @classmethod
    def get_campaign_performance(
        cls,
        campaign_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get performance metrics for a campaign.

        Args:
            campaign_id: ID of the campaign
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering

        Returns:
            Dictionary with campaign performance metrics
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

            # Set default date range if not provided
            if not start_date:
                start_date = campaign.start_date
            if not end_date:
                end_date = (
                    campaign.end_date
                    if campaign.end_date > timezone.now()
                    else timezone.now()
                )

            # Validate date range
            if end_date < start_date:
                return {
                    "success": False,
                    "message": "End date must be after start date",
                }

            # Get all ads in the campaign
            ads = Advertisement.objects.filter(campaign=campaign)

            # Aggregate metrics across all ads
            ad_metrics = []
            total_impressions = 0
            total_clicks = 0
            total_conversions = 0
            total_cost = 0

            for ad in ads:
                # Get individual ad performance
                ad_perf = cls.get_ad_performance(str(ad.id), start_date, end_date)
                if ad_perf["success"]:
                    metrics = ad_perf["overall_metrics"]
                    ad_metrics.append(
                        {
                            "ad_id": str(ad.id),
                            "ad_title": ad.title,
                            "status": ad.status,
                            "impressions": metrics["impressions"],
                            "clicks": metrics["clicks"],
                            "conversions": metrics["conversions"],
                            "ctr": metrics["ctr"],
                            "conversion_rate": metrics["conversion_rate"],
                            "total_cost": metrics["total_cost"],
                        }
                    )

                    # Add to totals
                    total_impressions += metrics["impressions"]
                    total_clicks += metrics["clicks"]
                    total_conversions += metrics["conversions"]
                    total_cost += metrics["total_cost"]

            # Calculate overall campaign metrics - with safe division
            overall_ctr = (
                (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            )
            overall_conversion_rate = (
                (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
            )
            overall_cpa = (
                (total_cost / total_conversions) if total_conversions > 0 else 0
            )

            # Get budget information
            budget_total = float(campaign.budget)
            budget_spent = float(campaign.budget_spent)
            budget_remaining = budget_total - budget_spent

            # Calculate daily spend trend
            daily_spend = cls._get_campaign_daily_spend(campaign, start_date, end_date)

            return {
                "success": True,
                "campaign_id": str(campaign.id),
                "campaign_name": campaign.name,
                "status": "active" if campaign.is_active else "inactive",
                "date_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": (end_date - start_date).days,
                },
                "overall_metrics": {
                    "impressions": total_impressions,
                    "clicks": total_clicks,
                    "conversions": total_conversions,
                    "ctr": round(overall_ctr, 2),
                    "conversion_rate": round(overall_conversion_rate, 2),
                    "total_cost": round(total_cost, 2),
                    "cost_per_acquisition": round(overall_cpa, 2),
                },
                "budget_metrics": {
                    "budget_total": round(budget_total, 2),
                    "budget_spent": round(budget_spent, 2),
                    "budget_remaining": round(budget_remaining, 2),
                    "budget_percentage_used": (
                        round((budget_spent / budget_total * 100), 2)
                        if budget_total > 0
                        else 0
                    ),
                },
                "ad_metrics": ad_metrics,
                "daily_spend": daily_spend,
            }

        except Exception as e:
            logger.error(f"Error getting campaign performance: {str(e)}")
            return {
                "success": False,
                "message": f"Error getting campaign performance: {str(e)}",
            }

    @classmethod
    def get_shop_advertising_overview(
        cls,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get an overview of all advertising for a shop.

        Args:
            shop_id: ID of the shop
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering

        Returns:
            Dictionary with shop advertising overview
        """
        try:
            # Set default date range if not provided
            if not start_date:
                start_date = timezone.now() - timedelta(days=90)  # 3 months by default
            if not end_date:
                end_date = timezone.now()

            # Validate date range
            if end_date < start_date:
                return {
                    "success": False,
                    "message": "End date must be after start date",
                }

            # Get all campaigns for the shop
            campaigns = Campaign.objects.filter(
                shop_id=shop_id, start_date__lte=end_date, end_date__gte=start_date
            )

            # If no campaigns, return empty metrics
            if not campaigns.exists():
                return {
                    "success": True,
                    "shop_id": shop_id,
                    "campaigns_count": 0,
                    "active_campaigns_count": 0,
                    "ads_count": 0,
                    "total_spent": 0,
                    "impressions": 0,
                    "clicks": 0,
                    "conversions": 0,
                    "ctr": 0,
                    "campaigns": [],
                }

            # Get all ads from these campaigns
            [str(c.id) for c in campaigns]
            ads = Advertisement.objects.filter(campaign__in=campaigns)

            # Get aggregate metrics
            total_impressions = 0
            total_clicks = 0
            total_conversions = 0
            total_spent = 0

            # Get campaign summaries
            campaign_summaries = []
            for campaign in campaigns:
                # Get campaign performance
                camp_perf = cls.get_campaign_performance(
                    str(campaign.id), start_date, end_date
                )
                if camp_perf["success"]:
                    metrics = camp_perf["overall_metrics"]
                    budget = camp_perf["budget_metrics"]

                    campaign_summaries.append(
                        {
                            "campaign_id": str(campaign.id),
                            "campaign_name": campaign.name,
                            "status": "active" if campaign.is_active else "inactive",
                            "start_date": campaign.start_date.isoformat(),
                            "end_date": campaign.end_date.isoformat(),
                            "impressions": metrics["impressions"],
                            "clicks": metrics["clicks"],
                            "conversions": metrics["conversions"],
                            "ctr": metrics["ctr"],
                            "conversion_rate": metrics["conversion_rate"],
                            "budget_total": budget["budget_total"],
                            "budget_spent": budget["budget_spent"],
                            "ads_count": ads.filter(campaign=campaign).count(),
                        }
                    )

                    # Add to totals
                    total_impressions += metrics["impressions"]
                    total_clicks += metrics["clicks"]
                    total_conversions += metrics["conversions"]
                    total_spent += budget["budget_spent"]

            # Calculate overall CTR - with safe division
            overall_ctr = (
                (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            )

            return {
                "success": True,
                "shop_id": shop_id,
                "date_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": (end_date - start_date).days,
                },
                "campaigns_count": campaigns.count(),
                "active_campaigns_count": campaigns.filter(is_active=True).count(),
                "ads_count": ads.count(),
                "total_spent": round(total_spent, 2),
                "impressions": total_impressions,
                "clicks": total_clicks,
                "conversions": total_conversions,
                "ctr": round(overall_ctr, 2),
                "campaigns": campaign_summaries,
            }

        except Exception as e:
            logger.error(f"Error getting shop advertising overview: {str(e)}")
            return {
                "success": False,
                "message": f"Error getting shop advertising overview: {str(e)}",
            }

    @classmethod
    @transaction.atomic
    def update_campaign_budget_spent(
        cls, campaign_id: str, additional_spend: float
    ) -> bool:
        """
        Atomically update a campaign's spent budget.

        Args:
            campaign_id: ID of the campaign
            additional_spend: Amount to add to spent budget

        Returns:
            Boolean indicating success
        """
        try:
            # Use select_for_update to lock the row during update
            campaign = Campaign.objects.select_for_update().get(id=campaign_id)

            # Update the budget spent
            campaign.budget_spent = F("budget_spent") + additional_spend
            campaign.save(update_fields=["budget_spent"])

            # Refresh from database to get the new value
            campaign.refresh_from_db()

            # Check if the campaign has exceeded its budget
            if campaign.budget_spent >= campaign.budget and campaign.is_active:
                # Deactivate campaign if budget is exceeded
                campaign.is_active = False
                campaign.save(update_fields=["is_active"])
                logger.info(
                    f"Campaign {campaign_id} deactivated due to budget depletion"
                )

            logger.info(
                f"Updated budget spent for campaign {campaign_id}, new total: {campaign.budget_spent}"
            )
            return True

        except Campaign.DoesNotExist:
            logger.error(f"Campaign {campaign_id} not found for budget update")
            return False
        except Exception as e:
            logger.error(f"Error updating campaign budget: {str(e)}")
            return False

    # Private helper methods

    @staticmethod
    def _get_daily_metrics(ad, views, clicks, start_date, end_date):
        """
        Get daily breakdown of metrics for an ad.
        """
        # Create date range
        date_range = []
        current_date = start_date.date()
        while current_date <= end_date.date():
            date_range.append(current_date)
            current_date += timedelta(days=1)

        # Get views by day
        views_by_day = (
            views.annotate(date=TruncDate("viewed_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        views_dict = {v["date"]: v["count"] for v in views_by_day}

        # Get clicks by day
        clicks_by_day = (
            clicks.annotate(date=TruncDate("clicked_at"))
            .values("date")
            .annotate(
                count=Count("id"),
                conversions=Sum(
                    Case(
                        When(led_to_booking=True, then=1),
                        default=0,
                        output_field=models.IntegerField(),
                    )
                ),
            )
            .order_by("date")
        )

        clicks_dict = {c["date"]: c["count"] for c in clicks_by_day}
        conversions_dict = {c["date"]: c["conversions"] for c in clicks_by_day}

        # Build daily metrics
        daily_metrics = []
        for date in date_range:
            views_count = views_dict.get(date, 0)
            clicks_count = clicks_dict.get(date, 0)
            conversions_count = (
                conversions_dict.get(date, 0) if date in conversions_dict else 0
            )

            # Safe calculation of rates
            ctr = (clicks_count / views_count * 100) if views_count > 0 else 0
            conversion_rate = (
                (conversions_count / clicks_count * 100) if clicks_count > 0 else 0
            )

            daily_metrics.append(
                {
                    "date": date.isoformat(),
                    "impressions": views_count,
                    "clicks": clicks_count,
                    "conversions": conversions_count,
                    "ctr": round(ctr, 2),
                    "conversion_rate": round(conversion_rate, 2),
                    "cost": round(
                        (views_count * ad.cost_per_view)
                        + (clicks_count * ad.cost_per_click),
                        2,
                    ),
                }
            )

        return daily_metrics

    @staticmethod
    def _get_audience_metrics(views, clicks):
        """
        Get audience breakdown metrics.
        """
        # City breakdown
        city_metrics = []
        cities_with_views = (
            views.filter(city__isnull=False)
            .values("city")
            .annotate(impressions=Count("id"))
        )

        for city_data in cities_with_views:
            city_id = city_data["city"]
            city_views = city_data["impressions"]

            city_clicks = clicks.filter(city_id=city_id).count()
            ctr = (city_clicks / city_views * 100) if city_views > 0 else 0

            # Get city name
            city_name = "Unknown"
            try:
                from apps.geoapp.models import City

                city = City.objects.get(id=city_id)
                city_name = city.name
            except Exception as e:
                # Log the error instead of silently ignoring it
                logger.warning(
                    f"Failed to get city name for city_id {city_id}: {str(e)}"
                )
                # Set a fallback city name that indicates the issue
                city_name = f"Unknown (ID: {city_id})"

            city_metrics.append(
                {
                    "city_id": str(city_id),
                    "city_name": city_name,
                    "impressions": city_views,
                    "clicks": city_clicks,
                    "ctr": round(ctr, 2),
                }
            )

        # User vs Anonymous
        user_views = views.filter(user__isnull=False).count()
        anon_views = views.filter(user__isnull=True).count()

        user_clicks = clicks.filter(user__isnull=False).count()
        anon_clicks = clicks.filter(user__isnull=True).count()

        # Safe division
        user_ctr = (user_clicks / user_views * 100) if user_views > 0 else 0
        anon_ctr = (anon_clicks / anon_views * 100) if anon_views > 0 else 0

        # Time of day analysis (hour of day)
        hour_metrics = []
        hours_with_views = (
            views.annotate(hour=TruncHour("viewed_at"))
            .values("hour")
            .annotate(impressions=Count("id"))
            .order_by("hour")
        )

        for hour_data in hours_with_views:
            hour = hour_data["hour"]
            hour_views = hour_data["impressions"]

            hour_start = hour.time().hour
            hour_label = f"{hour_start:02d}:00"

            # Get clicks for this hour
            hour_clicks = clicks.filter(clicked_at__hour=hour_start).count()
            hour_ctr = (hour_clicks / hour_views * 100) if hour_views > 0 else 0

            hour_metrics.append(
                {
                    "hour": hour_label,
                    "impressions": hour_views,
                    "clicks": hour_clicks,
                    "ctr": round(hour_ctr, 2),
                }
            )

        return {
            "cities": city_metrics,
            "user_types": {
                "registered": {
                    "impressions": user_views,
                    "clicks": user_clicks,
                    "ctr": round(user_ctr, 2),
                },
                "anonymous": {
                    "impressions": anon_views,
                    "clicks": anon_clicks,
                    "ctr": round(anon_ctr, 2),
                },
            },
            "hours": hour_metrics,
        }

    @staticmethod
    def _get_campaign_daily_spend(campaign, start_date, end_date):
        """
        Get daily spend for a campaign.
        """
        # Create date range
        date_range = []
        current_date = start_date.date()
        while current_date <= end_date.date():
            date_range.append(current_date)
            current_date += timedelta(days=1)

        # Get all ads in the campaign
        ads = Advertisement.objects.filter(campaign=campaign)

        # Get views by day
        views = (
            AdView.objects.filter(
                advertisement__in=ads,
                viewed_at__gte=start_date,
                viewed_at__lte=end_date,
            )
            .annotate(date=TruncDate("viewed_at"))
            .values("date", "advertisement")
            .annotate(count=Count("id"))
        )

        # Get clicks by day
        clicks = (
            AdClick.objects.filter(
                advertisement__in=ads,
                clicked_at__gte=start_date,
                clicked_at__lte=end_date,
            )
            .annotate(date=TruncDate("clicked_at"))
            .values("date", "advertisement")
            .annotate(count=Count("id"))
        )

        # Calculate spend by day
        daily_spend = []
        for date in date_range:
            date_spend = 0

            # Add view costs for this day
            for view in views:
                if view["date"] == date:
                    try:
                        ad = Advertisement.objects.get(id=view["advertisement"])
                        date_spend += view["count"] * ad.cost_per_view
                    except Advertisement.DoesNotExist:
                        logger.warning(
                            f"Advertisement {view['advertisement']} not found while calculating daily spend"
                        )
                        continue

            # Add click costs for this day
            for click in clicks:
                if click["date"] == date:
                    try:
                        ad = Advertisement.objects.get(id=click["advertisement"])
                        date_spend += click["count"] * ad.cost_per_click
                    except Advertisement.DoesNotExist:
                        logger.warning(
                            f"Advertisement {click['advertisement']} not found while calculating daily spend"
                        )
                        continue

            daily_spend.append(
                {"date": date.isoformat(), "spend": round(date_spend, 2)}
            )

        return daily_spend
