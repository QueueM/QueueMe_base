"""
Advanced Scheduling Service

This service provides sophisticated scheduling algorithms for handling
multi-service bookings with optimized time slots and resource allocation.
"""

import datetime
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q

from apps.bookingapp.models import Appointment, AppointmentItem, TimeSlot
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist

logger = logging.getLogger(__name__)


class MultiServiceScheduler:
    """
    Advanced scheduling engine for handling multiple services in a single booking
    with optimized resource allocation and time slot selection.
    """

    # Service order constants
    ORDER_SHORTEST_FIRST = "shortest_first"
    ORDER_LONGEST_FIRST = "longest_first"
    ORDER_HIGHEST_PRIORITY = "highest_priority"
    ORDER_DEPENDENCIES = "dependencies"

    # Buffer times in minutes
    DEFAULT_SERVICE_BUFFER = 5
    DEFAULT_SPECIALIST_BUFFER = 10
    DEFAULT_TRANSITION_BUFFER = 15

    # Limits
    MAX_SERVICES_PER_BOOKING = getattr(settings, "MAX_SERVICES_PER_BOOKING", 10)
    MAX_SCHEDULING_ITERATIONS = getattr(settings, "MAX_SCHEDULING_ITERATIONS", 100)

    def __init__(self, shop_id: str):
        self.shop_id = shop_id
        self.date = None
        self.services = []
        self.specialists = {}  # service_id -> specialist_id mapping
        self.service_order = self.ORDER_DEPENDENCIES
        self.optimize_for = "minimize_duration"  # or "minimize_wait_time", "maximize_specialist_utilization"
        self.allow_parallel = True  # Allow parallel services when possible

        # Cached data
        self._service_objects = {}
        self._specialist_objects = {}
        self._service_durations = {}
        self._service_dependencies = {}
        self._specialist_availability = {}

    def set_date(self, date: datetime.date) -> "MultiServiceScheduler":
        """Set the date for scheduling"""
        self.date = date
        return self

    def set_services(self, services: List[str]) -> "MultiServiceScheduler":
        """Set the list of service IDs to schedule"""
        if len(services) > self.MAX_SERVICES_PER_BOOKING:
            raise ValueError(
                f"Maximum of {self.MAX_SERVICES_PER_BOOKING} services allowed per booking"
            )

        self.services = services
        return self

    def set_specialists(self, specialists: Dict[str, str]) -> "MultiServiceScheduler":
        """Set specific specialists for services"""
        self.specialists = specialists
        return self

    def set_ordering(self, order_method: str) -> "MultiServiceScheduler":
        """Set the method for ordering services"""
        valid_methods = [
            self.ORDER_SHORTEST_FIRST,
            self.ORDER_LONGEST_FIRST,
            self.ORDER_HIGHEST_PRIORITY,
            self.ORDER_DEPENDENCIES,
        ]

        if order_method not in valid_methods:
            raise ValueError(
                f"Invalid ordering method. Must be one of: {', '.join(valid_methods)}"
            )

        self.service_order = order_method
        return self

    def set_optimization(self, optimize_for: str) -> "MultiServiceScheduler":
        """Set optimization strategy"""
        valid_strategies = [
            "minimize_duration",
            "minimize_wait_time",
            "maximize_specialist_utilization",
        ]

        if optimize_for not in valid_strategies:
            raise ValueError(
                f"Invalid optimization strategy. Must be one of: {', '.join(valid_strategies)}"
            )

        self.optimize_for = optimize_for
        return self

    def allow_parallel_services(self, allow: bool) -> "MultiServiceScheduler":
        """Set whether to allow parallel services"""
        self.allow_parallel = allow
        return self

    def find_available_slots(self) -> List[Dict[str, Any]]:
        """
        Find available time slots for the requested multi-service booking

        Returns:
            List of time slot options, each with a start time and schedule
        """
        if not self.shop_id:
            raise ValueError("Shop ID is required")

        if not self.date:
            raise ValueError("Date is required")

        if not self.services:
            raise ValueError("At least one service is required")

        # Load service and specialist information
        self._load_service_data()
        self._load_specialist_data()

        # Get all time slots for the date
        all_time_slots = self._get_available_time_slots()

        # Order services based on strategy
        ordered_services = self._order_services()

        # Keep track of the best schedules found
        best_schedules = []

        # Try each potential starting time slot
        start_times = self._get_potential_start_times(all_time_slots)

        for start_time in start_times:
            # Try to create a schedule starting at this time
            schedule = self._create_schedule(
                start_time, ordered_services, all_time_slots
            )

            if schedule:
                # Calculate metrics for evaluation
                total_duration = self._calculate_total_duration(schedule)
                total_wait_time = self._calculate_wait_time(schedule)
                specialist_utilization = self._calculate_specialist_utilization(
                    schedule
                )

                best_schedules.append(
                    {
                        "start_time": start_time,
                        "schedule": schedule,
                        "metrics": {
                            "total_duration": total_duration,
                            "wait_time": total_wait_time,
                            "specialist_utilization": specialist_utilization,
                        },
                    }
                )

        # Sort schedules based on optimization strategy
        if self.optimize_for == "minimize_duration":
            best_schedules.sort(key=lambda x: x["metrics"]["total_duration"])
        elif self.optimize_for == "minimize_wait_time":
            best_schedules.sort(key=lambda x: x["metrics"]["wait_time"])
        elif self.optimize_for == "maximize_specialist_utilization":
            best_schedules.sort(key=lambda x: -x["metrics"]["specialist_utilization"])

        # Return top options (limited to a reasonable number)
        return best_schedules[:5]

    @transaction.atomic
    def create_booking(
        self, start_time: datetime.datetime, customer_id: str, notes: str = ""
    ) -> Dict[str, Any]:
        """
        Create a booking with multiple services

        Args:
            start_time: When the booking should start
            customer_id: ID of the customer
            notes: Optional notes for the booking

        Returns:
            Dictionary with booking details
        """
        if not self.services:
            raise ValueError("At least one service is required")

        # Load service and specialist information
        self._load_service_data()
        self._load_specialist_data()

        # Order services
        ordered_services = self._order_services()

        # Get all time slots for the date
        all_time_slots = self._get_available_time_slots()

        # Create schedule
        schedule = self._create_schedule(start_time, ordered_services, all_time_slots)

        if not schedule:
            raise ValueError(
                "Unable to create schedule with the requested services and start time"
            )

        # Create main appointment
        total_duration = self._calculate_total_duration(schedule)
        end_time = start_time + datetime.timedelta(minutes=total_duration)

        appointment = Appointment.objects.create(
            shop_id=self.shop_id,
            customer_id=customer_id,
            status="confirmed",
            appointment_time=start_time,
            end_time=end_time,
            notes=notes,
            is_multi_service=True,
            total_duration=total_duration,
        )

        # Create appointment items
        for item in schedule:
            AppointmentItem.objects.create(
                appointment=appointment,
                service_id=item["service_id"],
                specialist_id=item["specialist_id"],
                start_time=item["start_time"],
                end_time=item["end_time"],
                duration=item["duration"],
                sequence=item["sequence"],
            )

        # Block time slots
        self._block_time_slots(schedule, appointment.id)

        return {
            "appointment_id": appointment.id,
            "start_time": start_time,
            "end_time": end_time,
            "total_duration": total_duration,
            "schedule": schedule,
        }

    def _load_service_data(self):
        """Load and cache service data"""
        services = Service.objects.filter(
            id__in=self.services, shop_id=self.shop_id, is_active=True
        )

        if len(services) != len(self.services):
            missing = set(self.services) - set(s.id for s in services)
            raise ValueError(f"Some services not found or inactive: {missing}")

        # Cache service objects and durations
        for service in services:
            self._service_objects[service.id] = service
            self._service_durations[service.id] = service.duration

            # Check for dependencies
            if service.dependencies:
                self._service_dependencies[service.id] = service.dependencies
            else:
                self._service_dependencies[service.id] = []

    def _load_specialist_data(self):
        """Load and cache specialist data"""
        specialist_ids = set(self.specialists.values())

        if specialist_ids:
            specialists = Specialist.objects.filter(
                id__in=specialist_ids, shop_id=self.shop_id, is_active=True
            )

            # Check if all requested specialists exist
            if len(specialists) != len(specialist_ids):
                missing = specialist_ids - set(s.id for s in specialists)
                raise ValueError(f"Some specialists not found or inactive: {missing}")

            # Cache specialist objects
            for specialist in specialists:
                self._specialist_objects[specialist.id] = specialist

        # For services without specified specialists, find suitable ones
        for service_id in self.services:
            if service_id not in self.specialists:
                specialists = Specialist.objects.filter(
                    shop_id=self.shop_id, is_active=True, services__id=service_id
                )

                if not specialists.exists():
                    raise ValueError(
                        f"No specialists available for service {service_id}"
                    )

                # Select the specialist with lowest booking count for the day
                specialist = (
                    specialists.annotate(
                        booking_count=Count(
                            "appointments",
                            filter=Q(appointments__appointment_time__date=self.date),
                        )
                    )
                    .order_by("booking_count")
                    .first()
                )

                self._specialist_objects[specialist.id] = specialist
                self.specialists[service_id] = specialist.id

    def _get_available_time_slots(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get available time slots for all specialists on the date

        Returns:
            Dictionary mapping specialist IDs to their available time slots
        """
        specialist_slots = {}

        # Get all specialists needed
        specialist_ids = set(self.specialists.values())

        # Query all time slots for these specialists on this date
        time_slots = TimeSlot.objects.filter(
            specialist_id__in=specialist_ids, date=self.date, is_available=True
        ).order_by("start_time")

        # Group by specialist
        for slot in time_slots:
            if slot.specialist_id not in specialist_slots:
                specialist_slots[slot.specialist_id] = []

            specialist_slots[slot.specialist_id].append(
                {
                    "id": slot.id,
                    "start_time": slot.start_time,
                    "end_time": slot.end_time,
                }
            )

        # Check if all specialists have slots
        for specialist_id in specialist_ids:
            if specialist_id not in specialist_slots:
                logger.warning(
                    f"No time slots found for specialist {specialist_id} on {self.date}"
                )
                specialist_slots[specialist_id] = []

        return specialist_slots

    def _order_services(self) -> List[str]:
        """
        Order services based on the specified strategy

        Returns:
            Ordered list of service IDs
        """
        if self.service_order == self.ORDER_SHORTEST_FIRST:
            # Order by duration (shortest first)
            return sorted(
                self.services, key=lambda x: self._service_durations.get(x, 0)
            )

        elif self.service_order == self.ORDER_LONGEST_FIRST:
            # Order by duration (longest first)
            return sorted(
                self.services, key=lambda x: -self._service_durations.get(x, 0)
            )

        elif self.service_order == self.ORDER_HIGHEST_PRIORITY:
            # Order by priority (if set in service)
            return sorted(
                self.services,
                key=lambda x: -(self._service_objects.get(x).priority or 0),
            )

        elif self.service_order == self.ORDER_DEPENDENCIES:
            # Order by dependencies (services that are dependencies come first)
            ordered = []
            remaining = set(self.services)

            # First add services that are dependencies of others
            all_dependencies = set()
            for service_id, deps in self._service_dependencies.items():
                all_dependencies.update(deps)

            # Add dependencies first (that are in our service list)
            for service_id in self.services:
                if service_id in all_dependencies and service_id in remaining:
                    ordered.append(service_id)
                    remaining.remove(service_id)

            # Then add remaining services
            ordered.extend(
                sorted(
                    list(remaining), key=lambda x: -self._service_durations.get(x, 0)
                )
            )

            return ordered

        # Default to original order if no valid strategy
        return self.services

    def _get_potential_start_times(
        self, time_slots: Dict[str, List[Dict[str, Any]]]
    ) -> List[datetime.datetime]:
        """
        Get potential starting times based on available slots

        Args:
            time_slots: Dictionary of specialist time slots

        Returns:
            List of potential starting times
        """
        all_start_times = []

        for specialist_id, slots in time_slots.items():
            for slot in slots:
                start_time = slot["start_time"]
                # Add time in 15-minute increments
                current = start_time
                end_time = slot["end_time"]

                while current < end_time:
                    all_start_times.append(current)
                    current += datetime.timedelta(minutes=15)

        # Remove duplicates and sort
        unique_times = sorted(list(set(all_start_times)))

        # Filter out times where there's not enough remaining time in the day
        total_min_duration = sum(self._service_durations.values())

        valid_start_times = []
        shop = Shop.objects.get(id=self.shop_id)
        closing_time = datetime.datetime.combine(
            self.date,
            shop.closing_time or datetime.time(22, 0),  # Default to 10 PM if not set
        )

        for start_time in unique_times:
            # Check if there's enough time before closing
            if (closing_time - start_time).total_seconds() / 60 >= total_min_duration:
                valid_start_times.append(start_time)

        return valid_start_times

    def _create_schedule(
        self,
        start_time: datetime.datetime,
        ordered_services: List[str],
        available_slots: Dict[str, List[Dict[str, Any]]],
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Create a schedule for the services starting at the given time

        Args:
            start_time: The starting time for the schedule
            ordered_services: List of service IDs in processing order
            available_slots: Dictionary of specialist time slots

        Returns:
            List of scheduled service items or None if not possible
        """
        schedule = []
        current_time = start_time
        used_slots = set()
        specialist_end_times = {}  # When each specialist finishes their last service

        for sequence, service_id in enumerate(ordered_services):
            service = self._service_objects[service_id]
            duration = self._service_durations[service_id]
            specialist_id = self.specialists[service_id]

            # Check if the specialist is already scheduled for an overlapping service
            if specialist_id in specialist_end_times:
                # Specialist's previous service end time
                prev_end_time = specialist_end_times[specialist_id]

                # Add buffer time between services for the same specialist
                min_start_time = prev_end_time + datetime.timedelta(
                    minutes=self.DEFAULT_SPECIALIST_BUFFER
                )

                # If parallel services aren't allowed, use the latest end time of any service
                if not self.allow_parallel and schedule:
                    latest_end = max(item["end_time"] for item in schedule)
                    min_start_time = max(min_start_time, latest_end)

                # Update current time if needed
                if min_start_time > current_time:
                    current_time = min_start_time

            # Determine end time for this service
            end_time = current_time + datetime.timedelta(minutes=duration)

            # Check if the specialist has available slots for this time period
            if not self._check_specialist_availability(
                specialist_id, current_time, end_time, available_slots, used_slots
            ):
                return None  # Can't schedule this service

            # Add to schedule
            schedule.append(
                {
                    "service_id": service_id,
                    "service_name": service.name,
                    "specialist_id": specialist_id,
                    "specialist_name": self._specialist_objects[specialist_id].name,
                    "start_time": current_time,
                    "end_time": end_time,
                    "duration": duration,
                    "sequence": sequence,
                }
            )

            # Update specialist's end time
            specialist_end_times[specialist_id] = end_time

            # Move current time to end of this service if not allowing parallel
            if not self.allow_parallel:
                current_time = end_time + datetime.timedelta(
                    minutes=self.DEFAULT_TRANSITION_BUFFER
                )

        return schedule

    def _check_specialist_availability(
        self,
        specialist_id: str,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        available_slots: Dict[str, List[Dict[str, Any]]],
        used_slots: Set[str],
    ) -> bool:
        """
        Check if a specialist is available during the given time period

        Args:
            specialist_id: The specialist to check
            start_time: Service start time
            end_time: Service end time
            available_slots: Dictionary of time slots by specialist
            used_slots: Set of already used slot IDs

        Returns:
            Boolean indicating if the specialist is available
        """
        if specialist_id not in available_slots:
            return False

        specialist_slots = available_slots[specialist_id]

        # Check if any slots cover the entire period
        for slot in specialist_slots:
            if slot["id"] in used_slots:
                continue

            slot_start = slot["start_time"]
            slot_end = slot["end_time"]

            # Check if slot covers the service time
            if slot_start <= start_time and slot_end >= end_time:
                used_slots.add(slot["id"])
                return True

        # If no single slot covers it, check if multiple consecutive slots can cover it
        current_slots = []
        current_coverage_end = None

        for slot in sorted(specialist_slots, key=lambda x: x["start_time"]):
            if slot["id"] in used_slots:
                continue

            slot_start = slot["start_time"]
            slot_end = slot["end_time"]

            # If this is the first slot or there's a gap, reset
            if current_coverage_end is None or slot_start > current_coverage_end:
                current_slots = [slot]
                current_coverage_end = slot_end
            else:
                # This slot extends the current coverage
                current_slots.append(slot)
                current_coverage_end = max(current_coverage_end, slot_end)

            # Check if we have enough coverage
            if (
                current_slots
                and current_slots[0]["start_time"] <= start_time
                and current_coverage_end >= end_time
            ):
                # Mark these slots as used
                for used_slot in current_slots:
                    used_slots.add(used_slot["id"])
                return True

        return False

    def _calculate_total_duration(self, schedule: List[Dict[str, Any]]) -> int:
        """
        Calculate the total duration of the schedule in minutes

        Args:
            schedule: The service schedule

        Returns:
            Total duration in minutes
        """
        if not schedule:
            return 0

        start_time = min(item["start_time"] for item in schedule)
        end_time = max(item["end_time"] for item in schedule)

        return int((end_time - start_time).total_seconds() / 60)

    def _calculate_wait_time(self, schedule: List[Dict[str, Any]]) -> int:
        """
        Calculate the total wait time between services

        Args:
            schedule: The service schedule

        Returns:
            Total wait time in minutes
        """
        if not schedule or len(schedule) <= 1:
            return 0

        # Sort by sequence
        sorted_schedule = sorted(schedule, key=lambda x: x["sequence"])

        total_wait = 0
        previous_end = sorted_schedule[0]["end_time"]

        for item in sorted_schedule[1:]:
            current_start = item["start_time"]

            if current_start > previous_end:
                # There's a wait time
                wait_minutes = int((current_start - previous_end).total_seconds() / 60)
                total_wait += wait_minutes

            previous_end = item["end_time"]

        return total_wait

    def _calculate_specialist_utilization(
        self, schedule: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate specialist utilization as a percentage

        Args:
            schedule: The service schedule

        Returns:
            Utilization percentage (0-100)
        """
        if not schedule:
            return 0

        # Get total schedule duration
        total_duration = self._calculate_total_duration(schedule)

        if total_duration == 0:
            return 0

        # Calculate active time for each specialist
        specialist_active_time = defaultdict(int)

        for item in schedule:
            specialist_id = item["specialist_id"]
            duration = item["duration"]
            specialist_active_time[specialist_id] += duration

        # Calculate average utilization across all specialists
        total_specialists = len(specialist_active_time)
        total_utilization = sum(
            time / total_duration * 100 for time in specialist_active_time.values()
        )

        return total_utilization / total_specialists if total_specialists > 0 else 0

    def _block_time_slots(self, schedule: List[Dict[str, Any]], appointment_id: str):
        """
        Block time slots for the scheduled services

        Args:
            schedule: The service schedule
            appointment_id: ID of the created appointment
        """
        for item in schedule:
            specialist_id = item["specialist_id"]
            start_time = item["start_time"]
            end_time = item["end_time"]

            # Get slots that need to be blocked
            slots = TimeSlot.objects.filter(
                specialist_id=specialist_id, date=start_time.date(), is_available=True
            ).filter(Q(start_time__lt=end_time) & Q(end_time__gt=start_time))

            if not slots:
                logger.warning(
                    f"No slots found to block for appointment {appointment_id}, service {item['service_id']}"
                )
                continue

            # Block these slots
            for slot in slots:
                # If the appointment only partially overlaps with the slot,
                # we need to split the slot

                if slot.start_time < start_time and slot.end_time > end_time:
                    # Appointment is in the middle of the slot - create two new slots
                    TimeSlot.objects.create(
                        specialist_id=specialist_id,
                        date=slot.date,
                        start_time=slot.start_time,
                        end_time=start_time,
                        is_available=True,
                    )

                    TimeSlot.objects.create(
                        specialist_id=specialist_id,
                        date=slot.date,
                        start_time=end_time,
                        end_time=slot.end_time,
                        is_available=True,
                    )

                    # Delete the original slot
                    slot.delete()

                elif slot.start_time < start_time:
                    # Appointment ends at or after slot end - resize slot
                    slot.end_time = start_time
                    slot.save()

                elif slot.end_time > end_time:
                    # Appointment starts at or before slot start - resize slot
                    slot.start_time = end_time
                    slot.save()

                else:
                    # Slot is completely covered by appointment - mark as unavailable
                    slot.is_available = False
                    slot.appointment_id = appointment_id
                    slot.save()


# Export the scheduler
scheduler = MultiServiceScheduler
