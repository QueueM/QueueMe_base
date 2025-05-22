from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.authapp.models import User
from apps.chatapp.models import Conversation, Message, TypingStatus
from apps.companiesapp.models import Company
from apps.employeeapp.models import Employee
from apps.rolesapp.models import Permission, Role, UserRole
from apps.shopapp.models import Shop


class ChatAPITest(TestCase):
    """Test cases for Chat API endpoints"""

    def setUp(self):
        """Set up test data"""
        # Create users
        self.customer = User.objects.create(
            phone_number="1234567890", user_type="customer"
        )

        self.shop_user = User.objects.create(
            phone_number="0987654321", user_type="employee"
        )

        # Create company
        self.company = Company.objects.create(
            name="Test Company", contact_phone="1122334455", owner=self.shop_user
        )

        # Create shop
        self.shop = Shop.objects.create(
            name="Test Shop",
            company=self.company,
            phone_number="1122334455",
            username="testshop",
        )

        # Create employee
        self.employee = Employee.objects.create(
            user=self.shop_user,
            shop=self.shop,
            first_name="Test",
            last_name="Employee",
            position="Manager",
        )

        # Create chat permission
        self.chat_permission = Permission.objects.create(resource="chat", action="view")

        # Create manager role
        self.manager_role = Role.objects.create(
            name="Shop Manager", role_type="shop_manager", shop=self.shop
        )
        self.manager_role.permissions.add(self.chat_permission)

        # Assign role to shop user
        UserRole.objects.create(user=self.shop_user, role=self.manager_role)

        # Create conversation
        self.conversation = Conversation.objects.create(
            customer=self.customer, shop=self.shop
        )

        # Create some messages
        self.customer_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.customer,
            content="Hello, I'd like to book an appointment",
        )

        self.employee_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.shop_user,
            employee=self.employee,
            content="Sure, I can help you with that",
        )

        # Set up API client
        self.client = APIClient()

    def test_list_conversations_as_customer(self):
        """Test listing conversations as a customer"""
        # Authenticate as customer
        self.client.force_authenticate(user=self.customer)

        # Get conversations
        url = reverse("conversation-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.conversation.id))

    def test_list_conversations_as_employee(self):
        """Test listing conversations as an employee"""
        # Authenticate as shop user
        self.client.force_authenticate(user=self.shop_user)

        # Get conversations
        url = reverse("conversation-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.conversation.id))

    def test_create_conversation(self):
        """Test creating a conversation"""
        # Create another customer
        customer2 = User.objects.create(phone_number="5556667777", user_type="customer")

        # Authenticate as the new customer
        self.client.force_authenticate(user=customer2)

        # Create a conversation
        url = reverse("conversation-list")
        data = {"shop": str(self.shop.id)}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["customer"], str(customer2.id))
        self.assertEqual(response.data["shop"], str(self.shop.id))

        # Verify in database
        conversation_exists = Conversation.objects.filter(
            customer=customer2, shop=self.shop
        ).exists()
        self.assertTrue(conversation_exists)

    def test_get_conversation_messages(self):
        """Test getting messages for a conversation"""
        # Authenticate as customer
        self.client.force_authenticate(user=self.customer)

        # Get messages
        url = reverse("conversation-messages", args=[self.conversation.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["count"], 2)

        # Messages should be in chronological order (oldest first)
        self.assertEqual(
            response.data["results"][0]["id"], str(self.customer_message.id)
        )
        self.assertEqual(
            response.data["results"][1]["id"], str(self.employee_message.id)
        )

    def test_send_message(self):
        """Test sending a message"""
        # Authenticate as customer
        self.client.force_authenticate(user=self.customer)

        # Send a message
        url = reverse("conversation-send-message", args=[self.conversation.id])
        data = {"content": "This is a test message", "message_type": "text"}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["content"], "This is a test message")
        self.assertEqual(response.data["sender"], str(self.customer.id))

        # Verify in database
        message_exists = Message.objects.filter(
            conversation=self.conversation,
            sender=self.customer,
            content="This is a test message",
        ).exists()
        self.assertTrue(message_exists)

    def test_mark_messages_as_read(self):
        """Test marking messages as read"""
        # Authenticate as customer
        self.client.force_authenticate(user=self.customer)

        # Initially, employee message is unread
        self.assertFalse(self.employee_message.is_read)

        # Mark as read
        url = reverse("conversation-mark-read", args=[self.conversation.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["marked_read"], 1)

        # Verify message is now read
        self.employee_message.refresh_from_db()
        self.assertTrue(self.employee_message.is_read)

    def test_typing_status(self):
        """Test updating typing status"""
        # Authenticate as customer
        self.client.force_authenticate(user=self.customer)

        # Set typing status
        url = reverse("conversation-typing-status", args=[self.conversation.id])
        data = {"is_typing": True}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "updated")

        # Verify in database
        typing_status = TypingStatus.objects.get(
            user=self.customer, conversation=self.conversation
        )
        self.assertTrue(typing_status.is_typing)

    def test_get_unread_count(self):
        """Test getting unread message count"""
        # Authenticate as customer
        self.client.force_authenticate(user=self.customer)

        # Get unread count
        url = reverse("conversation-unread-count")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["unread_count"], 1
        )  # One unread employee message

    def test_permissions_enforcement(self):
        """Test that permissions are properly enforced"""
        # Create a user with no permissions
        no_perm_user = User.objects.create(
            phone_number="9998887777", user_type="employee"
        )

        # Create an employee with no chat permission
        no_perm_employee = Employee.objects.create(
            user=no_perm_user,
            shop=self.shop,
            first_name="No",
            last_name="Permission",
            position="Staff",
        )

        # Create a role with no chat permission
        no_chat_role = Role.objects.create(
            name="No Chat Access", role_type="shop_employee", shop=self.shop
        )

        # Assign role to user
        UserRole.objects.create(user=no_perm_user, role=no_chat_role)

        # Authenticate as user with no permissions
        self.client.force_authenticate(user=no_perm_user)

        # Try to list conversations
        url = reverse("conversation-list")
        response = self.client.get(url)

        # Should be forbidden or empty list
        self.assertIn(
            response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_200_OK]
        )
        if response.status_code == status.HTTP_200_OK:
            self.assertEqual(len(response.data["results"]), 0)
