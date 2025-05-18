"""
Buffer Time Management Service

A specialized service for managing buffer times between appointments,
handling overlaps, and optimizing buffer time allocation.

Key features:
1. Automatic buffer time calculations
2. Buffer time enforcement
3. Optimal buffer time recommendations
4. Buffer time conflict resolution
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.db.models import Avg, Max, Min, Q
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.serviceapp.models import Service
from apps.specialistsapp.models import Specialist

logger = logging.getLogger(__name__)

# Type definitions
TimeSlot = Tuple[datetime, datetime]  # (start_time, end_time)
BufferResult = Dict[str, Any]  # Result of buffer calculations


class BufferManagementService:
    """
    Service to manage and optimize buffer times between appointments.

    This service ensures proper buffer times are maintained between appointments,
    optimizes buffer allocations, and handles buffer time conflicts.
    """

    # Default buffer time settings
    DEFAULT_MIN_BUFFER = 5  # Minimum buffer time in minutes
    DEFAULT_TRANSITION_BUFFER = 10  # Standard transition time
    DEFAULT_CLEANUP_BUFFER = 15  # Standard cleanup time

    @classmethod
    def calculate_buffer_requirements(
        cls, service_id: str, start_time: datetime, specialist_id: Optional[str] = None
    ) -> BufferResult:
        """
        Calculate required buffer times before and after an appointment.

        Args:
            service_id: ID of the service
            start_time: Start time of the appointment
            specialist_id: Optional specialist ID (if known)

        Returns:
            Dict with calculated buffer times and details
        """
        try:
            service = Service.objects.get(id=service_id)

            # Get base buffer times from service configuration
            buffer_before = service.buffer_before or cls.DEFAULT_MIN_BUFFER
            buffer_after = service.buffer_after or cls.DEFAULT_MIN_BUFFER

            # If specialist is provided, check their previous and next appointments
            if specialist_id:
                # Get specialist's adjacent appointments
                previous, next_appt = cls._get_adjacent_appointments(
                    specialist_id=specialist_id, reference_time=start_time
                )

                # Adjust buffer before based on previous appointment
                if previous:
                    previous_service = previous.service
                    previous_end = previous.end_time
                    previous_buffer = previous_service.buffer_after or cls.DEFAULT_MIN_BUFFER

                    # Calculate time between appointments
                    gap = (start_time - previous_end).total_seconds() / 60

                    # If gap is less than minimum required buffer, flag as warning
                    if gap < max(buffer_before, previous_buffer):
                        return {
                            "buffer_before": buffer_before,
                            "buffer_after": buffer_after,
                            "has_conflict": True,
                            "conflict_type": "insufficient_buffer_before",
                            "conflict_details": {
                                "previous_appointment_id": str(previous.id),
                                "previous_service_name": previous_service.name,
                                "previous_end_time": previous_end.isoformat(),
                                "gap_minutes": gap,
                                "required_buffer": max(buffer_before, previous_buffer),
                            },
                        }

                # Adjust buffer after based on next appointment
                if next_appt:
                    next_service = next_appt.service
                    next_start = next_appt.start_time
                    next_buffer = next_service.buffer_before or cls.DEFAULT_MIN_BUFFER

                    # Calculate end time with current service duration
                    end_time = start_time + timedelta(minutes=service.duration)

                    # Calculate time between appointments
                    gap = (next_start - end_time).total_seconds() / 60

                    # If gap is less than minimum required buffer, flag as warning
                    if gap < max(buffer_after, next_buffer):
                        return {
                            "buffer_before": buffer_before,
                            "buffer_after": buffer_after,
                            "has_conflict": True,
                            "conflict_type": "insufficient_buffer_after",
                            "conflict_details": {
                                "next_appointment_id": str(next_appt.id),
                                "next_service_name": next_service.name,
                                "next_start_time": next_start.isoformat(),
                                "gap_minutes": gap,
                                "required_buffer": max(buffer_after, next_buffer),
                            },
                        }

            # No conflicts found
            return {
                "buffer_before": buffer_before,
                "buffer_after": buffer_after,
                "has_conflict": False,
                "total_buffer_time": buffer_before + buffer_after,
            }

        except Exception as e:
            logger.error(f"Error calculating buffer requirements: {str(e)}")
            return {
                "buffer_before": cls.DEFAULT_MIN_BUFFER,
                "buffer_after": cls.DEFAULT_MIN_BUFFER,
                "has_conflict": True,
                "conflict_type": "error",
                "error_message": str(e),
            }

    @classmethod
    def suggest_optimal_buffer_times(
        cls,
        service_id: str,
        preparation_required: bool = True,
        cleanup_required: bool = True,
        transition_complexity: str = "medium",  # 'low', 'medium', 'high'
    ) -> BufferResult:
        """
        Suggest optimal buffer times for a service based on its requirements.

        Args:
            service_id: ID of the service
            preparation_required: Whether preparation time is needed
            cleanup_required: Whether cleanup time is needed
            transition_complexity: Complexity of transition between services

        Returns:
            Dict with suggested buffer times
        """
        try:
            service = Service.objects.get(id=service_id)

            # Base buffer calculation
            base_buffer_before = cls.DEFAULT_MIN_BUFFER
            base_buffer_after = cls.DEFAULT_MIN_BUFFER

            # Add preparation time if required
            if preparation_required:
                if service.duration <= 15:
                    base_buffer_before += 5
                elif service.duration <= 30:
                    base_buffer_before += 10
                else:
                    base_buffer_before += 15

            # Add cleanup time if required
            if cleanup_required:
                if service.duration <= 15:
                    base_buffer_after += 5
                elif service.duration <= 30:
                    base_buffer_after += 10
                else:
                    base_buffer_after += 15

            # Adjust based on transition complexity
            if transition_complexity == "high":
                transition_factor = 1.5
            elif transition_complexity == "low":
                transition_factor = 0.8
            else:  # medium
                transition_factor = 1.0

            # Apply transition factor
            suggested_before = round(base_buffer_before * transition_factor)
            suggested_after = round(base_buffer_after * transition_factor)

            # Calculate current average buffer times
            avg_buffers = cls._get_average_buffer_times(service_id)

            return {
                "suggested_buffer_before": suggested_before,
                "suggested_buffer_after": suggested_after,
                "total_buffer_time": suggested_before + suggested_after,
                "current_average_buffer_before": avg_buffers["avg_before"],
                "current_average_buffer_after": avg_buffers["avg_after"],
                "service_duration": service.duration,
                "explanation": cls._generate_buffer_explanation(
                    service=service,
                    suggested_before=suggested_before,
                    suggested_after=suggested_after,
                    preparation_required=preparation_required,
                    cleanup_required=cleanup_required,
                    transition_complexity=transition_complexity,
                ),
            }

        except Exception as e:
            logger.error(f"Error suggesting optimal buffer times: {str(e)}")
            return {
                "suggested_buffer_before": cls.DEFAULT_MIN_BUFFER,
                "suggested_buffer_after": cls.DEFAULT_MIN_BUFFER,
                "total_buffer_time": cls.DEFAULT_MIN_BUFFER * 2,
                "error_message": str(e),
            }

    @classmethod
    def check_buffer_conflicts(
        cls,
        specialist_id: str,
        date_to_check: datetime.date,
        ignore_appointment_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Check for buffer time conflicts in a specialist's schedule.

        Args:
            specialist_id: ID of the specialist
            date_to_check: Date to check for conflicts
            ignore_appointment_id: Optional ID of appointment to ignore

        Returns:
            List of buffer time conflicts with details
        """
        try:
            # Get all appointments for this specialist on this day
            day_start = datetime.combine(date_to_check, datetime.min.time())
            day_end = datetime.combine(date_to_check, datetime.max.time())

            appointments = Appointment.objects.filter(
                specialist_id=specialist_id,
                start_time__gte=day_start,
                start_time__lt=day_end,
                status__in=["scheduled", "confirmed", "in_progress"],
            ).order_by("start_time")

            if ignore_appointment_id:
                appointments = appointments.exclude(id=ignore_appointment_id)

            if not appointments:
                return []

            conflicts = []
            previous_appt = None

            for appt in appointments:
                if previous_appt:
                    # Calculate buffer between previous end and current start
                    previous_end = previous_appt.end_time
                    previous_service = previous_appt.service
                    current_start = appt.start_time
                    current_service = appt.service

                    # Required buffers
                    previous_buffer_after = previous_service.buffer_after or cls.DEFAULT_MIN_BUFFER
                    current_buffer_before = current_service.buffer_before or cls.DEFAULT_MIN_BUFFER
                    required_buffer = max(previous_buffer_after, current_buffer_before)

                    # Actual buffer time in minutes
                    actual_buffer = (current_start - previous_end).total_seconds() / 60

                    if actual_buffer < required_buffer:
                        conflicts.append(
                            {
                                "first_appointment_id": str(previous_appt.id),
                                "first_service_name": previous_service.name,
                                "first_end_time": previous_end.isoformat(),
                                "second_appointment_id": str(appt.id),
                                "second_service_name": current_service.name,
                                "second_start_time": current_start.isoformat(),
                                "actual_buffer_minutes": actual_buffer,
                                "required_buffer_minutes": required_buffer,
                                "buffer_deficit": required_buffer - actual_buffer,
                            }
                        )

                previous_appt = appt

            return conflicts

        except Exception as e:
            logger.error(f"Error checking buffer conflicts: {str(e)}")
            return []

    @classmethod
    def adjust_appointment_time_for_buffer(
        cls,
        appointment_id: str,
        fix_type: str = "auto",  # 'auto', 'delay_start', 'advance_end'
    ) -> BufferResult:
        """
        Adjust appointment time to resolve buffer conflicts.

        Args:
            appointment_id: ID of the appointment to adjust
            fix_type: Type of fix to apply

        Returns:
            Dict with adjustment result
        """
        try:
            appointment = Appointment.objects.get(id=appointment_id)

            # Get adjacent appointments
            previous, next_appt = cls._get_adjacent_appointments(
                specialist_id=appointment.specialist_id,
                reference_time=appointment.start_time,
            )

            # Check for buffer conflicts
            buffer_before_conflict = False
            buffer_after_conflict = False
            buffer_before_deficit = 0
            buffer_after_deficit = 0

            # Check buffer before
            if previous:
                previous_end = previous.end_time
                previous_buffer = previous.service.buffer_after or cls.DEFAULT_MIN_BUFFER
                current_buffer = appointment.service.buffer_before or cls.DEFAULT_MIN_BUFFER
                required_buffer = max(previous_buffer, current_buffer)

                actual_buffer = (appointment.start_time - previous_end).total_seconds() / 60

                if actual_buffer < required_buffer:
                    buffer_before_conflict = True
                    buffer_before_deficit = required_buffer - actual_buffer

            # Check buffer after
            if next_appt:
                current_end = appointment.end_time
                current_buffer = appointment.service.buffer_after or cls.DEFAULT_MIN_BUFFER
                next_buffer = next_appt.service.buffer_before or cls.DEFAULT_MIN_BUFFER
                required_buffer = max(current_buffer, next_buffer)

                actual_buffer = (next_appt.start_time - current_end).total_seconds() / 60

                if actual_buffer < required_buffer:
                    buffer_after_conflict = True
                    buffer_after_deficit = required_buffer - actual_buffer

            # If no conflicts, no adjustment needed
            if not buffer_before_conflict and not buffer_after_conflict:
                return {
                    "success": True,
                    "message": "No buffer conflicts detected, no adjustment needed",
                    "appointment_id": str(appointment.id),
                    "was_adjusted": False,
                }

            # Apply fix based on fix_type
            if fix_type == "auto":
                # Automatically determine best fix
                if buffer_before_conflict and not buffer_after_conflict:
                    fix_type = "delay_start"
                elif buffer_after_conflict and not buffer_before_conflict:
                    fix_type = "advance_end"
                else:
                    # Both conflicts - prioritize the larger deficit
                    fix_type = (
                        "delay_start"
                        if buffer_before_deficit >= buffer_after_deficit
                        else "advance_end"
                    )

            if fix_type == "delay_start":
                # Delay the appointment start time to resolve buffer_before conflict
                if buffer_before_conflict and previous:
                    previous_end = previous.end_time
                    previous_buffer = previous.service.buffer_after or cls.DEFAULT_MIN_BUFFER
                    current_buffer = appointment.service.buffer_before or cls.DEFAULT_MIN_BUFFER
                    required_buffer = max(previous_buffer, current_buffer)

                    new_start_time = previous_end + timedelta(minutes=required_buffer)
                    new_end_time = new_start_time + timedelta(minutes=appointment.service.duration)

                    # Check if this creates a conflict with the next appointment
                    if (
                        next_appt
                        and new_end_time
                        + timedelta(
                            minutes=appointment.service.buffer_after or cls.DEFAULT_MIN_BUFFER
                        )
                        > next_appt.start_time
                    ):
                        return {
                            "success": False,
                            "message": "Cannot delay start time as it would create a conflict with the next appointment",
                            "appointment_id": str(appointment.id),
                            "was_adjusted": False,
                            "conflict_details": {
                                "next_appointment_id": str(next_appt.id),
                                "next_start_time": next_appt.start_time.isoformat(),
                            },
                        }

                    # Update appointment times
                    original_start = appointment.start_time
                    original_end = appointment.end_time

                    appointment.start_time = new_start_time
                    appointment.end_time = new_end_time
                    appointment.last_modified = timezone.now()
                    appointment.save()

                    return {
                        "success": True,
                        "message": f"Appointment delayed by {buffer_before_deficit} minutes to ensure buffer time",
                        "appointment_id": str(appointment.id),
                        "was_adjusted": True,
                        "original_start_time": original_start.isoformat(),
                        "original_end_time": original_end.isoformat(),
                        "new_start_time": new_start_time.isoformat(),
                        "new_end_time": new_end_time.isoformat(),
                        "adjustment_minutes": buffer_before_deficit,
                    }

                return {
                    "success": False,
                    "message": "No buffer before conflict to resolve",
                    "appointment_id": str(appointment.id),
                    "was_adjusted": False,
                }

            elif fix_type == "advance_end":
                # Advance the appointment end time (shorten it) to resolve buffer_after conflict
                if buffer_after_conflict and next_appt:
                    current_service = appointment.service
                    next_start = next_appt.start_time
                    current_buffer = current_service.buffer_after or cls.DEFAULT_MIN_BUFFER
                    next_buffer = next_appt.service.buffer_before or cls.DEFAULT_MIN_BUFFER
                    required_buffer = max(current_buffer, next_buffer)

                    new_end_time = next_start - timedelta(minutes=required_buffer)

                    # Check if this makes the appointment too short
                    min_duration = min(
                        15, current_service.duration - 5
                    )  # Allow shortening by at most 5 minutes
                    required_start_time = new_end_time - timedelta(minutes=min_duration)

                    if required_start_time < appointment.start_time:
                        # Can shorten within limits
                        original_end = appointment.end_time
                        appointment.end_time = new_end_time
                        appointment.last_modified = timezone.now()
                        appointment.save()

                        actual_duration = (
                            new_end_time - appointment.start_time
                        ).total_seconds() / 60

                        return {
                            "success": True,
                            "message": f"Appointment shortened by {buffer_after_deficit} minutes to ensure buffer time",
                            "appointment_id": str(appointment.id),
                            "was_adjusted": True,
                            "original_end_time": original_end.isoformat(),
                            "new_end_time": new_end_time.isoformat(),
                            "new_duration": actual_duration,
                            "original_duration": current_service.duration,
                            "adjustment_minutes": buffer_after_deficit,
                        }
                    else:
                        return {
                            "success": False,
                            "message": "Cannot shorten appointment further without making it too short",
                            "appointment_id": str(appointment.id),
                            "was_adjusted": False,
                            "min_duration": min_duration,
                            "required_adjustment": buffer_after_deficit,
                        }

                return {
                    "success": False,
                    "message": "No buffer after conflict to resolve",
                    "appointment_id": str(appointment.id),
                    "was_adjusted": False,
                }

            return {
                "success": False,
                "message": f"Unknown fix type: {fix_type}",
                "appointment_id": str(appointment.id),
                "was_adjusted": False,
            }

        except Exception as e:
            logger.error(f"Error adjusting appointment for buffer: {str(e)}")
            return {
                "success": False,
                "message": f"Error adjusting appointment: {str(e)}",
                "appointment_id": appointment_id,
                "was_adjusted": False,
            }

    # ------------------------------------------------------------------------
    # Private helper methods
    # ------------------------------------------------------------------------

    @staticmethod
    def _get_adjacent_appointments(
        specialist_id: str, reference_time: datetime
    ) -> Tuple[Optional[Appointment], Optional[Appointment]]:
        """
        Get the appointments immediately before and after a reference time.

        Args:
            specialist_id: ID of the specialist
            reference_time: Reference time to find adjacent appointments

        Returns:
            Tuple of (previous_appointment, next_appointment), either may be None
        """
        try:
            # Find previous appointment (ends before reference time)
            previous = (
                Appointment.objects.filter(
                    specialist_id=specialist_id,
                    end_time__lte=reference_time,
                    status__in=["scheduled", "confirmed", "in_progress"],
                )
                .order_by("-end_time")
                .first()
            )

            # Find next appointment (starts after reference time)
            next_appt = (
                Appointment.objects.filter(
                    specialist_id=specialist_id,
                    start_time__gt=reference_time,
                    status__in=["scheduled", "confirmed", "in_progress"],
                )
                .order_by("start_time")
                .first()
            )

            return previous, next_appt

        except Exception as e:
            logger.error(f"Error getting adjacent appointments: {str(e)}")
            return None, None

    @staticmethod
    def _get_average_buffer_times(service_id: str) -> Dict[str, float]:
        """
        Calculate average buffer times used for a service.

        Args:
            service_id: ID of the service

        Returns:
            Dict with average buffer times before and after
        """
        try:
            # Get the service
            service = Service.objects.get(id=service_id)

            # Default values
            avg_before = service.buffer_before or BufferManagementService.DEFAULT_MIN_BUFFER
            avg_after = service.buffer_after or BufferManagementService.DEFAULT_MIN_BUFFER

            # Attempt to calculate from actual appointments
            appointments = Appointment.objects.filter(
                service_id=service_id, status="completed"
            ).order_by("specialist_id", "start_time")[
                :100
            ]  # Limit to recent appointments

            if not appointments:
                return {"avg_before": avg_before, "avg_after": avg_after}

            # Group by specialist and calculate actual buffer times
            buffer_before_times = []
            buffer_after_times = []

            current_specialist = None
            previous_appt = None

            for appt in appointments:
                if current_specialist != appt.specialist_id:
                    # Reset when changing specialist
                    current_specialist = appt.specialist_id
                    previous_appt = None

                if previous_appt:
                    # Calculate actual buffer time between appointments
                    actual_buffer = (appt.start_time - previous_appt.end_time).total_seconds() / 60

                    # Only consider reasonable buffer times (1-60 minutes)
                    if 1 <= actual_buffer <= 60:
                        buffer_after_times.append(actual_buffer)
                        buffer_before_times.append(actual_buffer)

                previous_appt = appt

            # Calculate averages if we have data
            if buffer_before_times:
                avg_before = round(sum(buffer_before_times) / len(buffer_before_times))

            if buffer_after_times:
                avg_after = round(sum(buffer_after_times) / len(buffer_after_times))

            return {"avg_before": avg_before, "avg_after": avg_after}

        except Exception as e:
            logger.error(f"Error calculating average buffer times: {str(e)}")
            return {
                "avg_before": BufferManagementService.DEFAULT_MIN_BUFFER,
                "avg_after": BufferManagementService.DEFAULT_MIN_BUFFER,
            }

    @staticmethod
    def _generate_buffer_explanation(
        service: Service,
        suggested_before: int,
        suggested_after: int,
        preparation_required: bool,
        cleanup_required: bool,
        transition_complexity: str,
    ) -> str:
        """
        Generate a human-readable explanation for buffer time suggestions.

        Args:
            service: Service object
            suggested_before: Suggested buffer time before (minutes)
            suggested_after: Suggested buffer time after (minutes)
            preparation_required: Whether preparation time is needed
            cleanup_required: Whether cleanup time is needed
            transition_complexity: Complexity of transition

        Returns:
            Explanation string
        """
        parts = []

        # Basic intro
        parts.append(f"For {service.name} ({service.duration} minutes)")

        # Buffer before explanation
        before_parts = []
        if preparation_required:
            before_parts.append("preparation time")
        if transition_complexity == "high":
            before_parts.append("complex transition")
        elif transition_complexity == "medium":
            before_parts.append("standard transition")

        if before_parts:
            parts.append(
                f"Buffer before: {suggested_before} minutes recommended for {' and '.join(before_parts)}"
            )
        else:
            parts.append(f"Buffer before: {suggested_before} minutes (minimal transition)")

        # Buffer after explanation
        after_parts = []
        if cleanup_required:
            after_parts.append("cleanup time")
        if transition_complexity == "high":
            after_parts.append("complex transition")
        elif transition_complexity == "medium":
            after_parts.append("standard transition")

        if after_parts:
            parts.append(
                f"Buffer after: {suggested_after} minutes recommended for {' and '.join(after_parts)}"
            )
        else:
            parts.append(f"Buffer after: {suggested_after} minutes (minimal transition)")

        return ". ".join(parts) + "."
