# tests/integration/test_api_integration.py
"""
Integration tests for Queue Me API.

This module tests complete business workflows across multiple API endpoints
to ensure that the entire system works correctly end-to-end.
"""


from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.authapp.models import User
from apps.authapp.services.token_service import TokenService
from apps.categoriesapp.models import Category
from apps.companiesapp.models import Company
from apps.employeeapp.models import Employee
from apps.geoapp.models import Location
from apps.queueapp.models import Queue
from apps.rolesapp.models import Permission, Role, UserRole
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop, ShopHours
from apps.specialistsapp.models import Specialist, SpecialistService


class BookingFlowIntegrationTest(TestCase):
    """Test the complete booking flow from availability to completion."""

    def setUp(self):
        """Set up test data."""
        # Create test client
        self.client = APIClient()

        # Create customer user
        self.customer = User.objects.create(
            phone_number="1234567890",
            user_type="customer",
            is_verified=True,
            profile_completed=True,
        )

        # Create location
        self.location = Location.objects.create(
            address="123 Test Street",
            city="Riyadh",
            country="Saudi Arabia",
            latitude=24.7136,
            longitude=46.6753,
        )

        # Create company
        self.company = Company.objects.create(
            name="Test Company",
            contact_phone="9876543210",
            owner=self.customer,  # Using customer as owner for simplicity
            location=self.location,
        )

        # Create shop
        self.shop = Shop.objects.create(
            company=self.company,
            name="Test Shop",
            phone_number="9876543210",
            username="testshop",
            location=self.location,
        )

        # Create shop hours
        for weekday in range(7):
            ShopHours.objects.create(
                shop=self.shop,
                weekday=weekday,
                from_hour="09:00:00",
                to_hour="17:00:00",
                is_closed=(weekday == 5),  # Closed on Friday
            )

        # Create category
        self.category = Category.objects.create(name="Test Category")

        # Create employee
        self.employee_user = User.objects.create(
            phone_number="5556667777",
            user_type="employee",
            is_verified=True,
            profile_completed=True,
        )
        self.employee = Employee.objects.create(
            user=self.employee_user,
            shop=self.shop,
            first_name="Test",
            last_name="Employee",
            position="manager",
        )

        # Create specialist
        self.specialist = Specialist.objects.create(
            employee=self.employee, bio="Test specialist", experience_years=5
        )

        # Create service
        self.service = Service.objects.create(
            shop=self.shop,
            category=self.category,
            name="Test Service",
            price=100.00,
            duration=60,
            slot_granularity=30,
            buffer_before=5,
            buffer_after=5,
            service_location="in_shop",
        )

        # Link specialist to service
        self.specialist_service = SpecialistService.objects.create(
            specialist=self.specialist, service=self.service, is_primary=True
        )

        # Create shop manager role and permissions
        self.manager_role = Role.objects.create(
            name="Shop Manager", role_type="shop_manager", shop=self.shop
        )

        # Add permissions to role
        for resource in ["booking", "service", "specialist", "employee"]:
            for action in ["view", "add", "edit", "delete"]:
                permission, _ = Permission.objects.get_or_create(
                    resource=resource, action=action
                )
                self.manager_role.permissions.add(permission)

        # Assign role to employee
        UserRole.objects.create(user=self.employee_user, role=self.manager_role)

        # Get JWT token for customer
        self.customer_token = TokenService.get_tokens_for_user(self.customer)["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer_token}")

    def test_end_to_end_booking_flow(self):
        """Test the entire booking flow from availability to completion."""
        # 1. Check service availability
        tomorrow = (timezone.now() + timezone.timedelta(days=1)).date()

        availability_response = self.client.get(
            reverse("service-availability", args=[self.service.id]),
            {"date": tomorrow.isoformat()},
        )

        self.assertEqual(availability_response.status_code, 200)

        # Get first available slot
        available_slots = availability_response.json()
        self.assertTrue(len(available_slots) > 0, "No available slots found")

        first_slot = available_slots[0]

        # 2. Create booking
        booking_data = {
            "service_id": str(self.service.id),
            "specialist_id": str(self.specialist.id),
            "date": tomorrow.isoformat(),
            "start_time": first_slot["start"],
        }

        booking_response = self.client.post(
            reverse("bookings-list"), booking_data, format="json"
        )

        self.assertEqual(booking_response.status_code, 201)

        # Extract booking ID
        booking_id = booking_response.json()["id"]

        # 3. Get booking details
        booking_detail_response = self.client.get(
            reverse("bookings-detail", args=[booking_id])
        )

        self.assertEqual(booking_detail_response.status_code, 200)
        self.assertEqual(booking_detail_response.json()["status"], "scheduled")

        # 4. Now login as shop manager to view and manage booking
        manager_token = TokenService.get_tokens_for_user(self.employee_user)["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {manager_token}")

        # 5. Get shop bookings
        shop_bookings_response = self.client.get(
            reverse("shop-bookings-list", args=[self.shop.id])
        )

        self.assertEqual(shop_bookings_response.status_code, 200)
        bookings_data = shop_bookings_response.json()
        self.assertTrue(len(bookings_data["results"]) > 0)

        # 6. Confirm booking
        confirm_response = self.client.post(
            reverse("bookings-confirm", args=[booking_id]), format="json"
        )

        self.assertEqual(confirm_response.status_code, 200)

        # 7. Check booking status is now confirmed
        booking_detail_response = self.client.get(
            reverse("bookings-detail", args=[booking_id])
        )

        self.assertEqual(booking_detail_response.status_code, 200)
        self.assertEqual(booking_detail_response.json()["status"], "confirmed")

        # 8. Switch back to customer to cancel booking
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer_token}")

        # 9. Cancel booking
        cancel_data = {"reason": "Test cancellation"}

        cancel_response = self.client.post(
            reverse("bookings-cancel", args=[booking_id]), cancel_data, format="json"
        )

        self.assertEqual(cancel_response.status_code, 200)

        # 10. Verify booking status is cancelled
        booking_detail_response = self.client.get(
            reverse("bookings-detail", args=[booking_id])
        )

        self.assertEqual(booking_detail_response.status_code, 200)
        self.assertEqual(booking_detail_response.json()["status"], "cancelled")


