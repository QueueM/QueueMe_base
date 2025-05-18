"""
Queue wait time prediction algorithm.

This module provides sophisticated algorithms for predicting customer wait times
in queues based on historical data, current queue state, staffing levels, and
time-of-day patterns.
"""

import logging
from datetime import timedelta
from statistics import mean, median, stdev
from typing import Dict, Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


class WaitTimePredictor:
    """
    Sophisticated wait time prediction engine for queues.

    This class uses multiple factors to predict wait times:
    1. Historical service times for similar services
    2. Current queue length and composition
    3. Number of active staff/specialists
    4. Time of day and day of week patterns
    5. Current queue processing speed
    """

    # Default service times if no historical data
    DEFAULT_SERVICE_TIME = 15  # minutes
    DEFAULT_VARIANCE = 5  # minutes

    # Weight factors for prediction model
    HISTORICAL_WEIGHT = 0.6
    CURRENT_SPEED_WEIGHT = 0.3
    TIME_PATTERN_WEIGHT = 0.1

    # Minimum required samples for reliable prediction
    MIN_SAMPLES = 5

    def __init__(self, shop_id: str = None):
        """
        Initialize the wait time predictor.

        Args:
            shop_id: The ID of the shop for which to predict wait times
        """
        self.shop_id = shop_id

    def predict_wait_time(
        self,
        queue_id: str,
        position: int,
        service_id: str = None,
        specialist_id: str = None,
    ) -> Dict:
        """
        Predict wait time for a customer at a given position in the queue.

        Args:
            queue_id: The queue ID
            position: Customer's position in queue (1 = next in line)
            service_id: Optional service ID for more accurate prediction
            specialist_id: Optional specialist ID for more accurate prediction

        Returns:
            Dictionary with predicted wait time, confidence level, and range
        """
        try:
            # Import models here to avoid circular imports
            from apps.queueapp.models import Queue, QueueTicket

            # Get queue info
            queue = Queue.objects.get(id=queue_id)
            active_staff_count = self._get_active_staff_count(queue)

            # Base case - empty queue or position is 0
            if position <= 0:
                return {
                    "estimated_wait_minutes": 0,
                    "confidence": 1.0,
                    "range_minutes": (0, 0),
                }

            # If position is 1 and someone is currently being served,
            # we need to estimate the remaining time for the current service
            if position == 1:
                current_ticket = QueueTicket.objects.filter(queue=queue, status="serving").first()

                if current_ticket:
                    remaining_time = self._estimate_remaining_time(current_ticket)

                    return {
                        "estimated_wait_minutes": remaining_time,
                        "confidence": 0.8,  # Slightly higher confidence for currently serving
                        "range_minutes": (
                            max(0, int(remaining_time * 0.6)),
                            int(remaining_time * 1.4),
                        ),
                    }

            # Get tickets ahead
            tickets_ahead = QueueTicket.objects.filter(
                queue=queue, position__lt=position, status__in=["waiting", "called"]
            ).order_by("position")

            # If specific service or specialist requested, get service time for that
            service_times = []
            if service_id:
                service_times = self._get_service_time_statistics(service_id=service_id)
            elif specialist_id:
                service_times = self._get_service_time_statistics(specialist_id=specialist_id)

            # If no specific service/specialist or not enough data, get average for
            # all services in this queue
            if not service_times or service_times.get("count", 0) < self.MIN_SAMPLES:
                service_times = self._get_service_time_statistics(queue_id=queue_id)

            # Extract average service time (default if no historical data)
            avg_service_time = service_times.get("avg", self.DEFAULT_SERVICE_TIME)

            # Calculate capacity factor (how many can be served simultaneously)
            capacity_factor = min(active_staff_count, 1)  # At least 1 staff

            # Get service mix for tickets ahead if available
            if tickets_ahead.exists():
                total_estimated_time = 0

                for ticket in tickets_ahead:
                    # Get service-specific time if available, otherwise use average
                    if ticket.service_id:
                        ticket_service_stats = self._get_service_time_statistics(
                            service_id=ticket.service_id
                        )

                        if (
                            ticket_service_stats
                            and ticket_service_stats.get("count", 0) >= self.MIN_SAMPLES
                        ):
                            ticket_service_time = ticket_service_stats.get("avg")
                        else:
                            ticket_service_time = avg_service_time
                    else:
                        ticket_service_time = avg_service_time

                    total_estimated_time += ticket_service_time

                # Account for parallel processing with multiple staff
                if capacity_factor > 1:
                    total_estimated_time = total_estimated_time / capacity_factor
            else:
                # If no tickets ahead (shouldn't happen given position > 0)
                total_estimated_time = 0

            # Adjust for time of day and day of week patterns
            time_factor = self._get_time_pattern_factor(queue)

            # Get current processing speed if available
            current_speed_factor = self._get_current_speed_factor(queue)

            # Combine factors with weights
            if current_speed_factor:
                final_estimate = (
                    total_estimated_time * self.HISTORICAL_WEIGHT
                    + (total_estimated_time / current_speed_factor) * self.CURRENT_SPEED_WEIGHT
                    + (total_estimated_time * time_factor) * self.TIME_PATTERN_WEIGHT
                )
            else:
                final_estimate = total_estimated_time * time_factor

            # Calculate confidence and range
            confidence = self._calculate_prediction_confidence(
                service_times.get("count", 0),
                service_times.get("std_dev", self.DEFAULT_VARIANCE),
                position,
                bool(current_speed_factor),
            )

            variance = service_times.get("std_dev", self.DEFAULT_VARIANCE)
            lower_bound = max(0, final_estimate - variance)
            upper_bound = final_estimate + variance

            # Round to nearest minute
            final_estimate = round(final_estimate)
            lower_bound = round(lower_bound)
            upper_bound = round(upper_bound)

            return {
                "estimated_wait_minutes": final_estimate,
                "confidence": confidence,
                "range_minutes": (lower_bound, upper_bound),
            }

        except Exception as e:
            logger.exception(f"Error predicting wait time: {str(e)}")
            # Fallback to simple estimation
            return {
                "estimated_wait_minutes": position * self.DEFAULT_SERVICE_TIME,
                "confidence": 0.3,  # Low confidence for fallback
                "range_minutes": (
                    position * (self.DEFAULT_SERVICE_TIME - 5),
                    position * (self.DEFAULT_SERVICE_TIME + 5),
                ),
            }

    def _get_service_time_statistics(
        self, queue_id: str = None, service_id: str = None, specialist_id: str = None
    ) -> Dict:
        """
        Get historical service time statistics.

        Args:
            queue_id: Optional queue ID filter
            service_id: Optional service ID filter
            specialist_id: Optional specialist ID filter

        Returns:
            Dictionary with avg, median, std_dev, min, max, count
        """
        try:
            # Import here to avoid circular imports
            from apps.queueapp.models import QueueTicket

            # Build query filters
            filters = {
                "status": "served",
                "serve_time__isnull": False,
                "complete_time__isnull": False,
            }

            if queue_id:
                filters["queue_id"] = queue_id

            if service_id:
                filters["service_id"] = service_id

            if specialist_id:
                filters["specialist_id"] = specialist_id

            if self.shop_id:
                filters["queue__shop_id"] = self.shop_id

            # Get tickets from the last 30 days for relevant statistics
            thirty_days_ago = timezone.now() - timedelta(days=30)
            filters["complete_time__gte"] = thirty_days_ago

            # Query tickets
            tickets = QueueTicket.objects.filter(**filters)

            # Calculate service times in minutes
            service_times = []
            for ticket in tickets:
                service_duration = (ticket.complete_time - ticket.serve_time).total_seconds() / 60

                # Filter out unreasonable values (e.g. system errors, forgotten checkouts)
                if 0 < service_duration < 180:  # Between 0 and 3 hours
                    service_times.append(service_duration)

            # If we have enough samples
            if len(service_times) >= self.MIN_SAMPLES:
                return {
                    "avg": mean(service_times),
                    "median": median(service_times),
                    "std_dev": (
                        stdev(service_times) if len(service_times) > 1 else self.DEFAULT_VARIANCE
                    ),
                    "min": min(service_times),
                    "max": max(service_times),
                    "count": len(service_times),
                }
            else:
                # Not enough data for reliable statistics
                return {
                    "avg": self.DEFAULT_SERVICE_TIME,
                    "median": self.DEFAULT_SERVICE_TIME,
                    "std_dev": self.DEFAULT_VARIANCE,
                    "min": self.DEFAULT_SERVICE_TIME - self.DEFAULT_VARIANCE,
                    "max": self.DEFAULT_SERVICE_TIME + self.DEFAULT_VARIANCE,
                    "count": len(service_times),
                }

        except Exception as e:
            logger.exception(f"Error getting service time statistics: {str(e)}")
            return {
                "avg": self.DEFAULT_SERVICE_TIME,
                "median": self.DEFAULT_SERVICE_TIME,
                "std_dev": self.DEFAULT_VARIANCE,
                "min": self.DEFAULT_SERVICE_TIME - self.DEFAULT_VARIANCE,
                "max": self.DEFAULT_SERVICE_TIME + self.DEFAULT_VARIANCE,
                "count": 0,
            }

    def _get_active_staff_count(self, queue) -> int:
        """
        Get number of active staff currently serving from the queue.

        Args:
            queue: The Queue object

        Returns:
            Count of active staff
        """
        try:
            # Import here to avoid circular imports
            from apps.employeeapp.models import Employee
            from apps.queueapp.models import QueueTicket

            # Count tickets currently in 'serving' status
            currently_serving = QueueTicket.objects.filter(queue=queue, status="serving").count()

            # If some tickets are being served, that's our count
            if currently_serving > 0:
                return currently_serving

            # Otherwise check employees assigned to this queue
            if hasattr(queue, "shop"):
                # Get count of active employees who can serve from this queue
                employee_count = Employee.objects.filter(shop=queue.shop, is_active=True).count()

                return max(1, employee_count)  # At least 1 staff member

            return 1  # Default if can't determine

        except Exception as e:
            logger.debug(f"Error getting active staff count: {str(e)}")
            return 1  # Default to 1 active staff

    def _get_time_pattern_factor(self, queue) -> float:
        """
        Get time-of-day and day-of-week adjustment factor.

        Args:
            queue: The Queue object

        Returns:
            Multiplier for wait time based on temporal patterns
        """
        try:
            # Import here to avoid circular imports
            from apps.queueapp.models import QueueTicket

            now = timezone.now()
            current_hour = now.hour
            current_weekday = now.weekday()  # 0 = Monday, 6 = Sunday

            # If Sunday in Python (6), convert to our system (0)
            if current_weekday == 6:
                adj_weekday = 0
            else:
                adj_weekday = current_weekday + 1

            # Get average wait times for this hour and day from the last 8 weeks
            eight_weeks_ago = now - timedelta(days=56)

            # Find tickets completed in similar hours and days
            similar_tickets = QueueTicket.objects.filter(
                queue__shop=queue.shop,  # Same shop rather than exact queue
                status="served",
                serve_time__isnull=False,
                complete_time__isnull=False,
                complete_time__gte=eight_weeks_ago,
            )

            # Filter to same hour of day
            # unused_unused_hour_start = current_hour
            # unused_unused_hour_end = (current_hour + 1) % 24

            similar_hour_tickets = [
                ticket for ticket in similar_tickets if ticket.serve_time.hour == current_hour
            ]

            # Filter to same day of week
            similar_day_tickets = [
                ticket
                for ticket in similar_tickets
                if (ticket.serve_time.weekday() == 6 and adj_weekday == 0)
                or (ticket.serve_time.weekday() + 1 == adj_weekday)
            ]

            # Calculate average service times
            overall_avg = self.DEFAULT_SERVICE_TIME

            # Get overall average if we have enough data
            if len(similar_tickets) >= self.MIN_SAMPLES:
                service_times = []
                for ticket in similar_tickets:
                    duration = (ticket.complete_time - ticket.serve_time).total_seconds() / 60
                    if 0 < duration < 180:  # Sanity check
                        service_times.append(duration)

                if service_times:
                    overall_avg = mean(service_times)

            # Calculate hour-specific average
            hour_avg = overall_avg
            if len(similar_hour_tickets) >= self.MIN_SAMPLES:
                hour_times = []
                for ticket in similar_hour_tickets:
                    duration = (ticket.complete_time - ticket.serve_time).total_seconds() / 60
                    if 0 < duration < 180:
                        hour_times.append(duration)

                if hour_times:
                    hour_avg = mean(hour_times)

            # Calculate day-specific average
            day_avg = overall_avg
            if len(similar_day_tickets) >= self.MIN_SAMPLES:
                day_times = []
                for ticket in similar_day_tickets:
                    duration = (ticket.complete_time - ticket.serve_time).total_seconds() / 60
                    if 0 < duration < 180:
                        day_times.append(duration)

                if day_times:
                    day_avg = mean(day_times)

            # Calculate adjustment factors
            hour_factor = hour_avg / overall_avg if overall_avg > 0 else 1.0
            day_factor = day_avg / overall_avg if overall_avg > 0 else 1.0

            # Combine factors (with more weight to hour of day)
            combined_factor = hour_factor * 0.7 + day_factor * 0.3

            # Cap the factor to reasonable range
            return max(0.7, min(1.3, combined_factor))

        except Exception as e:
            logger.debug(f"Error calculating time pattern factor: {str(e)}")
            return 1.0  # Default factor (no adjustment)

    def _get_current_speed_factor(self, queue) -> Optional[float]:
        """
        Calculate current queue processing speed relative to historical average.

        Args:
            queue: The Queue object

        Returns:
            Speed factor (>1 means faster than average, <1 means slower) or None if unavailable
        """
        try:
            # Import here to avoid circular imports
            from apps.queueapp.models import QueueTicket

            # Check if we have enough recently completed tickets to estimate current speed
            now = timezone.now()
            one_hour_ago = now - timedelta(hours=1)

            # Get tickets served in the last hour
            recent_tickets = QueueTicket.objects.filter(
                queue=queue,
                status="served",
                serve_time__gte=one_hour_ago,
                complete_time__isnull=False,
            ).order_by("-complete_time")

            # Need at least 3 recent tickets to estimate speed
            if recent_tickets.count() < 3:
                return None

            # Calculate recent service times
            recent_times = []
            for ticket in recent_tickets:
                duration = (ticket.complete_time - ticket.serve_time).total_seconds() / 60
                if 0 < duration < 180:  # Sanity check
                    recent_times.append(duration)

            if not recent_times:
                return None

            recent_avg = mean(recent_times)

            # Get historical average for comparison
            historical_stats = self._get_service_time_statistics(queue_id=queue.id)
            historical_avg = historical_stats.get("avg", self.DEFAULT_SERVICE_TIME)

            # Calculate speed factor
            if historical_avg > 0:
                speed_factor = historical_avg / recent_avg

                # Cap to reasonable range
                return max(0.5, min(2.0, speed_factor))

            return None

        except Exception as e:
            logger.debug(f"Error calculating current speed factor: {str(e)}")
            return None

    def _estimate_remaining_time(self, current_ticket) -> float:
        """
        Estimate remaining time for current service.

        Args:
            current_ticket: The ticket currently being served

        Returns:
            Estimated remaining time in minutes
        """
        try:
            # If we know when service started and the service type
            if current_ticket.serve_time and current_ticket.service_id:
                # Get average duration for this service
                service_stats = self._get_service_time_statistics(
                    service_id=current_ticket.service_id
                )

                avg_duration = service_stats.get("avg", self.DEFAULT_SERVICE_TIME)

                # Calculate elapsed time
                now = timezone.now()
                elapsed_minutes = (now - current_ticket.serve_time).total_seconds() / 60

                # Estimate remaining time (with minimum of 1 minute)
                remaining = max(1, avg_duration - elapsed_minutes)

                return remaining
            else:
                # Fallback to default if we don't have serve time or service info
                return self.DEFAULT_SERVICE_TIME / 2  # Assume halfway through

        except Exception as e:
            logger.debug(f"Error estimating remaining time: {str(e)}")
            return self.DEFAULT_SERVICE_TIME / 2  # Default if estimation fails

    def _calculate_prediction_confidence(
        self, sample_count: int, std_dev: float, position: int, has_speed_data: bool
    ) -> float:
        """
        Calculate confidence level for the prediction.

        Args:
            sample_count: Number of historical samples used
            std_dev: Standard deviation of service times
            position: Position in queue
            has_speed_data: Whether current speed data is available

        Returns:
            Confidence score between 0 and 1
        """
        # Base confidence based on sample size
        if sample_count >= 100:
            base_confidence = 0.9
        elif sample_count >= 50:
            base_confidence = 0.8
        elif sample_count >= 20:
            base_confidence = 0.7
        elif sample_count >= 10:
            base_confidence = 0.6
        elif sample_count >= 5:
            base_confidence = 0.5
        else:
            base_confidence = 0.4

        # Position penalty - further in queue means less confidence
        position_factor = max(
            0.7, 1.0 - (position * 0.02)
        )  # Every position reduces confidence by 2% up to 30%

        # Variability penalty - higher std_dev means less confidence
        variability_ratio = std_dev / self.DEFAULT_SERVICE_TIME
        variability_factor = max(0.7, 1.0 - (variability_ratio * 0.1))  # Cap penalty at 30%

        # Speed data bonus
        speed_bonus = 0.1 if has_speed_data else 0.0

        # Calculate final confidence
        confidence = base_confidence * position_factor * variability_factor + speed_bonus

        # Cap at 0.95 - we can never be 100% confident
        return min(0.95, confidence)
