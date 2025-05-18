import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MultiServiceScheduler:
    """
    Advanced algorithm for scheduling multiple services in an optimal
    sequence while avoiding conflicts and minimizing wait times.

    This algorithm helps customers book multiple services efficiently by:
    1. Finding the optimal sequence of services
    2. Minimizing gaps between services
    3. Considering specialist availability
    4. Avoiding timing conflicts
    5. Optimizing overall appointment time
    """

    def __init__(
        self,
        min_break_between_services: int = 10,
        max_break_between_services: int = 60,
        prefer_same_specialist: bool = True,
        allow_parallel_services: bool = False,
        max_total_duration: Optional[int] = None,
    ):
        """
        Initialize the multi-service scheduler with configurable parameters.

        Args:
            min_break_between_services: Minimum break between services in minutes
            max_break_between_services: Maximum acceptable break between services in minutes
            prefer_same_specialist: Whether to prefer the same specialist for consecutive services
            allow_parallel_services: Whether to allow services to be performed in parallel
                                     (by different specialists)
            max_total_duration: Maximum total duration for all services including breaks
                                (None = unlimited)
        """
        self.min_break_between_services = min_break_between_services
        self.max_break_between_services = max_break_between_services
        self.prefer_same_specialist = prefer_same_specialist
        self.allow_parallel_services = allow_parallel_services
        self.max_total_duration = max_total_duration

    def schedule_multiple_services(
        self,
        service_ids: List[str],
        preferred_date: datetime.date,
        preferred_time_window: Optional[Tuple[datetime.time, datetime.time]] = None,
        services_data: List[Dict] = None,
        specialist_availability: Dict[str, List[Dict]] = None,
        existing_appointments: List[Dict] = None,
        customer_id: Optional[str] = None,
        preferred_specialist_id: Optional[str] = None,
    ) -> Dict:
        """
        Schedule multiple services optimally for a customer.

        Args:
            service_ids: List of service IDs to schedule
            preferred_date: Preferred date for appointments
            preferred_time_window: Optional tuple of (start_time, end_time) for the appointment window
            services_data: List of service objects with fields:
                - id: Service ID
                - name: Service name
                - duration: Service duration in minutes
                - buffer_before: Buffer time before service in minutes
                - buffer_after: Buffer time after service in minutes
                - specialists: List of specialist IDs who can perform this service
            specialist_availability: Dict mapping specialist IDs to their availability windows
            existing_appointments: List of existing appointments for conflict checking
            customer_id: Optional customer ID for personalization
            preferred_specialist_id: Optional preferred specialist for services

        Returns:
            A dictionary containing:
            - success: Boolean indicating if a schedule was found
            - schedule: List of scheduled appointments with details
            - total_duration: Total duration of the appointment including breaks
            - start_time: Start time of the first service
            - end_time: End time of the last service
            - waiting_time: Total waiting time between services
            - specialists: List of specialists assigned to services
            - alternative_schedules: List of alternative schedule options
        """
        # Initialize result structure
        result = {
            "success": False,
            "schedule": [],
            "total_duration": 0,
            "start_time": None,
            "end_time": None,
            "waiting_time": 0,
            "specialists": [],
            "alternative_schedules": [],
        }

        # Validate inputs
        if not service_ids or not services_data or not specialist_availability:
            return result

        # Create service map for quick lookup
        service_map = {service["id"]: service for service in services_data}

        # Ensure all requested services exist in the data
        for service_id in service_ids:
            if service_id not in service_map:
                return result

        # Step 1: Calculate service dependencies and constraints
        service_constraints = self._calculate_service_constraints(service_ids, service_map)

        # Step 2: Get available time slots for each service
        available_slots = self._get_available_slots(
            service_ids,
            preferred_date,
            preferred_time_window,
            service_map,
            specialist_availability,
            existing_appointments,
        )

        # If any service has no available slots, scheduling is impossible
        for service_id, slots in available_slots.items():
            if not slots:
                return result

        # Step 3: Find optimal service ordering based on constraints and availability
        service_ordering = self._determine_service_ordering(
            service_ids, service_constraints, available_slots, service_map
        )

        # Step 4: Generate possible schedules
        possible_schedules = self._generate_possible_schedules(
            service_ordering,
            available_slots,
            service_map,
            specialist_availability,
            preferred_specialist_id,
        )

        # If no valid schedules found, return failure
        if not possible_schedules:
            return result

        # Step 5: Rank and select the best schedule
        ranked_schedules = self._rank_schedules(
            possible_schedules, preferred_time_window, preferred_specialist_id
        )

        # Get the best schedule
        best_schedule = ranked_schedules[0] if ranked_schedules else None

        if not best_schedule:
            return result

        # Step 6: Prepare detailed schedule for return
        result["success"] = True
        result["schedule"] = best_schedule["appointments"]
        result["total_duration"] = best_schedule["total_duration"]
        result["start_time"] = best_schedule["start_time"]
        result["end_time"] = best_schedule["end_time"]
        result["waiting_time"] = best_schedule["waiting_time"]
        result["specialists"] = best_schedule["specialists"]

        # Include alternative schedules (up to 3)
        if len(ranked_schedules) > 1:
            result["alternative_schedules"] = ranked_schedules[1:4]

        return result

    def _calculate_service_constraints(
        self, service_ids: List[str], service_map: Dict[str, Dict]
    ) -> Dict:
        """
        Analyze services and determine any constraints or dependencies.

        In a more advanced implementation, this would consider factors like:
        - Services that must be done in a specific order
        - Services that should be grouped together
        - Services that require drying or processing time
        """
        constraints = {
            "fixed_order_pairs": [],  # Pairs that must be in a specific order
            "preferred_groupings": [],  # Services that work well together
            "independents": [],  # Services that can be scheduled at any time
            "service_durations": {},  # Total duration including buffers
        }

        # Calculate total duration for each service (including buffers)
        for service_id in service_ids:
            service = service_map.get(service_id, {})
            duration = service.get("duration", 30)  # Default 30 min
            buffer_before = service.get("buffer_before", 0)
            buffer_after = service.get("buffer_after", 0)

            total_duration = duration + buffer_before + buffer_after
            constraints["service_durations"][service_id] = total_duration

        # Example logic for determining constraints
        # In a real application, this would be based on business rules
        # For this example, we'll use a simplified approach

        # If any service is significantly longer, it should be done first/last
        # if gap between appointments is likely
        services_with_duration = [
            (service_id, constraints["service_durations"][service_id]) for service_id in service_ids
        ]
        services_with_duration.sort(key=lambda x: x[1], reverse=True)

        # If the longest service is more than twice as long as the shortest,
        # add a constraint to do it first to minimize wait time
        if len(services_with_duration) > 1:
            longest_service, longest_duration = services_with_duration[0]
            shortest_service, shortest_duration = services_with_duration[-1]

            if longest_duration > shortest_duration * 2:
                constraints["fixed_order_pairs"].append(
                    (
                        longest_service,
                        shortest_service,
                    )  # Longest should come before shortest
                )

        # In reality, you would have more sophisticated business logic here
        # For example, hair coloring before haircut, etc.

        return constraints

    def _get_available_slots(
        self,
        service_ids: List[str],
        preferred_date: datetime.date,
        preferred_time_window: Optional[Tuple[datetime.time, datetime.time]],
        service_map: Dict[str, Dict],
        specialist_availability: Dict[str, List[Dict]],
        existing_appointments: List[Dict],
    ) -> Dict[str, List[Dict]]:
        """
        Get available time slots for each service on the preferred date.
        """
        available_slots = {}

        for service_id in service_ids:
            service = service_map.get(service_id, {})
            duration = service.get("duration", 30)  # Default 30 min
            buffer_before = service.get("buffer_before", 0)
            buffer_after = service.get("buffer_after", 0)

            # Get specialists who can perform this service
            service_specialists = service.get("specialists", [])

            # Get available slots for each specialist
            service_slots = []

            for specialist_id in service_specialists:
                # Get specialist's availability windows
                specialist_windows = specialist_availability.get(specialist_id, [])

                for window in specialist_windows:
                    # Skip if not for preferred date
                    window_date = window.get("date")
                    if window_date and window_date != preferred_date:
                        continue

                    start_time = window.get("start_time")
                    end_time = window.get("end_time")

                    # Skip if outside preferred time window (if specified)
                    if preferred_time_window:
                        pref_start, pref_end = preferred_time_window

                        # Convert times to datetime for comparison
                        window_start_dt = datetime.combine(preferred_date, start_time)
                        window_end_dt = datetime.combine(preferred_date, end_time)
                        pref_start_dt = datetime.combine(preferred_date, pref_start)
                        pref_end_dt = datetime.combine(preferred_date, pref_end)

                        # Check if window overlaps with preferred window
                        if window_end_dt <= pref_start_dt or window_start_dt >= pref_end_dt:
                            continue

                        # Adjust window to fit within preferred time
                        start_time = max(start_time, pref_start)
                        end_time = min(end_time, pref_end)

                    # Generate slots within this window
                    window_slots = self._generate_slots_in_window(
                        preferred_date,
                        start_time,
                        end_time,
                        duration,
                        buffer_before,
                        buffer_after,
                        specialist_id,
                        existing_appointments,
                    )

                    service_slots.extend(window_slots)

            # Store slots for this service
            available_slots[service_id] = service_slots

        return available_slots

    def _generate_slots_in_window(
        self,
        date: datetime.date,
        start_time: datetime.time,
        end_time: datetime.time,
        duration: int,
        buffer_before: int,
        buffer_after: int,
        specialist_id: str,
        existing_appointments: List[Dict],
    ) -> List[Dict]:
        """
        Generate available slots within a time window, accounting for existing appointments.
        """
        slots = []

        # Convert times to datetime objects for easier calculation
        start_dt = datetime.combine(date, start_time)
        end_dt = datetime.combine(date, end_time)

        # Total slot time including buffers
        total_slot_time = duration + buffer_before + buffer_after

        # Current slot start time
        current_time = start_dt

        # Generate slots in 15-minute increments
        while current_time + timedelta(minutes=total_slot_time) <= end_dt:
            # Calculate service start and end times (accounting for buffers)
            service_start = current_time + timedelta(minutes=buffer_before)
            service_end = service_start + timedelta(minutes=duration)

            # Check for conflicts with existing appointments
            has_conflict = False

            for appointment in existing_appointments:
                # Skip appointments for other specialists
                if appointment.get("specialist_id") != specialist_id:
                    continue

                # Skip non-active appointments
                if appointment.get("status") in ["cancelled", "no_show"]:
                    continue

                # Check for time overlap
                appt_start = appointment.get("start_time")
                appt_end = appointment.get("end_time")

                if service_start < appt_end and service_end > appt_start:
                    has_conflict = True
                    break

            if not has_conflict:
                slots.append(
                    {
                        "date": date,
                        "start_time": service_start,
                        "end_time": service_end,
                        "specialist_id": specialist_id,
                        "buffer_before": buffer_before,
                        "buffer_after": buffer_after,
                    }
                )

            # Move to next slot (15-min increment)
            current_time += timedelta(minutes=15)

        return slots

    def _determine_service_ordering(
        self,
        service_ids: List[str],
        service_constraints: Dict,
        available_slots: Dict[str, List[Dict]],
        service_map: Dict[str, Dict],
    ) -> List[str]:
        """
        Determine the optimal ordering of services based on constraints and availability.

        This uses a simple topological sort based on constraints,
        followed by optimization based on slot availability.
        """
        # Step 1: Build dependency graph based on fixed_order_pairs
        graph = {service_id: [] for service_id in service_ids}
        in_degree = {service_id: 0 for service_id in service_ids}

        for before_id, after_id in service_constraints["fixed_order_pairs"]:
            if before_id in graph and after_id in graph:
                graph[before_id].append(after_id)
                in_degree[after_id] += 1

        # Step 2: Topological sort to respect dependencies
        ordered_services = []
        queue = [service_id for service_id, degree in in_degree.items() if degree == 0]

        while queue:
            service_id = queue.pop(0)
            ordered_services.append(service_id)

            for next_service in graph[service_id]:
                in_degree[next_service] -= 1
                if in_degree[next_service] == 0:
                    queue.append(next_service)

        # Check if all services are included (if not, there's a circular dependency)
        if len(ordered_services) != len(service_ids):
            # Fall back to original order if topological sort fails
            return service_ids

        # Step 3: Apply additional ordering optimization based on availability
        # For example, services with fewer available slots should be scheduled first
        # to maximize the chance of finding a valid schedule

        # Count available slots for each service
        slot_counts = {}
        for service_id, slots in available_slots.items():
            slot_counts[service_id] = len(slots)

        # Reorder services with equal dependencies based on slot availability
        final_ordering = []
        current_group = []

        # Group services with the same dependency level
        for service_id in ordered_services:
            if not current_group:
                current_group.append(service_id)
            else:
                # Check if this service depends on any in the current group
                has_dependency = False
                for prev_service in current_group:
                    if service_id in graph[prev_service]:
                        has_dependency = True
                        break

                if has_dependency:
                    # Sort current group by slot availability (fewer slots first)
                    current_group.sort(key=lambda s: slot_counts.get(s, 0))
                    final_ordering.extend(current_group)
                    current_group = [service_id]
                else:
                    current_group.append(service_id)

        # Add the last group
        if current_group:
            current_group.sort(key=lambda s: slot_counts.get(s, 0))
            final_ordering.extend(current_group)

        return final_ordering

    def _generate_possible_schedules(
        self,
        service_ordering: List[str],
        available_slots: Dict[str, List[Dict]],
        service_map: Dict[str, Dict],
        specialist_availability: Dict[str, List[Dict]],
        preferred_specialist_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Generate possible schedules based on service ordering and available slots.

        This uses a recursive approach to build schedules, trying different
        combinations of slots for each service in the ordering.
        """
        possible_schedules = []

        # Helper function for recursive schedule generation
        def build_schedule(
            index: int,
            current_schedule: List[Dict],
            current_end_time: Optional[datetime] = None,
        ):
            # Base case: all services scheduled
            if index >= len(service_ordering):
                # Calculate schedule metrics
                if current_schedule:
                    first_appt = current_schedule[0]
                    last_appt = current_schedule[-1]

                    start_time = first_appt["start_time"]
                    end_time = last_appt["end_time"]

                    # Calculate total duration and waiting time
                    total_duration = (end_time - start_time).total_seconds() / 60

                    # Calculate waiting time between appointments
                    waiting_time = 0
                    for i in range(1, len(current_schedule)):
                        prev_end = current_schedule[i - 1]["end_time"]
                        curr_start = current_schedule[i]["start_time"]
                        gap = (curr_start - prev_end).total_seconds() / 60
                        waiting_time += max(0, gap)  # Only count positive gaps

                    # Get specialists used
                    specialists = [appt["specialist_id"] for appt in current_schedule]

                    # Check if total duration exceeds maximum (if set)
                    if self.max_total_duration and total_duration > self.max_total_duration:
                        return

                    possible_schedules.append(
                        {
                            "appointments": current_schedule,
                            "total_duration": total_duration,
                            "waiting_time": waiting_time,
                            "start_time": start_time,
                            "end_time": end_time,
                            "specialists": specialists,
                        }
                    )

                return

            # Get current service
            service_id = service_ordering[index]
            slots = available_slots.get(service_id, [])

            # If preferred specialist is specified, prioritize their slots
            if preferred_specialist_id:
                # Sort slots to put preferred specialist first
                slots.sort(
                    key=lambda x: (0 if x["specialist_id"] == preferred_specialist_id else 1)
                )

            # Try each available slot for this service
            for slot in slots:
                slot_start = slot["start_time"]
                slot_end = slot["end_time"]
                specialist_id = slot["specialist_id"]

                # If we have a previous appointment, check time constraints
                if current_end_time:
                    # Calculate gap between previous service and this one
                    gap_minutes = (slot_start - current_end_time).total_seconds() / 60

                    # Skip if gap is too small
                    if gap_minutes < self.min_break_between_services:
                        continue

                    # Skip if gap is too large
                    if gap_minutes > self.max_break_between_services:
                        continue

                    # Check specialist preference if enabled
                    if self.prefer_same_specialist and current_schedule:
                        prev_specialist = current_schedule[-1]["specialist_id"]

                        # If previous specialist is available and we prefer consistency,
                        # skip other specialists initially
                        if prev_specialist != specialist_id:
                            # Look for slots with same specialist before trying different ones
                            same_specialist_slots = [
                                s for s in slots if s["specialist_id"] == prev_specialist
                            ]

                            # If there are slots with the same specialist, skip this one
                            if same_specialist_slots:
                                continue

                # Check for conflicts with already scheduled appointments
                has_conflict = False
                for appt in current_schedule:
                    # If parallel services are not allowed, check for time overlap
                    if not self.allow_parallel_services:
                        appt_start = appt["start_time"]
                        appt_end = appt["end_time"]

                        if slot_start < appt_end and slot_end > appt_start:
                            has_conflict = True
                            break
                    else:
                        # If parallel services are allowed, only check for conflict
                        # if it's the same specialist
                        if appt["specialist_id"] == specialist_id:
                            appt_start = appt["start_time"]
                            appt_end = appt["end_time"]

                            if slot_start < appt_end and slot_end > appt_start:
                                has_conflict = True
                                break

                if has_conflict:
                    continue

                # Add appointment to schedule and continue building
                appointment = {
                    "service_id": service_id,
                    "start_time": slot_start,
                    "end_time": slot_end,
                    "specialist_id": specialist_id,
                    "service_name": service_map.get(service_id, {}).get(
                        "name", f"Service {service_id}"
                    ),
                }

                # Recursively build the rest of the schedule
                build_schedule(index + 1, current_schedule + [appointment], slot_end)

        # Start building schedules
        build_schedule(0, [], None)

        return possible_schedules

    def _rank_schedules(
        self,
        schedules: List[Dict],
        preferred_time_window: Optional[Tuple[datetime.time, datetime.time]],
        preferred_specialist_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Rank possible schedules based on various quality factors.
        """
        if not schedules:
            return []

        for schedule in schedules:
            score = 0

            # Factor 1: Minimize waiting time (highest priority)
            # Lower waiting time is better - invert for scoring
            waiting_time = schedule["waiting_time"]
            score += (120 - min(waiting_time, 120)) * 2  # Cap at 120 min, 2x weight

            # Factor 2: Minimize total duration
            # Shorter total duration is better - invert for scoring
            total_duration = schedule["total_duration"]
            score += 480 - min(total_duration, 480)  # Cap at 8 hours

            # Factor 3: Preferred time window (if specified)
            if preferred_time_window:
                pref_start, pref_end = preferred_time_window
                schedule_start = schedule["start_time"].time()
                # unused_unused_schedule_end = schedule["end_time"].time()

                # Closer to preferred time is better
                if pref_start <= schedule_start <= pref_end:
                    score += 50  # Big bonus for starting in preferred window
                elif schedule_start < pref_start:
                    # Too early - penalty based on how early
                    minutes_early = (
                        datetime.combine(datetime.today(), pref_start)
                        - datetime.combine(datetime.today(), schedule_start)
                    ).total_seconds() / 60
                    score -= min(minutes_early, 50)
                else:  # schedule_start > pref_end
                    # Too late - penalty based on how late
                    minutes_late = (
                        datetime.combine(datetime.today(), schedule_start)
                        - datetime.combine(datetime.today(), pref_end)
                    ).total_seconds() / 60
                    score -= min(minutes_late, 50)

            # Factor 4: Specialist consistency
            specialists = schedule["specialists"]
            unique_specialists = len(set(specialists))

            # Fewer specialists is better (if we prefer consistency)
            if self.prefer_same_specialist:
                score += (10 - min(unique_specialists, 10)) * 10

            # Factor 5: Preferred specialist (if specified)
            if preferred_specialist_id:
                # Count appointments with preferred specialist
                preferred_count = specialists.count(preferred_specialist_id)
                score += preferred_count * 15  # 15 points per appointment with preferred specialist

            # Store score in schedule
            schedule["score"] = score

        # Sort by score (highest first)
        return sorted(schedules, key=lambda x: x.get("score", 0), reverse=True)