class QueueIntegrationTest(TestCase):
    """Test the queue management functionality."""

    def setUp(self):
        """Set up test data."""
        # Similar setup as in BookingFlowIntegrationTest
        # Create test client
        self.client = APIClient()

        # Create customer user
        self.customer = User.objects.create(
            phone_number="1234567890",
            user_type="customer",
            is_verified=True,
            profile_completed=True,
        )

        # Create second customer user
        self.customer2 = User.objects.create(
            phone_number="9998887777",
            user_type="customer",
            is_verified=True,
            profile_completed=True,
        )

        # Create location
        self.location = Location.objects.create(
            address="123 Test Street",
            city="Riyadh",
            country="Saudi Arabia",
            latitude=24.7136,
            longitude=46.6753,
        )

        # Create company
        self.company = Company.objects.create(
            name="Test Company",
            contact_phone="9876543210",
            owner=self.customer,
            location=self.location,
        )

        # Create shop
        self.shop = Shop.objects.create(
            company=self.company,
            name="Test Shop",
            phone_number="9876543210",
            username="testshop",
            location=self.location,
        )

        # Create employee
        self.employee_user = User.objects.create(
            phone_number="5556667777",
            user_type="employee",
            is_verified=True,
            profile_completed=True,
        )
        self.employee = Employee.objects.create(
            user=self.employee_user,
            shop=self.shop,
            first_name="Test",
            last_name="Employee",
            position="manager",
        )

        # Create category
        self.category = Category.objects.create(name="Test Category")

        # Create service
        self.service = Service.objects.create(
            shop=self.shop,
            category=self.category,
            name="Test Service",
            price=100.00,
            duration=60,
            slot_granularity=30,
            buffer_before=5,
            buffer_after=5,
            service_location="in_shop",
        )

        # Create queue
        self.queue = Queue.objects.create(
            shop=self.shop, name="Main Queue", status="open", max_capacity=20
        )

        # Get JWT token for customer
        self.customer_token = TokenService.get_tokens_for_user(self.customer)["access"]
        self.customer2_token = TokenService.get_tokens_for_user(self.customer2)[
            "access"
        ]
        self.employee_token = TokenService.get_tokens_for_user(self.employee_user)[
            "access"
        ]

        # Set customer token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer_token}")

    def test_queue_management_flow(self):
        """Test end-to-end queue management flow."""
        # 1. Customer joins queue
        join_data = {"service_id": str(self.service.id)}

        join_response = self.client.post(
            reverse("queues-join", args=[self.queue.id]), join_data, format="json"
        )

        self.assertEqual(join_response.status_code, 201)
        ticket_data = join_response.json()
        ticket_id = ticket_data["id"]

        # 2. Customer checks queue status
        status_response = self.client.get(
            reverse("queue-tickets-detail", args=[ticket_id])
        )

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "waiting")

        # 3. Second customer joins queue
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer2_token}")

        join_response2 = self.client.post(
            reverse("queues-join", args=[self.queue.id]), join_data, format="json"
        )

        self.assertEqual(join_response2.status_code, 201)
        ticket2_id = join_response2.json()["id"]

        # 4. Staff views queue
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.employee_token}")

        queue_response = self.client.get(reverse("queues-detail", args=[self.queue.id]))

        self.assertEqual(queue_response.status_code, 200)
        queue_data = queue_response.json()
        self.assertEqual(len(queue_data["waiting_tickets"]), 2)

        # 5. Staff calls next customer
        call_response = self.client.post(
            reverse("queues-call-next", args=[self.queue.id]), format="json"
        )

        self.assertEqual(call_response.status_code, 200)

        # 6. Check first ticket status
        ticket_status_response = self.client.get(
            reverse("queue-tickets-detail", args=[ticket_id])
        )

        self.assertEqual(ticket_status_response.status_code, 200)
        self.assertEqual(ticket_status_response.json()["status"], "called")

        # 7. Staff marks customer as being served
        serve_response = self.client.post(
            reverse("queue-tickets-serve", args=[ticket_id]), format="json"
        )

        self.assertEqual(serve_response.status_code, 200)

        # 8. Check ticket status again
        ticket_status_response = self.client.get(
            reverse("queue-tickets-detail", args=[ticket_id])
        )

        self.assertEqual(ticket_status_response.status_code, 200)
        self.assertEqual(ticket_status_response.json()["status"], "serving")

        # 9. Staff completes service
        complete_response = self.client.post(
            reverse("queue-tickets-complete", args=[ticket_id]), format="json"
        )

        self.assertEqual(complete_response.status_code, 200)

        # 10. Second customer cancels their ticket
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer2_token}")

        cancel_response = self.client.post(
            reverse("queue-tickets-cancel", args=[ticket2_id]), format="json"
        )

        self.assertEqual(cancel_response.status_code, 200)

        # 11. Staff checks updated queue
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.employee_token}")

        updated_queue_response = self.client.get(
            reverse("queues-detail", args=[self.queue.id])
        )

        self.assertEqual(updated_queue_response.status_code, 200)
        updated_queue_data = updated_queue_response.json()
        self.assertEqual(len(updated_queue_data["waiting_tickets"]), 0)


