import logging
from datetime import timedelta

from django.db.models import Avg, Count, ExpressionWrapper, F, fields
from django.utils import timezone

from apps.queueapp.models import Queue, QueueTicket

logger = logging.getLogger(__name__)


class QueueOptimizer:
    """
    Advanced queue optimization algorithms to improve flow efficiency
    and reduce wait times.
    """

    @staticmethod
    def optimize_queue_order(queue_id):
        """
        Optimizes the order of tickets in a queue based on various factors:
        - Service duration (quick services can be moved up to fill gaps)
        - Specialist availability
        - Priority customers (VIPs, appointments that arrived early, etc.)

        This is an advanced optimization that should be used cautiously
        as it may affect fairness perception if overused.
        """
        try:
            queue = Queue.objects.get(id=queue_id)

            # Get waiting tickets
            waiting_tickets = QueueTicket.objects.filter(
                queue=queue, status="waiting"
            ).order_by("position")

            if waiting_tickets.count() <= 1:
                # Nothing to optimize with 0 or 1 ticket
                return {
                    "success": True,
                    "message": "Queue has 1 or fewer tickets, no optimization needed",
                    "changes": [],
                }

            # Get current served tickets to determine active specialists
            serving_tickets = QueueTicket.objects.filter(queue=queue, status="serving")

            active_specialists = set()
            for ticket in serving_tickets:
                if ticket.specialist:
                    active_specialists.add(ticket.specialist_id)

            # Get service times for services in the queue
            from apps.serviceapp.models import Service

            services_in_queue = set(
                ticket.service_id
                for ticket in waiting_tickets
                if ticket.service_id is not None
            )

            service_durations = {}
            if services_in_queue:
                services = Service.objects.filter(id__in=services_in_queue)
                for service in services:
                    service_durations[service.id] = service.duration

            # Start with a copy of the original order for comparison
            original_order = list(waiting_tickets.values_list("id", flat=True))
            optimized_order = list(original_order)  # Will be modified

            # Identify "quick service" tickets that could be moved up
            quick_services = []
            for i, ticket in enumerate(waiting_tickets):
                if not ticket.service_id:
                    continue

                duration = service_durations.get(
                    ticket.service_id, 30
                )  # Default to 30 min if unknown

                # Consider a service "quick" if it's less than 15 minutes
                if duration <= 15:
                    quick_services.append(
                        {"index": i, "ticket": ticket, "duration": duration}
                    )

            # Find specialist-specific tickets
            specialist_tickets = []
            for i, ticket in enumerate(waiting_tickets):
                if (
                    ticket.specialist_id
                    and ticket.specialist_id not in active_specialists
                ):
                    # This ticket needs a specific specialist who isn't currently busy
                    specialist_tickets.append({"index": i, "ticket": ticket})

            # Make optimization decisions
            changes = []

            # 1. Try to fit quick services into gaps
            if quick_services:
                # Move up to 2 quick services forward (at most) to maintain fairness
                max_moves = min(2, len(quick_services))
                moves_made = 0

                for quick in quick_services:
                    # Don't move if already in front
                    if quick["index"] <= 1:
                        continue

                    # Don't move ahead more than 3 positions to maintain fairness
                    new_position = max(0, quick["index"] - 3)

                    # Only move if it will improve efficiency
                    if new_position < quick["index"]:
                        # Get the ticket to move
                        ticket = quick["ticket"]

                        # Record change for tracking
                        changes.append(
                            {
                                "ticket_id": str(ticket.id),
                                "ticket_number": ticket.ticket_number,
                                "old_position": quick["index"]
                                + 1,  # 1-indexed for display
                                "new_position": new_position
                                + 1,  # 1-indexed for display
                                "reason": "Quick service optimization",
                            }
                        )

                        # Update positions in our tracking list
                        optimized_order.remove(ticket.id)
                        optimized_order.insert(new_position, ticket.id)

                        moves_made += 1
                        if moves_made >= max_moves:
                            break

            # 2. Try to optimize for available specialists
            if specialist_tickets:
                for specialist_item in specialist_tickets:
                    # Don't move specialists too far forward (max 2 positions)
                    if specialist_item["index"] <= 2:
                        continue

                    new_position = max(0, specialist_item["index"] - 2)

                    if new_position < specialist_item["index"]:
                        ticket = specialist_item["ticket"]

                        # Record change
                        changes.append(
                            {
                                "ticket_id": str(ticket.id),
                                "ticket_number": ticket.ticket_number,
                                "old_position": specialist_item["index"] + 1,
                                "new_position": new_position + 1,
                                "reason": "Specialist availability optimization",
                            }
                        )

                        # Update our tracking list
                        current_index = optimized_order.index(ticket.id)
                        optimized_order.remove(ticket.id)
                        optimized_order.insert(new_position, ticket.id)

            # If no changes, return early
            if not changes:
                return {
                    "success": True,
                    "message": "No optimizations needed",
                    "changes": [],
                }

            # Apply changes to the database in a single operation
            with transaction.atomic():
                # Update each ticket with new position
                for i, ticket_id in enumerate(optimized_order):
                    QueueTicket.objects.filter(id=ticket_id).update(position=i + 1)

            return {
                "success": True,
                "message": f"Queue optimized with {len(changes)} changes",
                "changes": changes,
            }

        except Queue.DoesNotExist:
            return {"success": False, "message": "Queue not found", "changes": []}
        except Exception as e:
            logger.error(f"Error optimizing queue: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}", "changes": []}

    @staticmethod
    def analyze_queue_efficiency(shop_id, date_range=7):
        """
        Analyze queue efficiency and identify potential bottlenecks
        or improvements over a given date range.
        """
        now = timezone.now()
        start_date = now - timedelta(days=date_range)

        # Get all tickets in date range
        tickets = QueueTicket.objects.filter(
            queue__shop_id=shop_id, join_time__gte=start_date
        )

        # Calculate key metrics
        total_tickets = tickets.count()

        served_tickets = tickets.filter(status="served")
        served_count = served_tickets.count()

        cancelled_tickets = tickets.filter(status="cancelled")
        cancelled_count = cancelled_tickets.count()

        skipped_tickets = tickets.filter(status="skipped")
        skipped_count = skipped_tickets.count()

        # Calculate wait time metrics
        avg_wait_time = (
            served_tickets.aggregate(avg=Avg("actual_wait_time"))["avg"] or 0
        )

        # Calculate time of day distribution
        hour_distribution = (
            tickets.annotate(
                hour=ExtpressionWrapper(
                    F("join_time__hour"), output_field=fields.IntegerField()
                )
            )
            .values("hour")
            .annotate(count=Count("id"))
            .order_by("hour")
        )

        # Find peak hours (top 3)
        peak_hours = sorted(hour_distribution, key=lambda x: x["count"], reverse=True)[
            :3
        ]

        # Calculate service time by service type
        service_metrics = (
            tickets.filter(status="served", service__isnull=False)
            .values("service__name", "service_id")
            .annotate(count=Count("id"), avg_wait=Avg("actual_wait_time"))
            .order_by("-count")
        )

        # Calculate completion rate
        completion_rate = (
            (served_count / total_tickets * 100) if total_tickets > 0 else 0
        )

        # Identify efficiency issues
        efficiency_issues = []

        # Check completion rate
        if completion_rate < 85:
            efficiency_issues.append(
                {
                    "issue": "Low completion rate",
                    "description": f"Only {completion_rate:.1f}% of tickets are being completed",
                    "suggestion": "Investigate reasons for high cancellation or skip rate",
                }
            )

        # Check wait time
        if avg_wait_time > 20:
            efficiency_issues.append(
                {
                    "issue": "High average wait time",
                    "description": f"Average wait time is {avg_wait_time:.1f} minutes",
                    "suggestion": "Consider adding more staff during peak hours or optimizing service delivery",
                }
            )

        # Identify services with unusually long wait times
        if service_metrics:
            for service in service_metrics:
                if service["avg_wait"] > avg_wait_time * 1.5:
                    efficiency_issues.append(
                        {
                            "issue": "Service with high wait time",
                            "description": f"{service['service__name']} has avg wait of {service['avg_wait']:.1f} min",
                            "suggestion": "Review this service process or allocate more specialists",
                        }
                    )

        # Check cancellation rate
        cancellation_rate = (
            (cancelled_count / total_tickets * 100) if total_tickets > 0 else 0
        )
        if cancellation_rate > 15:
            efficiency_issues.append(
                {
                    "issue": "High cancellation rate",
                    "description": f"{cancellation_rate:.1f}% of tickets are being cancelled",
                    "suggestion": "Improve wait time estimates or customer communication",
                }
            )

        return {
            "metrics": {
                "total_tickets": total_tickets,
                "served_count": served_count,
                "cancelled_count": cancelled_count,
                "skipped_count": skipped_count,
                "avg_wait_time": avg_wait_time,
                "completion_rate": completion_rate,
            },
            "distributions": {
                "hourly": list(hour_distribution),
                "peak_hours": peak_hours,
                "service_metrics": list(service_metrics),
            },
            "efficiency_issues": efficiency_issues,
        }

    @staticmethod
    def predict_queue_demand(shop_id, lookahead_days=7):
        """
        Predict future queue demand based on historical patterns.
        This can help shops plan staffing levels in advance.
        """
        now = timezone.now()

        # Get historical data for the past 28 days
        start_date = now - timedelta(days=28)

        # Get tickets grouped by day and hour
        historical_tickets = QueueTicket.objects.filter(
            queue__shop_id=shop_id, join_time__gte=start_date
        )

        # Get day of week distribution
        day_distribution = (
            historical_tickets.annotate(
                day=ExpressionWrapper(
                    F("join_time__week_day"), output_field=fields.IntegerField()
                )
            )
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )

        # Get hour of day distribution
        hour_distribution = (
            historical_tickets.annotate(
                hour=ExpressionWrapper(
                    F("join_time__hour"), output_field=fields.IntegerField()
                )
            )
            .values("hour")
            .annotate(count=Count("id"))
            .order_by("hour")
        )

        # Calculate daily average
        daily_counts = (
            historical_tickets.annotate(
                date=ExpressionWrapper(
                    F("join_time__date"), output_field=fields.DateField()
                )
            )
            .values("date")
            .annotate(count=Count("id"))
        )

        total_days = daily_counts.count()
        total_tickets = sum(day["count"] for day in daily_counts)
        daily_average = total_tickets / total_days if total_days > 0 else 0

        # Generate predictions for future days
        predictions = []

        # Convert to dict for easier lookup
        day_factors = {day["day"]: day["count"] for day in day_distribution}
        max_day_count = max(day_factors.values()) if day_factors else 1

        # Normalize day factors
        day_factors = {day: count / max_day_count for day, count in day_factors.items()}

        # Convert hour distribution to dict
        hour_factors = {hour["hour"]: hour["count"] for hour in hour_distribution}
        max_hour_count = max(hour_factors.values()) if hour_factors else 1

        # Normalize hour factors
        hour_factors = {
            hour: count / max_hour_count for hour, count in hour_factors.items()
        }

        # Generate predictions
        current_date = now.date()
        for day_offset in range(1, lookahead_days + 1):
            forecast_date = current_date + timedelta(days=day_offset)

            # Get day of week (1=Sunday, 7=Saturday in Django's week_day)
            forecast_day = forecast_date.isoweekday() % 7 + 1

            # Apply day factor
            day_factor = day_factors.get(forecast_day, 1.0)

            # Predict total tickets for the day
            predicted_total = daily_average * day_factor

            # Generate hourly breakdown
            hourly_predictions = []
            for hour in range(24):
                hour_factor = hour_factors.get(hour, 0.1)
                hourly_predictions.append(
                    {
                        "hour": hour,
                        "predicted_tickets": round(predicted_total * hour_factor, 1),
                    }
                )

            predictions.append(
                {
                    "date": forecast_date,
                    "day_of_week": forecast_date.strftime("%A"),
                    "predicted_total": round(predicted_total, 1),
                    "hourly_breakdown": hourly_predictions,
                }
            )

        return {
            "daily_average": daily_average,
            "predictions": predictions,
            "historical_patterns": {
                "day_distribution": list(day_distribution),
                "hour_distribution": list(hour_distribution),
            },
        }

    @staticmethod
    def calculate_optimal_staffing(shop_id, date=None):
        """
        Calculate optimal staffing levels based on predicted demand.
        """
        if not date:
            date = timezone.now().date() + timedelta(days=1)  # Default to tomorrow

        # Get demand prediction
        prediction_results = QueueOptimizer.predict_queue_demand(shop_id)

        # Find prediction for target date
        target_prediction = None
        for prediction in prediction_results["predictions"]:
            if prediction["date"] == date:
                target_prediction = prediction
                break

        if not target_prediction:
            return {"error": "No prediction available for specified date"}

        # Calculate specialists needed based on demand and service time
        # Assume each specialist can handle 4 customers per hour on average
        CUSTOMERS_PER_SPECIALIST_HOUR = 4

        # Calculate staffing needs by hour
        staffing_needs = []
        for hour_data in target_prediction["hourly_breakdown"]:
            if hour_data["hour"] < 8 or hour_data["hour"] > 21:
                # Assume business closed during these hours
                continue

            predicted_tickets = hour_data["predicted_tickets"]
            specialists_needed = max(
                1, round(predicted_tickets / CUSTOMERS_PER_SPECIALIST_HOUR)
            )

            staffing_needs.append(
                {
                    "hour": hour_data["hour"],
                    "hour_formatted": f"{hour_data['hour']}:00",
                    "predicted_tickets": predicted_tickets,
                    "specialists_needed": specialists_needed,
                }
            )

        # Get current staff count for comparison
        from apps.specialistsapp.models import Specialist

        total_specialists = Specialist.objects.filter(
            employee__shop_id=shop_id, employee__is_active=True
        ).count()

        return {
            "date": date,
            "day_of_week": date.strftime("%A"),
            "predicted_total_tickets": target_prediction["predicted_total"],
            "hourly_staffing_needs": staffing_needs,
            "peak_staffing_need": max(
                [h["specialists_needed"] for h in staffing_needs]
            ),
            "current_specialist_count": total_specialists,
        }
