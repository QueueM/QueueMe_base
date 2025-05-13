import logging
import re

from apps.serviceapp.models import Service

logger = logging.getLogger("chatapp.services")


class ResponseSuggester:
    """Service for generating intelligent response suggestions for shop employees"""

    # Common intents that can be detected in customer messages
    INTENT_PATTERNS = {
        "availability_question": [
            r"when.*?open",
            r"hours.*?operation",
            r"available.*?time",
            r"appointment.*?available",
            r"book.*?time",
            r"schedule.*?time",
            r"(available|free).*?(slot|time|day)",
        ],
        "booking_status": [
            r"my.*?appointment",
            r"my.*?booking",
            r"appointment.*?status",
            r"booking.*?status",
            r"cancel.*?appointment",
            r"reschedule",
        ],
        "service_question": [
            r"how.*?(long|much|cost)",
            r"price.*?service",
            r"service.*?include",
            r"service.*?detail",
            r"what.*?service",
            r"service.*?price",
        ],
        "greeting": [
            r"^hi",
            r"^hello",
            r"^hey",
            r"^good\s(morning|afternoon|evening)",
            r"^assalamu.*",
            r"^salam",
        ],
        "farewell": [
            r"bye",
            r"goodbye",
            r"see you",
            r"talk.*?later",
            r"thank.*?(you|for)",
            r"thanks",
        ],
        "location_question": [
            r"where.*?(you|located|find)",
            r"address",
            r"direction",
            r"how.*?(get|reach|find)",
        ],
        "specialist_question": [
            r"who.*?(specialist|expert)",
            r"specialist.*?available",
            r"expert.*?available",
            r"best.*?(stylist|specialist|doctor)",
        ],
    }

    @staticmethod
    def suggest_responses(message, conversation):
        """
        Generate intelligent response suggestions based on message content

        This uses:
        1. Intent detection from message
        2. Conversation context
        3. Shop-specific information
        4. Common responses for specific intents
        """
        if not message or not message.content:
            return []

        shop = conversation.shop
        content = message.content.lower()

        # Detect intent
        intent = ResponseSuggester._classify_intent(content)

        # Start with generic responses based on intent
        suggestions = ResponseSuggester._get_basic_responses(intent)

        # Add context-specific suggestions
        if intent == "availability_question":
            # Check for service references
            service_matches = ResponseSuggester._detect_service_references(content, shop.id)
            for service in service_matches:
                # Get next available slots
                pass

                # Note: In a real implementation, you would call AvailabilityService.get_next_available_slots
                # Since we can't import from availability_service, we'll simulate it
                suggestion = f"For our {service.name} service, we have availability tomorrow at 10:00 AM and 2:00 PM. Would you like to book an appointment?"
                suggestions.append(suggestion)

            if not service_matches:
                # Generic availability response with shop hours
                # In reality, you'd fetch actual shop hours
                suggestions.append(
                    "We're open Sunday to Thursday from 9:00 AM to 6:00 PM. Would you like to book an appointment for a specific service?"
                )

        elif intent == "booking_status":
            # Check for existing appointments
            # In reality, you'd fetch actual appointments
            suggestions.append(
                "I can see you have an appointment scheduled for [Date] at [Time]. Is there anything you'd like to know about it?"
            )
            suggestions.append("Would you like to reschedule or cancel your appointment?")

        elif intent == "service_question":
            # Service-specific responses
            service_matches = ResponseSuggester._detect_service_references(content, shop.id)
            for service in service_matches:
                duration = service.duration
                price = service.price
                suggestions.append(
                    f"Our {service.name} service takes approximately {duration} minutes and costs {price} SAR. Would you like to book this service?"
                )

            if not service_matches:
                suggestions.append(
                    "We offer various services. Is there a specific service you're interested in?"
                )

        elif intent == "specialist_question":
            # In reality, you'd fetch actual specialists
            suggestions.append(
                "We have several specialists available. What type of service are you looking for?"
            )
            suggestions.append(
                "Our most experienced specialist is [Name]. Would you like to book an appointment with them?"
            )

        elif intent == "location_question":
            # In reality, you'd fetch actual address
            address = (
                shop.location.address
                if hasattr(shop, "location") and shop.location
                else "our location"
            )
            suggestions.append(
                f"We're located at {address}. You can also find us on the map in our profile."
            )

        # Add shop-specific quick replies
        custom_replies = ResponseSuggester._get_shop_quick_replies(shop.id)
        suggestions.extend(custom_replies)

        # Remove duplicates and limit suggestions
        suggestions = list(dict.fromkeys(suggestions))  # Remove duplicates while preserving order
        return suggestions[:5]  # Limit to 5 suggestions

    @staticmethod
    def _classify_intent(content):
        """Classify the intent of a message using regex patterns"""
        for intent, patterns in ResponseSuggester.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return intent

        # Default intent if no match found
        return "general"

    @staticmethod
    def _get_basic_responses(intent):
        """Get basic response templates for an intent"""
        basic_responses = {
            "greeting": [
                "Hello! How can I help you today?",
                "Hi there! Welcome to our shop. What can I assist you with?",
                "Welcome! How may I assist you today?",
            ],
            "farewell": [
                "Thank you for contacting us. Have a great day!",
                "It was a pleasure helping you. Feel free to reach out if you need anything else.",
                "Thank you for your message. Is there anything else you'd like to know?",
            ],
            "availability_question": [
                "We have several time slots available. When would you like to visit us?",
                "I'd be happy to check our availability. Which day works best for you?",
            ],
            "booking_status": [
                "I can check your booking status. Could you confirm which appointment you're inquiring about?",
                "Let me check that for you. One moment please.",
            ],
            "service_question": [
                "I'd be happy to provide information about our services. Which one are you interested in?",
                "We offer a range of services. Could you specify which one you'd like to know more about?",
            ],
            "location_question": [
                "I can help you with directions. Are you familiar with our area?",
                "I'll be happy to provide our location details. Will you be driving or using public transport?",
            ],
            "specialist_question": [
                "We have several specialists available. What type of service are you looking for?",
                "I can help you find the right specialist. Could you tell me more about what you need?",
            ],
            "general": [
                "Thank you for your message. How can I assist you today?",
                "I'm here to help. Could you provide more details about what you're looking for?",
                "Thank you for reaching out. What can I do for you today?",
            ],
        }

        return basic_responses.get(intent, basic_responses["general"])

    @staticmethod
    def _detect_service_references(content, shop_id):
        """Detect references to specific services in the message"""
        # Get services for this shop
        services = Service.objects.filter(shop_id=shop_id)

        matches = []
        for service in services:
            # Check if service name is mentioned
            if service.name.lower() in content:
                matches.append(service)

            # Check category name as well
            if service.category and service.category.name.lower() in content:
                if service not in matches:
                    matches.append(service)

        return matches

    @staticmethod
    def _get_shop_quick_replies(shop_id):
        """Get shop-specific quick reply templates"""
        # In a real implementation, this would fetch from a database
        # For now, return some generic shop replies
        return [
            "Would you like to book an appointment with us?",
            "Can I help you with anything else?",
            "Is there a specific day or time that works best for you?",
        ]
