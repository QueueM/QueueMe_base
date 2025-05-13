"""
Queue Management Service

A comprehensive service for managing real-time queues including:
1. Walk-in customer queue management
2. Priority management between scheduled appointments and walk-ins
3. Real-time position tracking and updates
4. Queue optimization and rearrangement
5. Wait time estimation
6. Customer notifications
"""

import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from django.core.cache import cache
from django.db import transaction
from django.db.models import Avg, Case, Count, F, IntegerField, Q, QuerySet, Sum, Value, When
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.customersapp.models import Customer
from apps.notificationsapp.services.notification_service import NotificationService
from apps.queueapp.models import QueueEntry, QueueStatus, ServiceQueue
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist

logger = logging.getLogger(__name__)


class QueueEntryType(Enum):
    """Types of queue entries"""

    WALK_IN = "walk_in"
    APPOINTMENT = "appointment"
    VIP = "vip"
    RETURN = "return_visit"


class QueuePriority(Enum):
    """Priority levels for queue entries"""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    VIP = 5


class QueueActionResult:
    """Result of queue operations"""

    def __init__(
        self,
        success: bool,
        message: str,
        entry_id: Optional[str] = None,
        position: Optional[int] = None,
        estimated_wait: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.message = message
        self.entry_id = entry_id
        self.position = position
        self.estimated_wait = estimated_wait
        self.data = data or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "success": self.success,
            "message": self.message,
            "entry_id": self.entry_id,
            "position": self.position,
            "estimated_wait_minutes": self.estimated_wait,
            **self.data,
        }


