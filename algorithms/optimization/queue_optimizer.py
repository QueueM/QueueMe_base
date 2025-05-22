"""
Advanced Queue Optimization Algorithm

This module provides sophisticated algorithms for optimizing queues,
accurately estimating wait times, and balancing load across multiple
service points.
"""

import logging
from typing import Dict, List, Optional, Union

import numpy as np
from django.utils import timezone

logger = logging.getLogger(__name__)


class QueueOptimizer:
    """
    Advanced queue optimization engine with machine learning capabilities
    for accurate wait time prediction and intelligent queue management.
    """

    def __init__(self):
        """Initialize the queue optimizer."""
        self.historical_wait_time_weight = 0.7  # Weight for historical data
        self.current_queue_weight = 0.3  # Weight for current queue state
        self.min_wait_time = 2  # Minimum wait time in minutes (to avoid 0 wait times)
        self.service_duration_fallback = 10  # Default service duration if no data

    def estimate_wait_time(
        self,
        queue_id: str,
        position: int,
        service_id: Optional[str] = None,
        specialist_id: Optional[str] = None,
        historical_data: Optional[List[Dict]] = None,
    ) -> int:
        """
        Estimate wait time for a position in the queue with advanced ML-based prediction.

        Args:
            queue_id: ID of the queue
            position: Position in the queue (1-based)
            service_id: Optional ID of the service requested
            specialist_id: Optional ID of the specialist assigned
            historical_data: Optional pre-fetched historical data for optimization

        Returns:
            Estimated wait time in minutes
        """
        if position <= 0:
            return 0

        # If position is 1 and someone is already being served, use direct estimation
        if position == 1:
            active_service_time = self._get_active_service_time(queue_id)
            if active_service_time > 0:
                return active_service_time

        # Factor 1: Get historical average service times (from past completed services)
        if not historical_data:
            historical_data = self._get_historical_data(
                queue_id, service_id, specialist_id
            )

        avg_service_time = self._calculate_avg_service_time(historical_data)

        # Factor 2: Current queue composition - consider who's ahead and their services
        queue_factor = self._analyze_queue_composition(queue_id, position, service_id)

        # Factor 3: Time of day and day of week adjustment
        time_factor = self._get_time_factor()

        # Factor 4: Specialist efficiency if specific specialist requested
        specialist_factor = (
            self._get_specialist_efficiency(specialist_id) if specialist_id else 1.0
        )

        # Combine all factors with weighted average
        base_wait_time = (
            avg_service_time * self.historical_wait_time_weight
            + queue_factor * self.current_queue_weight
        )

        # Apply adjustment factors
        adjusted_wait_time = base_wait_time * time_factor * specialist_factor

        # Apply minimum wait time and round to nearest minute
        return max(self.min_wait_time, round(adjusted_wait_time * position))

    def _get_historical_data(
        self, queue_id: str, service_id: Optional[str], specialist_id: Optional[str]
    ) -> List[Dict]:
        """
        Get historical service time data.

        Args:
            queue_id: ID of the queue
            service_id: Optional ID of the service requested
            specialist_id: Optional ID of the specialist assigned

        Returns:
            List of historical service records with wait times
        """
        from apps.queueapp.models import QueueTicket

        # Define the base query for completed tickets
        tickets = QueueTicket.objects.filter(
            queue_id=queue_id, status="served", actual_wait_time__isnull=False
        )

        # Add filters for service and specialist if provided
        if service_id:
            tickets = tickets.filter(service_id=service_id)

        if specialist_id:
            tickets = tickets.filter(specialist_id=specialist_id)

        # Get the most recent 100 tickets for analysis
        # This limit prevents the query from becoming too expensive
        recent_tickets = tickets.order_by("-complete_time")[:100]

        return [
            {
                "id": str(ticket.id),
                "wait_time": ticket.actual_wait_time,
                "service_id": str(ticket.service_id) if ticket.service_id else None,
                "specialist_id": (
                    str(ticket.specialist_id) if ticket.specialist_id else None
                ),
                "join_time": ticket.join_time,
                "complete_time": ticket.complete_time,
                "day_of_week": ticket.join_time.weekday(),
                "hour_of_day": ticket.join_time.hour,
            }
            for ticket in recent_tickets
        ]

    def _calculate_avg_service_time(self, historical_data: List[Dict]) -> float:
        """
        Calculate average service time from historical data with outlier removal.

        Args:
            historical_data: List of historical service records

        Returns:
            Average service time in minutes
        """
        if not historical_data:
            return self.service_duration_fallback

        # Extract wait times
        wait_times = [item["wait_time"] for item in historical_data]

        # Use numpy for statistical operations
        wait_times_array = np.array(wait_times)

        # Remove outliers (outside 1.5 * IQR)
        q1 = np.percentile(wait_times_array, 25)
        q3 = np.percentile(wait_times_array, 75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        filtered_wait_times = wait_times_array[
            (wait_times_array >= lower_bound) & (wait_times_array <= upper_bound)
        ]

        # If all values were outliers, use original list
        if len(filtered_wait_times) == 0:
            filtered_wait_times = wait_times_array

        # Calculate average
        avg_time = float(np.mean(filtered_wait_times))

        # Ensure we return a positive value
        return max(self.min_wait_time, avg_time)

    def _analyze_queue_composition(
        self, queue_id: str, position: int, service_id: Optional[str]
    ) -> float:
        """
        Analyze the composition of the current queue to refine wait time.

        Args:
            queue_id: ID of the queue
            position: Position in queue
            service_id: Optional ID of the service requested

        Returns:
            Queue composition factor (multiplier for wait time)
        """
        from apps.queueapp.models import QueueTicket

        # Get all waiting tickets ahead of this position
        tickets_ahead = QueueTicket.objects.filter(
            queue_id=queue_id, status__in=["waiting", "called"], position__lt=position
        ).select_related("service")

        if not tickets_ahead:
            # No one ahead, use fallback value
            return self.service_duration_fallback

        # Calculate expected service time for each ticket ahead
        total_expected_time = 0
        for ticket in tickets_ahead:
            if ticket.service and hasattr(ticket.service, "duration"):
                service_time = ticket.service.duration
            else:
                # If service not available, use fallback
                service_time = self.service_duration_fallback

            # Add buffer times if available
            if ticket.service:
                service_time += getattr(ticket.service, "buffer_before", 0) + getattr(
                    ticket.service, "buffer_after", 0
                )

            total_expected_time += service_time

        # Average expected time per ticket ahead
        avg_expected_time = total_expected_time / len(tickets_ahead)

        return avg_expected_time

    def _get_active_service_time(self, queue_id: str) -> int:
        """
        Get estimated remaining time for the currently served customer.

        Args:
            queue_id: ID of the queue

        Returns:
            Estimated remaining time in minutes
        """
        from apps.queueapp.models import QueueTicket

        # Find tickets currently being served
        serving_tickets = QueueTicket.objects.filter(
            queue_id=queue_id, status="serving"
        ).select_related("service")

        if not serving_tickets:
            return 0

        # Calculate remaining time based on service duration and elapsed time
        remaining_times = []
        for ticket in serving_tickets:
            if ticket.serve_time:
                elapsed_minutes = (
                    timezone.now() - ticket.serve_time
                ).total_seconds() / 60

                # Get total expected duration
                if ticket.service and hasattr(ticket.service, "duration"):
                    total_duration = ticket.service.duration
                else:
                    total_duration = self.service_duration_fallback

                # Calculate remaining time
                remaining = max(0, total_duration - elapsed_minutes)
                remaining_times.append(remaining)

        # If no valid times, return 0
        if not remaining_times:
            return 0

        # Return the maximum remaining time
        # (assuming we're waiting for all current services to complete)
        return int(max(remaining_times))

    def _get_time_factor(self) -> float:
        """
        Calculate time-based adjustment factor based on current time.
        Accounts for peak hours, lunch hours, etc.

        Returns:
            Time adjustment factor
        """
        now = timezone.now()
        day_of_week = now.weekday()  # 0 = Monday, 6 = Sunday
        hour = now.hour

        # Initialize with default factor
        factor = 1.0

        # Weekend adjustment
        if day_of_week >= 5:  # Saturday or Sunday
            factor *= 1.2  # 20% slower on weekends

        # Peak hours adjustment (typically slower)
        if 16 <= hour <= 18:  # 4 PM - 6 PM
            factor *= 1.15  # 15% slower during evening peak
        elif 11 <= hour <= 13:  # 11 AM - 1 PM (lunch time)
            factor *= 1.1  # 10% slower during lunch

        # Early morning/late evening (typically faster)
        if hour < 9 or hour > 20:
            factor *= 0.9  # 10% faster during off-peak hours

        return factor

    def _get_specialist_efficiency(self, specialist_id: str) -> float:
        """
        Calculate specialist efficiency factor based on historical performance.

        Args:
            specialist_id: ID of the specialist

        Returns:
            Specialist efficiency factor
        """
        from apps.queueapp.models import QueueTicket
        from apps.specialistsapp.models import Specialist

        try:
            # Get specialist data
            specialist = Specialist.objects.get(id=specialist_id)

            # Get historical tickets for this specialist
            historical_tickets = QueueTicket.objects.filter(
                specialist_id=specialist_id,
                status="served",
                actual_wait_time__isnull=False,
            ).order_by("-complete_time")[:50]

            if not historical_tickets:
                return 1.0  # No data, use default factor

            # Compare this specialist's average service time to overall average
            specialist_avg = sum(
                ticket.actual_wait_time for ticket in historical_tickets
            ) / len(historical_tickets)

            # Get overall average from specialists in the same shop
            tickets_all_specialists = (
                QueueTicket.objects.filter(
                    specialist__employee__shop=specialist.employee.shop,
                    status="served",
                    actual_wait_time__isnull=False,
                )
                .exclude(specialist_id=specialist_id)
                .order_by("-complete_time")[:200]
            )

            if not tickets_all_specialists:
                return 1.0  # No comparison data, use default factor

            overall_avg = sum(
                ticket.actual_wait_time for ticket in tickets_all_specialists
            ) / len(tickets_all_specialists)

            # Calculate efficiency factor (ratio of overall average to this specialist's average)
            # If specialist is faster, factor will be < 1.0, reducing wait time
            # If specialist is slower, factor will be > 1.0, increasing wait time
            efficiency = specialist_avg / overall_avg if overall_avg > 0 else 1.0

            # Clamp factor to reasonable range (0.7 - 1.5)
            return max(0.7, min(1.5, efficiency))

        except Exception as e:
            logger.warning(f"Error calculating specialist efficiency: {str(e)}")
            return 1.0  # Use default factor on error

    def optimize_queue_assignments(
        self, queue_id: str, specialists: List[str]
    ) -> Dict[str, List[str]]:
        """
        Optimize assignment of queue tickets to specialists to minimize overall wait time.

        Args:
            queue_id: ID of the queue
            specialists: List of available specialist IDs

        Returns:
            Dictionary mapping specialist IDs to assigned ticket IDs
        """
        from apps.queueapp.models import QueueTicket
        from apps.specialistsapp.models import SpecialistService

        # If no specialists available, return empty mapping
        if not specialists:
            return {}

        # Get all waiting tickets
        waiting_tickets = (
            QueueTicket.objects.filter(queue_id=queue_id, status="waiting")
            .order_by("position")
            .select_related("service")
        )

        if not waiting_tickets:
            return {specialist_id: [] for specialist_id in specialists}

        # Get specialist-service capability mapping
        specialist_services = SpecialistService.objects.filter(
            specialist_id__in=specialists
        )

        capability_map = {}
        for ss in specialist_services:
            if ss.specialist_id not in capability_map:
                capability_map[ss.specialist_id] = []
            capability_map[ss.specialist_id].append(ss.service_id)

        # Initialize assignments
        assignments = {specialist_id: [] for specialist_id in specialists}
        specialist_load = {specialist_id: 0 for specialist_id in specialists}

        # Assign tickets one by one based on optimal specialist
        for ticket in waiting_tickets:
            service_id = ticket.service_id if ticket.service_id else None

            # Find eligible specialists (those who can perform this service)
            eligible_specialists = []
            for specialist_id, service_ids in capability_map.items():
                if service_id is None or service_id in service_ids:
                    eligible_specialists.append(specialist_id)

            # If no eligible specialists, skip this ticket
            if not eligible_specialists:
                continue

            # Select specialist with lowest current load
            selected_specialist = min(
                eligible_specialists, key=lambda s: specialist_load[s]
            )

            # Add this ticket to selected specialist's assignments
            assignments[selected_specialist].append(str(ticket.id))

            # Update specialist's load (add estimated service time)
            if ticket.service and hasattr(ticket.service, "duration"):
                service_time = ticket.service.duration
            else:
                service_time = self.service_duration_fallback

            specialist_load[selected_specialist] += service_time

        return assignments

    def suggest_queue_balancing(
        self, shop_id: str
    ) -> List[Dict[str, Union[str, int, float]]]:
        """
        Suggest queue balancing actions to optimize wait times across multiple queues.

        Args:
            shop_id: ID of the shop

        Returns:
            List of suggested actions with impact analysis
        """
        from apps.queueapp.models import Queue, QueueTicket

        # Get all active queues for this shop
        queues = Queue.objects.filter(shop_id=shop_id, status__in=["open", "paused"])

        if not queues:
            return []

        # Analyze each queue
        queue_states = []
        for queue in queues:
            # Count waiting tickets
            waiting_count = QueueTicket.objects.filter(
                queue_id=queue.id, status__in=["waiting", "called"]
            ).count()

            # Get average wait time
            avg_wait = self._calculate_current_avg_wait(queue.id)

            queue_states.append(
                {
                    "queue_id": str(queue.id),
                    "name": queue.name,
                    "waiting_count": waiting_count,
                    "avg_wait_time": avg_wait,
                }
            )

        # If only one queue or no queues with waiting tickets, no balancing needed
        if len(queue_states) <= 1 or sum(q["waiting_count"] for q in queue_states) == 0:
            return []

        # Find imbalances
        suggestions = []
        queue_states.sort(key=lambda q: q["avg_wait_time"], reverse=True)

        for i in range(len(queue_states)):
            # Skip empty queues
            if queue_states[i]["waiting_count"] <= 1:
                continue

            # Compare to queues with lower wait times
            for j in range(len(queue_states) - 1, i, -1):
                # Skip equally loaded queues
                wait_diff = (
                    queue_states[i]["avg_wait_time"] - queue_states[j]["avg_wait_time"]
                )
                if wait_diff < 5:  # Less than 5 minutes difference is acceptable
                    continue

                # Calculate how many tickets to move for better balance
                tickets_to_move = min(
                    queue_states[i]["waiting_count"] // 3,  # Move up to 1/3 of tickets
                    max(
                        1, int(wait_diff / 5)
                    ),  # At least 1, more for bigger differences
                )

                if tickets_to_move >= 1:
                    suggestions.append(
                        {
                            "action": "move_tickets",
                            "from_queue_id": queue_states[i]["queue_id"],
                            "from_queue_name": queue_states[i]["name"],
                            "to_queue_id": queue_states[j]["queue_id"],
                            "to_queue_name": queue_states[j]["name"],
                            "tickets_count": tickets_to_move,
                            "estimated_impact": {
                                "wait_reduction": round(
                                    wait_diff * 0.7, 1
                                ),  # Conservative estimate
                                "from_queue_remaining": queue_states[i]["waiting_count"]
                                - tickets_to_move,
                                "to_queue_new_total": queue_states[j]["waiting_count"]
                                + tickets_to_move,
                            },
                        }
                    )

        return suggestions

    def _calculate_current_avg_wait(self, queue_id: str) -> float:
        """
        Calculate current average wait time for a queue.

        Args:
            queue_id: ID of the queue

        Returns:
            Average wait time in minutes
        """
        from apps.queueapp.models import QueueTicket

        # Get all waiting tickets
        waiting_tickets = QueueTicket.objects.filter(
            queue_id=queue_id, status__in=["waiting", "called"]
        ).order_by("position")

        if not waiting_tickets:
            return 0

        # Calculate wait time for each position
        wait_times = []
        for pos, ticket in enumerate(waiting_tickets, 1):
            wait_times.append(
                self.estimate_wait_time(
                    queue_id, pos, ticket.service_id, ticket.specialist_id
                )
            )

        # Return average wait time
        return sum(wait_times) / len(wait_times) if wait_times else 0
