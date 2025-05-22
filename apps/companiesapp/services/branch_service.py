# apps/companiesapp/services/branch_service.py

from django.db import models, transaction

from apps.geoapp.models import Location
from apps.shopapp.models import Shop
from apps.subscriptionapp.services.subscription_service import SubscriptionService


class BranchService:
    @staticmethod
    @transaction.atomic
    def create_branch(company, branch_data, location_data=None, manager_data=None):
        """
        Create a new branch (shop) for a company
        This delegates to shopapp but handles subscription validation
        """
        # Check subscription limits
        subscription_info = SubscriptionService.validate_shop_creation(company)
        if not subscription_info["can_create_shop"]:
            raise ValueError(subscription_info["message"])

        # Create shop using ShopService
        from apps.shopapp.services.shop_service import ShopService

        shop = ShopService.create_shop(
            company=company,
            shop_data=branch_data,
            location_data=location_data,
            manager_data=manager_data,
        )

        # Update company shop count
        company.update_counts()

        return shop

    @staticmethod
    def get_company_branches(company, with_metrics=False):
        """
        Get all branches (shops) for a company with optional metrics
        """
        shops = Shop.objects.filter(company=company)

        if not with_metrics:
            return shops

        # Annotate shops with metrics
        from django.db.models import Avg, Count, Q
        from django.utils import timezone

        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        shops = shops.annotate(
            employee_count=Count("employees", distinct=True),
            specialist_count=Count("employees__specialist", distinct=True),
            total_bookings=Count("appointments", distinct=True),
            today_bookings=Count(
                "appointments",
                filter=Q(appointments__start_time__gte=today),
                distinct=True,
            ),
        )

        # For each shop, get average rating
        for shop in shops:
            try:
                from apps.reviewapp.models import ShopReview

                avg_rating = ShopReview.objects.filter(shop=shop).aggregate(
                    avg=Avg("rating")
                )["avg"]
                shop.avg_rating = avg_rating or 0
            except Exception:
                shop.avg_rating = 0

        return shops

    @staticmethod
    def get_optimal_branch_location(company, city=None):
        """
        Analyze existing branches and suggest optimal location for a new branch
        Using demand analysis from bookings
        """
        if city is None:
            # Get company's most popular city if not specified
            shops = Shop.objects.filter(company=company).select_related("location")

            if not shops.exists():
                # If no existing shops, return company location or None
                return company.location

            # Get the city with the most shops
            cities = {}
            for shop in shops:
                if shop.location and shop.location.city:
                    cities[shop.location.city] = cities.get(shop.location.city, 0) + 1

            if not cities:
                return company.location

            city = max(cities.items(), key=lambda x: x[1])[0]

        try:
            # Get all booking locations in this city from customers
            pass

            from apps.bookingapp.models import Appointment

            # Get all shops in this company
            shop_ids = Shop.objects.filter(company=company).values_list("id", flat=True)

            # Get all bookings from these shops
            appointments = Appointment.objects.filter(
                shop_id__in=shop_ids, status="completed"
            ).select_related("customer")

            # Extract customer locations
            customer_locations = []
            for appointment in appointments:
                if (
                    hasattr(appointment.customer, "profile")
                    and appointment.customer.profile.location
                ):
                    customer_locations.append(appointment.customer.profile.location)

            if not customer_locations:
                # If no customer data, return company location or None
                return company.location

            # Calculate average coordinates (simple approach)
            total_lat = sum(loc.latitude for loc in customer_locations if loc.latitude)
            total_lng = sum(
                loc.longitude for loc in customer_locations if loc.longitude
            )
            count = len(
                [loc for loc in customer_locations if loc.latitude and loc.longitude]
            )

            if count > 0:
                avg_lat = total_lat / count
                avg_lng = total_lng / count

                # Create a suggested location (don't save it)
                suggested_location = Location(
                    latitude=avg_lat,
                    longitude=avg_lng,
                    city=city,
                    country="Saudi Arabia",  # Assuming Saudi Arabia
                )

                return suggested_location

            return company.location

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error finding optimal branch location: {str(e)}")

            # Return company location as fallback
            return company.location

    @staticmethod
    def analyze_branch_performance(company):
        """
        Analyze performance metrics across all branches
        """
        try:
            # Get all shops for this company
            shops = Shop.objects.filter(company=company)

            if not shops.exists():
                return {"status": "error", "message": "No shops available for analysis"}

            # For each shop, calculate key metrics
            shop_metrics = []

            for shop in shops:
                # Calculate bookings
                from django.db.models import Avg, Count

                from apps.bookingapp.models import Appointment

                booking_stats = Appointment.objects.filter(shop=shop).aggregate(
                    total=Count("id"),
                    completed=Count("id", filter=models.Q(status="completed")),
                    cancelled=Count("id", filter=models.Q(status="cancelled")),
                    no_show=Count("id", filter=models.Q(status="no_show")),
                )

                # Calculate average rating
                try:
                    from apps.reviewapp.models import ShopReview

                    avg_rating = (
                        ShopReview.objects.filter(shop=shop).aggregate(
                            avg=Avg("rating")
                        )["avg"]
                        or 0
                    )
                except Exception:
                    avg_rating = 0

                # Calculate revenue if available
                try:
                    from django.db.models import Sum

                    from apps.payment.models import Transaction

                    revenue = (
                        Transaction.objects.filter(
                            content_type__model="appointment",
                            object_id__in=Appointment.objects.filter(
                                shop=shop
                            ).values_list("id", flat=True),
                            status="succeeded",
                        ).aggregate(total=Sum("amount"))["total"]
                        or 0
                    )
                except Exception:
                    revenue = 0

                # Add to metrics list
                shop_metrics.append(
                    {
                        "id": str(shop.id),
                        "name": shop.name,
                        "booking_stats": booking_stats,
                        "avg_rating": avg_rating,
                        "revenue": revenue,
                        "employee_count": shop.employees.count(),
                        "specialist_count": shop.employees.filter(
                            specialist__isnull=False
                        ).count(),
                    }
                )

            # Sort by total bookings (descending)
            shop_metrics.sort(key=lambda x: x["booking_stats"]["total"], reverse=True)

            # Calculate company-wide averages
            company_averages = {
                "avg_bookings_per_shop": sum(
                    s["booking_stats"]["total"] for s in shop_metrics
                )
                / len(shop_metrics),
                "avg_rating": sum(s["avg_rating"] for s in shop_metrics)
                / len(shop_metrics),
                "avg_revenue_per_shop": sum(s["revenue"] for s in shop_metrics)
                / len(shop_metrics),
            }

            return {
                "status": "success",
                "shop_metrics": shop_metrics,
                "company_averages": company_averages,
                "top_performing_shop": (
                    shop_metrics[0]["name"] if shop_metrics else None
                ),
            }

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error analyzing branch performance: {str(e)}")

            return {
                "status": "error",
                "message": f"Error analyzing branch performance: {str(e)}",
            }
