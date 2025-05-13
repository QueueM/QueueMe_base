# apps/companiesapp/services/company_service.py
from datetime import timedelta

from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.employeeapp.models import Employee
from apps.shopapp.models import Shop
from apps.subscriptionapp.models import Subscription

from ..models import Company, CompanyDocument


class CompanyService:
    @staticmethod
    @transaction.atomic
    def create_company(owner, company_data, location_data=None):
        """Create a new company with associated data"""
        from apps.geoapp.models import Location

        # Create location if provided
        location = None
        if location_data:
            location = Location.objects.create(**location_data)

        # Create company
        company_data["owner"] = owner
        company_data["location"] = location
        company = Company.objects.create(**company_data)

        # Ensure settings exist
        if not hasattr(company, "settings"):
            from ..models import CompanySettings

            CompanySettings.objects.create(company=company)

        return company

    @staticmethod
    @transaction.atomic
    def update_company(company, company_data, location_data=None):
        """Update company information"""
        # Handle location update if provided
        if location_data:
            if company.location:
                # Update existing location
                for key, value in location_data.items():
                    setattr(company.location, key, value)
                company.location.save()
            else:
                # Create new location
                from apps.geoapp.models import Location

                location = Location.objects.create(**location_data)
                company.location = location

        # Update company fields
        for key, value in company_data.items():
            if key != "location" and key != "owner":  # Don't update these directly
                setattr(company, key, value)

        company.save()
        return company

    @staticmethod
    @transaction.atomic
    def verify_company(company, verified_by):
        """Verify a company and its documents"""
        # Mark all unverified documents as verified
        now = timezone.now()
        CompanyDocument.objects.filter(company=company, is_verified=False).update(
            is_verified=True, verified_by=verified_by, verified_at=now
        )

        # Additional verification steps (if needed)
        # For example, we could update the company's subscription status

        # Send notification to company owner
        from apps.notificationsapp.services.notification_service import NotificationService

        NotificationService.send_notification(
            user_id=company.owner.id,
            notification_type="company_verified",
            data={"company_name": company.name, "verified_at": now.isoformat()},
        )

        return company

    @staticmethod
    def get_subscription_info(company):
        """Get detailed subscription information for a company"""
        try:
            # Get active subscription
            subscription = (
                Subscription.objects.filter(company=company, status="active")
                .select_related("plan")
                .first()
            )

            if not subscription:
                return {
                    "status": "inactive",
                    "message": "No active subscription found",
                    "plan": None,
                    "features": [],
                    "limitations": {
                        "max_shops": 0,
                        "max_specialists": 0,
                        "max_services": 0,
                    },
                }

            # Calculate usage
            total_shops = Shop.objects.filter(company=company).count()

            # Get all shop IDs for this company
            shop_ids = Shop.objects.filter(company=company).values_list("id", flat=True)

            # Calculate total employees and specialists
            total_employees = Employee.objects.filter(shop_id__in=shop_ids).count()
            total_specialists = Employee.objects.filter(
                shop_id__in=shop_ids, specialist__isnull=False
            ).count()

            # Get plan limitations
            plan_data = {
                "name": subscription.plan.name,
                "description": subscription.plan.description,
                "price": subscription.plan.price,
                "billing_cycle": subscription.plan.billing_cycle,
                "features": subscription.plan.features,
            }

            limitations = {
                "max_shops": subscription.plan.max_shops,
                "max_specialists": subscription.plan.max_specialists_per_shop * total_shops,
                "max_services": subscription.plan.max_services_per_shop * total_shops,
                "current_shops": total_shops,
                "current_specialists": total_specialists,
                "current_employees": total_employees,
            }

            # Calculate remaining days
            if subscription.end_date:
                today = timezone.now().date()
                remaining_days = (subscription.end_date.date() - today).days
            else:
                remaining_days = 0

            return {
                "status": subscription.status,
                "start_date": subscription.start_date,
                "end_date": subscription.end_date,
                "remaining_days": remaining_days,
                "plan": plan_data,
                "auto_renew": subscription.auto_renew,
                "limitations": limitations,
            }
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error getting subscription info: {str(e)}")

            return {
                "status": "error",
                "message": "Error retrieving subscription information",
            }

    @staticmethod
    def generate_company_statistics(company):
        """Generate comprehensive statistics for a company"""
        try:
            # Get all shops for this company
            shops = Shop.objects.filter(company=company)
            shop_ids = shops.values_list("id", flat=True)

            # Basic counts
            shop_count = shops.count()

            if shop_count == 0:
                return {
                    "shops": 0,
                    "employees": 0,
                    "specialists": 0,
                    "services": 0,
                    "bookings": 0,
                    "message": "No shops available for statistics",
                }

            # Time windows for calculations
            now = timezone.now()
            today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            last_7_days = today - timedelta(days=7)
            last_30_days = today - timedelta(days=30)

            # Employee statistics
            employee_stats = Employee.objects.filter(shop_id__in=shop_ids).aggregate(
                total=Count("id"), specialists=Count("specialist")
            )

            # Service statistics
            from apps.serviceapp.models import Service

            service_stats = Service.objects.filter(shop_id__in=shop_ids).aggregate(
                total=Count("id"), avg_price=Avg("price")
            )

            # Booking statistics
            booking_stats = Appointment.objects.filter(shop_id__in=shop_ids)

            today_bookings = booking_stats.filter(start_time__gte=today).count()

            weekly_bookings = booking_stats.filter(start_time__gte=last_7_days).count()

            monthly_bookings = booking_stats.filter(start_time__gte=last_30_days).count()

            completed_bookings = booking_stats.filter(status="completed").count()

            # Calculate no-show rate
            no_shows = booking_stats.filter(status="no_show").count()
            all_past_bookings = booking_stats.filter(
                Q(status__in=["completed", "no_show", "cancelled"]) | Q(start_time__lt=now)
            ).count()

            no_show_rate = (
                round((no_shows / all_past_bookings) * 100, 2) if all_past_bookings > 0 else 0
            )

            # Calculate popular times
            from django.db.models.functions import ExtractHour, ExtractWeekDay

            popular_hours = list(
                booking_stats.filter(status__in=["completed", "scheduled", "confirmed"])
                .annotate(hour=ExtractHour("start_time"))
                .values("hour")
                .annotate(count=Count("id"))
                .order_by("-count")[:5]
            )

            popular_days = list(
                booking_stats.filter(status__in=["completed", "scheduled", "confirmed"])
                .annotate(day=ExtractWeekDay("start_time"))
                .values("day")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            # Map day numbers to names
            day_names = {
                1: "Sunday",
                2: "Monday",
                3: "Tuesday",
                4: "Wednesday",
                5: "Thursday",
                6: "Friday",
                7: "Saturday",
            }

            for day in popular_days:
                day["day_name"] = day_names.get(day["day"], "Unknown")

            # Revenue statistics (if payment data available)
            revenue_stats = {}
            try:
                from apps.payment.models import Transaction

                revenue_stats = Transaction.objects.filter(
                    content_type__model="appointment",
                    object_id__in=booking_stats.values_list("id", flat=True),
                    status="succeeded",
                ).aggregate(
                    total_revenue=Sum("amount"),
                    monthly_revenue=Sum("amount", filter=Q(created_at__gte=last_30_days)),
                    weekly_revenue=Sum("amount", filter=Q(created_at__gte=last_7_days)),
                    today_revenue=Sum("amount", filter=Q(created_at__gte=today)),
                )
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Error calculating revenue stats: {str(e)}")

            # Review statistics
            review_stats = {}
            try:
                from apps.reviewapp.models import ShopReview, SpecialistReview

                shop_reviews = ShopReview.objects.filter(shop_id__in=shop_ids)
                specialist_reviews = SpecialistReview.objects.filter(
                    specialist__employee__shop_id__in=shop_ids
                )

                review_stats = {
                    "shop_reviews": shop_reviews.count(),
                    "shop_avg_rating": shop_reviews.aggregate(avg=Avg("rating"))["avg"] or 0,
                    "specialist_reviews": specialist_reviews.count(),
                    "specialist_avg_rating": specialist_reviews.aggregate(avg=Avg("rating"))["avg"]
                    or 0,
                }
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Error calculating review stats: {str(e)}")

            return {
                "general": {
                    "shop_count": shop_count,
                    "employee_count": employee_stats["total"],
                    "specialist_count": employee_stats["specialists"],
                    "service_count": service_stats["total"],
                    "avg_service_price": service_stats["avg_price"],
                },
                "bookings": {
                    "total": booking_stats.count(),
                    "today": today_bookings,
                    "this_week": weekly_bookings,
                    "this_month": monthly_bookings,
                    "completed": completed_bookings,
                    "no_show_rate": no_show_rate,
                },
                "revenue": revenue_stats,
                "reviews": review_stats,
                "popular_times": {"hours": popular_hours, "days": popular_days},
            }
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error generating company statistics: {str(e)}")

            return {
                "status": "error",
                "message": f"Error generating statistics: {str(e)}",
            }
