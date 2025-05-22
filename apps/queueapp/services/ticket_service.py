import logging

from django.db import transaction
from django.db.models import F, Max

from apps.notificationsapp.services.notification_service import NotificationService
from apps.queueapp.models import QueueTicket

logger = logging.getLogger(__name__)


class TicketService:
    """
    Specialized service for ticket manipulation and advanced operations
    beyond basic queue management.
    """

    @staticmethod
    @transaction.atomic
    def reorder_ticket(ticket_id, new_position):
        """
        Reorder a ticket in the queue (manual position change).
        This is an administrative function for special cases.
        """
        try:
            ticket = QueueTicket.objects.get(id=ticket_id)

            # Can only reorder waiting tickets
            if ticket.status != "waiting":
                return {"error": "Only waiting tickets can be reordered"}

            current_position = ticket.position
            queue_id = ticket.queue_id

            # Verify new position is valid
            max_position = (
                QueueTicket.objects.filter(
                    queue_id=queue_id, status="waiting"
                ).aggregate(max_position=Max("position"))["max_position"]
                or 0
            )

            if new_position < 1 or new_position > max_position:
                return {"error": f"Position must be between 1 and {max_position}"}

            # No change needed if same position
            if new_position == current_position:
                return ticket

            # Adjust positions of other tickets
            if new_position < current_position:
                # Moving forward in line (e.g., from position 5 to 3)
                QueueTicket.objects.filter(
                    queue_id=queue_id,
                    status="waiting",
                    position__gte=new_position,
                    position__lt=current_position,
                ).update(position=F("position") + 1)
            else:
                # Moving backward in line (e.g., from position 3 to 5)
                QueueTicket.objects.filter(
                    queue_id=queue_id,
                    status="waiting",
                    position__gt=current_position,
                    position__lte=new_position,
                ).update(position=F("position") - 1)

            # Update the ticket's position
            ticket.position = new_position
            ticket.save()

            # Recalculate wait times (if reordering affects other tickets)
            from apps.queueapp.services.queue_service import QueueService

            QueueService.recalculate_wait_times(queue_id)

            # Notify the customer if they were moved significantly forward
            if current_position - new_position >= 3:
                NotificationService.send_notification(
                    user_id=ticket.customer.id,
                    notification_type="queue_status_update",
                    data={
                        "ticket_id": str(ticket.id),
                        "ticket_number": ticket.ticket_number,
                        "shop_name": ticket.queue.shop.name,
                        "old_position": current_position,
                        "new_position": new_position,
                        "message": "Your position in the queue has improved",
                    },
                )

            return ticket

        except QueueTicket.DoesNotExist:
            return {"error": "Ticket not found"}
        except Exception as e:
            logger.error(f"Error reordering ticket: {str(e)}")
            return {"error": f"An error occurred: {str(e)}"}

    @staticmethod
    @transaction.atomic
    def skip_ticket(ticket_id, reason=None):
        """
        Skip a customer in the queue (mark as skipped and call next).
        Used when a customer is called but doesn't show up.
        """
        try:
            ticket = QueueTicket.objects.get(id=ticket_id)

            # Can only skip tickets in called status
            if ticket.status != "called":
                return {"error": "Only called tickets can be skipped"}

            # Get position and queue for updating
            position = ticket.position
            queue_id = ticket.queue_id

            # Update ticket status
            ticket.status = "skipped"
            if reason:
                ticket.notes = f"{ticket.notes}\nSkipped: {reason}".strip()
            ticket.save()

            # Update positions for tickets after this one
            QueueTicket.objects.filter(
                queue_id=queue_id, position__gt=position, status="waiting"
            ).update(position=F("position") - 1)

            # Recalculate wait times
            from apps.queueapp.services.queue_service import QueueService

            QueueService.recalculate_wait_times(queue_id)

            # Send notification
            NotificationService.send_notification(
                user_id=ticket.customer.id,
                notification_type="queue_cancelled",
                data={
                    "ticket_id": str(ticket.id),
                    "ticket_number": ticket.ticket_number,
                    "shop_name": ticket.queue.shop.name,
                    "reason": reason or "You did not appear when called",
                },
            )

            return ticket

        except QueueTicket.DoesNotExist:
            return {"error": "Ticket not found"}
        except Exception as e:
            logger.error(f"Error skipping ticket: {str(e)}")
            return {"error": f"An error occurred: {str(e)}"}

    @staticmethod
    def get_customer_queue_history(customer_id, limit=10):
        """
        Get a customer's queue history across all shops.
        Useful for personalization and recommendation.
        """
        try:
            tickets = (
                QueueTicket.objects.filter(customer_id=customer_id)
                .select_related("queue", "queue__shop", "service", "specialist")
                .order_by("-join_time")[:limit]
            )

            result = []
            for ticket in tickets:
                # Calculate service time if available
                service_time = None
                if ticket.serve_time and ticket.complete_time:
                    service_time = (
                        ticket.complete_time - ticket.serve_time
                    ).total_seconds() / 60

                result.append(
                    {
                        "id": str(ticket.id),
                        "ticket_number": ticket.ticket_number,
                        "shop_name": ticket.queue.shop.name,
                        "service_name": ticket.service.name if ticket.service else None,
                        "specialist_name": (
                            f"{ticket.specialist.employee.first_name} {ticket.specialist.employee.last_name}"
                            if ticket.specialist
                            else None
                        ),
                        "status": ticket.status,
                        "join_time": ticket.join_time,
                        "wait_time": ticket.actual_wait_time,
                        "service_time": round(service_time) if service_time else None,
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Error getting customer queue history: {str(e)}")
            return []

    @staticmethod
    def assign_specialist(ticket_id, specialist_id):
        """
        Assign a specialist to a ticket.
        Used when automatic assignment needs to be overridden.
        """
        try:
            ticket = QueueTicket.objects.get(id=ticket_id)

            # Can only assign specialist to waiting or called tickets
            if ticket.status not in ["waiting", "called"]:
                return {
                    "error": f"Cannot assign specialist to ticket in {ticket.status} status"
                }

            # Get specialist
            from apps.specialistsapp.models import Specialist

            try:
                specialist = Specialist.objects.get(id=specialist_id)

                # Verify specialist belongs to the same shop
                if specialist.employee.shop_id != ticket.queue.shop_id:
                    return {
                        "error": "Specialist does not belong to the same shop as the queue"
                    }

                # If ticket has a service, verify specialist can provide it
                if ticket.service_id:
                    from apps.specialistsapp.models import SpecialistService

                    can_provide = SpecialistService.objects.filter(
                        specialist=specialist, service=ticket.service
                    ).exists()

                    if not can_provide:
                        return {
                            "error": "Specialist cannot provide the requested service"
                        }

                # Assign specialist
                ticket.specialist = specialist
                ticket.save()

                return ticket

            except Specialist.DoesNotExist:
                return {"error": "Specialist not found"}

        except QueueTicket.DoesNotExist:
            return {"error": "Ticket not found"}
        except Exception as e:
            logger.error(f"Error assigning specialist: {str(e)}")
            return {"error": f"An error occurred: {str(e)}"}

    @staticmethod
    def get_active_tickets_by_shop(shop_id):
        """
        Get all active tickets for a shop across all queues.
        Used for shop-wide monitoring.
        """
        try:
            active_tickets = (
                QueueTicket.objects.filter(
                    queue__shop_id=shop_id, status__in=["waiting", "called", "serving"]
                )
                .select_related("queue", "customer", "service", "specialist")
                .order_by("status", "position")
            )

            result = {"waiting": [], "called": [], "serving": []}

            for ticket in active_tickets:
                ticket_data = {
                    "id": str(ticket.id),
                    "ticket_number": ticket.ticket_number,
                    "queue_name": ticket.queue.name,
                    "customer_phone": ticket.customer.phone_number,
                    "position": ticket.position if ticket.status == "waiting" else None,
                    "service_name": ticket.service.name if ticket.service else None,
                    "specialist_name": (
                        f"{ticket.specialist.employee.first_name} {ticket.specialist.employee.last_name}"
                        if ticket.specialist
                        else None
                    ),
                    "estimated_wait_time": (
                        ticket.estimated_wait_time
                        if ticket.status == "waiting"
                        else None
                    ),
                    "join_time": ticket.join_time,
                    "called_time": ticket.called_time,
                    "serve_time": ticket.serve_time,
                }

                result[ticket.status].append(ticket_data)

            # Add counts
            result["counts"] = {
                "waiting": len(result["waiting"]),
                "called": len(result["called"]),
                "serving": len(result["serving"]),
                "total": len(active_tickets),
            }

            return result

        except Exception as e:
            logger.error(f"Error getting active tickets by shop: {str(e)}")
            return {
                "error": f"An error occurred: {str(e)}",
                "waiting": [],
                "called": [],
                "serving": [],
                "counts": {"waiting": 0, "called": 0, "serving": 0, "total": 0},
            }

    @staticmethod
    def update_ticket_notes(ticket_id, notes):
        """
        Update notes on a ticket.
        Used for tracking special requests or issues.
        """
        try:
            ticket = QueueTicket.objects.get(id=ticket_id)

            # Update notes
            ticket.notes = notes
            ticket.save(update_fields=["notes"])

            return ticket

        except QueueTicket.DoesNotExist:
            return {"error": "Ticket not found"}
        except Exception as e:
            logger.error(f"Error updating ticket notes: {str(e)}")
            return {"error": f"An error occurred: {str(e)}"}