class ChatIntegrationTest(TestCase):
    """Test the chat functionality."""

    def setUp(self):
        """Set up test data."""
        # Create test client
        self.client = APIClient()

        # Create customer user
        self.customer = User.objects.create(
            phone_number="1234567890",
            user_type="customer",
            is_verified=True,
            profile_completed=True,
        )

        # Create location
        self.location = Location.objects.create(
            address="123 Test Street",
            city="Riyadh",
            country="Saudi Arabia",
            latitude=24.7136,
            longitude=46.6753,
        )

        # Create company
        self.company = Company.objects.create(
            name="Test Company",
            contact_phone="9876543210",
            owner=self.customer,
            location=self.location,
        )

        # Create shop
        self.shop = Shop.objects.create(
            company=self.company,
            name="Test Shop",
            phone_number="9876543210",
            username="testshop",
            location=self.location,
        )

        # Create employee user
        self.employee_user = User.objects.create(
            phone_number="5556667777",
            user_type="employee",
            is_verified=True,
            profile_completed=True,
        )

        # Create employee
        self.employee = Employee.objects.create(
            user=self.employee_user,
            shop=self.shop,
            first_name="Test",
            last_name="Employee",
            position="customer_service",
        )

        # Create chat permission
        self.chat_view_permission, _ = Permission.objects.get_or_create(
            resource="chat", action="view"
        )

        # Create employee role with chat permission
        self.employee_role = Role.objects.create(
            name="Customer Service", role_type="shop_employee", shop=self.shop
        )
        self.employee_role.permissions.add(self.chat_view_permission)

        # Assign role to employee
        UserRole.objects.create(user=self.employee_user, role=self.employee_role)

        # Get JWT tokens
        self.customer_token = TokenService.get_tokens_for_user(self.customer)["access"]
        self.employee_token = TokenService.get_tokens_for_user(self.employee_user)[
            "access"
        ]

        # Set customer token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer_token}")

    def test_chat_functionality(self):
        """Test end-to-end chat functionality."""
        # 1. Customer starts a conversation with shop
        conversation_data = {"shop_id": str(self.shop.id)}

        conversation_response = self.client.post(
            reverse("conversations-list"), conversation_data, format="json"
        )

        self.assertEqual(conversation_response.status_code, 201)
        conversation_id = conversation_response.json()["id"]

        # 2. Customer sends a message
        message_data = {
            "conversation_id": conversation_id,
            "content": "Hello, do you offer haircuts?",
            "message_type": "text",
        }

        message_response = self.client.post(
            reverse("messages-list"), message_data, format="json"
        )

        self.assertEqual(message_response.status_code, 201)

        # 3. Customer views conversation
        conversation_detail_response = self.client.get(
            reverse("conversations-detail", args=[conversation_id])
        )

        self.assertEqual(conversation_detail_response.status_code, 200)
        conversation_detail = conversation_detail_response.json()
        self.assertEqual(len(conversation_detail["messages"]), 1)

        # 4. Employee logs in and views conversations
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.employee_token}")

        shop_conversations_response = self.client.get(
            reverse("shop-conversations-list", args=[self.shop.id])
        )

        self.assertEqual(shop_conversations_response.status_code, 200)
        shop_conversations = shop_conversations_response.json()
        self.assertTrue(len(shop_conversations["results"]) > 0)

        # 5. Employee views specific conversation
        employee_conversation_response = self.client.get(
            reverse("conversations-detail", args=[conversation_id])
        )

        self.assertEqual(employee_conversation_response.status_code, 200)

        # 6. Employee replies to customer
        reply_data = {
            "conversation_id": conversation_id,
            "content": "Yes, we offer various haircut styles. Would you like to book an appointment?",
            "message_type": "text",
        }

        reply_response = self.client.post(
            reverse("messages-list"), reply_data, format="json"
        )

        self.assertEqual(reply_response.status_code, 201)

        # 7. Employee marks messages as read
        read_response = self.client.post(
            reverse("conversations-mark-read", args=[conversation_id]), format="json"
        )

        self.assertEqual(read_response.status_code, 200)

        # 8. Customer logs back in and views conversation
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer_token}")

        updated_conversation_response = self.client.get(
            reverse("conversations-detail", args=[conversation_id])
        )

        self.assertEqual(updated_conversation_response.status_code, 200)
        updated_conversation = updated_conversation_response.json()
        self.assertEqual(len(updated_conversation["messages"]), 2)
