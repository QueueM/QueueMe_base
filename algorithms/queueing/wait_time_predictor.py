"""
Wait Time Predictor

A sophisticated service for predicting customer wait times in queues and for
appointments. The predictor uses historical data, current queue status, and
machine learning techniques to provide accurate wait time estimates.

Features:
1. Real-time wait time prediction for queues
2. Historical data analysis for time patterns
3. Service-specific duration estimation
4. Specialist efficiency factors
5. Dynamic adjustment based on actual vs. predicted times
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import numpy as np
from django.core.cache import cache
from django.db.models import ExpressionWrapper, F, fields
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.queueapp.models import QueueEntry, ServiceQueue
from apps.serviceapp.models import Service

logger = logging.getLogger(__name__)


class WaitTimePredictor:
    """
    Service for predicting wait times for customers in queues and appointments.

    This service uses historical data, current queue status, and service characteristics
    to provide accurate wait time predictions.
    """

    # Cache settings
    CACHE_PREFIX = "wait_predictor:"
    CACHE_TTL = 60 * 5  # 5 minutes

    # Constants for prediction calculations
    HISTORY_DAYS = 30  # Days of historical data to consider
    MIN_DATA_POINTS = 5  # Minimum data points required for historical prediction
    DEFAULT_SERVICE_TIME = 15  # Default service time in minutes
    DEFAULT_WAIT_TIME = 20  # Default wait time in minutes
    PREDICTION_UNCERTAINTY = 0.2  # +/- 20% prediction uncertainty

    @classmethod
    def predict_queue_wait_time(
        cls,
        queue_id: str,
        position: int,
        priority: int = 2,  # Normal priority by default
        specialist_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Predict wait time for a customer in the queue.

        Args:
            queue_id: ID of the service queue
            position: Customer's position in queue
            priority: Priority level (1-5, higher is more priority)
            specialist_id: Optional specific specialist ID

        Returns:
            Dict with wait time prediction details
        """
        try:
            # Check cache first
            cache_key = (
                f"{cls.CACHE_PREFIX}queue:{queue_id}:pos:{position}:pri:{priority}"
            )
            if specialist_id:
                cache_key += f":spec:{specialist_id}"

            cached_prediction = cache.get(cache_key)
            if cached_prediction:
                return cached_prediction

            # Get the service queue
            try:
                service_queue = ServiceQueue.objects.select_related("service").get(
                    id=queue_id
                )
            except ServiceQueue.DoesNotExist:
                return {
                    "success": False,
                    "message": "Queue not found",
                    "prediction_minutes": cls.DEFAULT_WAIT_TIME,
                    "confidence": "low",
                }

            # Get service details
            service = service_queue.service
            service_duration = service.duration or cls.DEFAULT_SERVICE_TIME

            # 1. Current queue-based prediction
            current_prediction = cls._predict_from_current_queue(
                queue_id=queue_id,
                position=position,
                priority=priority,
                service_duration=service_duration,
                specialist_id=specialist_id,
            )

            # 2. Historical data-based prediction
            historical_prediction = cls._predict_from_historical_data(
                service_id=str(service.id),
                shop_id=str(service_queue.shop_id),
                current_time=timezone.now(),
                specialist_id=specialist_id,
            )

            # 3. Service duration-based fallback
            fallback_prediction = {
                "wait_minutes": position * service_duration,
                "confidence": "low",
                "method": "fallback",
            }

            # 4. Combine predictions with weights based on confidence
            final_prediction = cls._combine_predictions(
                current_prediction, historical_prediction, fallback_prediction
            )

            # 5. Apply priority adjustment
            priority_factor = cls._calculate_priority_factor(priority)
            priority_adjusted_minutes = round(
                final_prediction["wait_minutes"] * priority_factor
            )

            # 6. Add uncertainty range
            uncertainty = round(priority_adjusted_minutes * cls.PREDICTION_UNCERTAINTY)
            min_wait = max(1, priority_adjusted_minutes - uncertainty)
            max_wait = priority_adjusted_minutes + uncertainty

            # Build the final result
            result = {
                "success": True,
                "queue_id": queue_id,
                "service_id": str(service.id),
                "position": position,
                "priority": priority,
                "prediction_minutes": priority_adjusted_minutes,
                "min_wait": min_wait,
                "max_wait": max_wait,
                "confidence": final_prediction["confidence"],
                "method": final_prediction["method"],
                "is_specialist_specific": specialist_id is not None,
                "generated_at": timezone.now().isoformat(),
            }

            # Cache the result
            cache.set(cache_key, result, cls.CACHE_TTL)

            return result

        except Exception as e:
            logger.error(f"Error predicting queue wait time: {str(e)}")
            return {
                "success": False,
                "message": f"Error predicting wait time: {str(e)}",
                "prediction_minutes": cls.DEFAULT_WAIT_TIME,
                "confidence": "low",
            }

    @classmethod
    def predict_appointment_delay(cls, appointment_id: str) -> Dict[str, Any]:
        """
        Predict potential delay for a scheduled appointment.

        Args:
            appointment_id: ID of the appointment

        Returns:
            Dict with delay prediction details
        """
        try:
            # Get the appointment
            try:
                appointment = Appointment.objects.select_related(
                    "service", "specialist", "shop"
                ).get(id=appointment_id)
            except Appointment.DoesNotExist:
                return {
                    "success": False,
                    "message": "Appointment not found",
                    "delay_minutes": 0,
                    "confidence": "low",
                }

            # Check if appointment is still in the future
            if timezone.now() >= appointment.start_time:
                # Appointment time has passed
                if appointment.status in ["scheduled", "confirmed"]:
                    # Not started yet - calculate current delay
                    current_delay = round(
                        (timezone.now() - appointment.start_time).total_seconds() / 60
                    )
                    return {
                        "success": True,
                        "appointment_id": appointment_id,
                        "delay_minutes": current_delay,
                        "status": "delayed",
                        "confidence": "high",
                        "method": "current_time",
                    }
                else:
                    # Already started or completed
                    return {
                        "success": True,
                        "appointment_id": appointment_id,
                        "delay_minutes": 0,
                        "status": appointment.status,
                        "confidence": "high",
                        "method": "current_status",
                    }

            # For future appointments, predict possible delay

            # 1. Check specialist's current schedule
            specialist_delay = cls._predict_delay_from_specialist_schedule(
                specialist_id=str(appointment.specialist_id),
                appointment_time=appointment.start_time,
            )

            # 2. Check historical appointment delays
            historical_delay = cls._predict_delay_from_historical_data(
                service_id=str(appointment.service_id),
                specialist_id=str(appointment.specialist_id),
                shop_id=str(appointment.shop_id),
                appointment_time=appointment.start_time,
            )

            # 3. Combine predictions
            if specialist_delay["confidence"] == "high":
                # Current schedule is a strong indicator
                combined_delay = specialist_delay["delay_minutes"]
                confidence = "high"
                method = "specialist_schedule"
            elif historical_delay["confidence"] != "low":
                # Historical data is reasonably reliable
                combined_delay = round(
                    0.4 * specialist_delay["delay_minutes"]
                    + 0.6 * historical_delay["delay_minutes"]
                )
                confidence = historical_delay["confidence"]
                method = "combined"
            else:
                # Low confidence in both - conservative estimate
                combined_delay = max(
                    specialist_delay["delay_minutes"], historical_delay["delay_minutes"]
                )
                confidence = "low"
                method = "conservative"

            # Build the final result
            result = {
                "success": True,
                "appointment_id": appointment_id,
                "service_id": str(appointment.service_id),
                "specialist_id": str(appointment.specialist_id),
                "scheduled_time": appointment.start_time.isoformat(),
                "delay_minutes": combined_delay,
                "expected_start_time": (
                    appointment.start_time + timedelta(minutes=combined_delay)
                ).isoformat(),
                "status": "on_time" if combined_delay <= 5 else "delayed",
                "confidence": confidence,
                "method": method,
                "generated_at": timezone.now().isoformat(),
            }

            return result

        except Exception as e:
            logger.error(f"Error predicting appointment delay: {str(e)}")
            return {
                "success": False,
                "message": f"Error predicting delay: {str(e)}",
                "delay_minutes": 0,
                "confidence": "low",
            }

    @classmethod
    def estimate_service_duration(
        cls,
        service_id: str,
        specialist_id: Optional[str] = None,
        customer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Estimate the duration of a service based on historical data.

        Args:
            service_id: ID of the service
            specialist_id: Optional specialist ID
            customer_id: Optional customer ID

        Returns:
            Dict with service duration estimation details
        """
        try:
            # Get the service
            try:
                service = Service.objects.get(id=service_id)
            except Service.DoesNotExist:
                return {
                    "success": False,
                    "message": "Service not found",
                    "duration_minutes": cls.DEFAULT_SERVICE_TIME,
                    "confidence": "low",
                }

            # Start with the default service duration
            base_duration = service.duration or cls.DEFAULT_SERVICE_TIME

            # Query to get completed appointments for this service
            history_query = Appointment.objects.filter(
                service_id=service_id,
                status="completed",
                actual_start_time__isnull=False,
                actual_end_time__isnull=False,
            )

            # Filter by specialist if provided
            if specialist_id:
                history_query = history_query.filter(specialist_id=specialist_id)

            # Filter by customer if provided
            if customer_id:
                history_query = history_query.filter(customer_id=customer_id)

            # Limit to recent history and add duration expression
            history_query = history_query.filter(
                actual_end_time__gte=timezone.now() - timedelta(days=cls.HISTORY_DAYS)
            ).annotate(
                duration_minutes=ExpressionWrapper(
                    F("actual_end_time") - F("actual_start_time"),
                    output_field=fields.DurationField(),
                )
            )

            # If no historical data, return base duration
            if not history_query.exists():
                return {
                    "success": True,
                    "service_id": service_id,
                    "duration_minutes": base_duration,
                    "confidence": "low",
                    "method": "service_default",
                }

            # Calculate statistics from historical data
            appointments = list(history_query)
            actual_durations = []

            for appt in appointments:
                minutes = appt.duration_minutes.total_seconds() / 60
                if 5 <= minutes <= base_duration * 2:  # Filter unreasonable values
                    actual_durations.append(minutes)

            if not actual_durations:
                return {
                    "success": True,
                    "service_id": service_id,
                    "duration_minutes": base_duration,
                    "confidence": "low",
                    "method": "service_default",
                }

            # Calculate statistics
            mean_duration = round(sum(actual_durations) / len(actual_durations))
            median_duration = round(np.median(actual_durations))
            std_dev = np.std(actual_durations) if len(actual_durations) > 1 else 0

            # Determine confidence based on sample size and variability
            confidence = "medium"
            if len(actual_durations) >= cls.MIN_DATA_POINTS * 2:
                confidence = "high"
            elif len(actual_durations) < cls.MIN_DATA_POINTS:
                confidence = "low"

            # Adjust confidence based on variability
            if std_dev > 0.3 * mean_duration and confidence != "low":
                confidence = "medium" if confidence == "high" else "low"

            # Choose the predicted duration (prefer median for robustness)
            predicted_duration = median_duration

            # Build the final result
            result = {
                "success": True,
                "service_id": service_id,
                "service_name": service.name,
                "base_duration": base_duration,
                "predicted_duration": predicted_duration,
                "mean_duration": mean_duration,
                "median_duration": median_duration,
                "sample_size": len(actual_durations),
                "std_deviation": round(std_dev, 1),
                "confidence": confidence,
                "method": "historical_analysis",
                "is_specialist_specific": specialist_id is not None,
                "is_customer_specific": customer_id is not None,
                "generated_at": timezone.now().isoformat(),
            }

            return result

        except Exception as e:
            logger.error(f"Error estimating service duration: {str(e)}")
            return {
                "success": False,
                "message": f"Error estimating duration: {str(e)}",
                "duration_minutes": cls.DEFAULT_SERVICE_TIME,
                "confidence": "low",
            }

    @classmethod
    def update_predictions_with_actual(
        cls, entry_id: str, actual_wait_time: int
    ) -> bool:
        """
        Update prediction models with actual wait time data.

        Args:
            entry_id: ID of the queue entry
            actual_wait_time: Actual wait time in minutes

        Returns:
            Boolean indicating success
        """
        try:
            # Get the queue entry
            try:
                entry = QueueEntry.objects.select_related("queue").get(id=entry_id)
            except QueueEntry.DoesNotExist:
                logger.warning(
                    f"Queue entry {entry_id} not found for prediction update"
                )
                return False

            # Store the actual wait time
            entry.actual_wait_time = actual_wait_time
            entry.save(update_fields=["actual_wait_time"])

            # Update service queue wait time average if needed
            service_queue = entry.queue

            # Get recent entries with actual wait times
            recent_entries = QueueEntry.objects.filter(
                queue=service_queue,
                actual_wait_time__isnull=False,
                check_in_time__gte=timezone.now() - timedelta(days=7),
            )

            if recent_entries.exists():
                # Calculate new average wait time
                total_wait = 0
                count = 0
                for recent_entry in recent_entries:
                    wait_time = recent_entry.actual_wait_time
                    if 1 <= wait_time <= 120:  # Reasonable range
                        total_wait += wait_time
                        count += 1

                if count > 0:
                    new_avg_wait = round(total_wait / count)

                    # Update with smoothing (80% new, 20% old)
                    if service_queue.current_wait_time:
                        service_queue.current_wait_time = round(
                            0.8 * new_avg_wait + 0.2 * service_queue.current_wait_time
                        )
                    else:
                        service_queue.current_wait_time = new_avg_wait

                    service_queue.save(update_fields=["current_wait_time"])

            # Clear related cache entries
            cls._clear_prediction_cache(service_queue.id)

            return True

        except Exception as e:
            logger.error(f"Error updating predictions with actual data: {str(e)}")
            return False

    # ------------------------------------------------------------------------
    # Helper methods for prediction calculations
    # ------------------------------------------------------------------------

    @classmethod
    def _predict_from_current_queue(
        cls,
        queue_id: str,
        position: int,
        priority: int,
        service_duration: int,
        specialist_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Predict wait time based on current queue status.

        Args:
            queue_id: ID of the service queue
            position: Position in queue
            priority: Priority level
            service_duration: Service duration in minutes
            specialist_id: Optional specific specialist

        Returns:
            Dict with prediction details
        """
        try:
            # Get all waiting entries in this queue
            waiting_entries = QueueEntry.objects.filter(
                queue_id=queue_id, status="waiting"
            ).order_by("-priority", "position")

            # Get active specialists
            active_specialists = set()
            active_entries = QueueEntry.objects.filter(
                queue_id=queue_id, status__in=["called", "serving"]
            )

            for entry in active_entries:
                if entry.specialist_id:
                    active_specialists.add(str(entry.specialist_id))

            # If specialist specified, only consider that specialist
            if specialist_id:
                # Check if specialist is active
                is_active = str(specialist_id) in active_specialists

                # Count entries ahead with higher or same priority
                entries_ahead = 0
                for entry in waiting_entries:
                    if entry.position < position or (
                        entry.position == position and entry.priority > priority
                    ):
                        entries_ahead += 1

                # Calculate wait time
                # If specialist is active, they're already serving someone
                base_waiting_time = (
                    entries_ahead + (1 if is_active else 0)
                ) * service_duration

                return {
                    "wait_minutes": base_waiting_time,
                    "confidence": "medium" if is_active else "low",
                    "method": "specific_specialist",
                }
            else:
                # Multi-specialist prediction
                num_specialists = max(1, len(active_specialists))

                # Count entries ahead with higher priority
                higher_priority_entries = 0
                same_priority_entries = 0

                for entry in waiting_entries:
                    if entry.priority > priority:
                        higher_priority_entries += 1
                    elif entry.priority == priority and entry.position < position:
                        same_priority_entries += 1

                # Effective entries ahead
                effective_entries = higher_priority_entries + same_priority_entries

                # Calculate wait time with parallelism
                parallelism_factor = min(
                    num_specialists, 1 + (num_specialists - 1) * 0.7
                )  # Diminishing returns

                # Base wait time calculation
                wait_minutes = round(
                    (effective_entries / parallelism_factor) * service_duration
                )

                # Determine confidence based on queue stability
                if waiting_entries.count() > 0 and active_entries.count() > 0:
                    confidence = "medium"
                else:
                    confidence = "low"

                return {
                    "wait_minutes": wait_minutes,
                    "confidence": confidence,
                    "method": "current_queue",
                }

        except Exception as e:
            logger.error(f"Error predicting from current queue: {str(e)}")
            return {
                "wait_minutes": position * service_duration,
                "confidence": "low",
                "method": "fallback",
            }

    @classmethod
    def _predict_from_historical_data(
        cls,
        service_id: str,
        shop_id: str,
        current_time: datetime,
        specialist_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Predict wait time based on historical data.

        Args:
            service_id: ID of the service
            shop_id: ID of the shop
            current_time: Current datetime
            specialist_id: Optional specialist ID

        Returns:
            Dict with prediction details
        """
        try:
            # Get recent entries with actual wait times
            history_query = QueueEntry.objects.filter(
                queue__service_id=service_id,
                queue__shop_id=shop_id,
                actual_wait_time__isnull=False,
                check_in_time__gte=timezone.now() - timedelta(days=cls.HISTORY_DAYS),
            )

            # Filter by specialist if specified
            if specialist_id:
                history_query = history_query.filter(specialist_id=specialist_id)

            # Extract hour of day for time-based patterns
            current_hour = current_time.hour
            current_weekday = current_time.weekday()  # 0-6 for Monday-Sunday

            # Find entries from similar time periods
            similar_time_entries = history_query.filter(
                check_in_time__hour__range=(current_hour - 1, current_hour + 1),
                check_in_time__week_day=current_weekday
                + 1,  # Django's week_day is 1-7 for Sunday-Saturday
            )

            # If not enough data, widen the search
            if similar_time_entries.count() < cls.MIN_DATA_POINTS:
                similar_time_entries = history_query.filter(
                    check_in_time__hour__range=(current_hour - 2, current_hour + 2)
                )

            # If still not enough data, use all historical data
            if similar_time_entries.count() < cls.MIN_DATA_POINTS:
                similar_time_entries = history_query

            # If no historical data, return default with low confidence
            if not similar_time_entries.exists():
                return {
                    "wait_minutes": cls.DEFAULT_WAIT_TIME,
                    "confidence": "low",
                    "method": "no_history",
                }

            # Calculate average wait time from historical data
            wait_times = []
            for entry in similar_time_entries:
                wait_time = entry.actual_wait_time
                if 1 <= wait_time <= 120:  # Reasonable range
                    wait_times.append(wait_time)

            if not wait_times:
                return {
                    "wait_minutes": cls.DEFAULT_WAIT_TIME,
                    "confidence": "low",
                    "method": "no_valid_history",
                }

            # Calculate statistics
            avg_wait = round(sum(wait_times) / len(wait_times))

            # Determine confidence based on sample size
            confidence = "low"
            if len(wait_times) >= cls.MIN_DATA_POINTS * 3:
                confidence = "high"
            elif len(wait_times) >= cls.MIN_DATA_POINTS:
                confidence = "medium"

            return {
                "wait_minutes": avg_wait,
                "confidence": confidence,
                "method": "historical_data",
            }

        except Exception as e:
            logger.error(f"Error predicting from historical data: {str(e)}")
            return {
                "wait_minutes": cls.DEFAULT_WAIT_TIME,
                "confidence": "low",
                "method": "error",
            }

    @staticmethod
    def _combine_predictions(
        current_prediction: Dict[str, Any],
        historical_prediction: Dict[str, Any],
        fallback_prediction: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Combine multiple prediction methods into a single prediction.

        Args:
            current_prediction: Prediction based on current queue
            historical_prediction: Prediction based on historical data
            fallback_prediction: Fallback prediction

        Returns:
            Dict with combined prediction
        """
        # Define confidence weights
        confidence_weights = {"high": 1.0, "medium": 0.6, "low": 0.3}

        # Get weights for each prediction
        current_weight = confidence_weights.get(current_prediction["confidence"], 0.3)
        historical_weight = confidence_weights.get(
            historical_prediction["confidence"], 0.3
        )
        fallback_weight = confidence_weights.get(fallback_prediction["confidence"], 0.3)

        # Calculate weighted average
        total_weight = current_weight + historical_weight + fallback_weight
        if total_weight == 0:
            # All have zero weight (shouldn't happen)
            return fallback_prediction

        weighted_minutes = (
            current_prediction["wait_minutes"] * current_weight
            + historical_prediction["wait_minutes"] * historical_weight
            + fallback_prediction["wait_minutes"] * fallback_weight
        ) / total_weight

        # Round to nearest integer
        combined_minutes = round(weighted_minutes)

        # Determine overall confidence
        highest_weight = max(current_weight, historical_weight, fallback_weight)
        overall_confidence = "low"
        for conf, weight in confidence_weights.items():
            if weight == highest_weight:
                overall_confidence = conf
                break

        # Determine primary method
        if current_weight == highest_weight:
            method = current_prediction["method"]
        elif historical_weight == highest_weight:
            method = historical_prediction["method"]
        else:
            method = fallback_prediction["method"]

        # If multiple methods have equal highest weight, use "combined"
        weight_counts = sum(
            1
            for w in [current_weight, historical_weight, fallback_weight]
            if w == highest_weight
        )
        if weight_counts > 1:
            method = "combined"

        return {
            "wait_minutes": combined_minutes,
            "confidence": overall_confidence,
            "method": method,
        }

    @staticmethod
    def _calculate_priority_factor(priority: int) -> float:
        """
        Calculate the wait time adjustment factor based on priority.

        Args:
            priority: Priority level (1-5)

        Returns:
            Wait time adjustment factor
        """
        # Priority factors (higher priority = shorter wait)
        priority_factors = {
            1: 1.2,  # Low priority - wait 20% longer
            2: 1.0,  # Normal priority - standard wait
            3: 0.8,  # High priority - wait 20% less
            4: 0.6,  # Urgent - wait 40% less
            5: 0.4,  # VIP - wait 60% less
        }

        return priority_factors.get(priority, 1.0)

    @classmethod
    def _predict_delay_from_specialist_schedule(
        cls, specialist_id: str, appointment_time: datetime
    ) -> Dict[str, Any]:
        """
        Predict appointment delay based on specialist's current schedule.

        Args:
            specialist_id: ID of the specialist
            appointment_time: Scheduled appointment time

        Returns:
            Dict with delay prediction details
        """
        try:
            # Only consider for appointments in the near future (within 3 hours)
            time_diff = (appointment_time - timezone.now()).total_seconds() / 60
            if time_diff > 180:  # More than 3 hours away
                return {
                    "delay_minutes": 0,
                    "confidence": "low",
                    "method": "too_far_future",
                }

            # Get specialist's current status
            current_activity = QueueEntry.objects.filter(
                specialist_id=specialist_id, status__in=["called", "serving"]
            ).first()

            # Check previous appointments today
            today_start = timezone.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            previous_appointments = Appointment.objects.filter(
                specialist_id=specialist_id,
                start_time__gte=today_start,
                start_time__lt=appointment_time,
                status__in=["scheduled", "confirmed", "in_progress"],
            ).order_by("-start_time")

            # Calculate potential delay
            delay_minutes = 0

            # If specialist is currently serving someone
            if current_activity and current_activity.status == "serving":
                # Estimate remaining time
                service = current_activity.queue.service
                service_duration = service.duration or cls.DEFAULT_SERVICE_TIME

                if current_activity.start_time:
                    # Calculate elapsed time
                    elapsed_minutes = (
                        timezone.now() - current_activity.start_time
                    ).total_seconds() / 60

                    # Estimate remaining time
                    remaining_minutes = max(0, service_duration - elapsed_minutes)

                    # Add to delay if this would extend past the appointment time
                    service_end_time = timezone.now() + timedelta(
                        minutes=remaining_minutes
                    )

                    if service_end_time > appointment_time:
                        delay_minutes += (
                            service_end_time - appointment_time
                        ).total_seconds() / 60

            # Check for running behind on previous appointments
            running_behind = 0

            for prev_appt in previous_appointments[:3]:  # Consider most recent 3
                # If appointment is completed, use actual vs scheduled time
                if prev_appt.status == "completed" and prev_appt.actual_end_time:
                    behind_minutes = (
                        prev_appt.actual_end_time - prev_appt.end_time
                    ).total_seconds() / 60
                    if behind_minutes > 0:
                        running_behind += behind_minutes
                # If appointment is scheduled but not started and start time has passed
                elif (
                    prev_appt.status in ["scheduled", "confirmed"]
                    and timezone.now() > prev_appt.start_time
                ):
                    # Calculate how late it is
                    late_minutes = (
                        timezone.now() - prev_appt.start_time
                    ).total_seconds() / 60

                    # Estimate that the appointment will take its full duration from now
                    service_duration = (
                        prev_appt.service.duration or cls.DEFAULT_SERVICE_TIME
                    )
                    estimated_end = timezone.now() + timedelta(minutes=service_duration)

                    # See if this pushes past the scheduled appointment time
                    if estimated_end > appointment_time:
                        delay_minutes = max(
                            delay_minutes,
                            (estimated_end - appointment_time).total_seconds() / 60,
                        )

            # If specialist is consistently running behind, factor this in
            if running_behind > 0 and previous_appointments.count() >= 2:
                avg_behind = running_behind / min(3, previous_appointments.count())
                delay_minutes = max(delay_minutes, avg_behind)

            # Determine confidence based on proximity to appointment time
            confidence = "low"
            if time_diff < 60:  # Less than 1 hour away
                confidence = "high"
            elif time_diff < 120:  # Less than 2 hours away
                confidence = "medium"

            # Round the final delay prediction
            delay_minutes = round(delay_minutes)

            return {
                "delay_minutes": delay_minutes,
                "confidence": confidence,
                "method": "specialist_schedule",
            }

        except Exception as e:
            logger.error(f"Error predicting delay from specialist schedule: {str(e)}")
            return {"delay_minutes": 0, "confidence": "low", "method": "error"}

    @classmethod
    def _predict_delay_from_historical_data(
        cls,
        service_id: str,
        specialist_id: str,
        shop_id: str,
        appointment_time: datetime,
    ) -> Dict[str, Any]:
        """
        Predict appointment delay based on historical data.

        Args:
            service_id: ID of the service
            specialist_id: ID of the specialist
            shop_id: ID of the shop
            appointment_time: Scheduled appointment time

        Returns:
            Dict with delay prediction details
        """
        try:
            # Get historical appointments for this specialist and service
            history_query = Appointment.objects.filter(
                service_id=service_id,
                specialist_id=specialist_id,
                shop_id=shop_id,
                status="completed",
                actual_start_time__isnull=False,
                scheduled_start_time__isnull=False,
                end_time__gte=timezone.now() - timedelta(days=cls.HISTORY_DAYS),
            )

            # Extract hour of day and day of week
            appt_hour = appointment_time.hour
            appt_weekday = appointment_time.weekday()

            # Find appointments from similar time periods
            similar_time_appointments = history_query.filter(
                start_time__hour__range=(appt_hour - 1, appt_hour + 1),
                start_time__week_day=appt_weekday
                + 1,  # Django's week_day is 1-7 for Sunday-Saturday
            )

            # If not enough data, widen the search
            if similar_time_appointments.count() < cls.MIN_DATA_POINTS:
                similar_time_appointments = history_query

            # If no historical data, return default with low confidence
            if not similar_time_appointments.exists():
                return {"delay_minutes": 0, "confidence": "low", "method": "no_history"}

            # Calculate average delay from historical data
            delays = []
            for appt in similar_time_appointments:
                if appt.actual_start_time and appt.scheduled_start_time:
                    delay_minutes = (
                        appt.actual_start_time - appt.scheduled_start_time
                    ).total_seconds() / 60
                    if 0 <= delay_minutes <= 60:  # Reasonable range
                        delays.append(delay_minutes)

            if not delays:
                return {
                    "delay_minutes": 0,
                    "confidence": "low",
                    "method": "no_valid_history",
                }

            # Calculate average delay
            avg_delay = round(sum(delays) / len(delays))

            # Determine confidence based on sample size
            confidence = "low"
            if len(delays) >= cls.MIN_DATA_POINTS * 3:
                confidence = "high"
            elif len(delays) >= cls.MIN_DATA_POINTS:
                confidence = "medium"

            return {
                "delay_minutes": avg_delay,
                "confidence": confidence,
                "method": "historical_data",
            }

        except Exception as e:
            logger.error(f"Error predicting delay from historical data: {str(e)}")
            return {"delay_minutes": 0, "confidence": "low", "method": "error"}

    @classmethod
    def _clear_prediction_cache(cls, queue_id: str) -> None:
        """
        Clear related prediction cache entries for a queue.

        Args:
            queue_id: ID of the service queue
        """
        # We don't have a way to search for keys with wildcards in Django cache,
        # so we'll just delete the typical pattern-matched keys for positions 1-20
        for position in range(1, 21):
            for priority in range(1, 6):
                cache_key = (
                    f"{cls.CACHE_PREFIX}queue:{queue_id}:pos:{position}:pri:{priority}"
                )
                cache.delete(cache_key)
