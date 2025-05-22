"""
Multi-dimensional conflict detection algorithm.

This module provides sophisticated algorithms for detecting scheduling conflicts
across multiple dimensions, including time overlaps, resource conflicts, specialist
availability, and dependency violations.
"""

import logging
from collections import defaultdict
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class TimeRange:
    """Represents a time range with start and end times."""

    def __init__(self, start: Union[datetime, time], end: Union[datetime, time]):
        """
        Initialize a time range.

        Args:
            start: Start time of the range
            end: End time of the range
        """
        self.start = start
        self.end = end

    def __str__(self) -> str:
        """Return string representation."""
        if isinstance(self.start, datetime):
            return (
                f"{self.start.strftime('%Y-%m-%d %H:%M')} - "
                f"{self.end.strftime('%H:%M')}"
            )
        else:
            return f"{self.start.strftime('%H:%M')} - {self.end.strftime('%H:%M')}"

    def overlaps(self, other: "TimeRange") -> bool:
        """
        Check if this time range overlaps with another.

        Args:
            other: Another time range

        Returns:
            True if the ranges overlap, False otherwise
        """
        return (self.start < other.end) and (other.start < self.end)

    def contains(self, point: Union[datetime, time]) -> bool:
        """
        Check if this time range contains a specific time point.

        Args:
            point: A time or datetime object

        Returns:
            True if the time point is within this range, False otherwise
        """
        return self.start <= point < self.end

    def contains_range(self, other: "TimeRange") -> bool:
        """
        Check if this time range fully contains another range.

        Args:
            other: Another time range

        Returns:
            True if this range fully contains the other range, False otherwise
        """
        return (self.start <= other.start) and (self.end >= other.end)

    @staticmethod
    def from_booking(booking: Dict[str, Any]) -> "TimeRange":
        """
        Create a TimeRange from a booking dictionary.

        Args:
            booking: Dictionary containing 'start_time' and 'end_time' keys

        Returns:
            TimeRange object representing the booking's time range
        """
        return TimeRange(booking["start_time"], booking["end_time"])

    @staticmethod
    def from_slot(slot: Dict[str, Any], date: datetime.date) -> "TimeRange":
        """
        Create a TimeRange from a slot dictionary.

        Args:
            slot: Dictionary containing 'start' and 'end' keys as string time
            date: The date for the slot

        Returns:
            TimeRange object representing the slot's time range
        """
        start_time = datetime.strptime(slot["start"], "%H:%M").time()
        end_time = datetime.strptime(slot["end"], "%H:%M").time()

        start_datetime = datetime.combine(date, start_time)
        end_datetime = datetime.combine(date, end_time)

        return TimeRange(start_datetime, end_datetime)


