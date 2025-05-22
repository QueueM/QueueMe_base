"""
Scheduling Optimizer Service

A high-level orchestration service that combines availability calculation,
conflict detection, and resource optimization to provide sophisticated
scheduling capabilities for the QueueMe platform.

Key features:
1. Multi-service booking management (packages, sequences)
2. Smart specialist assignment based on workload balancing
3. Optimized resource allocation
4. Efficient handling of complex scheduling constraints
5. Support for different scheduling strategies
"""

import logging
import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.bookingapp.models import Appointment, AppointmentResource
from apps.bookingapp.services.availability_service import AvailabilityService
from apps.bookingapp.services.conflict_detection_service import ConflictDetectionService
from apps.serviceapp.models import (
    Service,
    ServiceResource,
)
from apps.shopapp.models import Resource
from apps.specialistsapp.models import Specialist

logger = logging.getLogger(__name__)

# Type definitions
TimeSlot = Tuple[datetime, datetime]  # (start_time, end_time)
SchedulingResult = Dict[str, Any]  # Result of scheduling operations


class SchedulingOptimizer:
    """
    Main orchestration service for advanced scheduling operations.

    This service integrates the lower-level availability and conflict detection
    services to provide high-level scheduling capabilities.
    """

    # Constants for scheduling strategies
    STRATEGY_EARLIEST_AVAILABLE = "earliest_available"  # Book at earliest possible time
    STRATEGY_BALANCED_WORKLOAD = (
        "balanced_workload"  # Distribute workload among specialists
    )
    STRATEGY_MINIMIZE_WAIT = "minimize_wait"  # Minimize customer wait time
    STRATEGY_RESOURCE_EFFICIENT = "resource_efficient"  # Optimize resource usage

    @classmethod
    def schedule_appointment(
        cls,
        shop_id: str,
        service_id: str,
        customer_id: str,
        target_date: date,
        target_time: Optional[time] = None,
        specialist_id: Optional[str] = None,
        strategy: str = STRATEGY_EARLIEST_AVAILABLE,
        notes: Optional[str] = None,
    ) -> SchedulingResult:
        """
        Schedule a single appointment using specified strategy.

        Args:
            shop_id: ID of the shop
            service_id: ID of the service
            customer_id: ID of the customer
            target_date: Preferred date for appointment
            target_time: Optional preferred time (if None, finds optimal time)
            specialist_id: Optional preferred specialist (if None, assigns optimal specialist)
            strategy: Scheduling strategy to use
            notes: Optional booking notes

        Returns:
            Dict with scheduling result and details
        """
        try:
            service = Service.objects.get(id=service_id)

            # If both time and specialist are specified, verify availability
            if target_time and specialist_id:
                target_datetime = datetime.combine(target_date, target_time)
                end_datetime = target_datetime + timedelta(minutes=service.duration)

                # Check conflicts
                conflicts = ConflictDetectionService.check_all_conflicts(
                    service_id=service_id,
                    shop_id=shop_id,
                    specialist_id=specialist_id,
                    start_time=target_datetime,
                    end_time=end_datetime,
                    customer_id=customer_id,
                )

                if conflicts["has_conflict"]:
                    return {
                        "success": False,
                        "message": f"Cannot schedule: {conflicts['message']}",
                        "conflicts": conflicts,
                    }

                # Create the appointment
                return cls._create_appointment(
                    shop_id=shop_id,
                    service_id=service_id,
                    specialist_id=specialist_id,
                    customer_id=customer_id,
                    start_time=target_datetime,
                    end_time=end_datetime,
                    notes=notes,
                )

            # If only time is specified, find available specialist
            elif target_time:
                target_datetime = datetime.combine(target_date, target_time)
                end_datetime = target_datetime + timedelta(minutes=service.duration)

                # Find an available specialist
                specialist_id = AvailabilityService.get_next_available_specialist(
                    shop_id=shop_id,
                    service_id=service_id,
                    target_date=target_date,
                    target_time=target_time,
                )

                if not specialist_id:
                    return {
                        "success": False,
                        "message": "No specialists available at the requested time",
                        "alternatives": cls._suggest_alternative_times(
                            shop_id=shop_id,
                            service_id=service_id,
                            target_date=target_date,
                            limit=3,
                        ),
                    }

                # Create the appointment
                return cls._create_appointment(
                    shop_id=shop_id,
                    service_id=service_id,
                    specialist_id=specialist_id,
                    customer_id=customer_id,
                    start_time=target_datetime,
                    end_time=end_datetime,
                    notes=notes,
                )

            # If only specialist is specified, find optimal time
            elif specialist_id:
                # Get available slots for this specialist
                available_slots = AvailabilityService.get_available_slots(
                    shop_id=shop_id,
                    service_id=service_id,
                    target_date=target_date,
                    specialist_id=specialist_id,
                )

                if not available_slots:
                    # Check future dates
                    earliest_slot = AvailabilityService.get_earliest_available_slot(
                        shop_id=shop_id,
                        service_id=service_id,
                        start_date=target_date + timedelta(days=1),
                        days_to_check=7,
                        specialist_id=specialist_id,
                    )

                    if earliest_slot:
                        return {
                            "success": False,
                            "message": f"No availability with this specialist on {target_date}",
                            "next_available": {
                                "date": earliest_slot[0].date(),
                                "time": earliest_slot[0].time(),
                                "specialist_id": specialist_id,
                            },
                        }
                    else:
                        return {
                            "success": False,
                            "message": "No availability with this specialist in the next 7 days",
                        }

                # Use the first available slot
                start_time, end_time = available_slots[0]

                # Create the appointment
                return cls._create_appointment(
                    shop_id=shop_id,
                    service_id=service_id,
                    specialist_id=specialist_id,
                    customer_id=customer_id,
                    start_time=start_time,
                    end_time=end_time,
                    notes=notes,
                )

            # If neither time nor specialist is specified, use the requested strategy
            else:
                return cls._schedule_with_strategy(
                    shop_id=shop_id,
                    service_id=service_id,
                    customer_id=customer_id,
                    target_date=target_date,
                    strategy=strategy,
                    notes=notes,
                )

        except Exception as e:
            logger.error(f"Error scheduling appointment: {str(e)}")
            return {
                "success": False,
                "message": f"Error scheduling appointment: {str(e)}",
            }

    @classmethod
    def schedule_multiple_services(
        cls,
        shop_id: str,
        service_ids: List[str],
        customer_id: str,
        target_date: date,
        sequential: bool = True,
        preferred_specialist_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> SchedulingResult:
        """
        Schedule multiple services either sequentially or independently.

        Args:
            shop_id: ID of the shop
            service_ids: List of service IDs to schedule
            customer_id: ID of the customer
            target_date: Preferred date for appointments
            sequential: If True, schedules services back-to-back; otherwise independently
            preferred_specialist_id: Optional preferred specialist for all services
            notes: Optional booking notes

        Returns:
            Dict with scheduling results for all services
        """
        try:
            if not service_ids:
                return {
                    "success": False,
                    "message": "No services specified for scheduling",
                }

            # Get service details
            services = []
            for service_id in service_ids:
                try:
                    service = Service.objects.get(id=service_id)
                    services.append(service)
                except Service.DoesNotExist:
                    return {
                        "success": False,
                        "message": f"Service with ID {service_id} not found",
                    }

            results = []

            # Handle sequential booking (back-to-back appointments)
            if sequential:
                # Sort services by duration if optimizing time
                services.sort(key=lambda s: s.duration, reverse=True)

                # Start with the first service
                next_start_time = None
                current_specialist_id = preferred_specialist_id

                for service in services:
                    # Schedule this service
                    result = cls.schedule_appointment(
                        shop_id=shop_id,
                        service_id=str(service.id),
                        customer_id=customer_id,
                        target_date=target_date,
                        target_time=next_start_time.time() if next_start_time else None,
                        specialist_id=current_specialist_id,
                        strategy=cls.STRATEGY_EARLIEST_AVAILABLE,
                        notes=notes,
                    )

                    results.append(result)

                    if not result["success"]:
                        # If any service fails, cancel previously booked ones
                        cls._cancel_appointments(
                            [
                                r.get("appointment_id")
                                for r in results
                                if r.get("success")
                            ]
                        )

                        return {
                            "success": False,
                            "message": f"Failed to schedule service {service.name}: {result['message']}",
                            "partial_results": results,
                        }

                    # Set the next start time to be right after this appointment
                    # Include buffer time if specified
                    buffer_after = service.buffer_after or 0
                    next_start_time = result["end_time"] + timedelta(
                        minutes=buffer_after
                    )

                    # Try to keep the same specialist if possible
                    if not preferred_specialist_id:
                        current_specialist_id = result["specialist_id"]

            # Handle independent bookings (not necessarily back-to-back)
            else:
                for service in services:
                    result = cls.schedule_appointment(
                        shop_id=shop_id,
                        service_id=str(service.id),
                        customer_id=customer_id,
                        target_date=target_date,
                        specialist_id=preferred_specialist_id,
                        strategy=cls.STRATEGY_EARLIEST_AVAILABLE,
                        notes=notes,
                    )

                    results.append(result)

            # Determine overall success
            all_successful = all(result["success"] for result in results)

            return {
                "success": all_successful,
                "message": (
                    "All services scheduled successfully"
                    if all_successful
                    else "Some services could not be scheduled"
                ),
                "appointments": [
                    {
                        "appointment_id": result["appointment_id"],
                        "service_id": result["service_id"],
                        "specialist_id": result["specialist_id"],
                        "start_time": result["start_time"],
                        "end_time": result["end_time"],
                    }
                    for result in results
                    if result["success"]
                ],
                "results": results,
            }

        except Exception as e:
            logger.error(f"Error scheduling multiple services: {str(e)}")
            return {
                "success": False,
                "message": f"Error scheduling multiple services: {str(e)}",
            }

    @classmethod
    def reschedule_appointment(
        cls,
        appointment_id: str,
        new_date: Optional[date] = None,
        new_time: Optional[time] = None,
        new_specialist_id: Optional[str] = None,
    ) -> SchedulingResult:
        """
        Reschedule an existing appointment.

        Args:
            appointment_id: ID of the appointment to reschedule
            new_date: Optional new date (if None, keeps original date)
            new_time: Optional new time (if None, keeps original time)
            new_specialist_id: Optional new specialist (if None, keeps original specialist)

        Returns:
            Dict with rescheduling result
        """
        try:
            # Get the existing appointment
            appointment = Appointment.objects.get(id=appointment_id)

            if appointment.status not in ["scheduled", "confirmed"]:
                return {
                    "success": False,
                    "message": f"Cannot reschedule appointment with status '{appointment.status}'",
                }

            # Determine the new date/time
            original_datetime = appointment.start_time
            original_date = original_datetime.date()
            original_time = original_datetime.time()

            new_date = new_date or original_date
            new_time = new_time or original_time

            new_datetime = datetime.combine(new_date, new_time)
            service = appointment.service

            # Calculate end time
            new_end_datetime = new_datetime + timedelta(minutes=service.duration)

            # Determine specialist
            specialist_id = new_specialist_id or appointment.specialist_id

            # Check for conflicts
            conflicts = ConflictDetectionService.check_all_conflicts(
                service_id=str(service.id),
                shop_id=str(appointment.shop_id),
                specialist_id=specialist_id,
                start_time=new_datetime,
                end_time=new_end_datetime,
                customer_id=(
                    str(appointment.customer_id) if appointment.customer else None
                ),
                exclude_appointment_id=appointment_id,
            )

            if conflicts["has_conflict"]:
                return {
                    "success": False,
                    "message": f"Cannot reschedule: {conflicts['message']}",
                    "conflicts": conflicts,
                }

            # Update the appointment
            with transaction.atomic():
                # Store original values for reference
                original_values = {
                    "start_time": appointment.start_time,
                    "end_time": appointment.end_time,
                    "specialist_id": appointment.specialist_id,
                }

                # Update appointment
                appointment.start_time = new_datetime
                appointment.end_time = new_end_datetime
                appointment.specialist_id = specialist_id
                appointment.last_modified = timezone.now()
                appointment.save()

                # Update resources if needed
                if new_specialist_id:
                    # Re-assign resources based on the new specialist/time
                    cls._update_appointment_resources(appointment)

            return {
                "success": True,
                "message": "Appointment rescheduled successfully",
                "appointment_id": str(appointment.id),
                "service_id": str(service.id),
                "specialist_id": specialist_id,
                "start_time": new_datetime,
                "end_time": new_end_datetime,
                "original": original_values,
            }

        except Appointment.DoesNotExist:
            return {
                "success": False,
                "message": f"Appointment with ID {appointment_id} not found",
            }
        except Exception as e:
            logger.error(f"Error rescheduling appointment: {str(e)}")
            return {
                "success": False,
                "message": f"Error rescheduling appointment: {str(e)}",
            }

    # ------------------------------------------------------------------------
    # Private helper methods
    # ------------------------------------------------------------------------

    @classmethod
    def _schedule_with_strategy(
        cls,
        shop_id: str,
        service_id: str,
        customer_id: str,
        target_date: date,
        strategy: str,
        notes: Optional[str] = None,
    ) -> SchedulingResult:
        """
        Schedule an appointment using a specific optimization strategy.

        Args:
            shop_id: ID of the shop
            service_id: ID of the service
            customer_id: ID of the customer
            target_date: Target date for the appointment
            strategy: Scheduling strategy to use
            notes: Optional booking notes

        Returns:
            Dict with scheduling result and details
        """
        try:
            service = Service.objects.get(id=service_id)

            if strategy == cls.STRATEGY_EARLIEST_AVAILABLE:
                # Find the earliest available slot with any specialist
                earliest_slot = AvailabilityService.get_earliest_available_slot(
                    shop_id=shop_id,
                    service_id=service_id,
                    start_date=target_date,
                    days_to_check=1,  # Only check this day
                )

                if not earliest_slot:
                    # Try next 7 days
                    earliest_slot = AvailabilityService.get_earliest_available_slot(
                        shop_id=shop_id,
                        service_id=service_id,
                        start_date=target_date + timedelta(days=1),
                        days_to_check=7,
                    )

                    if not earliest_slot:
                        return {
                            "success": False,
                            "message": "No availability found for the next 7 days",
                        }
                    else:
                        # Slot found on a future date
                        start_time, end_time = earliest_slot
                        specialist_id = (
                            AvailabilityService.get_next_available_specialist(
                                shop_id=shop_id,
                                service_id=service_id,
                                target_date=start_time.date(),
                                target_time=start_time.time(),
                            )
                        )

                        return cls._create_appointment(
                            shop_id=shop_id,
                            service_id=service_id,
                            specialist_id=specialist_id,
                            customer_id=customer_id,
                            start_time=start_time,
                            end_time=end_time,
                            notes=notes,
                        )

                # Slot found on the target date
                start_time, end_time = earliest_slot
                specialist_id = AvailabilityService.get_next_available_specialist(
                    shop_id=shop_id,
                    service_id=service_id,
                    target_date=target_date,
                    target_time=start_time.time(),
                )

                return cls._create_appointment(
                    shop_id=shop_id,
                    service_id=service_id,
                    specialist_id=specialist_id,
                    customer_id=customer_id,
                    start_time=start_time,
                    end_time=end_time,
                    notes=notes,
                )

            elif strategy == cls.STRATEGY_BALANCED_WORKLOAD:
                # Get available specialists for this service
                specialists = Specialist.objects.filter(
                    specialist_services__service_id=service_id, is_active=True
                )

                if not specialists:
                    return {
                        "success": False,
                        "message": "No specialists available for this service",
                    }

                # Get workload counts for today
                specialist_load = cls._get_specialist_workload(
                    specialists=specialists, target_date=target_date
                )

                # Sort specialists by workload (least busy first)
                sorted_specialists = sorted(specialist_load.items(), key=lambda x: x[1])

                # Try scheduling with each specialist in order of least busy
                for specialist_id, _ in sorted_specialists:
                    # Get available slots for this specialist
                    available_slots = AvailabilityService.get_available_slots(
                        shop_id=shop_id,
                        service_id=service_id,
                        target_date=target_date,
                        specialist_id=specialist_id,
                    )

                    if available_slots:
                        # Use the first available slot
                        start_time, end_time = available_slots[0]

                        return cls._create_appointment(
                            shop_id=shop_id,
                            service_id=service_id,
                            specialist_id=specialist_id,
                            customer_id=customer_id,
                            start_time=start_time,
                            end_time=end_time,
                            notes=notes,
                        )

                # If we got here, no specialist had availability on the target date
                return {
                    "success": False,
                    "message": "No availability found with any specialist on the target date",
                    "alternatives": cls._suggest_alternative_times(
                        shop_id=shop_id,
                        service_id=service_id,
                        target_date=target_date + timedelta(days=1),
                        limit=3,
                    ),
                }

            elif strategy == cls.STRATEGY_MINIMIZE_WAIT:
                # Get all available slots for the target date
                all_slots = []

                # Get specialists for this service
                specialists = Specialist.objects.filter(
                    specialist_services__service_id=service_id, is_active=True
                )

                for specialist in specialists:
                    specialist_slots = AvailabilityService.get_available_slots(
                        shop_id=shop_id,
                        service_id=service_id,
                        target_date=target_date,
                        specialist_id=str(specialist.id),
                    )

                    for slot in specialist_slots:
                        all_slots.append((slot[0], slot[1], str(specialist.id)))

                if not all_slots:
                    return {
                        "success": False,
                        "message": "No availability found on the target date",
                        "alternatives": cls._suggest_alternative_times(
                            shop_id=shop_id,
                            service_id=service_id,
                            target_date=target_date + timedelta(days=1),
                            limit=3,
                        ),
                    }

                # Sort slots by start time
                all_slots.sort(key=lambda x: x[0])

                # Use the earliest slot
                start_time, end_time, specialist_id = all_slots[0]

                return cls._create_appointment(
                    shop_id=shop_id,
                    service_id=service_id,
                    specialist_id=specialist_id,
                    customer_id=customer_id,
                    start_time=start_time,
                    end_time=end_time,
                    notes=notes,
                )

            elif strategy == cls.STRATEGY_RESOURCE_EFFICIENT:
                # This strategy minimizes resource fragmentation

                # Get service resource requirements
                service_resources = ServiceResource.objects.filter(
                    service_id=service_id
                )
                resource_ids = [sr.resource_id for sr in service_resources]

                if not resource_ids:
                    # If no special resources needed, fall back to earliest available
                    return cls._schedule_with_strategy(
                        shop_id=shop_id,
                        service_id=service_id,
                        customer_id=customer_id,
                        target_date=target_date,
                        strategy=cls.STRATEGY_EARLIEST_AVAILABLE,
                        notes=notes,
                    )

                # Get specialists for this service
                specialists = Specialist.objects.filter(
                    specialist_services__service_id=service_id, is_active=True
                )

                # Get current resource utilization
                resource_slots = cls._get_resource_availability(
                    shop_id=shop_id, resource_ids=resource_ids, target_date=target_date
                )

                # Find optimal slots where resources are already being used
                best_slot = None
                best_specialist = None

                for specialist in specialists:
                    # Get available slots for this specialist
                    specialist_slots = AvailabilityService.get_available_slots(
                        shop_id=shop_id,
                        service_id=service_id,
                        target_date=target_date,
                        specialist_id=str(specialist.id),
                    )

                    if not specialist_slots:
                        continue

                    # Evaluate each slot for resource efficiency
                    for slot_start, slot_end in specialist_slots:
                        score = cls._calculate_resource_efficiency_score(
                            slot_start=slot_start,
                            slot_end=slot_end,
                            resource_slots=resource_slots,
                        )

                        if best_slot is None or score > best_slot[2]:
                            best_slot = (slot_start, slot_end, score)
                            best_specialist = specialist

                if best_slot and best_specialist:
                    start_time, end_time, _ = best_slot

                    return cls._create_appointment(
                        shop_id=shop_id,
                        service_id=service_id,
                        specialist_id=str(best_specialist.id),
                        customer_id=customer_id,
                        start_time=start_time,
                        end_time=end_time,
                        notes=notes,
                    )
                else:
                    # Fall back to earliest available
                    return cls._schedule_with_strategy(
                        shop_id=shop_id,
                        service_id=service_id,
                        customer_id=customer_id,
                        target_date=target_date,
                        strategy=cls.STRATEGY_EARLIEST_AVAILABLE,
                        notes=notes,
                    )

            else:
                # Unknown strategy, fall back to earliest available
                return cls._schedule_with_strategy(
                    shop_id=shop_id,
                    service_id=service_id,
                    customer_id=customer_id,
                    target_date=target_date,
                    strategy=cls.STRATEGY_EARLIEST_AVAILABLE,
                    notes=notes,
                )

        except Exception as e:
            logger.error(f"Error scheduling with strategy '{strategy}': {str(e)}")
            return {
                "success": False,
                "message": f"Error scheduling with strategy '{strategy}': {str(e)}",
            }

    @classmethod
    def _create_appointment(
        cls,
        shop_id: str,
        service_id: str,
        specialist_id: str,
        customer_id: str,
        start_time: datetime,
        end_time: datetime,
        notes: Optional[str] = None,
    ) -> SchedulingResult:
        """
        Create a new appointment with the given parameters.

        Args:
            shop_id: ID of the shop
            service_id: ID of the service
            specialist_id: ID of the specialist
            customer_id: ID of the customer
            start_time: Start time of the appointment
            end_time: End time of the appointment
            notes: Optional booking notes

        Returns:
            Dict with creation result and appointment details
        """
        try:
            service = Service.objects.get(id=service_id)

            # Create appointment with transaction to ensure atomicity
            with transaction.atomic():
                appointment = Appointment.objects.create(
                    id=uuid.uuid4(),
                    shop_id=shop_id,
                    service_id=service_id,
                    specialist_id=specialist_id,
                    customer_id=customer_id,
                    start_time=start_time,
                    end_time=end_time,
                    status="scheduled",
                    notes=notes or "",
                    created_at=timezone.now(),
                    last_modified=timezone.now(),
                )

                # Allocate resources for the appointment
                cls._allocate_resources(appointment)

            return {
                "success": True,
                "message": "Appointment scheduled successfully",
                "appointment_id": str(appointment.id),
                "service_id": service_id,
                "service_name": service.name,
                "specialist_id": specialist_id,
                "customer_id": customer_id,
                "start_time": start_time,
                "end_time": end_time,
                "duration": service.duration,
                "status": "scheduled",
            }

        except Exception as e:
            logger.error(f"Error creating appointment: {str(e)}")
            return {
                "success": False,
                "message": f"Error creating appointment: {str(e)}",
            }

    @staticmethod
    def _allocate_resources(appointment: Appointment) -> List[AppointmentResource]:
        """
        Allocate required resources for an appointment.

        Args:
            appointment: The appointment to allocate resources for

        Returns:
            List of created AppointmentResource objects
        """
        try:
            # Get resource requirements for this service
            service_resources = ServiceResource.objects.filter(
                service_id=appointment.service_id
            )

            if not service_resources:
                return []

            allocated_resources = []

            for sr in service_resources:
                # Check if resource is available
                if not ConflictDetectionService._is_resource_available(
                    resource_id=str(sr.resource_id),
                    start_time=appointment.start_time,
                    end_time=appointment.end_time,
                ):
                    # If resource not available, try to find an alternative
                    alternative_resource = (
                        Resource.objects.filter(
                            shop_id=appointment.shop_id,
                            resource_type=sr.resource.resource_type,
                            is_active=True,
                        )
                        .exclude(id=sr.resource_id)
                        .first()
                    )

                    if (
                        alternative_resource
                        and ConflictDetectionService._is_resource_available(
                            resource_id=str(alternative_resource.id),
                            start_time=appointment.start_time,
                            end_time=appointment.end_time,
                        )
                    ):
                        # Use alternative resource
                        resource_id = alternative_resource.id
                    else:
                        # No alternative available, skip this resource
                        continue
                else:
                    resource_id = sr.resource_id

                # Create resource allocation
                appointment_resource = AppointmentResource.objects.create(
                    appointment=appointment,
                    resource_id=resource_id,
                    quantity=sr.quantity,
                )

                allocated_resources.append(appointment_resource)

            return allocated_resources

        except Exception as e:
            logger.error(
                f"Error allocating resources for appointment {appointment.id}: {str(e)}"
            )
            return []

    @staticmethod
    def _update_appointment_resources(appointment: Appointment) -> None:
        """
        Update resources allocated to an appointment after rescheduling.

        Args:
            appointment: The appointment to update resources for
        """
        try:
            # Remove current resource allocations
            AppointmentResource.objects.filter(appointment=appointment).delete()

            # Reallocate resources
            SchedulingOptimizer._allocate_resources(appointment)

        except Exception as e:
            logger.error(
                f"Error updating resources for appointment {appointment.id}: {str(e)}"
            )

    @staticmethod
    def _cancel_appointments(appointment_ids: List[str]) -> None:
        """
        Cancel multiple appointments and release their resources.

        Args:
            appointment_ids: List of appointment IDs to cancel
        """
        try:
            with transaction.atomic():
                # Update appointment status
                Appointment.objects.filter(id__in=appointment_ids).update(
                    status="cancelled", last_modified=timezone.now()
                )

                # Release resources
                AppointmentResource.objects.filter(
                    appointment_id__in=appointment_ids
                ).delete()

        except Exception as e:
            logger.error(f"Error cancelling appointments: {str(e)}")

    @staticmethod
    def _get_specialist_workload(
        specialists: List[Specialist], target_date: date
    ) -> Dict[str, int]:
        """
        Get the current workload for each specialist on a given date.

        Args:
            specialists: List of specialist objects
            target_date: Date to check workload for

        Returns:
            Dict mapping specialist IDs to their appointment count
        """
        try:
            # Convert date to datetime range
            day_start = datetime.combine(target_date, time.min)
            day_end = datetime.combine(target_date, time.max)

            # Count appointments for each specialist
            specialist_counts = (
                Appointment.objects.filter(
                    specialist__in=specialists,
                    start_time__gte=day_start,
                    start_time__lte=day_end,
                    status__in=["scheduled", "confirmed", "in_progress"],
                )
                .values("specialist_id")
                .annotate(count=Count("id"))
            )

            # Convert to dict
            workload = {str(s.id): 0 for s in specialists}

            for entry in specialist_counts:
                workload[str(entry["specialist_id"])] = entry["count"]

            return workload

        except Exception as e:
            logger.error(f"Error getting specialist workload: {str(e)}")
            return {str(s.id): 0 for s in specialists}

    @staticmethod
    def _get_resource_availability(
        shop_id: str, resource_ids: List[str], target_date: date
    ) -> Dict[str, List[TimeSlot]]:
        """
        Get availability slots for each resource on a given date.

        Args:
            shop_id: ID of the shop
            resource_ids: List of resource IDs to check
            target_date: Date to check availability for

        Returns:
            Dict mapping resource IDs to lists of used time slots
        """
        try:
            # Convert date to datetime range
            day_start = datetime.combine(target_date, time.min)
            day_end = datetime.combine(target_date, time.max)

            # Get all resource allocations for this day
            allocations = AppointmentResource.objects.filter(
                resource_id__in=resource_ids,
                appointment__start_time__gte=day_start,
                appointment__start_time__lte=day_end,
                appointment__status__in=["scheduled", "confirmed", "in_progress"],
            ).select_related("appointment")

            # Group by resource
            resource_slots = defaultdict(list)

            for alloc in allocations:
                resource_id = str(alloc.resource_id)
                start_time = alloc.appointment.start_time
                end_time = alloc.appointment.end_time

                resource_slots[resource_id].append((start_time, end_time))

            return resource_slots

        except Exception as e:
            logger.error(f"Error getting resource availability: {str(e)}")
            return {resource_id: [] for resource_id in resource_ids}

    @staticmethod
    def _calculate_resource_efficiency_score(
        slot_start: datetime,
        slot_end: datetime,
        resource_slots: Dict[str, List[TimeSlot]],
    ) -> float:
        """
        Calculate a score for a time slot based on resource utilization efficiency.

        Higher score means better resource utilization (less fragmentation).

        Args:
            slot_start: Start time of the proposed slot
            slot_end: End time of the proposed slot
            resource_slots: Dict of existing resource allocations

        Returns:
            Efficiency score (higher is better)
        """
        try:
            # Base score
            score = 0.0

            # Check each resource
            for resource_id, slots in resource_slots.items():
                # Skip if no existing allocations
                if not slots:
                    continue

                for existing_start, existing_end in slots:
                    # Calculate distance to this slot (in minutes)
                    if existing_end <= slot_start:
                        # Existing slot ends before proposed slot starts
                        gap = (slot_start - existing_end).total_seconds() / 60

                        if gap < 15:
                            # Very close - high efficiency
                            score += 10.0
                        elif gap < 30:
                            # Somewhat close
                            score += 5.0
                        elif gap < 60:
                            # Within an hour
                            score += 1.0

                    elif existing_start >= slot_end:
                        # Existing slot starts after proposed slot ends
                        gap = (existing_start - slot_end).total_seconds() / 60

                        if gap < 15:
                            # Very close - high efficiency
                            score += 10.0
                        elif gap < 30:
                            # Somewhat close
                            score += 5.0
                        elif gap < 60:
                            # Within an hour
                            score += 1.0

                    else:
                        # Overlap - penalize
                        score -= 20.0

            return score

        except Exception as e:
            logger.error(f"Error calculating resource efficiency score: {str(e)}")
            return 0.0

    @staticmethod
    def _suggest_alternative_times(
        shop_id: str, service_id: str, target_date: date, limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Suggest alternative times when no availability found.

        Args:
            shop_id: ID of the shop
            service_id: ID of the service
            target_date: Starting date for suggestions
            limit: Maximum number of suggestions

        Returns:
            List of alternative time suggestions
        """
        try:
            suggestions = []
            current_date = target_date
            days_checked = 0

            while len(suggestions) < limit and days_checked < 14:
                # Get available slots for this day
                specialists = Specialist.objects.filter(
                    specialist_services__service_id=service_id, is_active=True
                )

                day_slots = []

                for specialist in specialists:
                    specialist_slots = AvailabilityService.get_available_slots(
                        shop_id=shop_id,
                        service_id=service_id,
                        target_date=current_date,
                        specialist_id=str(specialist.id),
                    )

                    for slot in specialist_slots:
                        day_slots.append((slot[0], slot[1], str(specialist.id)))

                if day_slots:
                    # Sort by start time
                    day_slots.sort(key=lambda x: x[0])

                    # Take up to 3 slots from this day
                    for i, (start, end, specialist_id) in enumerate(day_slots[:3]):
                        if len(suggestions) >= limit:
                            break

                        suggestions.append(
                            {
                                "date": start.date(),
                                "time": start.time(),
                                "specialist_id": specialist_id,
                                "end_time": end,
                            }
                        )

                # Move to next day
                current_date += timedelta(days=1)
                days_checked += 1

            return suggestions

        except Exception as e:
            logger.error(f"Error suggesting alternative times: {str(e)}")
            return []
