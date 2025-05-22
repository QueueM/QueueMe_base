"""
Queue Optimization Service

A sophisticated service for optimizing queues to improve efficiency,
reduce wait times, and balance workloads. This service implements advanced
queue management strategies including dynamic prioritization, queue rebalancing,
and optimal specialist allocation.

Key features:
1. Queue balancing across specialists
2. Dynamic priority adjustment based on wait time
3. Customer satisfaction optimization
4. Workload distribution
5. Service time prediction integration
"""

import logging
from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone

from apps.queueapp.models import QueueEntry, ServiceQueue
from apps.specialistsapp.models import Specialist

logger = logging.getLogger(__name__)


class QueueOptimizer:
    """
    Service for optimizing queues to improve efficiency and reduce wait times.
    """

    # Constants for optimization strategies
    MAX_WAIT_THRESHOLD = 30  # Minutes before considering priority boost
    SATISFACTION_THRESHOLD = (
        45  # Minutes before customer satisfaction decreases significantly
    )
    FAIRNESS_WEIGHT = 0.6  # Weight for fairness vs. efficiency (0-1)
    WORKLOAD_IMBALANCE_THRESHOLD = 0.3  # Allowed workload imbalance before rebalancing

    @classmethod
    def optimize_queues(
        cls,
        shop_id: str,
        optimize_strategy: str = "balanced",  # balanced, efficiency, fairness
    ) -> Dict[str, Any]:
        """
        Optimize all queues for a shop.

        Args:
            shop_id: ID of the shop
            optimize_strategy: Strategy to use for optimization

        Returns:
            Dict with optimization results
        """
        try:
            # Get active queues for this shop
            active_queues = ServiceQueue.objects.filter(
                shop_id=shop_id, status="active"
            )

            if not active_queues.exists():
                return {
                    "success": True,
                    "message": "No active queues to optimize",
                    "shop_id": shop_id,
                    "queues_optimized": 0,
                }

            # Track optimization results
            optimization_results = []
            queues_modified = 0
            entries_modified = 0

            # Process each queue
            for queue in active_queues:
                result = cls.optimize_single_queue(
                    queue_id=str(queue.id), optimize_strategy=optimize_strategy
                )

                if result["success"] and result["entries_modified"] > 0:
                    queues_modified += 1
                    entries_modified += result["entries_modified"]

                optimization_results.append(
                    {
                        "queue_id": str(queue.id),
                        "service_name": queue.service.name,
                        "entries_modified": result["entries_modified"],
                        "actions": result["actions"],
                    }
                )

            return {
                "success": True,
                "message": f"Optimized {queues_modified} queues with {entries_modified} modified entries",
                "shop_id": shop_id,
                "queues_optimized": queues_modified,
                "entries_modified": entries_modified,
                "strategy": optimize_strategy,
                "queue_results": optimization_results,
            }

        except Exception as e:
            logger.error(f"Error optimizing queues: {str(e)}")
            return {
                "success": False,
                "message": f"Error optimizing queues: {str(e)}",
                "shop_id": shop_id,
                "queues_optimized": 0,
            }

    @classmethod
    def optimize_single_queue(
        cls,
        queue_id: str,
        optimize_strategy: str = "balanced",  # balanced, efficiency, fairness
    ) -> Dict[str, Any]:
        """
        Optimize a single queue.

        Args:
            queue_id: ID of the service queue
            optimize_strategy: Strategy to use for optimization

        Returns:
            Dict with optimization results
        """
        try:
            # Get the queue
            try:
                queue = ServiceQueue.objects.select_related("service").get(id=queue_id)
            except ServiceQueue.DoesNotExist:
                return {
                    "success": False,
                    "message": "Queue not found",
                    "queue_id": queue_id,
                    "entries_modified": 0,
                    "actions": [],
                }

            # Check if queue is active
            if queue.status != "active":
                return {
                    "success": False,
                    "message": f"Queue is not active (status: {queue.status})",
                    "queue_id": queue_id,
                    "entries_modified": 0,
                    "actions": [],
                }

            # Get waiting entries in the queue
            waiting_entries = QueueEntry.objects.filter(
                queue_id=queue_id, status="waiting"
            ).order_by("-priority", "position")

            if not waiting_entries.exists():
                return {
                    "success": True,
                    "message": "No waiting entries to optimize",
                    "queue_id": queue_id,
                    "entries_modified": 0,
                    "actions": [],
                }

            actions = []
            entries_modified = 0

            with transaction.atomic():
                # 1. Adjust priorities for long-waiting customers
                priority_updates = cls._adjust_priorities_for_wait_time(
                    queue_entries=waiting_entries, fairness_weight=cls.FAIRNESS_WEIGHT
                )

                if priority_updates:
                    for entry_id, old_priority, new_priority in priority_updates:
                        entry = QueueEntry.objects.get(id=entry_id)
                        entry.priority = new_priority
                        entry.notes = f"{entry.notes}\nAuto-adjusted priority: {old_priority} -> {new_priority}"
                        entry.save(update_fields=["priority", "notes"])
                        entries_modified += 1

                        actions.append(
                            {
                                "action": "priority_adjustment",
                                "entry_id": str(entry_id),
                                "old_priority": old_priority,
                                "new_priority": new_priority,
                                "reason": "long_wait_time",
                            }
                        )

                # 2. Optimize position sequencing
                if optimize_strategy == "efficiency":
                    # Efficiency-focused: Prioritize faster services, high-value customers
                    position_updates = cls._optimize_for_efficiency(
                        queue=queue,
                        queue_entries=waiting_entries.order_by(
                            "-priority", "position"
                        ),  # Refresh order
                    )
                elif optimize_strategy == "fairness":
                    # Fairness-focused: Strictly respect check-in times and priorities
                    position_updates = cls._optimize_for_fairness(
                        queue=queue,
                        queue_entries=waiting_entries.order_by(
                            "-priority", "position"
                        ),  # Refresh order
                    )
                else:
                    # Balanced approach (default)
                    position_updates = cls._optimize_balanced(
                        queue=queue,
                        queue_entries=waiting_entries.order_by(
                            "-priority", "position"
                        ),  # Refresh order
                        fairness_weight=cls.FAIRNESS_WEIGHT,
                    )

                if position_updates:
                    for entry_id, old_position, new_position in position_updates:
                        entry = QueueEntry.objects.get(id=entry_id)
                        entry.position = new_position
                        entry.save(update_fields=["position"])
                        entries_modified += 1

                        actions.append(
                            {
                                "action": "position_update",
                                "entry_id": str(entry_id),
                                "old_position": old_position,
                                "new_position": new_position,
                                "reason": optimize_strategy,
                            }
                        )

            # Return optimization results
            return {
                "success": True,
                "message": f"Queue optimized with {entries_modified} modifications",
                "queue_id": queue_id,
                "service_id": str(queue.service_id),
                "service_name": queue.service.name,
                "strategy": optimize_strategy,
                "entries_modified": entries_modified,
                "actions": actions,
            }

        except Exception as e:
            logger.error(f"Error optimizing queue {queue_id}: {str(e)}")
            return {
                "success": False,
                "message": f"Error optimizing queue: {str(e)}",
                "queue_id": queue_id,
                "entries_modified": 0,
                "actions": [],
            }

    @classmethod
    def balance_queues_across_specialists(
        cls, shop_id: str, service_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Balance queue load across specialists by reassigning specialists.

        Args:
            shop_id: ID of the shop
            service_ids: Optional list of service IDs to balance (if None, balance all)

        Returns:
            Dict with balancing results
        """
        try:
            # Build query for active queues
            queues_query = ServiceQueue.objects.filter(shop_id=shop_id, status="active")

            # Filter by service IDs if provided
            if service_ids:
                queues_query = queues_query.filter(service_id__in=service_ids)

            # Get active queues with waiting entries
            active_queues = []
            for queue in queues_query:
                waiting_count = QueueEntry.objects.filter(
                    queue_id=queue.id, status="waiting"
                ).count()

                if waiting_count > 0:
                    active_queues.append((queue, waiting_count))

            if not active_queues:
                return {
                    "success": True,
                    "message": "No active queues with waiting entries to balance",
                    "shop_id": shop_id,
                    "reassignments": 0,
                }

            # Get active specialists
            active_specialists = cls._get_active_specialists(shop_id)

            if not active_specialists:
                return {
                    "success": False,
                    "message": "No active specialists available for balancing",
                    "shop_id": shop_id,
                    "reassignments": 0,
                }

            # Calculate current load for each specialist
            specialist_loads = cls._calculate_specialist_loads(active_specialists)

            # Track reassignments
            reassignments = []

            with transaction.atomic():
                # Sort queues by waiting count (highest first)
                active_queues.sort(key=lambda x: x[1], reverse=True)

                for queue, waiting_count in active_queues:
                    # Get service and specialists who can provide it
                    service = queue.service
                    service_specialists = active_specialists.filter(
                        specialist_services__service_id=service.id
                    )

                    if not service_specialists:
                        continue

                    # Get entries that need a specialist assigned
                    unassigned_entries = QueueEntry.objects.filter(
                        queue_id=queue.id, status="waiting", specialist_id__isnull=True
                    ).order_by("-priority", "position")

                    # Get entries with specialists already assigned
                    assigned_entries = QueueEntry.objects.filter(
                        queue_id=queue.id, status="waiting", specialist_id__isnull=False
                    )

                    # Check if rebalancing is needed for assigned entries
                    if assigned_entries.exists():
                        assigned_loads = defaultdict(int)
                        for entry in assigned_entries:
                            assigned_loads[str(entry.specialist_id)] += 1

                        # Calculate load imbalance
                        max_load = max(assigned_loads.values()) if assigned_loads else 0
                        min_load = min(assigned_loads.values()) if assigned_loads else 0

                        # Rebalance if imbalance exceeds threshold
                        if max_load - min_load >= 2:
                            for entry in assigned_entries:
                                specialist_id = str(entry.specialist_id)

                                # Find a less loaded specialist for this service
                                if assigned_loads[specialist_id] > min_load + 1:
                                    # Find the least loaded specialist
                                    least_loaded = None
                                    min_load_value = float("inf")

                                    for spec in service_specialists:
                                        spec_id = str(spec.id)
                                        current_load = assigned_loads.get(spec_id, 0)

                                        if current_load < min_load_value:
                                            least_loaded = spec
                                            min_load_value = current_load

                                    if (
                                        least_loaded
                                        and min_load_value
                                        < assigned_loads[specialist_id] - 1
                                    ):
                                        # Reassign this entry
                                        old_specialist_id = entry.specialist_id
                                        entry.specialist_id = least_loaded.id
                                        entry.save(update_fields=["specialist_id"])

                                        # Update load tracking
                                        assigned_loads[specialist_id] -= 1
                                        assigned_loads[str(least_loaded.id)] += 1

                                        # Record reassignment
                                        reassignments.append(
                                            {
                                                "entry_id": str(entry.id),
                                                "old_specialist_id": str(
                                                    old_specialist_id
                                                ),
                                                "new_specialist_id": str(
                                                    least_loaded.id
                                                ),
                                                "reason": "load_balancing",
                                            }
                                        )

                    # Assign specialists to unassigned entries based on load
                    for entry in unassigned_entries:
                        # Find the least loaded specialist who can perform this service
                        least_loaded = None
                        min_load_value = float("inf")

                        for spec in service_specialists:
                            # Get current load
                            spec_id = str(spec.id)
                            current_load = specialist_loads.get(spec_id, 0)

                            if current_load < min_load_value:
                                least_loaded = spec
                                min_load_value = current_load

                        if least_loaded:
                            # Assign this specialist
                            entry.specialist_id = least_loaded.id
                            entry.save(update_fields=["specialist_id"])

                            # Update load tracking
                            specialist_loads[str(least_loaded.id)] += 1

                            # Record assignment
                            reassignments.append(
                                {
                                    "entry_id": str(entry.id),
                                    "new_specialist_id": str(least_loaded.id),
                                    "reason": "initial_assignment",
                                }
                            )

            return {
                "success": True,
                "message": f"Balanced queues with {len(reassignments)} specialist reassignments",
                "shop_id": shop_id,
                "reassignments": len(reassignments),
                "details": reassignments,
            }

        except Exception as e:
            logger.error(f"Error balancing queues across specialists: {str(e)}")
            return {
                "success": False,
                "message": f"Error balancing queues: {str(e)}",
                "shop_id": shop_id,
                "reassignments": 0,
            }

    @classmethod
    def optimize_for_appointment_integration(cls, shop_id: str) -> Dict[str, Any]:
        """
        Optimize queues to incorporate scheduled appointments efficiently.

        Args:
            shop_id: ID of the shop

        Returns:
            Dict with optimization results
        """
        try:
            # Get active queues
            active_queues = ServiceQueue.objects.filter(
                shop_id=shop_id, status="active"
            )

            if not active_queues.exists():
                return {
                    "success": True,
                    "message": "No active queues to optimize",
                    "shop_id": shop_id,
                    "entries_modified": 0,
                }

            # Get upcoming appointments (next 60 minutes)
            upcoming_cutoff = timezone.now() + timedelta(minutes=60)

            upcoming_appointments = QueueEntry.objects.filter(
                queue__shop_id=shop_id,
                entry_type="appointment",
                status="waiting",
                appointment_id__isnull=False,
            ).select_related("appointment")

            # Filter to just those appointments that have a time
            timed_appointments = []
            for entry in upcoming_appointments:
                if (
                    hasattr(entry, "appointment")
                    and entry.appointment
                    and entry.appointment.start_time
                ):
                    if entry.appointment.start_time <= upcoming_cutoff:
                        timed_appointments.append(entry)

            if not timed_appointments:
                return {
                    "success": True,
                    "message": "No upcoming appointments to integrate",
                    "shop_id": shop_id,
                    "entries_modified": 0,
                }

            # Track modifications
            entries_modified = 0
            modifications = []

            with transaction.atomic():
                # Sort appointments by scheduled time
                timed_appointments.sort(key=lambda x: x.appointment.start_time)

                # Process each appointment
                for entry in timed_appointments:
                    appointment = entry.appointment
                    time_until_appointment = (
                        appointment.start_time - timezone.now()
                    ).total_seconds() / 60

                    # Adjust priority based on appointment proximity
                    new_priority = cls._calculate_appointment_priority(
                        time_until_appointment
                    )

                    if entry.priority != new_priority:
                        old_priority = entry.priority
                        entry.priority = new_priority
                        entry.save(update_fields=["priority"])
                        entries_modified += 1

                        modifications.append(
                            {
                                "action": "priority_adjustment",
                                "entry_id": str(entry.id),
                                "appointment_id": str(appointment.id),
                                "old_priority": old_priority,
                                "new_priority": new_priority,
                                "minutes_until_appointment": round(
                                    time_until_appointment
                                ),
                            }
                        )

                # Reorder queue positions based on updated priorities
                for queue in active_queues:
                    # Get waiting entries for this queue
                    waiting_entries = QueueEntry.objects.filter(
                        queue_id=queue.id, status="waiting"
                    ).order_by("-priority", "position")

                    # Update positions to match priority order
                    position = 1
                    for entry in waiting_entries:
                        if entry.position != position:
                            entry.position = position
                            entry.save(update_fields=["position"])
                            entries_modified += 1
                        position += 1

            return {
                "success": True,
                "message": f"Optimized queues with {entries_modified} modifications for appointments",
                "shop_id": shop_id,
                "entries_modified": entries_modified,
                "modifications": modifications,
            }

        except Exception as e:
            logger.error(f"Error optimizing for appointment integration: {str(e)}")
            return {
                "success": False,
                "message": f"Error optimizing for appointments: {str(e)}",
                "shop_id": shop_id,
                "entries_modified": 0,
            }

    # ------------------------------------------------------------------------
    # Helper methods for optimization
    # ------------------------------------------------------------------------

    @classmethod
    def _adjust_priorities_for_wait_time(
        cls, queue_entries: List[QueueEntry], fairness_weight: float = 0.6
    ) -> List[Tuple[str, int, int]]:
        """
        Adjust priorities for entries that have been waiting too long.

        Args:
            queue_entries: List of queue entries
            fairness_weight: Weight for fairness vs. efficiency (0-1)

        Returns:
            List of (entry_id, old_priority, new_priority) tuples
        """
        updates = []

        for entry in queue_entries:
            # Calculate wait time in minutes
            wait_time = (timezone.now() - entry.check_in_time).total_seconds() / 60

            # Only adjust if wait time exceeds threshold
            if wait_time > cls.MAX_WAIT_THRESHOLD:
                old_priority = entry.priority

                # Calculate new priority based on wait time
                # More weight to fairness means more aggressive priority boosting
                if wait_time > cls.SATISFACTION_THRESHOLD:
                    # Severe wait time, significant boost
                    new_priority = max(old_priority, 4)  # Boost to urgent
                elif wait_time > cls.MAX_WAIT_THRESHOLD * 1.5:
                    # Moderate wait time, moderate boost
                    new_priority = max(old_priority, 3)  # Boost to high
                else:
                    # Just over threshold, minor boost
                    new_priority = min(5, old_priority + 1)  # Boost by one level

                # Only record if priority changed
                if new_priority != old_priority:
                    updates.append((str(entry.id), old_priority, new_priority))

        return updates

    @classmethod
    def _optimize_for_efficiency(
        cls, queue: ServiceQueue, queue_entries: List[QueueEntry]
    ) -> List[Tuple[str, int, int]]:
        """
        Optimize queue positions for maximum efficiency.

        Args:
            queue: The service queue
            queue_entries: List of queue entries ordered by priority, position

        Returns:
            List of (entry_id, old_position, new_position) tuples
        """
        updates = []

        # Group entries by priority
        priority_groups = defaultdict(list)
        for entry in queue_entries:
            priority_groups[entry.priority].append(entry)

        # Process each priority group
        new_position = 1
        for priority in sorted(priority_groups.keys(), reverse=True):
            entries = priority_groups[priority]

            # For efficiency, prioritize:
            # 1. VIP and appointment customers first
            # 2. Then shorter services
            # 3. Then regular customers by check-in time

            # Get service durations for efficiency sorting
            service_durations = {}
            for entry in entries:
                # Estimate service duration
                if entry.queue.service_id not in service_durations:
                    try:
                        service = entry.queue.service
                        service_durations[entry.queue.service_id] = (
                            service.duration or 15
                        )
                    except Exception:
                        service_durations[entry.queue.service_id] = 15

            # Sort entries within priority group
            # For high efficiency: VIPs first, then shorter services
            sorted_entries = []

            # First, VIPs and appointments
            vip_entries = [e for e in entries if e.entry_type in ["vip", "appointment"]]
            vip_entries.sort(key=lambda e: e.check_in_time)  # Earlier check-in first
            sorted_entries.extend(vip_entries)

            # Next, regular entries sorted by service duration (shorter first)
            regular_entries = [
                e for e in entries if e.entry_type not in ["vip", "appointment"]
            ]
            regular_entries.sort(
                key=lambda e: (
                    service_durations.get(e.queue.service_id, 15),
                    e.check_in_time,
                )
            )
            sorted_entries.extend(regular_entries)

            # Update positions
            for entry in sorted_entries:
                old_position = entry.position
                if old_position != new_position:
                    updates.append((str(entry.id), old_position, new_position))
                new_position += 1

        return updates

    @classmethod
    def _optimize_for_fairness(
        cls, queue: ServiceQueue, queue_entries: List[QueueEntry]
    ) -> List[Tuple[str, int, int]]:
        """
        Optimize queue positions for maximum fairness.

        Args:
            queue: The service queue
            queue_entries: List of queue entries ordered by priority, position

        Returns:
            List of (entry_id, old_position, new_position) tuples
        """
        updates = []

        # Group entries by priority
        priority_groups = defaultdict(list)
        for entry in queue_entries:
            priority_groups[entry.priority].append(entry)

        # Process each priority group
        new_position = 1
        for priority in sorted(priority_groups.keys(), reverse=True):
            entries = priority_groups[priority]

            # For fairness, strictly respect check-in order within priority
            sorted_entries = sorted(entries, key=lambda e: e.check_in_time)

            # Update positions
            for entry in sorted_entries:
                old_position = entry.position
                if old_position != new_position:
                    updates.append((str(entry.id), old_position, new_position))
                new_position += 1

        return updates

    @classmethod
    def _optimize_balanced(
        cls,
        queue: ServiceQueue,
        queue_entries: List[QueueEntry],
        fairness_weight: float = 0.6,
    ) -> List[Tuple[str, int, int]]:
        """
        Optimize queue positions with a balance of efficiency and fairness.

        Args:
            queue: The service queue
            queue_entries: List of queue entries ordered by priority, position
            fairness_weight: Weight for fairness vs. efficiency (0-1)

        Returns:
            List of (entry_id, old_position, new_position) tuples
        """
        updates = []

        # Group entries by priority
        priority_groups = defaultdict(list)
        for entry in queue_entries:
            priority_groups[entry.priority].append(entry)

        # Process each priority group
        new_position = 1
        for priority in sorted(priority_groups.keys(), reverse=True):
            entries = priority_groups[priority]

            # Get service durations for efficiency component
            service_durations = {}
            for entry in entries:
                if entry.queue.service_id not in service_durations:
                    try:
                        service = entry.queue.service
                        service_durations[entry.queue.service_id] = (
                            service.duration or 15
                        )
                    except Exception:
                        service_durations[entry.queue.service_id] = 15

            # For VIPs and appointments, always prioritize by check-in time
            if priority >= 4:  # Urgent and VIP priorities
                sorted_entries = sorted(entries, key=lambda e: e.check_in_time)
            else:
                # For regular priorities, balance check-in time and service duration
                # Calculate a score for each entry (lower is better)
                entry_scores = []

                for entry in entries:
                    # Normalize check-in time to 0-1 scale
                    earliest_time = min(e.check_in_time for e in entries)
                    latest_time = max(e.check_in_time for e in entries)

                    if latest_time == earliest_time:
                        time_factor = 0  # All checked in at same time
                    else:
                        time_diff = (
                            entry.check_in_time - earliest_time
                        ).total_seconds()
                        max_diff = (latest_time - earliest_time).total_seconds()
                        time_factor = time_diff / max_diff

                    # Normalize service duration to 0-1 scale
                    durations = list(service_durations.values())
                    min_duration = min(durations)
                    max_duration = max(durations)

                    if max_duration == min_duration:
                        duration_factor = 0  # All services same duration
                    else:
                        duration = service_durations.get(entry.queue.service_id, 15)
                        duration_factor = (duration - min_duration) / (
                            max_duration - min_duration
                        )

                    # Combined score (lower is better)
                    score = (time_factor * fairness_weight) + (
                        duration_factor * (1 - fairness_weight)
                    )

                    entry_scores.append((entry, score))

                # Sort by score
                entry_scores.sort(key=lambda x: x[1])
                sorted_entries = [entry for entry, _ in entry_scores]

            # Update positions
            for entry in sorted_entries:
                old_position = entry.position
                if old_position != new_position:
                    updates.append((str(entry.id), old_position, new_position))
                new_position += 1

        return updates

    @classmethod
    def _get_active_specialists(cls, shop_id: str) -> List[Specialist]:
        """
        Get active specialists for a shop.

        Args:
            shop_id: ID of the shop

        Returns:
            QuerySet of active specialists
        """
        # Get specialists in this shop
        return Specialist.objects.filter(
            employee__company__shops=shop_id, is_active=True
        )

    @classmethod
    def _calculate_specialist_loads(
        cls, specialists: List[Specialist]
    ) -> Dict[str, int]:
        """
        Calculate current load for each specialist.

        Args:
            specialists: List of specialists

        Returns:
            Dict mapping specialist IDs to load counts
        """
        specialist_loads = defaultdict(int)

        # Count active entries (called, serving)
        for specialist in specialists:
            active_count = QueueEntry.objects.filter(
                specialist_id=specialist.id, status__in=["called", "serving"]
            ).count()

            # Count waiting entries assigned to this specialist
            waiting_count = QueueEntry.objects.filter(
                specialist_id=specialist.id, status="waiting"
            ).count()

            # Calculate total load
            specialist_loads[str(specialist.id)] = active_count + waiting_count

        return specialist_loads

    @staticmethod
    def _calculate_appointment_priority(minutes_until_appointment: float) -> int:
        """
        Calculate priority for an appointment based on proximity.

        Args:
            minutes_until_appointment: Minutes until appointment time

        Returns:
            Priority level (1-5)
        """
        if minutes_until_appointment <= 5:
            return 5  # Immediate priority (VIP)
        elif minutes_until_appointment <= 15:
            return 4  # Urgent
        elif minutes_until_appointment <= 30:
            return 3  # High
        else:
            return 2  # Normal
