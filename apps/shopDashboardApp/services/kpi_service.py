from datetime import timedelta

from django.db.models import Avg, Count, Sum
from django.utils import timezone

from apps.shopDashboardApp.constants import DEFAULT_KPIS
from apps.shopDashboardApp.exceptions import DataAggregationException


class KPIService:
    """
    Service for calculating and retrieving Key Performance Indicators (KPIs).
    Handles various metrics related to shop performance.
    """

    def get_kpis(self, shop_id, start_date, end_date, kpi_keys=None):
        """
        Get KPI data for a shop within a date range.
        If kpi_keys is provided, only retrieve those specific KPIs.
        Otherwise, retrieve all default KPIs.
        """
        try:
            pass

            # unused_unused_shop = Shop.objects.get(id=shop_id)
            # If no specific KPIs requested, use all default KPIs
            if not kpi_keys:
                kpi_keys = [kpi["key"] for kpi in DEFAULT_KPIS]

            # Calculate comparison date range (same duration, previous period)
            period_length = (end_date - start_date).days + 1
            comparison_end = start_date - timedelta(days=1)
            comparison_start = comparison_end - timedelta(days=period_length - 1)

            # Build result list
            kpi_data = []

            for kpi_key in kpi_keys:
                kpi_info = self._get_kpi_info(kpi_key)

                if not kpi_info:
                    # Skip unknown KPIs
                    continue

                # Get current and comparison values
                current_value = self._calculate_kpi(
                    shop_id, kpi_key, start_date, end_date
                )

                comparison_value = self._calculate_kpi(
                    shop_id, kpi_key, comparison_start, comparison_end
                )

                # Calculate change percentage
                change_percentage = 0
                if (
                    comparison_value
                    and comparison_value.get("value")
                    and current_value.get("value")
                ):
                    try:
                        current_numeric = float(current_value.get("value"))
                        comparison_numeric = float(comparison_value.get("value"))

                        if comparison_numeric != 0:
                            change_percentage = (
                                (current_numeric - comparison_numeric)
                                / comparison_numeric
                            ) * 100
                        else:
                            change_percentage = 100 if current_numeric > 0 else 0
                    except (ValueError, TypeError):
                        # Handle non-numeric values gracefully
                        change_percentage = 0

                # Determine trend
                trend = "neutral"
                if change_percentage > 5:
                    trend = "up"
                elif change_percentage < -5:
                    trend = "down"

                # Format KPI data
                kpi_data.append(
                    {
                        "key": kpi_key,
                        "name": kpi_info["name"],
                        "category": kpi_info["category"],
                        "format": kpi_info["format"],
                        "value": current_value,
                        "comparison_value": comparison_value,
                        "change_percentage": round(change_percentage, 2),
                        "trend": trend,
                    }
                )

            return kpi_data

        except Exception as e:
            raise DataAggregationException(f"Error calculating KPIs: {str(e)}")

    def _get_kpi_info(self, kpi_key):
        """Get KPI metadata by key"""
        for kpi in DEFAULT_KPIS:
            if kpi["key"] == kpi_key:
                return kpi
        return None

    def _calculate_kpi(self, shop_id, kpi_key, start_date, end_date):
        """
        Calculate a specific KPI value.
        Each KPI has its own calculation logic.
        """
        if kpi_key == "total_revenue":
            return self._calculate_total_revenue(shop_id, start_date, end_date)

        elif kpi_key == "avg_revenue_per_booking":
            return self._calculate_avg_revenue_per_booking(
                shop_id, start_date, end_date
            )

        elif kpi_key == "total_bookings":
            return self._calculate_total_bookings(shop_id, start_date, end_date)

        elif kpi_key == "completed_bookings":
            return self._calculate_completed_bookings(shop_id, start_date, end_date)

        elif kpi_key == "cancellation_rate":
            return self._calculate_cancellation_rate(shop_id, start_date, end_date)

        elif kpi_key == "no_show_rate":
            return self._calculate_no_show_rate(shop_id, start_date, end_date)

        elif kpi_key == "total_customers":
            return self._calculate_total_customers(shop_id, start_date, end_date)

        elif kpi_key == "new_customers":
            return self._calculate_new_customers(shop_id, start_date, end_date)

        elif kpi_key == "returning_customer_rate":
            return self._calculate_returning_customer_rate(
                shop_id, start_date, end_date
            )

        elif kpi_key == "avg_queue_wait_time":
            return self._calculate_avg_queue_wait_time(shop_id, start_date, end_date)

        elif kpi_key == "avg_rating":
            return self._calculate_avg_rating(shop_id, start_date, end_date)

        elif kpi_key == "most_popular_service":
            return self._calculate_most_popular_service(shop_id, start_date, end_date)

        elif kpi_key == "top_specialist":
            return self._calculate_top_specialist(shop_id, start_date, end_date)

        elif kpi_key == "reel_views":
            return self._calculate_reel_views(shop_id, start_date, end_date)

        elif kpi_key == "story_views":
            return self._calculate_story_views(shop_id, start_date, end_date)

        # Default case - unknown KPI
        return {"value": None, "formatted": "N/A"}

    def _calculate_total_revenue(self, shop_id, start_date, end_date):
        """Calculate total revenue from completed bookings"""
        from apps.bookingapp.models import Appointment

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Query bookings with payment records
        bookings = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_datetime,
            start_time__lte=end_datetime,
            status__in=["completed"],
            payment_status="paid",
        )

        # Calculate total revenue
        from django.contrib.contenttypes.models import ContentType

        from apps.payment.models import Transaction

        appointment_content_type = ContentType.objects.get_for_model(Appointment)

        # Get transaction IDs from bookings
        booking_ids = bookings.values_list("id", flat=True)

        # Query transactions
        transactions = Transaction.objects.filter(
            content_type=appointment_content_type,
            object_id__in=booking_ids,
            status="succeeded",
        )

        total_revenue = transactions.aggregate(Sum("amount"))["amount__sum"] or 0

        # Format value
        return {"value": total_revenue, "formatted": f"{total_revenue:.2f} SAR"}

    def _calculate_avg_revenue_per_booking(self, shop_id, start_date, end_date):
        """Calculate average revenue per booking"""
        from apps.bookingapp.models import Appointment

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Query bookings with payment records
        bookings = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_datetime,
            start_time__lte=end_datetime,
            status__in=["completed"],
            payment_status="paid",
        )

        booking_count = bookings.count()

        if booking_count == 0:
            return {"value": 0, "formatted": "0 SAR"}

        # Calculate total revenue
        from django.contrib.contenttypes.models import ContentType

        from apps.payment.models import Transaction

        appointment_content_type = ContentType.objects.get_for_model(Appointment)

        # Get transaction IDs from bookings
        booking_ids = bookings.values_list("id", flat=True)

        # Query transactions
        transactions = Transaction.objects.filter(
            content_type=appointment_content_type,
            object_id__in=booking_ids,
            status="succeeded",
        )

        total_revenue = transactions.aggregate(Sum("amount"))["amount__sum"] or 0
        avg_revenue = total_revenue / booking_count if booking_count > 0 else 0

        # Format value
        return {"value": avg_revenue, "formatted": f"{avg_revenue:.2f} SAR"}

    def _calculate_total_bookings(self, shop_id, start_date, end_date):
        """Calculate total number of bookings in the period"""
        from apps.bookingapp.models import Appointment

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Count all bookings in the period
        booking_count = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_datetime,
            start_time__lte=end_datetime,
        ).count()

        # Format value
        return {"value": booking_count, "formatted": str(booking_count)}

    def _calculate_completed_bookings(self, shop_id, start_date, end_date):
        """Calculate number of completed bookings"""
        from apps.bookingapp.models import Appointment

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Count completed bookings
        completed_count = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_datetime,
            start_time__lte=end_datetime,
            status="completed",
        ).count()

        # Format value
        return {"value": completed_count, "formatted": str(completed_count)}

    def _calculate_cancellation_rate(self, shop_id, start_date, end_date):
        """Calculate booking cancellation rate"""
        from apps.bookingapp.models import Appointment

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Count total and cancelled bookings
        total_bookings = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_datetime,
            start_time__lte=end_datetime,
        ).count()

        cancelled_bookings = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_datetime,
            start_time__lte=end_datetime,
            status="cancelled",
        ).count()

        # Calculate rate
        cancellation_rate = (
            (cancelled_bookings / total_bookings * 100) if total_bookings > 0 else 0
        )

        # Format value
        return {"value": cancellation_rate, "formatted": f"{cancellation_rate:.1f}%"}

    def _calculate_no_show_rate(self, shop_id, start_date, end_date):
        """Calculate booking no-show rate"""
        from apps.bookingapp.models import Appointment

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Count total and no-show bookings
        total_bookings = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_datetime,
            start_time__lte=end_datetime,
        ).count()

        no_show_bookings = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_datetime,
            start_time__lte=end_datetime,
            status="no_show",
        ).count()

        # Calculate rate
        no_show_rate = (
            (no_show_bookings / total_bookings * 100) if total_bookings > 0 else 0
        )

        # Format value
        return {"value": no_show_rate, "formatted": f"{no_show_rate:.1f}%"}

    def _calculate_total_customers(self, shop_id, start_date, end_date):
        """Calculate total unique customers who made bookings"""
        from apps.bookingapp.models import Appointment

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Count unique customers
        customer_count = (
            Appointment.objects.filter(
                shop_id=shop_id,
                start_time__gte=start_datetime,
                start_time__lte=end_datetime,
            )
            .values("customer")
            .distinct()
            .count()
        )

        # Format value
        return {"value": customer_count, "formatted": str(customer_count)}

    def _calculate_new_customers(self, shop_id, start_date, end_date):
        """Calculate number of new customers (first booking in this period)"""
        from apps.bookingapp.models import Appointment

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Get all customers who booked in this period
        period_customers = (
            Appointment.objects.filter(
                shop_id=shop_id,
                start_time__gte=start_datetime,
                start_time__lte=end_datetime,
            )
            .values_list("customer", flat=True)
            .distinct()
        )

        # Get customers who had previous bookings
        previous_customers = (
            Appointment.objects.filter(
                shop_id=shop_id,
                start_time__lt=start_datetime,
                customer__in=period_customers,
            )
            .values_list("customer", flat=True)
            .distinct()
        )

        # Calculate new customers (in period but not before)
        new_customers = len(set(period_customers) - set(previous_customers))

        # Format value
        return {"value": new_customers, "formatted": str(new_customers)}

    def _calculate_returning_customer_rate(self, shop_id, start_date, end_date):
        """Calculate percentage of returning customers"""
        from apps.bookingapp.models import Appointment

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Get all customers who booked in this period
        period_customers = (
            Appointment.objects.filter(
                shop_id=shop_id,
                start_time__gte=start_datetime,
                start_time__lte=end_datetime,
            )
            .values_list("customer", flat=True)
            .distinct()
        )

        total_customers = len(period_customers)

        if total_customers == 0:
            return {"value": 0, "formatted": "0%"}

        # Get customers who had previous bookings
        previous_customers = (
            Appointment.objects.filter(
                shop_id=shop_id,
                start_time__lt=start_datetime,
                customer__in=period_customers,
            )
            .values_list("customer", flat=True)
            .distinct()
        )

        returning_customers = len(previous_customers)

        # Calculate returning rate
        returning_rate = (
            (returning_customers / total_customers * 100) if total_customers > 0 else 0
        )

        # Format value
        return {"value": returning_rate, "formatted": f"{returning_rate:.1f}%"}

    def _calculate_avg_queue_wait_time(self, shop_id, start_date, end_date):
        """Calculate average wait time for queue customers"""
        from apps.queueapp.models import QueueTicket

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Get served tickets with actual wait time
        tickets = QueueTicket.objects.filter(
            queue__shop_id=shop_id,
            join_time__gte=start_datetime,
            join_time__lte=end_datetime,
            status="served",
            actual_wait_time__isnull=False,
        )

        # Calculate average wait time
        avg_wait = (
            tickets.aggregate(Avg("actual_wait_time"))["actual_wait_time__avg"] or 0
        )

        # Format value (minutes)
        return {"value": avg_wait, "formatted": f"{avg_wait:.1f} min"}

    def _calculate_avg_rating(self, shop_id, start_date, end_date):
        """Calculate average rating from reviews"""
        from apps.reviewapp.models import ShopReview

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Get reviews in period
        reviews = ShopReview.objects.filter(
            shop_id=shop_id,
            created_at__gte=start_datetime,
            created_at__lte=end_datetime,
        )

        # Calculate average rating
        avg_rating = reviews.aggregate(Avg("rating"))["rating__avg"] or 0

        # Format value (stars)
        return {"value": avg_rating, "formatted": f"{avg_rating:.1f} ★"}

    def _calculate_most_popular_service(self, shop_id, start_date, end_date):
        """Identify the most booked service"""
        from apps.bookingapp.models import Appointment
        from apps.serviceapp.models import Service

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Get booking counts by service
        service_counts = (
            Appointment.objects.filter(
                shop_id=shop_id,
                start_time__gte=start_datetime,
                start_time__lte=end_datetime,
            )
            .values("service")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        if not service_counts:
            return {"value": None, "formatted": "N/A"}

        # Get top service
        top_service_id = service_counts[0]["service"]
        booking_count = service_counts[0]["count"]

        try:
            # Get service details
            service = Service.objects.get(id=top_service_id)

            # Format value
            return {
                "value": {
                    "id": str(service.id),
                    "name": service.name,
                    "booking_count": booking_count,
                },
                "formatted": f"{service.name} ({booking_count})",
            }
        except Service.DoesNotExist:
            return {"value": None, "formatted": "N/A"}

    def _calculate_top_specialist(self, shop_id, start_date, end_date):
        """Identify the specialist with most bookings"""
        from apps.bookingapp.models import Appointment
        from apps.specialistsapp.models import Specialist

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Get booking counts by specialist
        specialist_counts = (
            Appointment.objects.filter(
                shop_id=shop_id,
                start_time__gte=start_datetime,
                start_time__lte=end_datetime,
            )
            .values("specialist")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        if not specialist_counts:
            return {"value": None, "formatted": "N/A"}

        # Get top specialist
        top_specialist_id = specialist_counts[0]["specialist"]
        booking_count = specialist_counts[0]["count"]

        try:
            # Get specialist details
            specialist = Specialist.objects.get(id=top_specialist_id)

            # Format value
            return {
                "value": {
                    "id": str(specialist.id),
                    "name": f"{specialist.employee.first_name} {specialist.employee.last_name}",
                    "booking_count": booking_count,
                },
                "formatted": f"{specialist.employee.first_name} {specialist.employee.last_name} ({booking_count})",
            }
        except Specialist.DoesNotExist:
            return {"value": None, "formatted": "N/A"}

    def _calculate_reel_views(self, shop_id, start_date, end_date):
        """Calculate total reel views"""
        from apps.reelsapp.models import Reel, ReelView

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Get shop reels
        shop_reels = Reel.objects.filter(shop_id=shop_id)

        if not shop_reels.exists():
            return {"value": 0, "formatted": "0"}

        # Count views
        view_count = ReelView.objects.filter(
            reel__in=shop_reels,
            viewed_at__gte=start_datetime,
            viewed_at__lte=end_datetime,
        ).count()

        # Format value
        return {"value": view_count, "formatted": str(view_count)}

    def _calculate_story_views(self, shop_id, start_date, end_date):
        """Calculate total story views"""
        from apps.storiesapp.models import Story, StoryView

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Get shop stories
        shop_stories = Story.objects.filter(shop_id=shop_id)

        if not shop_stories.exists():
            return {"value": 0, "formatted": "0"}

        # Count views
        view_count = StoryView.objects.filter(
            story__in=shop_stories,
            viewed_at__gte=start_datetime,
            viewed_at__lte=end_datetime,
        ).count()

        # Format value
        return {"value": view_count, "formatted": str(view_count)}
