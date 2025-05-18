import logging
import random

from django.db import transaction
from django.db.models import Avg, Count, F, Max, Q
from django.utils import timezone

from apps.notificationsapp.services.notification_service import NotificationService
from apps.queueapp.models import Queue, QueueTicket

logger = logging.getLogger(__name__)


class QueueService:
    """
    Core Queue Management Service with advanced business logic
    for managing virtual queues.
    """

    @staticmethod
    def generate_ticket_number(shop_id):
        """Generate unique ticket number with contextual information"""
        prefix = "Q"
        # Get current date in format YYMMDD
        date_str = timezone.now().strftime("%y%m%d")

        # Get last ticket for the day
        last_ticket = (
            QueueTicket.objects.filter(
                queue__shop_id=shop_id, ticket_number__startswith=f"{prefix}-{date_str}"
            )
            .order_by("ticket_number")
            .last()
        )

        if last_ticket:
            # Extract sequence number and increment
            seq_str = last_ticket.ticket_number.split("-")[-1]
            try:
                seq_num = int(seq_str) + 1
            except (ValueError, IndexError):
                # Fallback if parsing fails
                seq_num = random.randint(1, 999)
        else:
            # Start at 1
            seq_num = 1

        # Format with leading zeros
        seq_str = f"{seq_num:03d}"

        return f"{prefix}-{date_str}-{seq_str}"

    @staticmethod
    def estimate_wait_time(queue_id, position):
        """
        Advanced wait time prediction algorithm based on multiple factors:
        - Historical service times
        - Current staff availability
        - Service mix in the queue
        - Time of day patterns
        - Day of week patterns
        """
        try:
            queue = Queue.objects.get(id=queue_id)

            # Get average service time for recently served tickets
            recent_tickets = QueueTicket.objects.filter(
                queue=queue,
                status="served",
                complete_time__isnull=False,
                serve_time__isnull=False,
            ).order_by("-complete_time")[:20]

            if recent_tickets:
                # Calculate average service duration in minutes
                avg_service_time = 0
                count = 0

                for ticket in recent_tickets:
                    if ticket.serve_time and ticket.complete_time:
                        service_duration = (
                            ticket.complete_time - ticket.serve_time
                        ).total_seconds() / 60
                        if 0 < service_duration < 120:  # Ignore outliers
                            avg_service_time += service_duration
                            count += 1

                if count > 0:
                    avg_service_time /= count
                else:
                    avg_service_time = 10  # Default if no valid data
            else:
                avg_service_time = 10  # Default estimate

            # Get number of tickets ahead
            tickets_ahead = QueueTicket.objects.filter(
                queue=queue, position__lt=position, status__in=["waiting", "called"]
            ).count()

            # Calculate base wait time
            estimated_wait = tickets_ahead * avg_service_time

            # Get number of active specialists to factor in parallel processing
            from apps.specialistsapp.models import Specialist

            active_specialists = Specialist.objects.filter(
                employee__shop=queue.shop, employee__is_active=True
            ).count()

            # Adjust for multiple specialists
            if active_specialists > 1:
                # Each specialist can handle customers in parallel
                # But there's diminishing returns (not linear scaling)
                parallelism_factor = 0.7 + (0.3 / active_specialists)  # Between 0.7 and 1.0
                estimated_wait = estimated_wait / (active_specialists * parallelism_factor)

            # Factor in time of day - certain times might be busier
            now = timezone.now()
            hour = now.hour

            # Get historical efficiency for this hour
            hour_efficiency = (
                QueueTicket.objects.filter(
                    queue=queue, status="served", serve_time__hour=hour
                ).aggregate(avg_wait=Avg("actual_wait_time"))["avg_wait"]
                or avg_service_time
            )

            hour_factor = hour_efficiency / avg_service_time
            hour_factor = max(0.8, min(1.2, hour_factor))  # Limit impact to ±20%

            estimated_wait *= hour_factor

            # Factor in day of week patterns
            day_of_week = now.weekday()

            # Get historical efficiency for this day
            day_efficiency = (
                QueueTicket.objects.filter(
                    queue=queue, status="served", join_time__week_day=day_of_week
                ).aggregate(avg_wait=Avg("actual_wait_time"))["avg_wait"]
                or avg_service_time
            )

            day_factor = day_efficiency / avg_service_time
            day_factor = max(0.9, min(1.1, day_factor))  # Limit impact to ±10%

            estimated_wait *= day_factor

            # Check service types in the queue for more accurate prediction
            service_factor = 1.0
            tickets_with_service = QueueTicket.objects.filter(
                queue=queue,
                position__lt=position,
                status="waiting",
                service__isnull=False,
            )

            if tickets_with_service.exists():
                # Get average duration for these specific services
                from apps.serviceapp.models import Service

                service_ids = tickets_with_service.values_list("service_id", flat=True)
                avg_duration = (
                    Service.objects.filter(id__in=service_ids).aggregate(
                        avg_duration=Avg("duration")
                    )["avg_duration"]
                    or 30
                )

                # Compare with our general average
                if avg_duration > 0:
                    service_factor = avg_duration / 30  # Assuming 30 min is baseline
                    service_factor = max(0.8, min(1.2, service_factor))  # Limit impact

                    estimated_wait *= service_factor

            # Add base wait time (5 minutes) for check-in, etc.
            estimated_wait += 5

            # Round to nearest whole minute and ensure reasonable bounds
            estimated_wait = max(1, min(120, round(estimated_wait)))

            return estimated_wait

        except Queue.DoesNotExist:
            return 0  # Return 0 if queue doesn't exist
        except Exception as e:
            logger.error(f"Error estimating wait time: {str(e)}")
            return 15  # Default fallback

    @staticmethod
    @transaction.atomic
    def join_queue(
        queue_id,
        customer_id,
        service_id=None,
        is_appointment=False,
        appointment_id=None,
    ):
        """
        Add customer to queue with advanced logic for handling
        priority cases, optimizing positions, and providing accurate
        wait times.
        """
        try:
            queue = Queue.objects.get(id=queue_id)

            # Check if queue is open
            if queue.status != "open":
                return {"error": "Queue is not currently open for new joins"}

            # Check if customer is already in queue
            existing_ticket = QueueTicket.objects.filter(
                queue=queue, customer_id=customer_id, status__in=["waiting", "called"]
            ).first()

            if existing_ticket:
                return {"error": "You are already in this queue"}

            # Check capacity if limited
            if queue.max_capacity > 0:
                active_tickets = QueueTicket.objects.filter(
                    queue=queue, status__in=["waiting", "called"]
                ).count()

                if active_tickets >= queue.max_capacity:
                    return {"error": "Queue is at maximum capacity. Please try again later."}

            # Get service if provided
            service = None
            if service_id:
                from apps.serviceapp.models import Service

                try:
                    service = Service.objects.get(id=service_id)
                except Service.DoesNotExist:
                    # Continue without service if not found
                    pass

            # Determine position in queue
            if is_appointment:
                # Appointment customers get priority - place them near the front
                # But not at the very front to maintain fairness for those already waiting
                highest_position = (
                    QueueTicket.objects.filter(queue=queue).aggregate(max_position=Max("position"))[
                        "max_position"
                    ]
                    or 0
                )

                # Put them in position 2 if possible, or 1/3 into the queue
                if highest_position <= 3:
                    position = 2 if highest_position >= 2 else highest_position + 1
                else:
                    position = max(2, round(highest_position / 3))

                # Shift other tickets down
                QueueTicket.objects.filter(queue=queue, position__gte=position).update(
                    position=F("position") + 1
                )

            else:
                # Regular customer goes to the end of queue
                highest_position = (
                    QueueTicket.objects.filter(queue=queue).aggregate(max_position=Max("position"))[
                        "max_position"
                    ]
                    or 0
                )
                position = highest_position + 1

            # Generate ticket number
            ticket_number = QueueService.generate_ticket_number(queue.shop.id)

            # Handle specialist assignment if needed
            specialist = None
            if service and service_id:
                # Check if service has any specific specialists
                from apps.specialistsapp.models import SpecialistService

                available_specialists = SpecialistService.objects.filter(
                    service_id=service_id, specialist__employee__is_active=True
                )

                if available_specialists.exists():
                    # Assign specialist with fewest active tickets
                    from django.db.models import Count

                    specialist_counts = (
                        QueueTicket.objects.filter(
                            queue=queue,
                            status__in=["waiting", "called", "serving"],
                            specialist__in=[sp.specialist for sp in available_specialists],
                        )
                        .values("specialist")
                        .annotate(count=Count("specialist"))
                    )

                    # Convert to dict for easier lookup
                    specialist_load = {sc["specialist"]: sc["count"] for sc in specialist_counts}

                    # Find specialist with lowest load
                    min_load = float("inf")
                    for sp in available_specialists:
                        load = specialist_load.get(sp.specialist_id, 0)
                        if load < min_load:
                            min_load = load
                            specialist = sp.specialist

            # Create ticket
            ticket = QueueTicket.objects.create(
                queue=queue,
                ticket_number=ticket_number,
                customer_id=customer_id,
                service=service,
                specialist=specialist,
                position=position,
                status="waiting",
                notes="Appointment customer" if is_appointment else "",
            )

            # Store appointment reference if applicable
            if is_appointment and appointment_id:
                ticket.notes = f"Appointment ID: {appointment_id}"
                ticket.save()

            # Estimate wait time
            estimated_wait = QueueService.estimate_wait_time(queue_id, ticket.position)
            ticket.estimated_wait_time = estimated_wait
            ticket.save()

            # Send notification
            NotificationService.send_notification(
                user_id=customer_id,
                notification_type="queue_join_confirmation",
                data={
                    "ticket_id": str(ticket.id),
                    "ticket_number": ticket.ticket_number,
                    "shop_name": queue.shop.name,
                    "position": ticket.position,
                    "estimated_wait": ticket.estimated_wait_time,
                    "service_name": service.name if service else "",
                },
            )

            return ticket

        except Queue.DoesNotExist:
            return {"error": "Queue not found"}
        except Exception as e:
            logger.error(f"Error joining queue: {str(e)}")
            return {"error": f"An error occurred: {str(e)}"}

    @staticmethod
    @transaction.atomic
    def call_next(queue_id, specialist_id=None):
        """
        Call next customer in queue with advanced logic for handling
        specialist matching and priority cases.
        """
        try:
            queue = Queue.objects.get(id=queue_id)

            # Build query for next customer
            query = Q(queue=queue, status="waiting")

            # Add specialist filter if provided
            if specialist_id:
                # Get tickets assigned to this specialist OR with no specialist assigned
                query &= Q(specialist_id=specialist_id) | Q(specialist_id=None)

            # First try to get a ticket that matches the specialist
            next_ticket = QueueTicket.objects.filter(query).order_by("position").first()

            if not next_ticket:
                return {"error": "No customers waiting in queue"}

            # Assign specialist if provided and not already assigned
            if specialist_id and not next_ticket.specialist_id:
                from apps.specialistsapp.models import Specialist

                try:
                    specialist = Specialist.objects.get(id=specialist_id)
                    next_ticket.specialist = specialist
                except Specialist.DoesNotExist:
                    # Continue without assigning specialist
                    pass

            # Update ticket status
            next_ticket.status = "called"
            next_ticket.called_time = timezone.now()
            next_ticket.save()

            # Send notification
            NotificationService.send_notification(
                user_id=next_ticket.customer.id,
                notification_type="queue_called",
                data={
                    "ticket_id": str(next_ticket.id),
                    "ticket_number": next_ticket.ticket_number,
                    "shop_name": queue.shop.name,
                    "specialist_name": (
                        f"{next_ticket.specialist.employee.first_name} {next_ticket.specialist.employee.last_name}"
                        if next_ticket.specialist
                        else ""
                    ),
                },
                channels=["push", "sms"],  # Prioritize immediate channels
            )

            return next_ticket

        except Queue.DoesNotExist:
            return {"error": "Queue not found"}
        except Exception as e:
            logger.error(f"Error calling next customer: {str(e)}")
            return {"error": f"An error occurred: {str(e)}"}

    @staticmethod
    @transaction.atomic
    def mark_serving(ticket_id, specialist_id=None):
        """Mark customer as being served"""
        try:
            ticket = QueueTicket.objects.get(id=ticket_id)

            # Check if ticket is in called status
            if ticket.status != "called":
                return {"error": 'Ticket must be in "called" status to mark as serving'}

            # Update specialist if provided
            if specialist_id:
                from apps.specialistsapp.models import Specialist

                try:
                    specialist = Specialist.objects.get(id=specialist_id)
                    ticket.specialist = specialist
                except Specialist.DoesNotExist:
                    # Continue without changing specialist
                    pass

            # Update ticket status
            ticket.status = "serving"
            ticket.serve_time = timezone.now()

            # Calculate actual wait time
            wait_time = (ticket.serve_time - ticket.join_time).total_seconds() / 60
            ticket.actual_wait_time = int(wait_time)

            ticket.save()

            return ticket

        except QueueTicket.DoesNotExist:
            return {"error": "Ticket not found"}
        except Exception as e:
            logger.error(f"Error marking ticket as serving: {str(e)}")
            return {"error": f"An error occurred: {str(e)}"}

    @staticmethod
    @transaction.atomic
    def mark_served(ticket_id):
        """Mark customer as served (completed)"""
        try:
            ticket = QueueTicket.objects.get(id=ticket_id)

            # Check if ticket is in serving status
            if ticket.status != "serving":
                return {"error": 'Ticket must be in "serving" status to mark as served'}

            # Update ticket status
            ticket.status = "served"
            ticket.complete_time = timezone.now()
            ticket.save()

            # Update queue - recalculate wait times for remaining tickets
            QueueService.recalculate_wait_times(ticket.queue_id)

            # Send feedback request notification
            NotificationService.send_notification(
                user_id=ticket.customer.id,
                notification_type="service_feedback",
                data={
                    "ticket_id": str(ticket.id),
                    "shop_name": ticket.queue.shop.name,
                    "service_name": ticket.service.name if ticket.service else "",
                    "specialist_name": (
                        f"{ticket.specialist.employee.first_name} {ticket.specialist.employee.last_name}"
                        if ticket.specialist
                        else ""
                    ),
                },
            )

            return ticket

        except QueueTicket.DoesNotExist:
            return {"error": "Ticket not found"}
        except Exception as e:
            logger.error(f"Error marking ticket as served: {str(e)}")
            return {"error": f"An error occurred: {str(e)}"}

    @staticmethod
    @transaction.atomic
    def recalculate_wait_times(queue_id):
        """Recalculate wait times for all waiting tickets in queue"""
        try:
            queue = Queue.objects.get(id=queue_id)

            waiting_tickets = QueueTicket.objects.filter(queue=queue, status="waiting").order_by(
                "position"
            )

            for ticket in waiting_tickets:
                estimated_wait = QueueService.estimate_wait_time(queue_id, ticket.position)
                ticket.estimated_wait_time = estimated_wait
                ticket.save(update_fields=["estimated_wait_time"])

            return True

        except Queue.DoesNotExist:
            logger.error(f"Queue not found for recalculation: {queue_id}")
            return False
        except Exception as e:
            logger.error(f"Error recalculating wait times: {str(e)}")
            return False

    @staticmethod
    @transaction.atomic
    def cancel_ticket(ticket_id):
        """Cancel a queue ticket"""
        try:
            ticket = QueueTicket.objects.get(id=ticket_id)

            # Can only cancel if waiting or called
            if ticket.status not in ["waiting", "called"]:
                return {"error": f"Cannot cancel ticket in {ticket.status} status"}

            # Get position for updating others
            position = ticket.position
            queue_id = ticket.queue_id

            # Update ticket status
            ticket.status = "cancelled"
            ticket.save()

            # Update positions for tickets after this one
            QueueTicket.objects.filter(
                queue_id=queue_id, position__gt=position, status="waiting"
            ).update(position=F("position") - 1)

            # Recalculate wait times
            QueueService.recalculate_wait_times(queue_id)

            # Send notification
            NotificationService.send_notification(
                user_id=ticket.customer.id,
                notification_type="queue_cancelled",
                data={
                    "ticket_id": str(ticket.id),
                    "ticket_number": ticket.ticket_number,
                    "shop_name": ticket.queue.shop.name,
                    "reason": "Cancelled at your request",
                },
            )

            return ticket

        except QueueTicket.DoesNotExist:
            return {"error": "Ticket not found"}
        except Exception as e:
            logger.error(f"Error cancelling ticket: {str(e)}")
            return {"error": f"An error occurred: {str(e)}"}

    @staticmethod
    def get_queue_analytics(queue_id, date_range=7):
        """
        Get detailed analytics for a queue including:
        - Average wait times
        - Service completion rates
        - Peak hours
        - Customer cancellation rates
        - Service distribution
        """
        try:
            queue = Queue.objects.get(id=queue_id)

            # Set date range for analytics
            end_date = timezone.now()
            start_date = end_date - timezone.timedelta(days=date_range)

            # Get tickets in range
            tickets = QueueTicket.objects.filter(
                queue=queue, join_time__gte=start_date, join_time__lte=end_date
            )

            # Calculate total counts
            total_count = tickets.count()
            served_count = tickets.filter(status="served").count()
            cancelled_count = tickets.filter(status="cancelled").count()
            skipped_count = tickets.filter(status="skipped").count()

            # Calculate completion rate
            completion_rate = (served_count / total_count * 100) if total_count > 0 else 0

            # Calculate average wait time
            avg_wait = (
                tickets.filter(status="served").aggregate(avg=Avg("actual_wait_time"))["avg"] or 0
            )

            # Calculate hourly distribution
            hourly_distribution = (
                tickets.annotate(hour=F("join_time__hour"))
                .values("hour")
                .annotate(count=Count("id"))
                .order_by("hour")
            )

            # Calculate day of week distribution
            day_distribution = (
                tickets.annotate(day=F("join_time__week_day"))
                .values("day")
                .annotate(count=Count("id"))
                .order_by("day")
            )

            # Calculate service distribution
            service_distribution = (
                tickets.filter(service__isnull=False)
                .values("service__name")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            return {
                "queue": {
                    "id": str(queue.id),
                    "name": queue.name,
                    "shop_name": queue.shop.name,
                },
                "date_range": {
                    "start": start_date,
                    "end": end_date,
                    "days": date_range,
                },
                "metrics": {
                    "total_tickets": total_count,
                    "served": served_count,
                    "cancelled": cancelled_count,
                    "skipped": skipped_count,
                    "completion_rate": round(completion_rate, 2),
                    "avg_wait_time": round(avg_wait, 2),
                },
                "distributions": {
                    "hourly": list(hourly_distribution),
                    "daily": list(day_distribution),
                    "services": list(service_distribution),
                },
            }

        except Queue.DoesNotExist:
            return {"error": "Queue not found"}
        except Exception as e:
            logger.error(f"Error generating queue analytics: {str(e)}")
            return {"error": f"An error occurred: {str(e)}"}
