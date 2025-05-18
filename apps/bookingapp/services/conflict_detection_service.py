"""
Conflict Detection Service

A sophisticated service for identifying and preventing booking conflicts related to:
1. Specialist scheduling
2. Resource allocation
3. Room/location availability
4. Service capacity
5. Overlapping service dependencies

This service helps maintain booking integrity and prevents double-booking.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.bookingapp.models import Appointment, AppointmentResource
from apps.serviceapp.models import Service, ServiceDependency, ServiceResource
from apps.shopapp.models import Resource, ResourceAvailability
from apps.specialistsapp.models import Specialist

logger = logging.getLogger(__name__)

# Type definitions
TimeSlot = Tuple[datetime, datetime]  # (start_time, end_time)
ConflictResult = Dict[str, Any]  # Result of conflict check with details


class ConflictDetectionService:
    """
    Service for detecting various types of booking conflicts to maintain
    scheduling integrity in the QueueMe platform.
    """

    @classmethod
    def check_specialist_conflict(
        cls,
        specialist_id: str,
        start_time: datetime,
        end_time: datetime,
        exclude_appointment_id: Optional[str] = None,
    ) -> ConflictResult:
        """
        Check if a specialist has any conflicting appointments during the specified time slot.

        Args:
            specialist_id: ID of the specialist to check
            start_time: Start time of the appointment (with buffer before)
            end_time: End time of the appointment (with buffer after)
            exclude_appointment_id: Optional ID of an appointment to exclude from conflict check

        Returns:
            Dict with conflict status and details
        """
        try:
            # Build query for overlapping appointments
            query = Q(
                specialist_id=specialist_id,
                start_time__lt=end_time,  # Starts before this appointment ends
                end_time__gt=start_time,  # Ends after this appointment starts
                status__in=[
                    "scheduled",
                    "confirmed",
                    "in_progress",
                ],  # Only active appointments
            )

            # Exclude the specified appointment if provided (for reschedule)
            if exclude_appointment_id:
                query &= ~Q(id=exclude_appointment_id)

            # Check for conflicts
            conflicts = Appointment.objects.filter(query)

            if conflicts.exists():
                conflict_details = [
                    {
                        "appointment_id": str(appt.id),
                        "service_name": appt.service.name,
                        "customer_name": (appt.customer.name if appt.customer else "Unknown"),
                        "start_time": appt.start_time.isoformat(),
                        "end_time": appt.end_time.isoformat(),
                    }
                    for appt in conflicts[:5]
                ]  # Limit to 5 conflicts for performance

                return {
                    "has_conflict": True,
                    "conflict_type": "specialist_schedule",
                    "message": f"Specialist has {conflicts.count()} conflicting appointment(s)",
                    "details": conflict_details,
                }

            return {
                "has_conflict": False,
                "conflict_type": None,
                "message": "No specialist scheduling conflicts detected",
                "details": [],
            }

        except Exception as e:
            logger.error(f"Error checking specialist conflict: {str(e)}")
            return {
                "has_conflict": True,
                "conflict_type": "system_error",
                "message": f"Error checking specialist availability: {str(e)}",
                "details": [],
            }

    @classmethod
    def check_resource_conflict(
        cls,
        shop_id: str,
        resource_ids: List[str],
        start_time: datetime,
        end_time: datetime,
        exclude_appointment_id: Optional[str] = None,
    ) -> ConflictResult:
        """
        Check if any required resources have conflicting allocations.

        Args:
            shop_id: ID of the shop
            resource_ids: List of resource IDs required for the service
            start_time: Start time of the appointment
            end_time: End time of the appointment
            exclude_appointment_id: Optional appointment ID to exclude

        Returns:
            Dict with conflict status and details
        """
        try:
            if not resource_ids:
                return {
                    "has_conflict": False,
                    "conflict_type": None,
                    "message": "No resources required for this service",
                    "details": [],
                }

            conflict_resources = []

            for resource_id in resource_ids:
                # Check resource availability during the timeframe
                if not cls._is_resource_available(resource_id, start_time, end_time):
                    resource = Resource.objects.get(id=resource_id)
                    conflict_resources.append(
                        {
                            "resource_id": str(resource_id),
                            "resource_name": resource.name,
                            "message": "Resource is not available during this time",
                        }
                    )
                    continue

                # Check for conflicting resource allocations
                query = Q(
                    resource_id=resource_id,
                    appointment__start_time__lt=end_time,
                    appointment__end_time__gt=start_time,
                    appointment__status__in=["scheduled", "confirmed", "in_progress"],
                )

                # Exclude the specified appointment if provided
                if exclude_appointment_id:
                    query &= ~Q(appointment_id=exclude_appointment_id)

                conflicts = AppointmentResource.objects.filter(query)

                if conflicts.exists():
                    resource = Resource.objects.get(id=resource_id)
                    conflict_details = [
                        {
                            "appointment_id": str(alloc.appointment.id),
                            "start_time": alloc.appointment.start_time.isoformat(),
                            "end_time": alloc.appointment.end_time.isoformat(),
                        }
                        for alloc in conflicts[:3]
                    ]  # Limit to 3 for brevity

                    conflict_resources.append(
                        {
                            "resource_id": str(resource_id),
                            "resource_name": resource.name,
                            "message": f"Resource has {conflicts.count()} conflicting allocation(s)",
                            "details": conflict_details,
                        }
                    )

            if conflict_resources:
                return {
                    "has_conflict": True,
                    "conflict_type": "resource_allocation",
                    "message": f"{len(conflict_resources)} resource(s) have conflicts",
                    "details": conflict_resources,
                }

            return {
                "has_conflict": False,
                "conflict_type": None,
                "message": "No resource conflicts detected",
                "details": [],
            }

        except Exception as e:
            logger.error(f"Error checking resource conflicts: {str(e)}")
            return {
                "has_conflict": True,
                "conflict_type": "system_error",
                "message": f"Error checking resource availability: {str(e)}",
                "details": [],
            }

    @classmethod
    def check_service_capacity(
        cls,
        service_id: str,
        start_time: datetime,
        exclude_appointment_id: Optional[str] = None,
    ) -> ConflictResult:
        """
        Check if a service has reached its maximum capacity for the time slot.

        Args:
            service_id: ID of the service
            start_time: Start time of the appointment
            exclude_appointment_id: Optional appointment ID to exclude

        Returns:
            Dict with conflict status and details
        """
        try:
            service = Service.objects.get(id=service_id)

            # If service has no capacity limit, no conflict possible
            if not service.max_concurrent_bookings or service.max_concurrent_bookings <= 0:
                return {
                    "has_conflict": False,
                    "conflict_type": None,
                    "message": "Service has no capacity limit",
                    "details": [],
                }

            # Find appointments for this service at the same time
            query = Q(
                service_id=service_id,
                start_time__lte=start_time,
                end_time__gt=start_time,
                status__in=["scheduled", "confirmed", "in_progress"],
            )

            # Exclude the specified appointment if provided
            if exclude_appointment_id:
                query &= ~Q(id=exclude_appointment_id)

            concurrent_count = Appointment.objects.filter(query).count()

            if concurrent_count >= service.max_concurrent_bookings:
                return {
                    "has_conflict": True,
                    "conflict_type": "service_capacity",
                    "message": f"Service has reached maximum capacity of {service.max_concurrent_bookings}",
                    "details": {
                        "service_name": service.name,
                        "current_bookings": concurrent_count,
                        "max_capacity": service.max_concurrent_bookings,
                    },
                }

            return {
                "has_conflict": False,
                "conflict_type": None,
                "message": f"Service has available capacity ({concurrent_count}/{service.max_concurrent_bookings})",
                "details": {
                    "service_name": service.name,
                    "current_bookings": concurrent_count,
                    "max_capacity": service.max_concurrent_bookings,
                },
            }

        except Exception as e:
            logger.error(f"Error checking service capacity: {str(e)}")
            return {
                "has_conflict": True,
                "conflict_type": "system_error",
                "message": f"Error checking service capacity: {str(e)}",
                "details": [],
            }

    @classmethod
    def check_dependent_service_conflicts(
        cls,
        service_id: str,
        start_time: datetime,
        end_time: datetime,
        shop_id: str,
        customer_id: Optional[str] = None,
    ) -> ConflictResult:
        """
        Check if there are conflicts with dependent services.

        Args:
            service_id: ID of the service
            start_time: Start time of the appointment
            end_time: End time of the appointment
            shop_id: ID of the shop
            customer_id: Optional customer ID

        Returns:
            Dict with conflict status and details
        """
        try:
            # Check for prerequisites that must be completed before this service
            prerequisite_dependencies = ServiceDependency.objects.filter(
                dependent_service_id=service_id, dependency_type="prerequisite"
            )

            if not prerequisite_dependencies.exists() or not customer_id:
                return {
                    "has_conflict": False,
                    "conflict_type": None,
                    "message": "No prerequisite dependencies to check",
                    "details": [],
                }

            missing_prerequisites = []

            for dep in prerequisite_dependencies:
                # Look for completed appointments for this prerequisite service
                completed_prerequisite = Appointment.objects.filter(
                    service_id=dep.service_id,
                    customer_id=customer_id,
                    shop_id=shop_id,
                    status="completed",
                    end_time__lt=start_time,
                ).exists()

                if not completed_prerequisite:
                    service = Service.objects.get(id=dep.service_id)
                    missing_prerequisites.append(
                        {
                            "service_id": str(dep.service_id),
                            "service_name": service.name,
                            "dependency_type": "prerequisite",
                            "message": "Required prerequisite service has not been completed",
                        }
                    )

            if missing_prerequisites:
                return {
                    "has_conflict": True,
                    "conflict_type": "service_dependency",
                    "message": f"Missing {len(missing_prerequisites)} prerequisite service(s)",
                    "details": missing_prerequisites,
                }

            return {
                "has_conflict": False,
                "conflict_type": None,
                "message": "All service dependencies satisfied",
                "details": [],
            }

        except Exception as e:
            logger.error(f"Error checking service dependencies: {str(e)}")
            return {
                "has_conflict": True,
                "conflict_type": "system_error",
                "message": f"Error checking service dependencies: {str(e)}",
                "details": [],
            }

    @classmethod
    def check_all_conflicts(
        cls,
        service_id: str,
        shop_id: str,
        specialist_id: str,
        start_time: datetime,
        end_time: datetime,
        customer_id: Optional[str] = None,
        exclude_appointment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Comprehensive conflict check for all possible booking conflicts.

        Args:
            service_id: ID of the service
            shop_id: ID of the shop
            specialist_id: ID of the specialist
            start_time: Start time of the appointment
            end_time: End time of the appointment
            customer_id: Optional customer ID
            exclude_appointment_id: Optional appointment ID to exclude from conflict checks

        Returns:
            Dict with overall conflict status and detailed results for each check
        """
        try:
            # Get required resources for this service
            service_resources = ServiceResource.objects.filter(service_id=service_id)
            resource_ids = [sr.resource_id for sr in service_resources]

            # Run all conflict checks
            specialist_result = cls.check_specialist_conflict(
                specialist_id, start_time, end_time, exclude_appointment_id
            )

            resource_result = cls.check_resource_conflict(
                shop_id, resource_ids, start_time, end_time, exclude_appointment_id
            )

            capacity_result = cls.check_service_capacity(
                service_id, start_time, exclude_appointment_id
            )

            dependency_result = cls.check_dependent_service_conflicts(
                service_id, start_time, end_time, shop_id, customer_id
            )

            # Determine overall conflict status
            has_conflict = (
                specialist_result["has_conflict"]
                or resource_result["has_conflict"]
                or capacity_result["has_conflict"]
                or dependency_result["has_conflict"]
            )

            # Collect conflict messages
            conflict_messages = []
            if specialist_result["has_conflict"]:
                conflict_messages.append(specialist_result["message"])
            if resource_result["has_conflict"]:
                conflict_messages.append(resource_result["message"])
            if capacity_result["has_conflict"]:
                conflict_messages.append(capacity_result["message"])
            if dependency_result["has_conflict"]:
                conflict_messages.append(dependency_result["message"])

            return {
                "has_conflict": has_conflict,
                "message": (
                    "; ".join(conflict_messages) if has_conflict else "No conflicts detected"
                ),
                "checks": {
                    "specialist": specialist_result,
                    "resources": resource_result,
                    "capacity": capacity_result,
                    "dependencies": dependency_result,
                },
            }

        except Exception as e:
            logger.error(f"Error performing conflict checks: {str(e)}")
            return {
                "has_conflict": True,
                "message": f"Error performing conflict checks: {str(e)}",
                "checks": {},
            }

    # ------------------------------------------------------------------------
    # Private helper methods
    # ------------------------------------------------------------------------

    @staticmethod
    def _is_resource_available(resource_id: str, start_time: datetime, end_time: datetime) -> bool:
        """
        Check if a resource is generally available during a time range based on its
        availability schedule.

        Args:
            resource_id: ID of the resource
            start_time: Start time of the appointment
            end_time: End time of the appointment

        Returns:
            Boolean indicating if the resource is available during this time
        """
        try:
            resource = Resource.objects.get(id=resource_id)

            # If resource has no availability restrictions, it's always available
            if not ResourceAvailability.objects.filter(resource=resource).exists():
                return True

            # Get the day of week for the appointment
            day_of_week = start_time.weekday()

            # Find resource availability for this day
            availability = ResourceAvailability.objects.filter(
                resource=resource, day_of_week=day_of_week, is_available=True
            )

            # If no availability defined for this day, resource is not available
            if not availability.exists():
                return False

            # Check if the appointment time falls within any availability window
            start_time_obj = start_time.time()
            end_time_obj = end_time.time()

            for avail in availability:
                if start_time_obj >= avail.start_time and end_time_obj <= avail.end_time:
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking resource availability: {str(e)}")
            return False