class ConflictDetector:
    """
    Advanced conflict detection system that identifies scheduling conflicts
    across multiple dimensions, including time, resources, specialists, and dependencies.
    """

    def __init__(self):
        """Initialize the conflict detector."""
        self.conflict_types = [
            "time_overlap",
            "specialist_conflict",
            "resource_conflict",
            "dependency_violation",
            "availability_conflict",
            "working_hours_conflict",
        ]

    def check_booking_conflicts(
        self,
        new_booking: Dict[str, Any],
        existing_bookings: List[Dict[str, Any]],
        specialists_schedule: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        resources_schedule: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        dependencies: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Check for conflicts between a new booking and existing bookings.

        Args:
            new_booking: The new booking to check
            existing_bookings: List of existing bookings
            specialists_schedule: Optional specialist availability schedule
            resources_schedule: Optional resource availability schedule
            dependencies: Optional service dependencies

        Returns:
            Dictionary with conflict information:
            {
                'has_conflict': bool,
                'conflicts': [{
                    'type': str,
                    'description': str,
                    'conflicting_booking_id': str (if applicable)
                }]
            }
        """
        logger.debug(f"Checking conflicts for booking {new_booking.get('id', 'new')}")

        result = {"has_conflict": False, "conflicts": []}

        # 1. Create a TimeRange for the new booking
        new_booking_range = TimeRange(
            new_booking["start_time"], new_booking["end_time"]
        )

        # Add buffer times if provided
        buffer_before = new_booking.get("buffer_before", 0)
        buffer_after = new_booking.get("buffer_after", 0)

        if buffer_before > 0 or buffer_after > 0:
            buffered_start = new_booking["start_time"] - timedelta(
                minutes=buffer_before
            )
            buffered_end = new_booking["end_time"] + timedelta(minutes=buffer_after)
            buffered_range = TimeRange(buffered_start, buffered_end)
        else:
            buffered_range = new_booking_range

        # 2. Check for time conflicts with existing bookings
        for booking in existing_bookings:
            # Skip if it's the same booking (for updates)
            if booking.get("id") == new_booking.get("id"):
                continue

            existing_range = TimeRange.from_booking(booking)

            # Check if the bookings overlap in time
            if buffered_range.overlaps(existing_range):
                # Check if they're for the same specialist
                if (
                    new_booking.get("specialist_id")
                    and booking.get("specialist_id")
                    and new_booking["specialist_id"] == booking["specialist_id"]
                ):

                    result["has_conflict"] = True
                    result["conflicts"].append(
                        {
                            "type": "specialist_conflict",
                            "description": (
                                f"Specialist {new_booking['specialist_id']} "
                                "is already booked during this time"
                            ),
                            "conflicting_booking_id": booking.get("id"),
                        }
                    )

                # Check if they're using any of the same resources
                new_resources = new_booking.get("resources", [])
                existing_resources = booking.get("resources", [])

                common_resources = set(new_resources) & set(existing_resources)
                if common_resources:
                    result["has_conflict"] = True
                    result["conflicts"].append(
                        {
                            "type": "resource_conflict",
                            "description": (
                                f"Resources {', '.join(common_resources)} "
                                "are already booked during this time"
                            ),
                            "conflicting_booking_id": booking.get("id"),
                        }
                    )

        # 3. Check specialist availability if provided
        if specialists_schedule and new_booking.get("specialist_id"):
            specialist_id = new_booking["specialist_id"]
            specialist_slots = specialists_schedule.get(specialist_id, [])

            if specialist_slots:
                # Check if booking time is within any available slot
                is_available = False
                for slot in specialist_slots:
                    slot_start = slot["start_time"]
                    slot_end = slot["end_time"]

                    slot_range = TimeRange(slot_start, slot_end)
                    if slot_range.contains_range(buffered_range):
                        is_available = True
                        break

                if not is_available:
                    result["has_conflict"] = True
                    result["conflicts"].append(
                        {
                            "type": "availability_conflict",
                            "description": (
                                f"Specialist {specialist_id} is not available during this time"
                            ),
                        }
                    )

        # 4. Check resource availability if provided
        if resources_schedule and new_booking.get("resources"):
            for resource_id in new_booking["resources"]:
                resource_slots = resources_schedule.get(resource_id, [])

                if resource_slots:
                    # Check if booking time is within any available slot
                    is_available = False
                    for slot in resource_slots:
                        slot_start = slot["start_time"]
                        slot_end = slot["end_time"]

                        slot_range = TimeRange(slot_start, slot_end)
                        if slot_range.contains_range(buffered_range):
                            is_available = True
                            break

                    if not is_available:
                        result["has_conflict"] = True
                        result["conflicts"].append(
                            {
                                "type": "availability_conflict",
                                "description": (
                                    f"Resource {resource_id} is not available during this time"
                                ),
                            }
                        )

        # 5. Check dependencies if provided
        if dependencies:
            for dependency in dependencies:
                if dependency["service_id"] == new_booking.get("service_id"):
                    # This service depends on another service
                    for dep_service_id in dependency.get("depends_on", []):
                        # Find if there's a booking for the dependent service before this one
                        dep_booking_found = False
                        for booking in existing_bookings:
                            if booking.get("service_id") == dep_service_id:
                                # Check if the dependent booking ends before this one starts
                                if booking["end_time"] <= new_booking["start_time"]:
                                    dep_booking_found = True
                                    break

                        if not dep_booking_found:
                            result["has_conflict"] = True
                            result["conflicts"].append(
                                {
                                    "type": "dependency_violation",
                                    "description": (
                                        f"Service {new_booking.get('service_id')} depends on service "
                                        f"{dep_service_id} which must be completed before"
                                    ),
                                }
                            )

        return result

    def check_multi_booking_feasibility(
        self,
        bookings: List[Dict[str, Any]],
        specialists_schedule: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        resources_schedule: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        dependencies: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Check if a set of bookings can all be scheduled without conflicts.

        Args:
            bookings: List of bookings to check
            specialists_schedule: Optional specialist availability schedule
            resources_schedule: Optional resource availability schedule
            dependencies: Optional service dependencies

        Returns:
            Dictionary with feasibility information:
            {
                'is_feasible': bool,
                'conflicts': [{
                    'type': str,
                    'description': str,
                    'bookings': [booking_indices]
                }]
            }
        """
        result = {"is_feasible": True, "conflicts": []}

        # Sort bookings by start time
        sorted_bookings = sorted(bookings, key=lambda x: x["start_time"])

        # Check for conflicts between each pair of bookings
        for i, booking1 in enumerate(sorted_bookings):
            # Check against all other bookings
            for j, booking2 in enumerate(sorted_bookings[i + 1 :], i + 1):
                # Create TimeRanges with buffers
                booking1_start = booking1["start_time"]
                booking1_end = booking1["end_time"]
                booking1_before = booking1.get("buffer_before", 0)
                booking1_after = booking1.get("buffer_after", 0)

                booking2_start = booking2["start_time"]
                booking2_end = booking2["end_time"]
                booking2_before = booking2.get("buffer_before", 0)
                booking2_after = booking2.get("buffer_after", 0)

                # Adjust for buffers
                buffered1_start = booking1_start - timedelta(minutes=booking1_before)
                buffered1_end = booking1_end + timedelta(minutes=booking1_after)

                buffered2_start = booking2_start - timedelta(minutes=booking2_before)
                buffered2_end = booking2_end + timedelta(minutes=booking2_after)

                # Create ranges
                range1 = TimeRange(buffered1_start, buffered1_end)
                range2 = TimeRange(buffered2_start, buffered2_end)

                # Check for time overlap
                if range1.overlaps(range2):
                    # Check if same specialist
                    if (
                        booking1.get("specialist_id")
                        and booking2.get("specialist_id")
                        and booking1["specialist_id"] == booking2["specialist_id"]
                    ):

                        result["is_feasible"] = False
                        result["conflicts"].append(
                            {
                                "type": "specialist_conflict",
                                "description": f"Specialist {booking1['specialist_id']} is double-booked",
                                "bookings": [i, j],
                            }
                        )

                    # Check if using same resources
                    resources1 = booking1.get("resources", [])
                    resources2 = booking2.get("resources", [])

                    common_resources = set(resources1) & set(resources2)
                    if common_resources:
                        result["is_feasible"] = False
                        result["conflicts"].append(
                            {
                                "type": "resource_conflict",
                                "description": f"Resources {', '.join(common_resources)} are double-booked",
                                "bookings": [i, j],
                            }
                        )

            # Check specialist availability for this booking
            if specialists_schedule and booking1.get("specialist_id"):
                specialist_id = booking1["specialist_id"]
                specialist_slots = specialists_schedule.get(specialist_id, [])

                if specialist_slots:
                    # Create the buffered range
                    buffer_before = booking1.get("buffer_before", 0)
                    buffer_after = booking1.get("buffer_after", 0)

                    buffered_start = booking1["start_time"] - timedelta(
                        minutes=buffer_before
                    )
                    buffered_end = booking1["end_time"] + timedelta(
                        minutes=buffer_after
                    )
                    buffered_range = TimeRange(buffered_start, buffered_end)

                    # Check if booking time is within any available slot
                    is_available = False
                    for slot in specialist_slots:
                        slot_start = slot["start_time"]
                        slot_end = slot["end_time"]

                        slot_range = TimeRange(slot_start, slot_end)
                        if slot_range.contains_range(buffered_range):
                            is_available = True
                            break

                    if not is_available:
                        result["is_feasible"] = False
                        result["conflicts"].append(
                            {
                                "type": "availability_conflict",
                                "description": (
                                    f"Specialist {specialist_id} is not available for booking {i}"
                                ),
                                "bookings": [i],
                            }
                        )

        # Check dependencies
        if dependencies:
            # Create a mapping of service IDs to bookings
            service_bookings = defaultdict(list)
            for i, booking in enumerate(sorted_bookings):
                service_id = booking.get("service_id")
                if service_id:
                    service_bookings[service_id].append((i, booking))

            # Check each dependency
            for dependency in dependencies:
                service_id = dependency["service_id"]
                depends_on = dependency.get("depends_on", [])

                if service_id in service_bookings and depends_on:
                    # For each booking of this service
                    for i, booking in service_bookings[service_id]:
                        # Check if all dependencies are met
                        for dep_service_id in depends_on:
                            # Find if there's a booking for the dependent service that ends before
                            # this one starts
                            dep_satisfied = False
                            for dep_idx, dep_booking in service_bookings.get(
                                dep_service_id, []
                            ):
                                if dep_booking["end_time"] <= booking["start_time"]:
                                    dep_satisfied = True
                                    break

                            if not dep_satisfied:
                                result["is_feasible"] = False
                                result["conflicts"].append(
                                    {
                                        "type": "dependency_violation",
                                        "description": (
                                            f"Service {service_id} depends on service {dep_service_id} "
                                            "which must be completed before"
                                        ),
                                        "bookings": [i],
                                    }
                                )

        return result

    def find_next_available_slot(
        self,
        failed_booking: Dict[str, Any],
        existing_bookings: List[Dict[str, Any]],
        working_hours: List[Dict[str, Any]],
        specialists_schedule: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        resources_schedule: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
        max_days: int = 30,
    ) -> Optional[Dict[str, Any]]:
        """
        Find the next available time slot for a booking that failed due to conflicts.

        Args:
            failed_booking: The booking that had conflicts
            existing_bookings: List of existing bookings
            working_hours: List of working hours by day of week
            specialists_schedule: Optional specialist availability schedule
            resources_schedule: Optional resource availability schedule
            start_date: Optional start date for search range
            end_date: Optional end date for search range
            max_days: Maximum number of days to search ahead

        Returns:
            Dictionary with next available time slot, or None if none found
        """
        # Set up search range
        if not start_date:
            start_date = datetime.now().date()

        if not end_date:
            end_date = start_date + timedelta(days=max_days)

        # Get duration and buffer times
        duration = int(
            (failed_booking["end_time"] - failed_booking["start_time"]).total_seconds()
            / 60
        )
        buffer_before = failed_booking.get("buffer_before", 0)
        buffer_after = failed_booking.get("buffer_after", 0)

        # Get specialist ID if applicable
        specialist_id = failed_booking.get("specialist_id")

        # Get resource IDs if applicable
        resource_ids = failed_booking.get("resources", [])

        # Track the current date
        current_date = start_date

        # Search each day in the range
        while current_date <= end_date:
            # Get day of week (0 = Sunday, 6 = Saturday)
            day_of_week = current_date.weekday()
            # Adjust for Python's weekday (0 = Monday) vs our schema (0 = Sunday)
            if day_of_week == 6:  # If Python's Sunday (6)
                day_of_week = 0  # Set to our Sunday (0)
            else:
                day_of_week += 1  # Otherwise add 1

            # Find working hours for this day
            day_hours = None
            for hours in working_hours:
                if hours.get("weekday") == day_of_week:
                    day_hours = hours
                    break

            if not day_hours or day_hours.get("is_closed", False):
                # Skip closed days
                current_date += timedelta(days=1)
                continue

            # Convert working hours to datetime on the current date
            day_start = datetime.combine(current_date, day_hours["from_hour"])
            day_end = datetime.combine(current_date, day_hours["to_hour"])

            # Adjust for minimum starting time on current day
            min_start = datetime.now()
            if (
                current_date == datetime.now().date()
                and min_start.time() > day_hours["from_hour"]
            ):
                day_start = datetime.combine(current_date, min_start.time())

            # Find all bookings for this day
            day_bookings = [
                b for b in existing_bookings if b["start_time"].date() == current_date
            ]

            # Get specialist availability for this day if applicable
            specialist_day_slots = []
            if specialist_id and specialists_schedule:
                specialist_day_slots = [
                    s
                    for s in specialists_schedule.get(specialist_id, [])
                    if s["start_time"].date() == current_date
                ]

            # Get resource availability for this day if applicable
            resource_day_slots = defaultdict(list)
            if resource_ids and resources_schedule:
                for resource_id in resource_ids:
                    resource_day_slots[resource_id] = [
                        s
                        for s in resources_schedule.get(resource_id, [])
                        if s["start_time"].date() == current_date
                    ]

            # Generate potential start times
            current_time = day_start
            granularity = timedelta(minutes=15)  # 15-minute intervals

            while current_time + timedelta(minutes=duration) <= day_end:
                # Create a test booking
                test_booking = {
                    "start_time": current_time,
                    "end_time": current_time + timedelta(minutes=duration),
                    "buffer_before": buffer_before,
                    "buffer_after": buffer_after,
                    "specialist_id": specialist_id,
                    "resources": resource_ids,
                    "service_id": failed_booking.get("service_id"),
                }

                # Check for conflicts
                conflicts = self.check_booking_conflicts(
                    test_booking,
                    day_bookings,
                    {specialist_id: specialist_day_slots} if specialist_id else None,
                    (
                        {r_id: resource_day_slots[r_id] for r_id in resource_ids}
                        if resource_ids
                        else None
                    ),
                )

                if not conflicts["has_conflict"]:
                    # Found an available slot
                    return {
                        "date": current_date.strftime("%Y-%m-%d"),
                        "start_time": current_time.strftime("%H:%M"),
                        "end_time": (
                            current_time + timedelta(minutes=duration)
                        ).strftime("%H:%M"),
                        "duration": duration,
                        "buffer_before": buffer_before,
                        "buffer_after": buffer_after,
                    }

                # Move to next potential start time
                current_time += granularity

            # Move to next day
            current_date += timedelta(days=1)

        # No available slot found
        return None

    def resolve_conflicts(
        self,
        bookings: List[Dict[str, Any]],
        specialists_schedule: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        resources_schedule: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """
        Attempt to resolve conflicts in a set of bookings by adjusting times.

        Args:
            bookings: List of bookings to resolve conflicts for
            specialists_schedule: Optional specialist availability schedule
            resources_schedule: Optional resource availability schedule

        Returns:
            Dictionary with resolution results:
            {
                'success': bool,
                'resolved_bookings': [adjusted_bookings] if success,
                'unresolvable_conflicts': [conflict_info] if not success
            }
        """
        # Check initial feasibility
        feasibility = self.check_multi_booking_feasibility(
            bookings, specialists_schedule, resources_schedule
        )

        # If already feasible, return the original bookings
        if feasibility["is_feasible"]:
            return {"success": True, "resolved_bookings": bookings}

        # Try to resolve conflicts
        # This is a complex resolution algorithm that could use various strategies:
        # 1. Shifting times
        # 2. Changing specialists
        # 3. Reordering bookings
        # 4. Finding alternative resources

        # For this implementation, we'll use a simple time-shifting approach

        # Create a working copy of bookings
        working_bookings = [booking.copy() for booking in bookings]

        # Sort conflicts by type (prioritize certain types)
        conflicts = sorted(
            feasibility["conflicts"],
            key=lambda c: self._get_conflict_priority(c["type"]),
        )

        # Try to resolve each conflict
        for conflict in conflicts:
            conflict_type = conflict["type"]
            conflict_bookings = conflict.get("bookings", [])

            if conflict_type == "specialist_conflict":
                # Try to shift one of the bookings or change specialist
                result = self._resolve_specialist_conflict(
                    working_bookings, conflict_bookings, specialists_schedule
                )
                if not result["success"]:
                    return {"success": False, "unresolvable_conflicts": [conflict]}
                working_bookings = result["bookings"]

            elif conflict_type == "resource_conflict":
                # Try to shift one of the bookings or find alternative resources
                result = self._resolve_resource_conflict(
                    working_bookings, conflict_bookings, resources_schedule
                )
                if not result["success"]:
                    return {"success": False, "unresolvable_conflicts": [conflict]}
                working_bookings = result["bookings"]

            elif conflict_type == "availability_conflict":
                # Try to find a time when the specialist or resource is available
                result = self._resolve_availability_conflict(
                    working_bookings,
                    conflict_bookings[0] if conflict_bookings else 0,
                    specialists_schedule,
                    resources_schedule,
                )
                if not result["success"]:
                    return {"success": False, "unresolvable_conflicts": [conflict]}
                working_bookings = result["bookings"]

            elif conflict_type == "dependency_violation":
                # Try to reorder bookings to satisfy dependencies
                result = self._resolve_dependency_conflict(
                    working_bookings, conflict_bookings
                )
                if not result["success"]:
                    return {"success": False, "unresolvable_conflicts": [conflict]}
                working_bookings = result["bookings"]

        # Final check after attempted resolutions
        final_feasibility = self.check_multi_booking_feasibility(
            working_bookings, specialists_schedule, resources_schedule
        )

        if final_feasibility["is_feasible"]:
            return {"success": True, "resolved_bookings": working_bookings}
        else:
            return {
                "success": False,
                "unresolvable_conflicts": final_feasibility["conflicts"],
            }

    def _get_conflict_priority(self, conflict_type: str) -> int:
        """
        Get priority value for a conflict type (lower number = higher priority).

        Args:
            conflict_type: Type of conflict

        Returns:
            Priority value
        """
        priorities = {
            "dependency_violation": 1,  # Highest priority
            "availability_conflict": 2,
            "specialist_conflict": 3,
            "resource_conflict": 4,
        }

        return priorities.get(
            conflict_type, 10
        )  # Default low priority for unknown types

    def _resolve_specialist_conflict(
        self,
        bookings: List[Dict[str, Any]],
        conflict_indices: List[int],
        specialists_schedule: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """
        Resolve a specialist conflict by shifting time or changing specialist.

        Args:
            bookings: List of all bookings
            conflict_indices: Indices of bookings in conflict
            specialists_schedule: Optional specialist availability schedule

        Returns:
            Dictionary with resolution results
        """
        # This is a simplified implementation - in a real system, this would be
        # much more sophisticated, considering various factors like preferences,
        # priority, etc.

        # Try shifting the second booking to after the first
        if len(conflict_indices) >= 2:
            idx1 = conflict_indices[0]
            idx2 = conflict_indices[1]

            booking1 = bookings[idx1]
            booking2 = bookings[idx2]

            # Calculate buffer times
            buffer_after1 = booking1.get("buffer_after", 0)
            buffer_before2 = booking2.get("buffer_before", 0)

            # Calculate new start time for booking2
            new_start = booking1["end_time"] + timedelta(
                minutes=buffer_after1 + buffer_before2
            )

            # Calculate duration
            duration = int(
                (booking2["end_time"] - booking2["start_time"]).total_seconds() / 60
            )

            # Set new times
            bookings[idx2]["start_time"] = new_start
            bookings[idx2]["end_time"] = new_start + timedelta(minutes=duration)

            return {"success": True, "bookings": bookings}

        # If we can't resolve by shifting, we could try to find another specialist
        # (not implemented in this simplified version)

        return {"success": False, "bookings": bookings}

    def _resolve_resource_conflict(
        self,
        bookings: List[Dict[str, Any]],
        conflict_indices: List[int],
        resources_schedule: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """
        Resolve a resource conflict by shifting time or finding alternative resources.

        Args:
            bookings: List of all bookings
            conflict_indices: Indices of bookings in conflict
            resources_schedule: Optional resource availability schedule

        Returns:
            Dictionary with resolution results
        """
        # Similar approach to specialist conflict resolution
        # Try shifting the second booking to after the first
        if len(conflict_indices) >= 2:
            idx1 = conflict_indices[0]
            idx2 = conflict_indices[1]

            booking1 = bookings[idx1]
            booking2 = bookings[idx2]

            # Calculate buffer times
            buffer_after1 = booking1.get("buffer_after", 0)
            buffer_before2 = booking2.get("buffer_before", 0)

            # Calculate new start time for booking2
            new_start = booking1["end_time"] + timedelta(
                minutes=buffer_after1 + buffer_before2
            )

            # Calculate duration
            duration = int(
                (booking2["end_time"] - booking2["start_time"]).total_seconds() / 60
            )

            # Set new times
            bookings[idx2]["start_time"] = new_start
            bookings[idx2]["end_time"] = new_start + timedelta(minutes=duration)

            return {"success": True, "bookings": bookings}

        # If we can't resolve by shifting, we could try to find alternative resources
        # (not implemented in this simplified version)

        return {"success": False, "bookings": bookings}

    def _resolve_availability_conflict(
        self,
        bookings: List[Dict[str, Any]],
        booking_index: int,
        specialists_schedule: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        resources_schedule: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """
        Resolve an availability conflict by finding a time when all required
        resources and specialists are available.

        Args:
            bookings: List of all bookings
            booking_index: Index of booking with availability conflict
            specialists_schedule: Optional specialist availability schedule
            resources_schedule: Optional resource availability schedule

        Returns:
            Dictionary with resolution results
        """
        # In a real implementation, this would search for the next available
        # time slot when all required resources and specialists are available

        # For this simplified version, we'll return failure
        return {"success": False, "bookings": bookings}

    def _resolve_dependency_conflict(
        self, bookings: List[Dict[str, Any]], conflict_indices: List[int]
    ) -> Dict[str, Any]:
        """
        Resolve a dependency conflict by reordering bookings.

        Args:
            bookings: List of all bookings
            conflict_indices: Indices of bookings in conflict

        Returns:
            Dictionary with resolution results
        """
        # In a real implementation, this would reorder bookings to satisfy
        # dependencies, potentially adjusting times

        # For this simplified version, we'll return failure
        return {"success": False, "bookings": bookings}
