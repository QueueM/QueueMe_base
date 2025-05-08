import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class QueueOptimizer:
    """
    Advanced queue optimization algorithm that handles hybrid queue management
    for both scheduled appointments and walk-in customers.

    This algorithm intelligently manages the queue flow by:
    1. Prioritizing scheduled appointments at their designated times
    2. Filling gaps with walk-ins when appropriate
    3. Handling late appointments and no-shows
    4. Optimizing overall service efficiency
    5. Balancing fairness with efficiency
    """

    def __init__(
        self,
        appointment_grace_period: int = 5,
        walk_in_slot_buffer: int = 3,
        no_show_threshold: int = 15,
        prioritize_late_appointments: bool = True,
        enable_smart_reordering: bool = True,
    ):
        """
        Initialize the queue optimizer with configurable parameters.

        Args:
            appointment_grace_period: Minutes to wait for late appointments before taking walk-ins
            walk_in_slot_buffer: Minutes buffer to add before inserting walk-ins
            no_show_threshold: Minutes after which an appointment is considered a no-show
            prioritize_late_appointments: Whether to prioritize late appointments over walk-ins
            enable_smart_reordering: Whether to enable reordering for efficiency
        """
        self.appointment_grace_period = appointment_grace_period
        self.walk_in_slot_buffer = walk_in_slot_buffer
        self.no_show_threshold = no_show_threshold
        self.prioritize_late_appointments = prioritize_late_appointments
        self.enable_smart_reordering = enable_smart_reordering

    def optimize_queue(
        self,
        current_time: datetime,
        scheduled_appointments: List[Dict],
        walk_in_queue: List[Dict],
        specialist_availability: Dict[str, List[Tuple[datetime, datetime]]],
        service_durations: Dict[str, int],
        current_serving: Dict[str, Optional[Dict]] = None,
    ) -> Dict:
        """
        Optimize the queue flow by determining who should be served next
        and updating wait time estimates for all customers.

        Args:
            current_time: Current datetime
            scheduled_appointments: List of appointment objects with fields:
                - id: Unique identifier
                - specialist_id: ID of assigned specialist
                - service_id: ID of the service
                - scheduled_time: Datetime of scheduled appointment
                - customer_id: ID of the customer
                - status: Status of the appointment ('scheduled', 'checked_in', 'late', etc.)
            walk_in_queue: List of walk-in queue tickets with fields:
                - id: Unique identifier
                - service_id: ID of the requested service
                - customer_id: ID of the customer
                - join_time: Datetime when customer joined the queue
                - position: Current position in queue
                - status: Status of the ticket ('waiting', 'called', etc.)
                - estimated_wait_time: Current wait estimate (minutes)
            specialist_availability: Dict mapping specialist ID to their availability windows
            service_durations: Dict mapping service ID to service duration in minutes
            current_serving: Dict mapping specialist ID to the customer they're currently serving

        Returns:
            A dictionary containing:
            - next_customers: Dict mapping specialist ID to the next customer to serve
            - updated_appointments: List of appointments with updated status
            - updated_walk_ins: List of walk-ins with updated position and wait times
            - recommended_actions: List of recommended actions for staff
        """
        # Initialize result structure
        result = {
            "next_customers": {},
            "updated_appointments": [],
            "updated_walk_ins": [],
            "recommended_actions": [],
        }

        # Default current_serving if not provided
        if current_serving is None:
            current_serving = {
                specialist_id: None for specialist_id in specialist_availability
            }

        # Step 1: Identify due appointments and check for late/no-shows
        due_appointments, late_appointments, no_show_appointments = (
            self._categorize_appointments(current_time, scheduled_appointments)
        )

        # Step 2: Determine which specialists are or will be available
        available_specialists = self._get_available_specialists(
            current_time, specialist_availability, current_serving
        )

        # Step 3: Assign customers to available specialists
        for specialist_id in available_specialists:
            # Skip if specialist is currently serving someone
            if current_serving.get(specialist_id):
                continue

            # First priority: Scheduled appointments that are due now
            next_customer = self._find_next_due_appointment(
                due_appointments, specialist_id, current_time
            )

            # Second priority: Late appointments (if prioritizing them)
            if (
                not next_customer
                and self.prioritize_late_appointments
                and late_appointments
            ):
                next_customer = self._find_next_late_appointment(
                    late_appointments, specialist_id
                )

            # Third priority: Walk-ins (if no due appointments or after grace period)
            if not next_customer and walk_in_queue:
                # Check if we should process a walk-in or wait for a late appointment
                should_process_walk_in = self._should_process_walk_in(
                    current_time,
                    specialist_id,
                    late_appointments,
                    specialist_availability,
                )

                if should_process_walk_in:
                    next_customer = self._find_next_walk_in(
                        walk_in_queue, specialist_id, service_durations
                    )

            # If we've identified a next customer, add to results
            if next_customer:
                result["next_customers"][specialist_id] = next_customer

                # Update status of the selected customer
                if next_customer.get("type") == "appointment":
                    self._update_appointment_status(
                        next_customer, result["updated_appointments"]
                    )
                else:  # walk-in
                    self._update_walk_in_status(
                        next_customer, result["updated_walk_ins"]
                    )

        # Step 4: Handle no-shows
        for appointment in no_show_appointments:
            appointment["status"] = "no_show"
            result["updated_appointments"].append(appointment)
            result["recommended_actions"].append(
                {
                    "action": "mark_no_show",
                    "appointment_id": appointment["id"],
                    "message": f"Appointment {appointment['id']} is a no-show. Consider marking as no-show.",
                }
            )

        # Step 5: Update wait times for remaining walk-ins
        self._update_wait_times(
            current_time,
            walk_in_queue,
            result["updated_walk_ins"],
            specialist_availability,
            current_serving,
            service_durations,
        )

        # Step 6: If smart reordering is enabled, check if we can optimize further
        if self.enable_smart_reordering:
            self._apply_smart_reordering(result, walk_in_queue, service_durations)

        return result

    def _categorize_appointments(
        self, current_time: datetime, appointments: List[Dict]
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Categorize appointments as due, late, or no-show.
        """
        due_appointments = []
        late_appointments = []
        no_show_appointments = []

        for appointment in appointments:
            # Skip appointments that are not in scheduled or checked_in status
            if appointment["status"] not in ["scheduled", "checked_in"]:
                continue

            scheduled_time = appointment["scheduled_time"]
            time_diff = (current_time - scheduled_time).total_seconds() / 60

            # Due appointments: Starting within the next 5 minutes or up to grace period minutes late
            if -5 <= time_diff <= self.appointment_grace_period:
                appointment["type"] = "appointment"
                due_appointments.append(appointment)
            # Late appointments: Beyond grace period but not yet a no-show
            elif self.appointment_grace_period < time_diff < self.no_show_threshold:
                appointment["type"] = "appointment"
                appointment["status"] = "late"
                late_appointments.append(appointment)
            # No-show appointments: Beyond no-show threshold
            elif time_diff >= self.no_show_threshold:
                no_show_appointments.append(appointment)

        return due_appointments, late_appointments, no_show_appointments

    def _get_available_specialists(
        self,
        current_time: datetime,
        specialist_availability: Dict[str, List[Tuple[datetime, datetime]]],
        current_serving: Dict[str, Optional[Dict]],
    ) -> List[str]:
        """
        Determine which specialists are available now or will be soon.
        """
        available_specialists = []

        for specialist_id, availability_windows in specialist_availability.items():
            # Check if specialist is currently available
            is_available = False
            for start_time, end_time in availability_windows:
                if start_time <= current_time <= end_time:
                    is_available = True
                    break

            if is_available:
                # Check if specialist is not currently serving anyone
                if not current_serving.get(specialist_id):
                    available_specialists.append(specialist_id)

        return available_specialists

    def _find_next_due_appointment(
        self, due_appointments: List[Dict], specialist_id: str, current_time: datetime
    ) -> Optional[Dict]:
        """
        Find the next due appointment for a specific specialist.
        """
        # Filter appointments for this specialist, sorted by scheduled time
        specialist_appointments = [
            a for a in due_appointments if a["specialist_id"] == specialist_id
        ]

        if not specialist_appointments:
            return None

        # Sort by scheduled time (earliest first)
        specialist_appointments.sort(key=lambda a: a["scheduled_time"])

        # Prioritize checked-in appointments
        checked_in = [a for a in specialist_appointments if a["status"] == "checked_in"]
        if checked_in:
            return checked_in[0]

        # Otherwise take the earliest scheduled appointment
        return specialist_appointments[0]

    def _find_next_late_appointment(
        self, late_appointments: List[Dict], specialist_id: str
    ) -> Optional[Dict]:
        """
        Find the next late appointment for a specific specialist.
        """
        # Filter late appointments for this specialist, sorted by scheduled time
        specialist_appointments = [
            a for a in late_appointments if a["specialist_id"] == specialist_id
        ]

        if not specialist_appointments:
            return None

        # Sort by scheduled time (earliest first)
        specialist_appointments.sort(key=lambda a: a["scheduled_time"])

        # Prioritize checked-in appointments
        checked_in = [a for a in specialist_appointments if a["status"] == "checked_in"]
        if checked_in:
            return checked_in[0]

        # Otherwise take the earliest scheduled appointment
        return specialist_appointments[0]

    def _should_process_walk_in(
        self,
        current_time: datetime,
        specialist_id: str,
        late_appointments: List[Dict],
        specialist_availability: Dict[str, List[Tuple[datetime, datetime]]],
    ) -> bool:
        """
        Determine if we should process a walk-in or wait for a late appointment.
        """
        # Check if there are any late appointments for this specialist
        specialist_late_appointments = [
            a for a in late_appointments if a["specialist_id"] == specialist_id
        ]

        if not specialist_late_appointments:
            # No late appointments for this specialist, safe to process walk-in
            return True

        # Check if there's an upcoming appointment soon that would be interrupted
        for appointment in specialist_late_appointments:
            # If appointment is checked in, prioritize it over walk-ins
            if appointment["status"] == "checked_in":
                return False

        # Check if there's sufficient time for a quick service before next appointment
        next_appointment_time = self._get_next_appointment_time(
            current_time, specialist_id, specialist_availability
        )

        if next_appointment_time:
            # Calculate time until next appointment
            time_until_next = (
                next_appointment_time - current_time
            ).total_seconds() / 60

            # If next appointment is soon, don't process walk-in now
            if time_until_next < self.walk_in_slot_buffer:
                return False

        # Default to processing walk-in if no constraints found
        return True

    def _get_next_appointment_time(
        self,
        current_time: datetime,
        specialist_id: str,
        specialist_availability: Dict[str, List[Tuple[datetime, datetime]]],
    ) -> Optional[datetime]:
        """
        Get the time of the next appointment for a specialist.
        """
        # This would be implemented to query the database for the next scheduled appointment
        # For this example, we'll return None (simulating no upcoming appointments)
        return None

    def _find_next_walk_in(
        self,
        walk_in_queue: List[Dict],
        specialist_id: str,
        service_durations: Dict[str, int],
    ) -> Optional[Dict]:
        """
        Find the next walk-in to serve, optimizing for efficiency.
        """
        if not walk_in_queue:
            return None

        # By default, take the first person in the queue (FIFO)
        next_customer = walk_in_queue[0].copy()
        next_customer["type"] = "walk_in"

        # If smart reordering is enabled, also consider service duration
        if self.enable_smart_reordering:
            # Get time window until next fixed appointment (if any)
            available_time = self._get_available_time_window(specialist_id)

            if available_time:
                # Find walk-ins with services that fit in the available window
                # This is a simplified version - in reality, would be more complex
                fitting_walk_ins = []
                for walk_in in walk_in_queue[
                    :3
                ]:  # Look at first 3 to maintain some fairness
                    service_id = walk_in["service_id"]
                    duration = service_durations.get(service_id, 30)  # Default 30 min

                    if duration <= available_time:
                        fitting_walk_ins.append(walk_in)

                if fitting_walk_ins:
                    # Take the first fitting walk-in to maintain some fairness
                    next_customer = fitting_walk_ins[0].copy()
                    next_customer["type"] = "walk_in"

        return next_customer

    def _get_available_time_window(self, specialist_id: str) -> Optional[int]:
        """
        Get the available time window for a specialist until their next fixed appointment.
        """
        # In a real implementation, this would query upcoming appointments
        # For this example, we'll return None (simulating no fixed time constraint)
        return None

    def _update_appointment_status(
        self, appointment: Dict, updated_appointments: List[Dict]
    ) -> None:
        """
        Update the status of an appointment and add to updated list.
        """
        appointment["status"] = "called"
        updated_appointments.append(appointment)

    def _update_walk_in_status(
        self, walk_in: Dict, updated_walk_ins: List[Dict]
    ) -> None:
        """
        Update the status of a walk-in and add to updated list.
        """
        walk_in["status"] = "called"
        updated_walk_ins.append(walk_in)

    def _update_wait_times(
        self,
        current_time: datetime,
        walk_in_queue: List[Dict],
        updated_walk_ins: List[Dict],
        specialist_availability: Dict[str, List[Tuple[datetime, datetime]]],
        current_serving: Dict[str, Optional[Dict]],
        service_durations: Dict[str, int],
    ) -> None:
        """
        Update wait time estimates for all waiting customers.
        """
        # Skip walk-ins that have already been updated
        updated_ids = {w["id"] for w in updated_walk_ins}
        waiting_walk_ins = [w for w in walk_in_queue if w["id"] not in updated_ids]

        if not waiting_walk_ins:
            return

        # Count available specialists
        available_specialist_count = len(
            self._get_available_specialists(
                current_time, specialist_availability, current_serving
            )
        )

        # If no specialists are available, use total count for calculation
        if available_specialist_count == 0:
            available_specialist_count = len(specialist_availability)

        # Calculate average service duration for waiting customers
        total_duration = 0
        for walk_in in waiting_walk_ins:
            service_id = walk_in["service_id"]
            total_duration += service_durations.get(service_id, 30)  # Default 30 min

        avg_service_time = total_duration / len(waiting_walk_ins)

        # Update each waiting customer's estimated wait time
        for i, walk_in in enumerate(waiting_walk_ins):
            # Calculate position-based wait time
            # Formula: (position / available specialists) * average service time
            position = i + 1  # Position in the remaining queue
            estimated_wait = (position / available_specialist_count) * avg_service_time

            # Add a buffer for variability
            estimated_wait = int(estimated_wait * 1.2)  # 20% buffer

            # Update wait time and add to updated list
            walk_in_copy = walk_in.copy()
            walk_in_copy["estimated_wait_time"] = estimated_wait
            updated_walk_ins.append(walk_in_copy)

    def _apply_smart_reordering(
        self, result: Dict, walk_in_queue: List[Dict], service_durations: Dict[str, int]
    ) -> None:
        """
        Apply smart reordering to optimize queue flow.

        This is a simplified implementation. In reality, this would be
        a more sophisticated algorithm that considers multiple factors.
        """
        # Identify quick services that can be slotted in efficiently
        if len(walk_in_queue) < 2:
            return  # Need at least 2 walk-ins to consider reordering

        # Find quick services among waiting customers
        quick_services = []
        for i, walk_in in enumerate(walk_in_queue):
            if i == 0:
                continue  # Skip the first person (already being served or about to be)

            service_id = walk_in["service_id"]
            duration = service_durations.get(service_id, 30)

            # Consider services under 15 minutes as "quick"
            if duration <= 15 and i > 0:
                quick_services.append((i, walk_in.copy(), duration))

        # If no quick services found, no reordering needed
        if not quick_services:
            return

        # For simplicity, just suggest moving the quickest service forward
        # In a real implementation, would consider more factors
        quick_services.sort(key=lambda x: x[2])  # Sort by duration
        idx, walk_in, duration = quick_services[0]

        # Only suggest reordering if it would significantly improve efficiency
        if idx > 1:  # Only suggest moving if not already near the front
            result["recommended_actions"].append(
                {
                    "action": "reorder",
                    "ticket_id": walk_in["id"],
                    "current_position": idx + 1,  # 1-based position
                    "suggested_position": 2,  # Move to position 2 (right after current)
                    "message": f"Consider moving ticket {walk_in['id']} forward as it's a quick {duration}-minute service.",
                }
            )
