from django.db import transaction
from django.db.models import Count, Q

from ..constants import (
    TICKET_STATUS_CHOICES,
    TICKET_STATUS_IN_PROGRESS,
    TICKET_STATUS_OPEN,
    TICKET_STATUS_WAITING,
)
from ..models import SupportMessage, SupportTicket
from .admin_service import AdminService


class SupportService:
    """
    Service for managing support tickets and customer service.
    """

    @staticmethod
    @transaction.atomic
    def create_ticket(
        subject,
        description,
        created_by,
        category,
        priority="medium",
        shop=None,
        attachments=None,
    ):
        """
        Create a new support ticket.

        Args:
            subject: Ticket subject
            description: Ticket description
            created_by: User creating the ticket
            category: Ticket category
            priority: Ticket priority (default: medium)
            shop: Related shop (optional)
            attachments: Ticket attachments (optional)

        Returns:
            SupportTicket: The created ticket
        """
        # Create the ticket
        ticket = SupportTicket.objects.create(
            subject=subject,
            description=description,
            created_by=created_by,
            category=category,
            priority=priority,
            shop=shop,
            attachments=attachments or [],
        )

        # Create an initial message from the description
        SupportMessage.objects.create(
            ticket=ticket, sender=created_by, message=description, is_from_admin=False
        )

        # Create a notification for admins
        AdminService.create_notification(
            title=f"New support ticket: {ticket.reference_number}",
            message=f"A new support ticket has been created: {subject}",
            level="info",
            data={
                "ticket_id": str(ticket.id),
                "reference_number": ticket.reference_number,
                "category": category,
                "priority": priority,
            },
        )

        return ticket

    @staticmethod
    @transaction.atomic
    def assign_ticket(ticket, admin, assigned_by):
        """
        Assign a ticket to an admin.

        Args:
            ticket: The ticket to assign
            admin: The admin user to assign to
            assigned_by: The user doing the assignment

        Returns:
            SupportTicket: The updated ticket
        """
        # Update ticket
        old_admin = ticket.assigned_to
        ticket.assigned_to = admin

        # If the ticket is open, mark it as in progress
        if ticket.status == TICKET_STATUS_OPEN:
            ticket.status = TICKET_STATUS_IN_PROGRESS

        ticket.save()

        # Log the assignment as an internal note
        message = f"Ticket assigned to {admin.phone_number}"
        if old_admin:
            message += f" (previously assigned to {old_admin.phone_number})"

        SupportMessage.objects.create(
            ticket=ticket,
            sender=assigned_by,
            message=message,
            is_from_admin=True,
            is_internal_note=True,
        )

        # Log the action in audit log
        AdminService.log_audit(
            assigned_by,
            "assign",
            "SupportTicket",
            str(ticket.id),
            {
                "ticket_reference": ticket.reference_number,
                "assigned_to": str(admin.id),
                "old_assignee": str(old_admin.id) if old_admin else None,
            },
        )

        return ticket

    @staticmethod
    @transaction.atomic
    def update_ticket_status(ticket, new_status, updated_by):
        """
        Update a ticket's status.

        Args:
            ticket: The ticket to update
            new_status: The new status
            updated_by: The user updating the status

        Returns:
            SupportTicket: The updated ticket
        """
        if new_status not in dict(TICKET_STATUS_CHOICES).keys():
            raise ValueError(f"Invalid status: {new_status}")

        old_status = ticket.status
        ticket.status = new_status
        ticket.save()

        # Log the status change as an internal note
        status_display = dict(TICKET_STATUS_CHOICES)[new_status]
        old_status_display = dict(TICKET_STATUS_CHOICES)[old_status]

        message = f"Ticket status changed from {old_status_display} to {status_display}"
        SupportMessage.objects.create(
            ticket=ticket,
            sender=updated_by,
            message=message,
            is_from_admin=True,
            is_internal_note=True,
        )

        # Log the action in audit log
        AdminService.log_audit(
            updated_by,
            "status_update",
            "SupportTicket",
            str(ticket.id),
            {
                "ticket_reference": ticket.reference_number,
                "old_status": old_status,
                "new_status": new_status,
            },
        )

        return ticket

    @staticmethod
    def update_ticket_on_new_message(ticket_id, admin_user):
        """
        Update ticket status when a new message is added by an admin.

        Args:
            ticket_id: The ticket ID
            admin_user: The admin user adding the message

        Returns:
            SupportTicket: The updated ticket
        """
        ticket = SupportTicket.objects.get(id=ticket_id)

        # If ticket was waiting for admin response, update to in progress
        if ticket.status == TICKET_STATUS_WAITING:
            return SupportService.update_ticket_status(
                ticket, TICKET_STATUS_IN_PROGRESS, admin_user
            )

        return ticket

    @staticmethod
    def get_ticket_stats():
        """
        Get support ticket statistics.

        Returns:
            dict: Ticket statistics
        """
        # Get total counts by status
        status_counts = SupportTicket.objects.values("status").annotate(count=Count("id"))

        # Convert to dictionary for easier access
        status_dict = {item["status"]: item["count"] for item in status_counts}

        # Get counts by category
        category_counts = SupportTicket.objects.values("category").annotate(count=Count("id"))

        # Get counts by priority
        priority_counts = SupportTicket.objects.values("priority").annotate(count=Count("id"))

        # Get unassigned tickets count
        unassigned_count = SupportTicket.objects.filter(assigned_to__isnull=True).count()

        # Get average response time (time to first admin response)
        # This would require more complex querying in a real implementation

        # Calculate average resolution time for resolved tickets
        # This would also be more complex in reality

        return {
            "total_tickets": SupportTicket.objects.count(),
            "status_breakdown": dict(status_dict),
            "category_breakdown": {item["category"]: item["count"] for item in category_counts},
            "priority_breakdown": {item["priority"]: item["count"] for item in priority_counts},
            "unassigned_tickets": unassigned_count,
            # Additional metrics would be added here
        }

    @staticmethod
    def search_tickets(query, status=None, category=None, priority=None, assigned_to=None):
        """
        Search for tickets based on criteria.

        Args:
            query: Search query
            status: Filter by status (optional)
            category: Filter by category (optional)
            priority: Filter by priority (optional)
            assigned_to: Filter by assigned admin (optional)

        Returns:
            QuerySet: Filtered tickets
        """
        tickets = SupportTicket.objects.all()

        # Apply filters
        if status:
            tickets = tickets.filter(status=status)

        if category:
            tickets = tickets.filter(category=category)

        if priority:
            tickets = tickets.filter(priority=priority)

        if assigned_to:
            tickets = tickets.filter(assigned_to=assigned_to)

        # Apply search query
        if query:
            tickets = tickets.filter(
                Q(reference_number__icontains=query)
                | Q(subject__icontains=query)
                | Q(description__icontains=query)
                | Q(created_by__phone_number__icontains=query)
            )

        return tickets.order_by("-created_at")
