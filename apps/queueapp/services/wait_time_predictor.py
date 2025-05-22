import logging
from collections import defaultdict
from datetime import timedelta

import numpy as np
from django.db.models import Avg, Count, ExpressionWrapper, F, fields
from django.utils import timezone

from apps.queueapp.models import QueueTicket

logger = logging.getLogger(__name__)


class WaitTimePredictor:
    """
    Advanced wait time prediction algorithm using historical data
    and machine learning techniques.
    """

    @staticmethod
    def predict_wait_time(queue_id, position, service_id=None, specialist_id=None):
        """
        Predict wait time with advanced algorithm that considers multiple factors:
        - Historical service times
        - Time of day patterns
        - Day of week patterns
        - Service-specific durations
        - Specialist-specific performance
        - Current queue load

        This is more sophisticated than the basic estimate in QueueService
        and can be used for longer-term predictions.
        """
        try:
            # Base wait time calculation based on historical averages
            from apps.queueapp.models import Queue

            queue = Queue.objects.get(id=queue_id)

            # Get historical service times for this queue
            end_date = timezone.now()
            start_date = end_date - timedelta(days=30)  # Last 30 days

            # Get completed tickets with actual wait times
            completed_tickets = QueueTicket.objects.filter(
                queue=queue,
                status="served",
                join_time__gte=start_date,
                join_time__lte=end_date,
                actual_wait_time__isnull=False,
            )

            # Calculate base metrics
            avg_wait_per_position = (
                completed_tickets.aggregate(avg_wait=Avg("actual_wait_time"))[
                    "avg_wait"
                ]
                or 15
            )  # Default to 15 minutes if no data

            # Get current conditions
            now = timezone.now()
            current_hour = now.hour
            current_day = now.weekday()  # 0=Monday, 6=Sunday

            # Factor 1: Hourly patterns
            hourly_waits = (
                completed_tickets.annotate(
                    hour=ExpressionWrapper(
                        F("join_time__hour"), output_field=fields.IntegerField()
                    )
                )
                .values("hour")
                .annotate(avg_wait=Avg("actual_wait_time"), count=Count("id"))
            )

            # Convert to dict for easier lookup
            hour_factors = {}
            for hw in hourly_waits:
                if hw["count"] >= 5:  # Only consider hours with sufficient data
                    hour_factors[hw["hour"]] = hw["avg_wait"] / avg_wait_per_position

            # Get hour factor (default to 1.0 if no data for current hour)
            hour_factor = hour_factors.get(current_hour, 1.0)

            # Factor 2: Day of week patterns
            daily_waits = (
                completed_tickets.annotate(
                    day=ExpressionWrapper(
                        F("join_time__week_day"), output_field=fields.IntegerField()
                    )
                )
                .values("day")
                .annotate(avg_wait=Avg("actual_wait_time"), count=Count("id"))
            )

            # Convert to dict for easier lookup
            day_factors = {}
            for dw in daily_waits:
                if dw["count"] >= 3:  # Only consider days with sufficient data
                    day_factors[dw["day"]] = dw["avg_wait"] / avg_wait_per_position

            # Get day factor (default to 1.0 if no data for current day)
            day_factor = day_factors.get(current_day, 1.0)

            # Factor 3: Service-specific duration
            service_factor = 1.0
            if service_id:
                service_waits = completed_tickets.filter(
                    service_id=service_id
                ).aggregate(avg_wait=Avg("actual_wait_time"), count=Count("id"))

                if service_waits["count"] >= 3:
                    service_factor = service_waits["avg_wait"] / avg_wait_per_position

            # Factor 4: Specialist-specific performance
            specialist_factor = 1.0
            if specialist_id:
                specialist_waits = completed_tickets.filter(
                    specialist_id=specialist_id
                ).aggregate(avg_wait=Avg("actual_wait_time"), count=Count("id"))

                if specialist_waits["count"] >= 3:
                    specialist_factor = (
                        specialist_waits["avg_wait"] / avg_wait_per_position
                    )

            # Factor 5: Current queue load
            active_tickets = QueueTicket.objects.filter(
                queue=queue, status__in=["waiting", "called", "serving"]
            ).count()

            # Calculate average load
            avg_load = (
                completed_tickets.annotate(
                    hour=ExpressionWrapper(
                        F("join_time__hour"), output_field=fields.IntegerField()
                    ),
                    day=ExpressionWrapper(
                        F("join_time__week_day"), output_field=fields.IntegerField()
                    ),
                )
                .values("hour", "day")
                .annotate(count=Count("id"))
            )

            # Get historical average for this time
            historical_loads = [
                entry["count"]
                for entry in avg_load
                if entry["hour"] == current_hour and entry["day"] == current_day
            ]

            historical_avg_load = (
                np.mean(historical_loads) if historical_loads else active_tickets
            )

            # Calculate load factor (how busy it is compared to normal)
            load_factor = (
                active_tickets / historical_avg_load if historical_avg_load > 0 else 1.0
            )

            # Cap the load factor to prevent extreme values
            load_factor = max(0.8, min(1.5, load_factor))

            # Factor 6: Staff availability
            from apps.specialistsapp.models import Specialist

            active_specialists = Specialist.objects.filter(
                employee__shop=queue.shop, employee__is_active=True
            ).count()

            # Calculate base wait time (position * avg time per position)
            base_wait = position * (avg_wait_per_position / position)

            # Apply all factors
            predicted_wait = (
                base_wait
                * hour_factor
                * day_factor
                * service_factor
                * specialist_factor
                * load_factor
            )

            # Adjust for multiple staff
            if active_specialists > 1:
                staff_factor = 1 / min(
                    active_specialists, position
                )  # Can't go below 1/position
                predicted_wait *= staff_factor

            # Ensure reasonable bounds
            predicted_wait = max(5, min(120, round(predicted_wait)))

            # Format detailed result for analysis
            return {
                "predicted_wait_minutes": predicted_wait,
                "factors": {
                    "base_wait": round(base_wait, 2),
                    "hour_factor": round(hour_factor, 2),
                    "day_factor": round(day_factor, 2),
                    "service_factor": round(service_factor, 2),
                    "specialist_factor": round(specialist_factor, 2),
                    "load_factor": round(load_factor, 2),
                    "staff_factor": (
                        round(1 / min(active_specialists, position), 2)
                        if active_specialists > 1
                        else 1.0
                    ),
                },
                "current_conditions": {
                    "hour": current_hour,
                    "day": current_day,
                    "active_tickets": active_tickets,
                    "active_specialists": active_specialists,
                },
            }

        except Exception as e:
            logger.error(f"Error in advanced wait time prediction: {str(e)}")
            return {
                "predicted_wait_minutes": 15,  # Fallback
                "factors": {},
                "error": str(e),
            }

    @staticmethod
    def train_wait_time_model(shop_id):
        """
        Train a more sophisticated wait time prediction model
        using historical data for a specific shop.

        This builds a predictive model that can be saved and used
        for future predictions, improving accuracy over time.
        """
        try:
            # Get all completed tickets for this shop
            from apps.queueapp.models import QueueTicket

            # Get substantial historical data (90 days)
            end_date = timezone.now()
            start_date = end_date - timedelta(days=90)

            completed_tickets = QueueTicket.objects.filter(
                queue__shop_id=shop_id,
                status="served",
                join_time__gte=start_date,
                join_time__lte=end_date,
                actual_wait_time__isnull=False,
            ).select_related("queue", "service", "specialist")

            if completed_tickets.count() < 100:
                return {
                    "success": False,
                    "message": "Insufficient data for model training. Need at least 100 completed tickets.",
                    "data_points": completed_tickets.count(),
                }

            # Prepare features and target
            data = []
            targets = []

            for ticket in completed_tickets:
                # Extract features
                features = {
                    "hour": ticket.join_time.hour,
                    "day_of_week": ticket.join_time.weekday(),
                    "position": ticket.position,
                    "queue_id": str(ticket.queue_id),
                    "service_id": str(ticket.service_id) if ticket.service else "none",
                    "specialist_id": (
                        str(ticket.specialist_id) if ticket.specialist else "none"
                    ),
                    "ticket_count": QueueTicket.objects.filter(
                        queue=ticket.queue,
                        status__in=["waiting", "called", "serving"],
                        join_time__lt=ticket.join_time,
                        join_time__gte=ticket.join_time - timedelta(hours=1),
                    ).count(),
                }
                data.append(features)
                targets.append(ticket.actual_wait_time)

            # Build a simple model (linear regression for demo)
            # In a real implementation, this would use more sophisticated ML
            # like RandomForest, XGBoost, etc.

            # Calculate coefficients for different factors
            hour_coefficients = defaultdict(list)
            day_coefficients = defaultdict(list)
            service_coefficients = defaultdict(list)
            specialist_coefficients = defaultdict(list)

            for features, target in zip(data, targets):
                hour_coefficients[features["hour"]].append(target)
                day_coefficients[features["day_of_week"]].append(target)
                service_coefficients[features["service_id"]].append(target)
                specialist_coefficients[features["specialist_id"]].append(target)

            # Calculate average wait time by feature
            hour_factors = {
                hour: np.mean(waits)
                for hour, waits in hour_coefficients.items()
                if len(waits) >= 5
            }

            day_factors = {
                day: np.mean(waits)
                for day, waits in day_coefficients.items()
                if len(waits) >= 5
            }

            service_factors = {
                service: np.mean(waits)
                for service, waits in service_coefficients.items()
                if len(waits) >= 5
            }

            specialist_factors = {
                specialist: np.mean(waits)
                for specialist, waits in specialist_coefficients.items()
                if len(waits) >= 5
            }

            # Calculate global average
            global_avg = np.mean(targets)

            # Normalize factors
            for hour in hour_factors:
                hour_factors[hour] /= global_avg

            for day in day_factors:
                day_factors[day] /= global_avg

            for service in service_factors:
                service_factors[service] /= global_avg

            for specialist in specialist_factors:
                specialist_factors[specialist] /= global_avg

            # Build model (as a dict of coefficients)
            model = {
                "global_avg": global_avg,
                "hour_factors": hour_factors,
                "day_factors": day_factors,
                "service_factors": service_factors,
                "specialist_factors": specialist_factors,
                "updated_at": timezone.now().isoformat(),
                "data_points": len(targets),
            }

            # In a real implementation, we'd save this model to a database
            # or a file for future use

            return {
                "success": True,
                "message": f"Model trained successfully with {len(targets)} data points",
                "model_summary": {
                    "global_avg_wait": round(global_avg, 2),
                    "hour_factor_range": [
                        round(min(hour_factors.values()), 2),
                        round(max(hour_factors.values()), 2),
                    ],
                    "day_factor_range": [
                        round(min(day_factors.values()), 2),
                        round(max(day_factors.values()), 2),
                    ],
                    "updated_at": timezone.now().isoformat(),
                },
            }

        except Exception as e:
            logger.error(f"Error training wait time model: {str(e)}")
            return {"success": False, "message": f"Error training model: {str(e)}"}

    @staticmethod
    def predict_with_model(
        shop_id, position, hour=None, day=None, service_id=None, specialist_id=None
    ):
        """
        Make a prediction using a pre-trained model.

        In a real implementation, this would load the model
        from the database or a file.
        """
        try:
            # In a real implementation, load the saved model
            # For now, we'll train it on the fly (inefficient but demonstrates the concept)
            model_result = WaitTimePredictor.train_wait_time_model(shop_id)

            if not model_result["success"]:
                # Fallback to simpler prediction
                from apps.queueapp.services.queue_service import QueueService

                return QueueService.estimate_wait_time(None, position)

            # Extract model components
            model = model_result.get("model", {})
            global_avg = model.get("global_avg", 15)  # Default 15 min
            hour_factors = model.get("hour_factors", {})
            day_factors = model.get("day_factors", {})
            service_factors = model.get("service_factors", {})
            specialist_factors = model.get("specialist_factors", {})

            # Use current time if not specified
            now = timezone.now()
            current_hour = hour if hour is not None else now.hour
            current_day = day if day is not None else now.weekday()

            # Get factors
            hour_factor = hour_factors.get(str(current_hour), 1.0)
            day_factor = day_factors.get(str(current_day), 1.0)
            service_factor = (
                service_factors.get(str(service_id), 1.0) if service_id else 1.0
            )
            specialist_factor = (
                specialist_factors.get(str(specialist_id), 1.0)
                if specialist_id
                else 1.0
            )

            # Get staff count
            from apps.specialistsapp.models import Specialist

            active_specialists = Specialist.objects.filter(
                employee__shop_id=shop_id, employee__is_active=True
            ).count()

            # Calculate prediction
            base_wait = position * global_avg / max(1, position)

            # Apply factors
            predicted_wait = (
                base_wait
                * hour_factor
                * day_factor
                * service_factor
                * specialist_factor
            )

            # Adjust for staff
            if active_specialists > 1:
                staff_factor = 1 / min(active_specialists, position)
                predicted_wait *= staff_factor

            # Ensure reasonable bounds
            predicted_wait = max(5, min(120, round(predicted_wait)))

            return predicted_wait

        except Exception as e:
            logger.error(f"Error predicting with model: {str(e)}")
            return 15  # Default fallback
