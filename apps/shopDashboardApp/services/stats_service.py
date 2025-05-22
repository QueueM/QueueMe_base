from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDay, TruncHour, TruncMonth, TruncWeek
from django.utils import timezone

from apps.shopDashboardApp.exceptions import (
    DataAggregationException,
    InvalidChartTypeException,
)


class StatsService:
    """
    Service for generating statistical data for charts and tables.
    Handles data aggregation and transformation for visualization.
    """

    def get_chart_data(
        self, shop_id, chart_type, data_source, start_date, end_date, config=None
    ):
        """
        Get chart data for visualization.

        Args:
            shop_id: Shop ID
            chart_type: Type of chart (line, bar, pie, etc.)
            data_source: Data source identifier
            start_date: Start date for data
            end_date: End date for data
            config: Optional configuration parameters

        Returns:
            Dictionary with chart data (title, type, labels, datasets, options)
        """
        try:
            # Define the chart data fetcher based on data source
            if data_source == "revenue_trend":
                return self._get_revenue_trend_chart(
                    shop_id, chart_type, start_date, end_date, config
                )

            elif data_source == "bookings_by_service":
                return self._get_bookings_by_service_chart(
                    shop_id, chart_type, start_date, end_date, config
                )

            elif data_source == "bookings_by_day":
                return self._get_bookings_by_day_chart(
                    shop_id, chart_type, start_date, end_date, config
                )

            elif data_source == "booking_status":
                return self._get_booking_status_chart(
                    shop_id, chart_type, start_date, end_date, config
                )

            elif data_source == "specialist_performance":
                return self._get_specialist_performance_chart(
                    shop_id, chart_type, start_date, end_date, config
                )

            elif data_source == "customer_retention":
                return self._get_customer_retention_chart(
                    shop_id, chart_type, start_date, end_date, config
                )

            elif data_source == "queue_wait_times":
                return self._get_queue_wait_times_chart(
                    shop_id, chart_type, start_date, end_date, config
                )

            elif data_source == "rating_distribution":
                return self._get_rating_distribution_chart(
                    shop_id, chart_type, start_date, end_date, config
                )

            else:
                # Unknown data source
                raise DataAggregationException(
                    f"Unknown chart data source: {data_source}"
                )

        except Exception as e:
            raise DataAggregationException(f"Error generating chart data: {str(e)}")

    def get_table_data(
        self,
        shop_id,
        data_source,
        start_date,
        end_date,
        page=1,
        page_size=10,
        config=None,
    ):
        """
        Get tabular data for the dashboard.

        Args:
            shop_id: Shop ID
            data_source: Data source identifier
            start_date: Start date for data
            end_date: End date for data
            page: Page number for pagination
            page_size: Items per page
            config: Optional configuration parameters

        Returns:
            Dictionary with table data (title, columns, rows, pagination)
        """
        try:
            # Define the table data fetcher based on data source
            if data_source == "recent_bookings":
                return self._get_recent_bookings_table(
                    shop_id, start_date, end_date, page, page_size, config
                )

            elif data_source == "top_services":
                return self._get_top_services_table(
                    shop_id, start_date, end_date, page, page_size, config
                )

            elif data_source == "top_customers":
                return self._get_top_customers_table(
                    shop_id, start_date, end_date, page, page_size, config
                )

            elif data_source == "specialist_table":
                return self._get_specialist_table(
                    shop_id, start_date, end_date, page, page_size, config
                )

            elif data_source == "recent_reviews":
                return self._get_recent_reviews_table(
                    shop_id, start_date, end_date, page, page_size, config
                )

            else:
                # Unknown data source
                raise DataAggregationException(
                    f"Unknown table data source: {data_source}"
                )

        except Exception as e:
            raise DataAggregationException(f"Error generating table data: {str(e)}")

    def _get_date_range_granularity(self, start_date, end_date):
        """Determine appropriate granularity based on date range"""
        days_diff = (end_date - start_date).days

        if days_diff <= 1:
            return "hourly"
        elif days_diff <= 31:
            return "daily"
        elif days_diff <= 90:
            return "weekly"
        elif days_diff <= 365:
            return "monthly"
        else:
            return "quarterly"

    def _get_date_trunc_function(self, granularity):
        """Get the appropriate date truncation function"""
        if granularity == "hourly":
            return TruncHour
        elif granularity == "daily":
            return TruncDay
        elif granularity == "weekly":
            return TruncWeek
        elif granularity == "monthly":
            return TruncMonth
        else:
            # Default to daily
            return TruncDay

    def _get_revenue_trend_chart(
        self, shop_id, chart_type, start_date, end_date, config=None
    ):
        """Generate revenue trend chart data"""
        from django.contrib.contenttypes.models import ContentType

        from apps.bookingapp.models import Appointment
        from apps.payment.models import Transaction

        if chart_type not in ["line", "bar"]:
            raise InvalidChartTypeException(
                "Revenue trend chart requires line or bar chart type."
            )

        # Determine granularity based on date range
        granularity = self._get_date_range_granularity(start_date, end_date)
        trunc_func = self._get_date_trunc_function(granularity)

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Get completed bookings with payments
        bookings = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_datetime,
            start_time__lte=end_datetime,
            status="completed",
            payment_status="paid",
        )

        # Get booking IDs
        booking_ids = bookings.values_list("id", flat=True)

        # Get transactions for these bookings
        appointment_content_type = ContentType.objects.get_for_model(Appointment)
        transactions = Transaction.objects.filter(
            content_type=appointment_content_type,
            object_id__in=booking_ids,
            status="succeeded",
        )

        # Aggregate revenue by date
        revenue_by_date = {}

        for transaction in transactions:
            # Get booking date
            booking = bookings.get(id=transaction.object_id)
            date_key = trunc_func(booking.start_time).strftime("%Y-%m-%d %H:%M:%S")

            # Add revenue to date
            if date_key in revenue_by_date:
                revenue_by_date[date_key] += float(transaction.amount)
            else:
                revenue_by_date[date_key] = float(transaction.amount)

        # Sort dates
        sorted_dates = sorted(revenue_by_date.keys())

        # Prepare chart data
        labels = []
        data = []

        for date_key in sorted_dates:
            # Format label based on granularity
            if granularity == "hourly":
                label = timezone.datetime.strptime(
                    date_key, "%Y-%m-%d %H:%M:%S"
                ).strftime("%I %p")
            elif granularity == "daily":
                label = timezone.datetime.strptime(
                    date_key, "%Y-%m-%d %H:%M:%S"
                ).strftime("%b %d")
            elif granularity == "weekly":
                label = timezone.datetime.strptime(
                    date_key, "%Y-%m-%d %H:%M:%S"
                ).strftime("Week %W")
            elif granularity == "monthly":
                label = timezone.datetime.strptime(
                    date_key, "%Y-%m-%d %H:%M:%S"
                ).strftime("%b %Y")
            else:
                label = date_key

            labels.append(label)
            data.append(revenue_by_date[date_key])

        # Prepare dataset
        datasets = [
            {
                "label": "Revenue (SAR)",
                "data": data,
                "backgroundColor": "rgba(75, 192, 192, 0.2)",
                "borderColor": "rgba(75, 192, 192, 1)",
                "borderWidth": 1,
            }
        ]

        # Prepare chart options
        options = {
            "scales": {
                "y": {
                    "beginAtZero": True,
                    "title": {"display": True, "text": "Revenue (SAR)"},
                },
                "x": {
                    "title": {
                        "display": True,
                        "text": self._get_granularity_label(granularity),
                    }
                },
            }
        }

        return {
            "title": "Revenue Trend",
            "chart_type": chart_type,
            "labels": labels,
            "datasets": datasets,
            "options": options,
        }

    def _get_bookings_by_service_chart(
        self, shop_id, chart_type, start_date, end_date, config=None
    ):
        """Generate chart showing bookings distribution by service"""
        from apps.bookingapp.models import Appointment
        from apps.serviceapp.models import Service

        if chart_type not in ["pie", "doughnut", "bar"]:
            raise InvalidChartTypeException(
                "Bookings by service chart requires pie, doughnut, or bar chart type."
            )

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Count bookings by service
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

        # Get service details
        services = Service.objects.filter(
            id__in=[item["service"] for item in service_counts]
        )
        service_dict = {str(service.id): service.name for service in services}

        # Prepare chart data
        labels = []
        data = []
        background_colors = []

        # Color palette for services
        colors = [
            "rgba(255, 99, 132, 0.8)",
            "rgba(54, 162, 235, 0.8)",
            "rgba(255, 206, 86, 0.8)",
            "rgba(75, 192, 192, 0.8)",
            "rgba(153, 102, 255, 0.8)",
            "rgba(255, 159, 64, 0.8)",
            "rgba(255, 99, 132, 0.8)",
            "rgba(54, 162, 235, 0.8)",
            "rgba(255, 206, 86, 0.8)",
            "rgba(75, 192, 192, 0.8)",
        ]

        # Limit to top 10 services for readability
        for i, item in enumerate(service_counts[:10]):
            service_id = item["service"]
            service_name = service_dict.get(str(service_id), f"Service {service_id}")
            count = item["count"]

            labels.append(service_name)
            data.append(count)
            background_colors.append(colors[i % len(colors)])

        # If there are more services, add an "Others" category
        if len(service_counts) > 10:
            other_count = sum(item["count"] for item in service_counts[10:])
            labels.append("Others")
            data.append(other_count)
            background_colors.append("rgba(128, 128, 128, 0.8)")

        # Prepare dataset
        datasets = [
            {
                "label": "Bookings",
                "data": data,
                "backgroundColor": background_colors,
                "borderColor": "rgba(255, 255, 255, 1)",
                "borderWidth": 1,
            }
        ]

        # Prepare chart options
        options = {
            "responsive": True,
            "plugins": {
                "legend": {
                    "position": "right",
                },
                "title": {"display": True, "text": "Bookings by Service"},
            },
        }

        if chart_type == "bar":
            options["scales"] = {
                "y": {
                    "beginAtZero": True,
                    "title": {"display": True, "text": "Number of Bookings"},
                }
            }

        return {
            "title": "Bookings by Service",
            "chart_type": chart_type,
            "labels": labels,
            "datasets": datasets,
            "options": options,
        }

    def _get_bookings_by_day_chart(
        self, shop_id, chart_type, start_date, end_date, config=None
    ):
        """Generate chart showing bookings by day of week"""
        from apps.bookingapp.models import Appointment

        if chart_type not in ["bar", "line"]:
            raise InvalidChartTypeException(
                "Bookings by day chart requires bar or line chart type."
            )

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Days of week
        days = [
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ]
        day_counts = [0] * 7

        # Count bookings by day of week
        bookings = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_datetime,
            start_time__lte=end_datetime,
        )

        for booking in bookings:
            # Get day of week index (0 = Monday, 6 = Sunday in datetime, but we want 0 = Sunday)
            day_idx = (booking.start_time.weekday() + 1) % 7
            day_counts[day_idx] += 1

        # Prepare dataset
        datasets = [
            {
                "label": "Bookings",
                "data": day_counts,
                "backgroundColor": "rgba(54, 162, 235, 0.5)",
                "borderColor": "rgba(54, 162, 235, 1)",
                "borderWidth": 1,
            }
        ]

        # Prepare chart options
        options = {
            "scales": {
                "y": {
                    "beginAtZero": True,
                    "title": {"display": True, "text": "Number of Bookings"},
                }
            }
        }

        return {
            "title": "Bookings by Day of Week",
            "chart_type": chart_type,
            "labels": days,
            "datasets": datasets,
            "options": options,
        }

    def _get_booking_status_chart(
        self, shop_id, chart_type, start_date, end_date, config=None
    ):
        """Generate chart showing booking status distribution"""
        from apps.bookingapp.models import Appointment

        if chart_type not in ["pie", "doughnut", "bar"]:
            raise InvalidChartTypeException(
                "Booking status chart requires pie, doughnut, or bar chart type."
            )

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Count bookings by status
        status_counts = (
            Appointment.objects.filter(
                shop_id=shop_id,
                start_time__gte=start_datetime,
                start_time__lte=end_datetime,
            )
            .values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )

        # Status labels mapping
        status_labels = {
            "scheduled": "Scheduled",
            "confirmed": "Confirmed",
            "in_progress": "In Progress",
            "completed": "Completed",
            "cancelled": "Cancelled",
            "no_show": "No Show",
        }

        # Status colors mapping
        status_colors = {
            "scheduled": "rgba(54, 162, 235, 0.8)",  # Blue
            "confirmed": "rgba(75, 192, 192, 0.8)",  # Teal
            "in_progress": "rgba(255, 206, 86, 0.8)",  # Yellow
            "completed": "rgba(75, 192, 192, 0.8)",  # Green
            "cancelled": "rgba(255, 99, 132, 0.8)",  # Red
            "no_show": "rgba(153, 102, 255, 0.8)",  # Purple
        }

        # Prepare chart data
        labels = []
        data = []
        background_colors = []

        # Create a dictionary to store counts by status
        status_data = {status: 0 for status in status_labels.keys()}

        # Fill in actual counts
        for item in status_counts:
            status = item["status"]
            status_data[status] = item["count"]

        # Build labels, data, and colors arrays
        for status, label in status_labels.items():
            labels.append(label)
            data.append(status_data[status])
            background_colors.append(status_colors[status])

        # Prepare dataset
        datasets = [
            {
                "label": "Bookings",
                "data": data,
                "backgroundColor": background_colors,
                "borderColor": "rgba(255, 255, 255, 1)",
                "borderWidth": 1,
            }
        ]

        # Prepare chart options
        options = {
            "responsive": True,
            "plugins": {
                "legend": {
                    "position": "right",
                },
                "title": {"display": True, "text": "Booking Status Distribution"},
            },
        }

        if chart_type == "bar":
            options["scales"] = {
                "y": {
                    "beginAtZero": True,
                    "title": {"display": True, "text": "Number of Bookings"},
                }
            }

        return {
            "title": "Booking Status Distribution",
            "chart_type": chart_type,
            "labels": labels,
            "datasets": datasets,
            "options": options,
        }

    def _get_specialist_performance_chart(
        self, shop_id, chart_type, start_date, end_date, config=None
    ):
        """Generate chart showing booking counts by specialist"""
        from apps.bookingapp.models import Appointment
        from apps.specialistsapp.models import Specialist

        if chart_type not in ["bar", "horizontalBar"]:
            raise InvalidChartTypeException(
                "Specialist performance chart requires bar chart type."
            )

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Count bookings by specialist
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

        # Get specialist details
        specialists = Specialist.objects.filter(
            id__in=[
                item["specialist"] for item in specialist_counts if item["specialist"]
            ]
        )
        specialist_dict = {}

        for specialist in specialists:
            name = f"{specialist.employee.first_name} {specialist.employee.last_name}"
            specialist_dict[str(specialist.id)] = name

        # Prepare chart data
        labels = []
        booking_counts = []
        completed_counts = []

        # Limit to top 10 specialists for readability
        for item in specialist_counts[:10]:
            if not item["specialist"]:
                continue

            specialist_id = item["specialist"]
            specialist_name = specialist_dict.get(
                str(specialist_id), f"Specialist {specialist_id}"
            )
            count = item["count"]

            # Get completed bookings count
            completed_count = Appointment.objects.filter(
                shop_id=shop_id,
                specialist_id=specialist_id,
                start_time__gte=start_datetime,
                start_time__lte=end_datetime,
                status="completed",
            ).count()

            labels.append(specialist_name)
            booking_counts.append(count)
            completed_counts.append(completed_count)

        # Prepare datasets
        datasets = [
            {
                "label": "Total Bookings",
                "data": booking_counts,
                "backgroundColor": "rgba(54, 162, 235, 0.7)",
                "borderColor": "rgba(54, 162, 235, 1)",
                "borderWidth": 1,
            },
            {
                "label": "Completed",
                "data": completed_counts,
                "backgroundColor": "rgba(75, 192, 192, 0.7)",
                "borderColor": "rgba(75, 192, 192, 1)",
                "borderWidth": 1,
            },
        ]

        # Prepare chart options
        options = {
            "indexAxis": "y" if chart_type == "horizontalBar" else "x",
            "scales": {
                "y": {
                    "beginAtZero": True,
                    "title": {"display": True, "text": "Number of Bookings"},
                }
            },
        }

        return {
            "title": "Specialist Performance",
            "chart_type": "bar",  # Always use 'bar' type since 'horizontalBar' is deprecated in Chart.js v3
            "labels": labels,
            "datasets": datasets,
            "options": options,
        }

    def _get_customer_retention_chart(
        self, shop_id, chart_type, start_date, end_date, config=None
    ):
        """Generate chart showing new vs. returning customers over time"""
        from apps.bookingapp.models import Appointment

        if chart_type not in ["line", "bar"]:
            raise InvalidChartTypeException(
                "Customer retention chart requires line or bar chart type."
            )

        # Determine granularity based on date range
        granularity = self._get_date_range_granularity(start_date, end_date)
        trunc_func = self._get_date_trunc_function(granularity)

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Get all bookings in period
        bookings = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_datetime,
            start_time__lte=end_datetime,
        )

        # Track new and returning customers by date
        new_customers_by_date = {}
        returning_customers_by_date = {}

        # Create a set of all customers who have booked before the start date
        previous_customers = set(
            Appointment.objects.filter(
                shop_id=shop_id, start_time__lt=start_datetime
            ).values_list("customer_id", flat=True)
        )

        # Create a dictionary to track when each customer first booked in the period
        first_booking_date = {}

        # Group bookings by date and customer
        for booking in bookings:
            date_key = trunc_func(booking.start_time).strftime("%Y-%m-%d %H:%M:%S")
            customer_id = str(booking.customer_id)

            # Initialize the date in dictionaries if needed
            if date_key not in new_customers_by_date:
                new_customers_by_date[date_key] = 0
                returning_customers_by_date[date_key] = 0

            # Check if this is a returning customer from before the period
            if customer_id in previous_customers:
                returning_customers_by_date[date_key] += 1
                continue

            # Check if this customer has already booked in the period
            if customer_id in first_booking_date:
                # If they booked before on a different date, they're returning
                if first_booking_date[customer_id] != date_key:
                    returning_customers_by_date[date_key] += 1
                # If they booked before on the same date, don't count again
            else:
                # This is a new customer for the period
                first_booking_date[customer_id] = date_key
                new_customers_by_date[date_key] += 1

        # Sort dates
        sorted_dates = sorted(
            list(
                set(
                    list(new_customers_by_date.keys())
                    + list(returning_customers_by_date.keys())
                )
            )
        )

        # Prepare chart data
        labels = []
        new_data = []
        returning_data = []

        for date_key in sorted_dates:
            # Format label based on granularity
            if granularity == "hourly":
                label = timezone.datetime.strptime(
                    date_key, "%Y-%m-%d %H:%M:%S"
                ).strftime("%I %p")
            elif granularity == "daily":
                label = timezone.datetime.strptime(
                    date_key, "%Y-%m-%d %H:%M:%S"
                ).strftime("%b %d")
            elif granularity == "weekly":
                label = timezone.datetime.strptime(
                    date_key, "%Y-%m-%d %H:%M:%S"
                ).strftime("Week %W")
            elif granularity == "monthly":
                label = timezone.datetime.strptime(
                    date_key, "%Y-%m-%d %H:%M:%S"
                ).strftime("%b %Y")
            else:
                label = date_key

            labels.append(label)
            new_data.append(new_customers_by_date.get(date_key, 0))
            returning_data.append(returning_customers_by_date.get(date_key, 0))

        # Prepare datasets
        datasets = [
            {
                "label": "New Customers",
                "data": new_data,
                "backgroundColor": "rgba(54, 162, 235, 0.5)",
                "borderColor": "rgba(54, 162, 235, 1)",
                "borderWidth": 1,
            },
            {
                "label": "Returning Customers",
                "data": returning_data,
                "backgroundColor": "rgba(75, 192, 192, 0.5)",
                "borderColor": "rgba(75, 192, 192, 1)",
                "borderWidth": 1,
            },
        ]

        # Prepare chart options
        options = {
            "scales": {
                "y": {
                    "beginAtZero": True,
                    "title": {"display": True, "text": "Number of Customers"},
                },
                "x": {
                    "title": {
                        "display": True,
                        "text": self._get_granularity_label(granularity),
                    }
                },
            }
        }

        return {
            "title": "New vs. Returning Customers",
            "chart_type": chart_type,
            "labels": labels,
            "datasets": datasets,
            "options": options,
        }

    def _get_queue_wait_times_chart(
        self, shop_id, chart_type, start_date, end_date, config=None
    ):
        """Generate chart showing average queue wait times"""
        from apps.queueapp.models import QueueTicket

        if chart_type not in ["line", "bar"]:
            raise InvalidChartTypeException(
                "Queue wait times chart requires line or bar chart type."
            )

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

        # Group by hour of day
        wait_times_by_hour = {}
        counts_by_hour = {}

        for ticket in tickets:
            hour = ticket.join_time.hour

            if hour not in wait_times_by_hour:
                wait_times_by_hour[hour] = 0
                counts_by_hour[hour] = 0

            wait_times_by_hour[hour] += ticket.actual_wait_time
            counts_by_hour[hour] += 1

        # Calculate average wait time by hour
        avg_wait_by_hour = {}

        for hour in wait_times_by_hour:
            if counts_by_hour[hour] > 0:
                avg_wait_by_hour[hour] = wait_times_by_hour[hour] / counts_by_hour[hour]
            else:
                avg_wait_by_hour[hour] = 0

        # Prepare chart data
        labels = []
        data = []

        # Create a list of all hours (0-23)
        all_hours = list(range(24))

        for hour in all_hours:
            # Format hour label (12-hour format with AM/PM)
            if hour == 0:
                label = "12 AM"
            elif hour < 12:
                label = f"{hour} AM"
            elif hour == 12:
                label = "12 PM"
            else:
                label = f"{hour - 12} PM"

            labels.append(label)
            data.append(avg_wait_by_hour.get(hour, 0))

        # Prepare dataset
        datasets = [
            {
                "label": "Average Wait Time (minutes)",
                "data": data,
                "backgroundColor": "rgba(255, 159, 64, 0.5)",
                "borderColor": "rgba(255, 159, 64, 1)",
                "borderWidth": 1,
            }
        ]

        # Prepare chart options
        options = {
            "scales": {
                "y": {
                    "beginAtZero": True,
                    "title": {"display": True, "text": "Wait Time (minutes)"},
                },
                "x": {"title": {"display": True, "text": "Hour of Day"}},
            }
        }

        return {
            "title": "Average Queue Wait Time by Hour",
            "chart_type": chart_type,
            "labels": labels,
            "datasets": datasets,
            "options": options,
        }

    def _get_rating_distribution_chart(
        self, shop_id, chart_type, start_date, end_date, config=None
    ):
        """Generate chart showing distribution of ratings"""
        from apps.reviewapp.models import ShopReview

        if chart_type not in ["bar", "pie", "doughnut"]:
            raise InvalidChartTypeException(
                "Rating distribution chart requires bar, pie, or doughnut chart type."
            )

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Count reviews by rating
        rating_counts = (
            ShopReview.objects.filter(
                shop_id=shop_id,
                created_at__gte=start_datetime,
                created_at__lte=end_datetime,
            )
            .values("rating")
            .annotate(count=Count("id"))
            .order_by("rating")
        )

        # Create a dictionary with all possible ratings (1-5)
        all_ratings = {i: 0 for i in range(1, 6)}

        # Fill in actual counts
        for item in rating_counts:
            rating = item["rating"]
            all_ratings[rating] = item["count"]

        # Prepare chart data
        labels = ["1 ★", "2 ★", "3 ★", "4 ★", "5 ★"]
        data = [all_ratings[i] for i in range(1, 6)]

        # Colors for ratings (red to green)
        colors = [
            "rgba(255, 99, 132, 0.7)",  # 1 star - Red
            "rgba(255, 159, 64, 0.7)",  # 2 stars - Orange
            "rgba(255, 205, 86, 0.7)",  # 3 stars - Yellow
            "rgba(75, 192, 192, 0.7)",  # 4 stars - Teal
            "rgba(54, 162, 235, 0.7)",  # 5 stars - Blue
        ]

        # Prepare dataset
        datasets = [
            {
                "label": "Number of Reviews",
                "data": data,
                "backgroundColor": colors,
                "borderColor": colors,
                "borderWidth": 1,
            }
        ]

        # Prepare chart options
        options = {
            "responsive": True,
            "plugins": {
                "legend": {
                    "position": "right",
                    "display": chart_type in ["pie", "doughnut"],
                },
                "title": {"display": True, "text": "Rating Distribution"},
            },
        }

        if chart_type == "bar":
            options["scales"] = {
                "y": {
                    "beginAtZero": True,
                    "title": {"display": True, "text": "Number of Reviews"},
                }
            }

        return {
            "title": "Rating Distribution",
            "chart_type": chart_type,
            "labels": labels,
            "datasets": datasets,
            "options": options,
        }

    def _get_recent_bookings_table(
        self, shop_id, start_date, end_date, page=1, page_size=10, config=None
    ):
        """Generate table with recent bookings"""
        from apps.bookingapp.models import Appointment

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Get bookings
        bookings = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_datetime,
            start_time__lte=end_datetime,
        ).order_by("-start_time")

        # Total count for pagination
        total_count = bookings.count()

        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        bookings_page = bookings[start_idx:end_idx]

        # Define columns
        columns = [
            {"field": "id", "headerName": "ID", "width": 100},
            {"field": "customer", "headerName": "Customer", "width": 150},
            {"field": "service", "headerName": "Service", "width": 200},
            {"field": "specialist", "headerName": "Specialist", "width": 150},
            {"field": "start_time", "headerName": "Date & Time", "width": 150},
            {"field": "status", "headerName": "Status", "width": 120},
            {"field": "payment_status", "headerName": "Payment", "width": 120},
        ]

        # Prepare rows
        rows = []

        for booking in bookings_page:
            # Format customer name
            customer_name = booking.customer.phone_number

            # Try to get a more friendly name if available
            try:
                from apps.customersapp.models import Customer

                customer_profile = Customer.objects.get(user=booking.customer)
                if customer_profile.first_name or customer_profile.last_name:
                    customer_name = f"{customer_profile.first_name} {customer_profile.last_name}".strip()
            except Exception:
                pass

            # Format specialist name
            specialist_name = ""
            if booking.specialist:
                specialist_name = f"{booking.specialist.employee.first_name} {booking.specialist.employee.last_name}"

            # Format status with proper capitalization
            status_formatted = booking.status.replace("_", " ").title()
            payment_status_formatted = booking.payment_status.replace("_", " ").title()

            # Create row
            row = [
                str(booking.id),
                customer_name,
                booking.service.name,
                specialist_name,
                booking.start_time.strftime("%Y-%m-%d %I:%M %p"),
                status_formatted,
                payment_status_formatted,
            ]

            rows.append(row)

        return {
            "title": "Recent Bookings",
            "columns": columns,
            "rows": rows,
            "total_rows": total_count,
            "page": page,
            "page_size": page_size,
        }

    def _get_top_services_table(
        self, shop_id, start_date, end_date, page=1, page_size=10, config=None
    ):
        """Generate table with top services by booking count"""
        from apps.bookingapp.models import Appointment
        from apps.serviceapp.models import Service

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Count bookings by service
        service_stats = (
            Appointment.objects.filter(
                shop_id=shop_id,
                start_time__gte=start_datetime,
                start_time__lte=end_datetime,
            )
            .values("service")
            .annotate(
                booking_count=Count("id"),
                completed_count=Count("id", filter=Q(status="completed")),
                cancelled_count=Count("id", filter=Q(status="cancelled")),
            )
            .order_by("-booking_count")
        )

        # Total count for pagination
        total_count = len(service_stats)

        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        service_stats_page = service_stats[start_idx:end_idx]

        # Get service details
        service_ids = [item["service"] for item in service_stats_page]
        services = Service.objects.filter(id__in=service_ids)
        service_dict = {str(service.id): service for service in services}

        # Define columns
        columns = [
            {"field": "service", "headerName": "Service", "width": 250},
            {"field": "category", "headerName": "Category", "width": 150},
            {"field": "price", "headerName": "Price (SAR)", "width": 120},
            {"field": "bookings", "headerName": "Total Bookings", "width": 150},
            {"field": "completed", "headerName": "Completed", "width": 120},
            {"field": "cancelled", "headerName": "Cancelled", "width": 120},
            {"field": "completion_rate", "headerName": "Completion Rate", "width": 150},
        ]

        # Prepare rows
        rows = []

        for stat in service_stats_page:
            service_id = stat["service"]
            service = service_dict.get(str(service_id))

            if not service:
                continue

            # Calculate completion rate
            booking_count = stat["booking_count"]
            completed_count = stat["completed_count"]
            completion_rate = (
                (completed_count / booking_count * 100) if booking_count > 0 else 0
            )

            # Get category name
            category_name = service.category.name if service.category else "N/A"

            # Create row
            row = [
                service.name,
                category_name,
                str(service.price),
                str(booking_count),
                str(completed_count),
                str(stat["cancelled_count"]),
                f"{completion_rate:.1f}%",
            ]

            rows.append(row)

        return {
            "title": "Top Services",
            "columns": columns,
            "rows": rows,
            "total_rows": total_count,
            "page": page,
            "page_size": page_size,
        }

    def _get_top_customers_table(
        self, shop_id, start_date, end_date, page=1, page_size=10, config=None
    ):
        """Generate table with top customers by booking count"""
        from apps.authapp.models import User
        from apps.bookingapp.models import Appointment

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Count bookings by customer
        customer_stats = (
            Appointment.objects.filter(
                shop_id=shop_id,
                start_time__gte=start_datetime,
                start_time__lte=end_datetime,
            )
            .values("customer")
            .annotate(
                booking_count=Count("id"),
                completed_count=Count("id", filter=Q(status="completed")),
                cancelled_count=Count("id", filter=Q(status="cancelled")),
            )
            .order_by("-booking_count")
        )

        # Total count for pagination
        total_count = len(customer_stats)

        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        customer_stats_page = customer_stats[start_idx:end_idx]

        # Get customer details
        customer_ids = [item["customer"] for item in customer_stats_page]
        customers = User.objects.filter(id__in=customer_ids)
        customer_dict = {str(customer.id): customer for customer in customers}

        # Try to get additional customer profile info
        customer_profiles = {}
        try:
            from apps.customersapp.models import Customer

            profiles = Customer.objects.filter(user_id__in=customer_ids)
            customer_profiles = {str(profile.user_id): profile for profile in profiles}
        except Exception:
            pass

        # Define columns
        columns = [
            {"field": "customer", "headerName": "Customer", "width": 200},
            {"field": "phone", "headerName": "Phone", "width": 150},
            {"field": "bookings", "headerName": "Total Bookings", "width": 150},
            {"field": "completed", "headerName": "Completed", "width": 120},
            {"field": "cancelled", "headerName": "Cancelled", "width": 120},
            {"field": "completion_rate", "headerName": "Completion Rate", "width": 150},
            {"field": "first_booking", "headerName": "First Booking", "width": 150},
        ]

        # Prepare rows
        rows = []

        for stat in customer_stats_page:
            customer_id = stat["customer"]
            customer = customer_dict.get(str(customer_id))

            if not customer:
                continue

            # Calculate completion rate
            booking_count = stat["booking_count"]
            completed_count = stat["completed_count"]
            completion_rate = (
                (completed_count / booking_count * 100) if booking_count > 0 else 0
            )

            # Get customer name
            customer_name = customer.phone_number

            # Try to get more friendly name from profile
            profile = customer_profiles.get(str(customer_id))
            if profile and (profile.first_name or profile.last_name):
                customer_name = f"{profile.first_name} {profile.last_name}".strip()

            # Get first booking date
            first_booking = (
                Appointment.objects.filter(shop_id=shop_id, customer_id=customer_id)
                .order_by("start_time")
                .first()
            )

            first_booking_date = (
                first_booking.start_time.strftime("%Y-%m-%d")
                if first_booking
                else "N/A"
            )

            # Create row
            row = [
                customer_name,
                customer.phone_number,
                str(booking_count),
                str(completed_count),
                str(stat["cancelled_count"]),
                f"{completion_rate:.1f}%",
                first_booking_date,
            ]

            rows.append(row)

        return {
            "title": "Top Customers",
            "columns": columns,
            "rows": rows,
            "total_rows": total_count,
            "page": page,
            "page_size": page_size,
        }

    def _get_specialist_table(
        self, shop_id, start_date, end_date, page=1, page_size=10, config=None
    ):
        """Generate table with specialist performance metrics"""
        from apps.bookingapp.models import Appointment
        from apps.reviewapp.models import SpecialistReview
        from apps.specialistsapp.models import Specialist

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Get all specialists for the shop
        specialists = Specialist.objects.filter(employee__shop_id=shop_id)

        # Total count for pagination
        total_count = specialists.count()

        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        specialists_page = specialists[start_idx:end_idx]

        # Define columns
        columns = [
            {"field": "specialist", "headerName": "Specialist", "width": 200},
            {"field": "bookings", "headerName": "Total Bookings", "width": 150},
            {"field": "completed", "headerName": "Completed", "width": 120},
            {"field": "cancelled", "headerName": "Cancelled", "width": 120},
            {"field": "no_show", "headerName": "No Show", "width": 120},
            {"field": "completion_rate", "headerName": "Completion Rate", "width": 150},
            {"field": "avg_rating", "headerName": "Avg. Rating", "width": 120},
        ]

        # Prepare rows
        rows = []

        for specialist in specialists_page:
            # Get booking stats
            bookings = Appointment.objects.filter(
                shop_id=shop_id,
                specialist=specialist,
                start_time__gte=start_datetime,
                start_time__lte=end_datetime,
            )

            booking_count = bookings.count()
            completed_count = bookings.filter(status="completed").count()
            cancelled_count = bookings.filter(status="cancelled").count()
            no_show_count = bookings.filter(status="no_show").count()

            # Calculate completion rate
            completion_rate = (
                (completed_count / booking_count * 100) if booking_count > 0 else 0
            )

            # Get average rating
            avg_rating = (
                SpecialistReview.objects.filter(
                    specialist=specialist,
                    created_at__gte=start_datetime,
                    created_at__lte=end_datetime,
                ).aggregate(Avg("rating"))["rating__avg"]
                or 0
            )

            # Format specialist name
            specialist_name = (
                f"{specialist.employee.first_name} {specialist.employee.last_name}"
            )

            # Create row
            row = [
                specialist_name,
                str(booking_count),
                str(completed_count),
                str(cancelled_count),
                str(no_show_count),
                f"{completion_rate:.1f}%",
                f"{avg_rating:.1f} ★",
            ]

            rows.append(row)

        return {
            "title": "Specialist Performance",
            "columns": columns,
            "rows": rows,
            "total_rows": total_count,
            "page": page,
            "page_size": page_size,
        }

    def _get_recent_reviews_table(
        self, shop_id, start_date, end_date, page=1, page_size=10, config=None
    ):
        """Generate table with recent reviews"""
        from apps.reviewapp.models import ShopReview

        # Convert dates to datetimes for comparison
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        # Get reviews
        reviews = ShopReview.objects.filter(
            shop_id=shop_id,
            created_at__gte=start_datetime,
            created_at__lte=end_datetime,
        ).order_by("-created_at")

        # Total count for pagination
        total_count = reviews.count()

        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        reviews_page = reviews[start_idx:end_idx]

        # Define columns
        columns = [
            {"field": "customer", "headerName": "Customer", "width": 200},
            {"field": "rating", "headerName": "Rating", "width": 100},
            {"field": "title", "headerName": "Title", "width": 200},
            {"field": "comment", "headerName": "Comment", "width": 300},
            {"field": "date", "headerName": "Date", "width": 150},
        ]

        # Prepare rows
        rows = []

        for review in reviews_page:
            # Format customer name
            customer_name = review.customer.phone_number

            # Try to get a more friendly name if available
            try:
                from apps.customersapp.models import Customer

                customer_profile = Customer.objects.get(user=review.customer)
                if customer_profile.first_name or customer_profile.last_name:
                    customer_name = f"{customer_profile.first_name} {customer_profile.last_name}".strip()
            except Exception:
                pass

            # Format rating with stars
            rating_formatted = f"{review.rating} ★"

            # Create row
            row = [
                customer_name,
                rating_formatted,
                review.title,
                review.comment,
                review.created_at.strftime("%Y-%m-%d"),
            ]

            rows.append(row)

        return {
            "title": "Recent Reviews",
            "columns": columns,
            "rows": rows,
            "total_rows": total_count,
            "page": page,
            "page_size": page_size,
        }

    def _get_granularity_label(self, granularity):
        """Get appropriate axis label for granularity"""
        if granularity == "hourly":
            return "Hour"
        elif granularity == "daily":
            return "Day"
        elif granularity == "weekly":
            return "Week"
        elif granularity == "monthly":
            return "Month"
        elif granularity == "quarterly":
            return "Quarter"
        elif granularity == "yearly":
            return "Year"
        else:
            return "Time"