class QueueManager:
    """
    Service for managing real-time queues with integrated appointment handling.
    """

    # Constants for queue management
    CACHE_PREFIX = "queue:"
    CACHE_TTL = 60 * 15  # 15 minutes
    DEFAULT_PRIORITY_WEIGHTS = {
        QueuePriority.LOW.value: 0.5,
        QueuePriority.NORMAL.value: 1.0,
        QueuePriority.HIGH.value: 1.5,
        QueuePriority.URGENT.value: 2.0,
        QueuePriority.VIP.value: 3.0,
    }

    @classmethod
    def add_to_queue(
        cls,
        shop_id: str,
        service_id: str,
        customer_id: Optional[str] = None,
        specialist_id: Optional[str] = None,
        entry_type: QueueEntryType = QueueEntryType.WALK_IN,
        appointment_id: Optional[str] = None,
        priority: QueuePriority = QueuePriority.NORMAL,
        notes: Optional[str] = None,
    ) -> QueueActionResult:
        """
        Add a customer to the queue.

        Args:
            shop_id: ID of the shop
            service_id: ID of the requested service
            customer_id: Optional ID of the customer
            specialist_id: Optional ID of the requested specialist
            entry_type: Type of queue entry (walk-in, appointment, etc.)
            appointment_id: Optional ID of related appointment
            priority: Priority level
            notes: Optional notes

        Returns:
            QueueActionResult with status and details
        """
        try:
            # Check if service queue exists for this service
            service_queue, created = ServiceQueue.objects.get_or_create(
                shop_id=shop_id,
                service_id=service_id,
                defaults={
                    "status": "active",
                    "current_wait_time": 15,  # Default 15-minute wait
                },
            )

            if not service_queue.status == "active":
                return QueueActionResult(
                    success=False,
                    message=f"Queue is currently {service_queue.status}. Cannot add new entries.",
                    entry_id=None,
                )

            # Check for duplicate entry
            if customer_id:
                existing_entry = QueueEntry.objects.filter(
                    queue=service_queue,
                    customer_id=customer_id,
                    status__in=["waiting", "called", "serving"],
                ).first()

                if existing_entry:
                    return QueueActionResult(
                        success=False,
                        message="Customer is already in the queue",
                        entry_id=str(existing_entry.id),
                        position=cls.get_position(existing_entry.id),
                        estimated_wait=cls.estimate_wait_time(existing_entry.id),
                    )

            # For appointment entries, verify the appointment exists
            if entry_type == QueueEntryType.APPOINTMENT and appointment_id:
                try:
                    appointment = Appointment.objects.get(
                        id=appointment_id, status__in=["scheduled", "confirmed"]
                    )

                    # Update priority based on appointment status
                    if timezone.now() > appointment.start_time:
                        # Appointment is late, give higher priority
                        minutes_late = (timezone.now() - appointment.start_time).seconds // 60
                        if minutes_late > 30:
                            priority = QueuePriority.URGENT
                        elif minutes_late > 15:
                            priority = QueuePriority.HIGH

                except Appointment.DoesNotExist:
                    return QueueActionResult(
                        success=False,
                        message="Invalid appointment ID or appointment not confirmed",
                        entry_id=None,
                    )

            # Create new queue entry
            with transaction.atomic():
                # Get the position
                last_entry = (
                    QueueEntry.objects.filter(queue=service_queue, status__in=["waiting", "called"])
                    .order_by("-position")
                    .first()
                )

                position = 1 if not last_entry else last_entry.position + 1

                # Create the entry
                entry = QueueEntry.objects.create(
                    id=uuid.uuid4(),
                    queue=service_queue,
                    customer_id=customer_id,
                    specialist_id=specialist_id,
                    entry_type=entry_type.value,
                    appointment_id=appointment_id,
                    position=position,
                    priority=priority.value,
                    status="waiting",
                    check_in_time=timezone.now(),
                    notes=notes or "",
                )

                # Update service queue statistics
                cls._update_queue_statistics(service_queue.id)

            # Estimate wait time
            estimated_wait = cls.estimate_wait_time(entry.id)

            # Send notification to customer if available
            if customer_id:
                cls._notify_customer_added(
                    entry_id=str(entry.id),
                    customer_id=customer_id,
                    queue_name=service_queue.service.name,
                    position=position,
                    estimated_wait=estimated_wait,
                )

            return QueueActionResult(
                success=True,
                message="Successfully added to queue",
                entry_id=str(entry.id),
                position=position,
                estimated_wait=estimated_wait,
                data={
                    "queue_id": str(service_queue.id),
                    "entry_type": entry_type.value,
                    "priority": priority.value,
                },
            )

        except Exception as e:
            logger.error(f"Error adding to queue: {str(e)}")
            return QueueActionResult(
                success=False, message=f"Error adding to queue: {str(e)}", entry_id=None
            )

    @classmethod
    def remove_from_queue(cls, entry_id: str, reason: str = "customer_left") -> QueueActionResult:
        """
        Remove an entry from the queue.

        Args:
            entry_id: ID of the queue entry
            reason: Reason for removal

        Returns:
            QueueActionResult with status
        """
        try:
            # Find the entry
            try:
                entry = QueueEntry.objects.get(id=entry_id)
            except QueueEntry.DoesNotExist:
                return QueueActionResult(
                    success=False, message="Queue entry not found", entry_id=None
                )

            # Only allow removal if status is waiting or called
            if entry.status not in ["waiting", "called"]:
                return QueueActionResult(
                    success=False,
                    message=f"Cannot remove entry with status '{entry.status}'",
                    entry_id=entry_id,
                )

            # Update entry status
            with transaction.atomic():
                entry.status = "cancelled"
                entry.end_time = timezone.now()
                entry.notes = f"{entry.notes}\nRemoved: {reason}"
                entry.save()

                # Notify customer if available
                if entry.customer_id:
                    cls._notify_customer_removed(
                        entry_id=entry_id,
                        customer_id=str(entry.customer_id),
                        reason=reason,
                    )

                # Update queue statistics
                cls._update_queue_statistics(entry.queue_id)

                # Reorder remaining entries if needed
                cls._reorder_queue(entry.queue_id)

            return QueueActionResult(
                success=True,
                message="Successfully removed from queue",
                entry_id=entry_id,
            )

        except Exception as e:
            logger.error(f"Error removing from queue: {str(e)}")
            return QueueActionResult(
                success=False,
                message=f"Error removing from queue: {str(e)}",
                entry_id=entry_id,
            )

    @classmethod
    def call_next(cls, queue_id: str, specialist_id: str) -> QueueActionResult:
        """
        Call the next customer in the queue.

        Args:
            queue_id: ID of the service queue
            specialist_id: ID of the specialist calling the next customer

        Returns:
            QueueActionResult with next customer details
        """
        try:
            # Check if specialist has any customers currently being served
            active_entries = QueueEntry.objects.filter(
                queue_id=queue_id,
                specialist_id=specialist_id,
                status__in=["called", "serving"],
            )

            if active_entries.exists():
                # Specialist is already serving someone
                entry = active_entries.first()
                return QueueActionResult(
                    success=False,
                    message="Already serving a customer",
                    entry_id=str(entry.id),
                    data={
                        "active_entry": {
                            "entry_id": str(entry.id),
                            "status": entry.status,
                            "customer_id": (str(entry.customer_id) if entry.customer_id else None),
                            "customer_name": (entry.customer.name if entry.customer else "Unknown"),
                            "start_time": (
                                entry.start_time.isoformat() if entry.start_time else None
                            ),
                        }
                    },
                )

            # Get the next entry in the queue based on priority and position
            with transaction.atomic():
                # Lock the queue to prevent race conditions
                service_queue = ServiceQueue.objects.select_for_update().get(id=queue_id)

                # Find the next entry - first by priority, then by position
                next_entries = QueueEntry.objects.filter(
                    queue_id=queue_id, status="waiting"
                ).order_by("-priority", "position")

                # Filter by specialist preference if any entries have it
                specialist_preferred = next_entries.filter(specialist_id=specialist_id)
                if specialist_preferred.exists():
                    next_entry = specialist_preferred.first()
                elif next_entries.exists():
                    next_entry = next_entries.first()
                else:
                    return QueueActionResult(
                        success=False,
                        message="No customers waiting in queue",
                        entry_id=None,
                    )

                # Update entry status
                next_entry.status = "called"
                next_entry.specialist_id = specialist_id
                next_entry.call_time = timezone.now()
                next_entry.save()

                # Update queue statistics
                cls._update_queue_statistics(queue_id)

            # Notify customer if available
            if next_entry.customer_id:
                cls._notify_customer_called(
                    entry_id=str(next_entry.id),
                    customer_id=str(next_entry.customer_id),
                    specialist_id=specialist_id,
                )

            # Get customer details if available
            customer_data = {}
            if next_entry.customer:
                customer_data = {
                    "customer_id": str(next_entry.customer_id),
                    "customer_name": next_entry.customer.name,
                    "customer_phone": next_entry.customer.phone,
                    "is_regular": next_entry.customer.is_regular_customer,
                }

            # Get appointment details if available
            appointment_data = {}
            if next_entry.appointment_id:
                try:
                    appointment = Appointment.objects.get(id=next_entry.appointment_id)
                    appointment_data = {
                        "appointment_id": str(appointment.id),
                        "scheduled_time": appointment.start_time.isoformat(),
                        "duration": appointment.service.duration,
                    }
                except Appointment.DoesNotExist:
                    pass

            return QueueActionResult(
                success=True,
                message="Successfully called next customer",
                entry_id=str(next_entry.id),
                data={
                    "queue_id": queue_id,
                    "entry_type": next_entry.entry_type,
                    "wait_time_minutes": cls._calculate_wait_time_minutes(next_entry),
                    "position": next_entry.position,
                    "priority": next_entry.priority,
                    "customer": customer_data,
                    "appointment": appointment_data,
                    "service_id": str(service_queue.service_id),
                    "service_name": service_queue.service.name,
                    "call_time": (
                        next_entry.call_time.isoformat() if next_entry.call_time else None
                    ),
                },
            )

        except Exception as e:
            logger.error(f"Error calling next customer: {str(e)}")
            return QueueActionResult(
                success=False,
                message=f"Error calling next customer: {str(e)}",
                entry_id=None,
            )

    @classmethod
    def start_service(cls, entry_id: str) -> QueueActionResult:
        """
        Start serving a customer from the queue.

        Args:
            entry_id: ID of the queue entry

        Returns:
            QueueActionResult with status
        """
        try:
            # Find the entry
            try:
                entry = QueueEntry.objects.get(id=entry_id)
            except QueueEntry.DoesNotExist:
                return QueueActionResult(
                    success=False, message="Queue entry not found", entry_id=None
                )

            # Only allow start if status is called
            if entry.status != "called":
                return QueueActionResult(
                    success=False,
                    message=f"Cannot start service for entry with status '{entry.status}'",
                    entry_id=entry_id,
                )

            # Update entry status
            with transaction.atomic():
                entry.status = "serving"
                entry.start_time = timezone.now()
                entry.save()

                # Update appointment if exists
                if entry.appointment_id:
                    try:
                        appointment = Appointment.objects.get(id=entry.appointment_id)
                        appointment.status = "in_progress"
                        appointment.actual_start_time = entry.start_time
                        appointment.save()
                    except Appointment.DoesNotExist:
                        pass

                # Update queue statistics
                cls._update_queue_statistics(entry.queue_id)

            # Calculate wait time
            wait_time = cls._calculate_wait_time_minutes(entry)

            return QueueActionResult(
                success=True,
                message="Successfully started service",
                entry_id=entry_id,
                data={
                    "queue_id": str(entry.queue_id),
                    "start_time": entry.start_time.isoformat(),
                    "wait_time_minutes": wait_time,
                    "service_id": str(entry.queue.service_id),
                    "specialist_id": (str(entry.specialist_id) if entry.specialist_id else None),
                },
            )

        except Exception as e:
            logger.error(f"Error starting service: {str(e)}")
            return QueueActionResult(
                success=False,
                message=f"Error starting service: {str(e)}",
                entry_id=entry_id,
            )

    @classmethod
    def complete_service(cls, entry_id: str, notes: Optional[str] = None) -> QueueActionResult:
        """
        Complete service for a customer.

        Args:
            entry_id: ID of the queue entry
            notes: Optional completion notes

        Returns:
            QueueActionResult with status
        """
        try:
            # Find the entry
            try:
                entry = QueueEntry.objects.get(id=entry_id)
            except QueueEntry.DoesNotExist:
                return QueueActionResult(
                    success=False, message="Queue entry not found", entry_id=None
                )

            # Only allow completion if status is serving
            if entry.status != "serving":
                return QueueActionResult(
                    success=False,
                    message=f"Cannot complete service for entry with status '{entry.status}'",
                    entry_id=entry_id,
                )

            # Update entry status
            with transaction.atomic():
                entry.status = "completed"
                entry.end_time = timezone.now()
                if notes:
                    entry.notes = f"{entry.notes}\nCompletion: {notes}"
                entry.save()

                # Update appointment if exists
                if entry.appointment_id:
                    try:
                        appointment = Appointment.objects.get(id=entry.appointment_id)
                        appointment.status = "completed"
                        appointment.actual_end_time = entry.end_time
                        appointment.save()
                    except Appointment.DoesNotExist:
                        pass

                # Update queue statistics
                cls._update_queue_statistics(entry.queue_id)

            # Calculate service duration
            service_duration = 0
            if entry.start_time and entry.end_time:
                service_duration = (entry.end_time - entry.start_time).seconds // 60

            return QueueActionResult(
                success=True,
                message="Successfully completed service",
                entry_id=entry_id,
                data={
                    "queue_id": str(entry.queue_id),
                    "end_time": entry.end_time.isoformat(),
                    "service_duration_minutes": service_duration,
                    "specialist_id": (str(entry.specialist_id) if entry.specialist_id else None),
                },
            )

        except Exception as e:
            logger.error(f"Error completing service: {str(e)}")
            return QueueActionResult(
                success=False,
                message=f"Error completing service: {str(e)}",
                entry_id=entry_id,
            )

    @classmethod
    def update_priority(cls, entry_id: str, new_priority: QueuePriority) -> QueueActionResult:
        """
        Update the priority of a queue entry.

        Args:
            entry_id: ID of the queue entry
            new_priority: New priority level

        Returns:
            QueueActionResult with status
        """
        try:
            # Find the entry
            try:
                entry = QueueEntry.objects.get(id=entry_id)
            except QueueEntry.DoesNotExist:
                return QueueActionResult(
                    success=False, message="Queue entry not found", entry_id=None
                )

            # Only allow priority update if status is waiting
            if entry.status != "waiting":
                return QueueActionResult(
                    success=False,
                    message=f"Cannot update priority for entry with status '{entry.status}'",
                    entry_id=entry_id,
                )

            # Update priority
            old_priority = entry.priority
            with transaction.atomic():
                entry.priority = new_priority.value
                entry.save()

                # Note the priority change
                entry.notes = (
                    f"{entry.notes}\nPriority changed: {old_priority} -> {new_priority.value}"
                )
                entry.save(update_fields=["notes"])

                # Update position in queue
                cls._reorder_queue(entry.queue_id)

            # Get updated position
            position = cls.get_position(entry_id)

            return QueueActionResult(
                success=True,
                message="Successfully updated priority",
                entry_id=entry_id,
                position=position,
                estimated_wait=cls.estimate_wait_time(entry_id),
                data={"old_priority": old_priority, "new_priority": new_priority.value},
            )

        except Exception as e:
            logger.error(f"Error updating priority: {str(e)}")
            return QueueActionResult(
                success=False,
                message=f"Error updating priority: {str(e)}",
                entry_id=entry_id,
            )

    @classmethod
    def get_queue_status(cls, queue_id: str) -> Dict[str, Any]:
        """
        Get the current status of a queue.

        Args:
            queue_id: ID of the service queue

        Returns:
            Dict with queue status details
        """
        try:
            # Get queue data from cache first
            cache_key = f"{cls.CACHE_PREFIX}status:{queue_id}"
            cached_status = cache.get(cache_key)

            if cached_status:
                return cached_status

            # Get the queue
            try:
                service_queue = ServiceQueue.objects.get(id=queue_id)
            except ServiceQueue.DoesNotExist:
                return {
                    "success": False,
                    "message": "Queue not found",
                    "queue_id": queue_id,
                }

            # Get active entries in the queue
            waiting_entries = QueueEntry.objects.filter(
                queue_id=queue_id, status="waiting"
            ).order_by("-priority", "position")

            called_entries = QueueEntry.objects.filter(queue_id=queue_id, status="called")

            serving_entries = QueueEntry.objects.filter(queue_id=queue_id, status="serving")

            # Count by entry type
            waiting_by_type = cls._count_by_entry_type(waiting_entries)

            # Collect active specialists
            active_specialists = set()
            for entry in list(called_entries) + list(serving_entries):
                if entry.specialist_id:
                    active_specialists.add(str(entry.specialist_id))

            # Build queue status
            status = {
                "success": True,
                "queue_id": queue_id,
                "service_id": str(service_queue.service_id),
                "service_name": service_queue.service.name,
                "shop_id": str(service_queue.shop_id),
                "status": service_queue.status,
                "current_wait_time": service_queue.current_wait_time,
                "total_waiting": waiting_entries.count(),
                "total_active": called_entries.count() + serving_entries.count(),
                "waiting_by_type": waiting_by_type,
                "active_specialists": len(active_specialists),
                "updated_at": timezone.now().isoformat(),
            }

            # Cache the result
            cache.set(cache_key, status, cls.CACHE_TTL)

            return status

        except Exception as e:
            logger.error(f"Error getting queue status: {str(e)}")
            return {
                "success": False,
                "message": f"Error getting queue status: {str(e)}",
                "queue_id": queue_id,
            }

    @classmethod
    def get_position(cls, entry_id: str) -> Optional[int]:
        """
        Get the current position of an entry in the queue.

        Args:
            entry_id: ID of the queue entry

        Returns:
            Current position in queue or None if not in queue
        """
        try:
            # Find the entry
            try:
                entry = QueueEntry.objects.get(id=entry_id)
            except QueueEntry.DoesNotExist:
                return None

            # Only return position if status is waiting
            if entry.status != "waiting":
                return None

            # For high priority entries, calculate effective position based on priority
            if entry.priority > QueuePriority.NORMAL.value:
                higher_priority_count = QueueEntry.objects.filter(
                    queue_id=entry.queue_id,
                    status="waiting",
                    priority__gt=entry.priority,
                ).count()

                same_priority_ahead = QueueEntry.objects.filter(
                    queue_id=entry.queue_id,
                    status="waiting",
                    priority=entry.priority,
                    position__lt=entry.position,
                ).count()

                return higher_priority_count + same_priority_ahead + 1

            # For normal and low priority, use position field
            return entry.position

        except Exception as e:
            logger.error(f"Error getting position: {str(e)}")
            return None

    @classmethod
    def estimate_wait_time(cls, entry_id: str) -> Optional[int]:
        """
        Estimate wait time for a queue entry in minutes.

        Args:
            entry_id: ID of the queue entry

        Returns:
            Estimated wait time in minutes or None if not applicable
        """
        try:
            # Find the entry
            try:
                entry = QueueEntry.objects.get(id=entry_id)
            except QueueEntry.DoesNotExist:
                return None

            # Only estimate wait time if status is waiting
            if entry.status != "waiting":
                return None

            # Get queue average service time
            service_queue = entry.queue
            avg_service_time = service_queue.current_wait_time or 15  # Default to 15 minutes

            # Get position in queue
            position = cls.get_position(entry_id)
            if position is None:
                return None

            # Base estimate on position and average service time
            base_estimate = position * avg_service_time

            # Apply priority factor
            priority_factor = cls.DEFAULT_PRIORITY_WEIGHTS.get(entry.priority, 1.0)
            priority_adjusted = base_estimate / priority_factor

            # Get number of active specialists
            active_specialists = cls._count_active_specialists(entry.queue_id)
            if active_specialists > 1:
                # Adjust for parallel processing
                specialist_factor = max(1, active_specialists * 0.7)  # Diminishing returns
                priority_adjusted = priority_adjusted / specialist_factor

            return max(5, round(priority_adjusted))  # Minimum 5 minutes wait

        except Exception as e:
            logger.error(f"Error estimating wait time: {str(e)}")
            return None

    @classmethod
    def get_specialist_queue(
        cls, specialist_id: str, shop_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get the current queue status for a specialist.

        Args:
            specialist_id: ID of the specialist
            shop_id: Optional shop ID to filter by

        Returns:
            Dict with specialist queue details
        """
        try:
            # Filter by shop if provided
            queue_filter = {}
            if shop_id:
                queue_filter["queue__shop_id"] = shop_id

            # Get current entry being served
            current_entry = (
                QueueEntry.objects.filter(
                    specialist_id=specialist_id,
                    status__in=["called", "serving"],
                    **queue_filter,
                )
                .order_by("-status")
                .first()
            )  # serving comes before called alphabetically

            # Get next entries in queue
            next_entries = []

            if current_entry:
                # Get entries in the same queue
                queue_entries = QueueEntry.objects.filter(
                    queue_id=current_entry.queue_id, status="waiting"
                ).order_by("-priority", "position")[
                    :5
                ]  # Get top 5

                next_entries = [
                    {
                        "entry_id": str(entry.id),
                        "position": entry.position,
                        "priority": entry.priority,
                        "entry_type": entry.entry_type,
                        "customer_name": (entry.customer.name if entry.customer else "Anonymous"),
                        "check_in_time": entry.check_in_time.isoformat(),
                        "wait_time_minutes": cls._calculate_wait_time_minutes(entry),
                    }
                    for entry in queue_entries
                ]

            # Build specialist queue status
            current_entry_data = None
            if current_entry:
                current_entry_data = {
                    "entry_id": str(current_entry.id),
                    "status": current_entry.status,
                    "queue_id": str(current_entry.queue_id),
                    "service_id": str(current_entry.queue.service_id),
                    "service_name": current_entry.queue.service.name,
                    "customer_id": (
                        str(current_entry.customer_id) if current_entry.customer_id else None
                    ),
                    "customer_name": (
                        current_entry.customer.name if current_entry.customer else "Anonymous"
                    ),
                    "entry_type": current_entry.entry_type,
                    "appointment_id": (
                        str(current_entry.appointment_id) if current_entry.appointment_id else None
                    ),
                    "check_in_time": current_entry.check_in_time.isoformat(),
                    "call_time": (
                        current_entry.call_time.isoformat() if current_entry.call_time else None
                    ),
                    "start_time": (
                        current_entry.start_time.isoformat() if current_entry.start_time else None
                    ),
                    "wait_time_minutes": cls._calculate_wait_time_minutes(current_entry),
                }

            # Get counts from all queues for this specialist
            queue_counts = {}
            if shop_id:
                service_queues = ServiceQueue.objects.filter(shop_id=shop_id)
                for queue in service_queues:
                    waiting_count = QueueEntry.objects.filter(
                        queue_id=queue.id, status="waiting"
                    ).count()

                    if waiting_count > 0:
                        queue_counts[str(queue.id)] = {
                            "service_id": str(queue.service_id),
                            "service_name": queue.service.name,
                            "waiting_count": waiting_count,
                        }

            return {
                "success": True,
                "specialist_id": specialist_id,
                "current_entry": current_entry_data,
                "next_entries": next_entries,
                "queue_counts": queue_counts,
                "updated_at": timezone.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting specialist queue: {str(e)}")
            return {
                "success": False,
                "message": f"Error getting specialist queue: {str(e)}",
                "specialist_id": specialist_id,
            }

    # ------------------------------------------------------------------------
    # Private helper methods
    # ------------------------------------------------------------------------

    @classmethod
    def _update_queue_statistics(cls, queue_id: str) -> None:
        """Update queue statistics based on recent service times."""
        try:
            # Get the queue
            service_queue = ServiceQueue.objects.get(id=queue_id)

            # Get recently completed entries (last 24 hours)
            recent_entries = QueueEntry.objects.filter(
                queue_id=queue_id,
                status="completed",
                end_time__gte=timezone.now() - timedelta(hours=24),
            )

            if recent_entries.exists():
                # Calculate average service time
                total_time = 0
                count = 0

                for entry in recent_entries:
                    if entry.start_time and entry.end_time:
                        service_time = (entry.end_time - entry.start_time).seconds // 60
                        if 5 <= service_time <= 120:  # Reasonable range
                            total_time += service_time
                            count += 1

                if count > 0:
                    avg_time = total_time / count
                    # Update with some smoothing (70% new, 30% old)
                    if service_queue.current_wait_time:
                        service_queue.current_wait_time = round(
                            0.7 * avg_time + 0.3 * service_queue.current_wait_time
                        )
                    else:
                        service_queue.current_wait_time = round(avg_time)

                    service_queue.save(update_fields=["current_wait_time"])

            # Clear cache
            cache_key = f"{cls.CACHE_PREFIX}status:{queue_id}"
            cache.delete(cache_key)

        except Exception as e:
            logger.error(f"Error updating queue statistics: {str(e)}")

    @classmethod
    def _reorder_queue(cls, queue_id: str) -> None:
        """Reorder queue entries based on priority and check-in time."""
        try:
            # Get waiting entries ordered by priority (desc) and check-in time (asc)
            entries = QueueEntry.objects.filter(queue_id=queue_id, status="waiting").order_by(
                "-priority", "check_in_time"
            )

            # Reorder positions
            position = 1
            for entry in entries:
                if entry.position != position:
                    entry.position = position
                    entry.save(update_fields=["position"])
                position += 1

        except Exception as e:
            logger.error(f"Error reordering queue: {str(e)}")

    @staticmethod
    def _count_by_entry_type(entries: QuerySet) -> Dict[str, int]:
        """Count entries by entry type."""
        counts = {}
        for entry_type in QueueEntryType:
            count = entries.filter(entry_type=entry_type.value).count()
            if count > 0:
                counts[entry_type.value] = count
        return counts

    @staticmethod
    def _count_active_specialists(queue_id: str) -> int:
        """Count active specialists serving a queue."""
        # Get unique specialists currently serving or called
        specialist_count = (
            QueueEntry.objects.filter(
                queue_id=queue_id,
                status__in=["called", "serving"],
                specialist_id__isnull=False,
            )
            .values("specialist_id")
            .distinct()
            .count()
        )

        return max(1, specialist_count)  # At least 1

    @staticmethod
    def _calculate_wait_time_minutes(entry: QueueEntry) -> int:
        """Calculate actual wait time in minutes."""
        if entry.status == "waiting":
            # For waiting entries, calculate time since check-in
            return (timezone.now() - entry.check_in_time).seconds // 60
        elif entry.call_time:
            # For called/serving/completed, calculate time from check-in to call
            return (entry.call_time - entry.check_in_time).seconds // 60
        else:
            # Fallback
            return 0

    @classmethod
    def _notify_customer_added(
        cls,
        entry_id: str,
        customer_id: str,
        queue_name: str,
        position: int,
        estimated_wait: Optional[int],
    ) -> None:
        """Send notification to customer when added to queue."""
        try:
            wait_time_text = (
                f"estimated wait time is {estimated_wait} minutes"
                if estimated_wait
                else "wait time will be calculated"
            )

            notification_data = {
                "entry_id": entry_id,
                "queue_name": queue_name,
                "position": position,
                "estimated_wait": estimated_wait,
            }

            NotificationService.send_notification(
                recipient_id=customer_id,
                notification_type="queue_join",
                title=f"You're in line for {queue_name}",
                message=f"You are now position #{position} in the queue. Your {wait_time_text}.",
                data=notification_data,
            )
        except Exception as e:
            logger.error(f"Error sending customer added notification: {str(e)}")

    @classmethod
    def _notify_customer_called(cls, entry_id: str, customer_id: str, specialist_id: str) -> None:
        """Send notification to customer when called from queue."""
        try:
            # Get specialist name if available
            specialist_name = "A specialist"
            try:
                specialist = Specialist.objects.get(id=specialist_id)
                if hasattr(specialist, "employee") and specialist.employee:
                    specialist_name = specialist.employee.name
            except Specialist.DoesNotExist:
                pass

            notification_data = {"entry_id": entry_id, "specialist_id": specialist_id}

            NotificationService.send_notification(
                recipient_id=customer_id,
                notification_type="queue_called",
                title="It's Your Turn!",
                message=f"{specialist_name} is ready to see you now.",
                data=notification_data,
                priority="high",
            )
        except Exception as e:
            logger.error(f"Error sending customer called notification: {str(e)}")

    @classmethod
    def _notify_customer_removed(cls, entry_id: str, customer_id: str, reason: str) -> None:
        """Send notification to customer when removed from queue."""
        try:
            notification_data = {"entry_id": entry_id, "reason": reason}

            # Only notify for certain reasons
            if reason in ["no_show", "rescheduled", "cancelled_by_shop"]:
                title = "Removed from Queue"
                message = "You have been removed from the queue."

                if reason == "no_show":
                    message = (
                        "You were removed from the queue because you didn't respond when called."
                    )
                elif reason == "rescheduled":
                    message = "Your appointment has been rescheduled and you've been removed from the current queue."

                NotificationService.send_notification(
                    recipient_id=customer_id,
                    notification_type="queue_removed",
                    title=title,
                    message=message,
                    data=notification_data,
                )
        except Exception as e:
            logger.error(f"Error sending customer removed notification: {str(e)}")
