import logging
import re

from apps.chatapp.models import Conversation, Message
from apps.employeeapp.models import Employee
from apps.rolesapp.services.permission_resolver import PermissionResolver

logger = logging.getLogger("chatapp.services")


class MessageRouter:
    """Service for intelligent routing of messages to appropriate staff members"""

    @staticmethod
    def route_incoming_message(message, shop):
        """
        Determine the most appropriate staff member to handle a customer message.

        This uses a sophisticated algorithm that considers:
        1. Previous conversation history
        2. Staff workload
        3. Message content/intent
        4. Staff expertise
        5. Staff availability
        """
        # Get all potential staff members who can handle customer chats
        eligible_staff = MessageRouter._get_eligible_staff(shop)

        if not eligible_staff:
            # No eligible staff - should not happen but handle gracefully
            logger.warning(f"No eligible staff found for shop {shop.id}")
            return None

        # Get context from the conversation
        conversation = message.conversation

        # First, check if there's a previous staff member who handled this conversation
        previous_staff = MessageRouter._get_previous_staff(conversation)
        if previous_staff and previous_staff in eligible_staff:
            # Check if previous staff is available (not overloaded)
            if not MessageRouter._is_staff_overloaded(previous_staff):
                # Prioritize continuity - same staff handling the conversation
                return previous_staff

        # Score remaining staff based on multiple factors
        scored_staff = []

        for staff in eligible_staff:
            score = 0

            # Workload factor (fewer active chats is better)
            workload_score = MessageRouter._calculate_workload_score(staff)
            score += workload_score * 0.4  # 40% weight for workload

            # Expertise match (if message contains service keywords)
            expertise_score = MessageRouter._calculate_expertise_match(
                message.content, staff
            )
            score += expertise_score * 0.3  # 30% weight for expertise

            # Response time history
            response_score = MessageRouter._calculate_response_time_score(staff)
            score += response_score * 0.2  # 20% weight for response time

            # Role appropriateness
            role_score = MessageRouter._calculate_role_score(message, staff)
            score += role_score * 0.1  # 10% weight for role match

            scored_staff.append({"staff": staff, "score": score})

        # Sort by score descending
        sorted_staff = sorted(scored_staff, key=lambda x: x["score"], reverse=True)

        if not sorted_staff:
            return None

        # Return highest scored staff
        return sorted_staff[0]["staff"]

    @staticmethod
    def _get_eligible_staff(shop):
        """Get all staff members who can handle chat for this shop"""
        employees = Employee.objects.filter(shop=shop, is_active=True)
        eligible_staff = []

        for employee in employees:
            if PermissionResolver.has_permission(employee.user, "chat", "view"):
                eligible_staff.append(employee)

        return eligible_staff

    @staticmethod
    def _get_previous_staff(conversation):
        """Find staff who previously responded in this conversation"""
        previous_message = (
            Message.objects.filter(conversation=conversation, employee__isnull=False)
            .order_by("-created_at")
            .first()
        )

        if previous_message and previous_message.employee:
            return previous_message.employee

        return None

    @staticmethod
    def _is_staff_overloaded(staff, threshold=10):
        """Check if staff has too many active conversations"""
        active_conversations = (
            Conversation.objects.filter(messages__employee=staff, is_active=True)
            .distinct()
            .count()
        )

        return active_conversations >= threshold

    @staticmethod
    def _calculate_workload_score(staff):
        """Calculate score based on staff's current workload (lower is better)"""
        # Count active conversations where staff sent a message
        active_conversations = (
            Conversation.objects.filter(messages__employee=staff, is_active=True)
            .distinct()
            .count()
        )

        # Invert score (fewer conversations = higher score)
        if active_conversations > 20:  # Cap at 20 conversations
            return 0

        return 1 - (active_conversations / 20)

    @staticmethod
    def _calculate_expertise_match(content, staff):
        """Calculate how well staff expertise matches message content"""
        # This could be enhanced with NLP in a production system
        # For now, use simple keyword matching

        # Get services provided by this staff member if they're a specialist
        keywords = []

        try:
            from apps.specialistsapp.models import Specialist

            specialist = Specialist.objects.get(employee=staff)

            # Get service names
            services = specialist.services.all()
            for service in services:
                # Add service name and category name as keywords
                keywords.append(service.name.lower())
                keywords.append(service.category.name.lower())

                # Add keywords from service description
                if service.description:
                    # Extract meaningful words from description
                    words = re.findall(r"\b[a-zA-Z]{4,}\b", service.description.lower())
                    keywords.extend(words)
        except Specialist.DoesNotExist:
            # Not a specialist, use role or position as fallback
            keywords.append(staff.position.lower())

        # Count keyword matches in content
        content_lower = content.lower()
        matches = sum(1 for keyword in keywords if keyword in content_lower)

        # Normalize score (0-1)
        if not keywords:
            return 0.5  # Neutral score if no keywords

        max_possible_matches = min(len(keywords), 5)  # Cap at 5 matches

        return min(1.0, matches / max_possible_matches)

    @staticmethod
    def _calculate_response_time_score(staff):
        """Calculate score based on staff's historical response time"""
        # Get average response time for this staff member

        # This query finds messages pairs (customer -> staff response)
        # and calculates average time difference
        conversations = Conversation.objects.filter(messages__employee=staff).values(
            "id"
        )

        # If no previous conversations, return neutral score
        if not conversations:
            return 0.5

        # Get average response time for each conversation
        response_times = []

        for conv in conversations:
            # Get messages in this conversation
            messages = Message.objects.filter(conversation_id=conv["id"]).order_by(
                "created_at"
            )

            # Find customer-staff message pairs
            customer_msgs = messages.filter(employee__isnull=True)
            staff_msgs = messages.filter(employee=staff)

            for cust_msg in customer_msgs:
                # Find next staff message after this customer message
                next_staff_msg = (
                    staff_msgs.filter(created_at__gt=cust_msg.created_at)
                    .order_by("created_at")
                    .first()
                )

                if next_staff_msg:
                    # Calculate time difference in minutes
                    time_diff = (
                        next_staff_msg.created_at - cust_msg.created_at
                    ).total_seconds() / 60
                    if time_diff < 60:  # Only consider reasonable times (< 1 hour)
                        response_times.append(time_diff)

        # Calculate average response time
        if not response_times:
            return 0.5

        avg_response_time = sum(response_times) / len(response_times)

        # Convert to score (faster = better)
        # Assume 5 minutes is excellent (1.0), 30+ minutes is poor (0.0)
        if avg_response_time <= 5:
            return 1.0
        elif avg_response_time >= 30:
            return 0.0
        else:
            return 1.0 - ((avg_response_time - 5) / 25)

    @staticmethod
    def _calculate_role_score(message, staff):
        """Calculate score based on appropriate role for the message"""
        # Simple intent detection
        content = message.content.lower()

        # This could be enhanced with proper NLP in a production system
        # Here we use simple keyword matching for demonstration

        # Check for booking related queries
        booking_keywords = [
            "book",
            "appointment",
            "schedule",
            "reservation",
            "when",
            "available",
        ]
        if any(keyword in content for keyword in booking_keywords):
            # Reception staff would be good for booking queries
            return 1.0 if "reception" in staff.position.lower() else 0.3

        # Check for technical/service queries
        service_keywords = ["how", "service", "work", "price", "cost", "duration"]
        if any(keyword in content for keyword in service_keywords):
            # Specialists would be good for service queries
            try:
                from apps.specialistsapp.models import Specialist

                is_specialist = Specialist.objects.filter(employee=staff).exists()
                return 1.0 if is_specialist else 0.5
            except Exception:
                return 0.5

        # Check for support queries
        support_keywords = ["help", "problem", "issue", "cancel", "change"]
        if any(keyword in content for keyword in support_keywords):
            # Customer service staff would be good for support
            return 1.0 if "service" in staff.position.lower() else 0.4

        # No specific match detected
        return 0.5  # Neutral score
