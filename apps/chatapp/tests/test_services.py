from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.chatapp.models import Conversation, Presence, TypingStatus
from apps.chatapp.services.chat_service import ChatService
from apps.chatapp.services.presence_service import PresenceService
from apps.companiesapp.models import Company
from apps.employeeapp.models import Employee
from apps.shopapp.models import Shop


class ChatServiceTest(TestCase):
    """Test cases for ChatService"""

    def setUp(self):
        """Set up test data"""
        # Create users
        self.customer = User.objects.create(phone_number="1234567890", user_type="customer")

        self.shop_user = User.objects.create(phone_number="0987654321", user_type="employee")

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

    def test_get_or_create_conversation(self):
        """Test getting or creating a conversation"""
        # First call should create a new conversation
        conversation, created = ChatService.get_or_create_conversation(
            self.customer.id, self.shop.id
        )

        self.assertTrue(created)
        self.assertEqual(conversation.customer, self.customer)
        self.assertEqual(conversation.shop, self.shop)

        # Check that presence records were created
        customer_presence = Presence.objects.filter(
            user=self.customer, conversation=conversation
        ).exists()
        self.assertTrue(customer_presence)

        # Second call should return existing conversation
        conversation2, created2 = ChatService.get_or_create_conversation(
            self.customer.id, self.shop.id
        )

        self.assertFalse(created2)
        self.assertEqual(conversation.id, conversation2.id)

    def test_send_message(self):
        """Test sending a message"""
        # Create a conversation first
        conversation, _ = ChatService.get_or_create_conversation(self.customer.id, self.shop.id)

        # Send a customer message
        message = ChatService.send_message(
            conversation_id=conversation.id,
            sender_id=self.customer.id,
            content="Hello, I'd like to book an appointment",
        )

        self.assertEqual(message.conversation, conversation)
        self.assertEqual(message.sender, self.customer)
        self.assertIsNone(message.employee)
        self.assertEqual(message.content, "Hello, I'd like to book an appointment")
        self.assertEqual(message.message_type, "text")

        # Send an employee message
        employee_message = ChatService.send_message(
            conversation_id=conversation.id,
            sender_id=self.shop_user.id,
            content="Sure, I can help you with that",
            employee_id=self.employee.id,
        )

        self.assertEqual(employee_message.conversation, conversation)
        self.assertEqual(employee_message.sender, self.shop_user)
        self.assertEqual(employee_message.employee, self.employee)
        self.assertEqual(employee_message.content, "Sure, I can help you with that")

    @patch("core.storage.s3_storage.S3Storage.upload_file")
    def test_send_message_with_media(self, mock_upload_file):
        """Test sending a message with media"""
        # Mock S3 upload to return a URL
        mock_upload_file.return_value = "https://example.com/image.jpg"

        # Create a conversation first
        conversation, _ = ChatService.get_or_create_conversation(self.customer.id, self.shop.id)

        # Create a mock file
        mock_file = MagicMock()
        mock_file.name = "test_image.jpg"

        # Send a message with media
        message = ChatService.send_message(
            conversation_id=conversation.id,
            sender_id=self.customer.id,
            content="Check out this image",
            message_type="image",
            media_file=mock_file,
        )

        self.assertEqual(message.message_type, "image")
        self.assertEqual(message.media_url, "https://example.com/image.jpg")
        mock_upload_file.assert_called_once()

    def test_mark_messages_as_read(self):
        """Test marking messages as read"""
        # Create a conversation
        conversation, _ = ChatService.get_or_create_conversation(self.customer.id, self.shop.id)

        # Send a customer message
        customer_message = ChatService.send_message(
            conversation_id=conversation.id, sender_id=self.customer.id, content="Hello"
        )

        # Send an employee message
        employee_message = ChatService.send_message(
            conversation_id=conversation.id,
            sender_id=self.shop_user.id,
            content="Hi there",
            employee_id=self.employee.id,
        )

        # Mark as read by customer
        count = ChatService.mark_messages_as_read(
            conversation_id=conversation.id, user_id=self.customer.id
        )

        # Should mark the employee message as read
        self.assertEqual(count, 1)
        employee_message.refresh_from_db()
        self.assertTrue(employee_message.is_read)

        # Customer message should still be unread
        customer_message.refresh_from_db()
        self.assertFalse(customer_message.is_read)

        # Mark as read by employee
        count = ChatService.mark_messages_as_read(
            conversation_id=conversation.id, user_id=self.shop_user.id
        )

        # Should mark the customer message as read
        self.assertEqual(count, 1)
        customer_message.refresh_from_db()
        self.assertTrue(customer_message.is_read)

    def test_get_unread_count(self):
        """Test getting unread message count"""
        # Create conversations and messages
        conversation1, _ = ChatService.get_or_create_conversation(self.customer.id, self.shop.id)

        # Create another customer for a second conversation
        customer2 = User.objects.create(phone_number="5556667777", user_type="customer")

        conversation2, _ = ChatService.get_or_create_conversation(customer2.id, self.shop.id)

        # Send messages (unread)
        ChatService.send_message(
            conversation_id=conversation1.id,
            sender_id=self.shop_user.id,
            content="Message 1",
            employee_id=self.employee.id,
        )

        ChatService.send_message(
            conversation_id=conversation1.id,
            sender_id=self.shop_user.id,
            content="Message 2",
            employee_id=self.employee.id,
        )

        ChatService.send_message(
            conversation_id=conversation2.id,
            sender_id=self.shop_user.id,
            content="Message for customer 2",
            employee_id=self.employee.id,
        )

        # Customer should have 2 unread messages
        count = ChatService.get_unread_count(self.customer.id)
        self.assertEqual(count, 2)

        # Customer 2 should have 1 unread message
        count = ChatService.get_unread_count(customer2.id)
        self.assertEqual(count, 1)

        # Shop employee should have 0 unread messages
        count = ChatService.get_unread_count(self.shop_user.id)
        self.assertEqual(count, 0)

        # Send customer messages
        ChatService.send_message(
            conversation_id=conversation1.id,
            sender_id=self.customer.id,
            content="Customer reply",
        )

        ChatService.send_message(
            conversation_id=conversation2.id,
            sender_id=customer2.id,
            content="Customer 2 reply",
        )

        # Now shop employee should have 2 unread messages
        count = ChatService.get_unread_count(self.shop_user.id)
        self.assertEqual(count, 2)


class PresenceServiceTest(TestCase):
    """Test cases for PresenceService"""

    def setUp(self):
        """Set up test data"""
        # Create users
        self.customer = User.objects.create(phone_number="1234567890", user_type="customer")

        self.shop_user = User.objects.create(phone_number="0987654321", user_type="employee")

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

        # Create conversation
        self.conversation = Conversation.objects.create(customer=self.customer, shop=self.shop)

    def test_set_user_online(self):
        """Test setting a user as online"""
        # Set customer as online
        presence = PresenceService.set_user_online(
            user_id=self.customer.id, conversation_id=self.conversation.id
        )

        self.assertTrue(presence.is_online)
        self.assertEqual(presence.user, self.customer)
        self.assertEqual(presence.conversation, self.conversation)

        # Verify in database
        db_presence = Presence.objects.get(user=self.customer, conversation=self.conversation)
        self.assertTrue(db_presence.is_online)

    def test_set_user_offline(self):
        """Test setting a user as offline"""
        # First, set as online
        PresenceService.set_user_online(
            user_id=self.customer.id, conversation_id=self.conversation.id
        )

        # Then set as offline
        presence = PresenceService.set_user_offline(
            user_id=self.customer.id, conversation_id=self.conversation.id
        )

        self.assertFalse(presence.is_online)

        # Verify in database
        db_presence = Presence.objects.get(user=self.customer, conversation=self.conversation)
        self.assertFalse(db_presence.is_online)

    def test_set_typing_status(self):
        """Test setting typing status"""
        # Set customer as typing
        typing_status = PresenceService.set_typing_status(
            user_id=self.customer.id,
            conversation_id=self.conversation.id,
            is_typing=True,
        )

        self.assertTrue(typing_status.is_typing)

        # Verify in database
        db_typing = TypingStatus.objects.get(user=self.customer, conversation=self.conversation)
        self.assertTrue(db_typing.is_typing)

        # Change to not typing
        typing_status = PresenceService.set_typing_status(
            user_id=self.customer.id,
            conversation_id=self.conversation.id,
            is_typing=False,
        )

        self.assertFalse(typing_status.is_typing)

        # Verify in database
        db_typing.refresh_from_db()
        self.assertFalse(db_typing.is_typing)

    def test_get_conversation_presence(self):
        """Test getting presence for a conversation"""
        # Set up presence records
        PresenceService.set_user_online(
            user_id=self.customer.id, conversation_id=self.conversation.id
        )

        PresenceService.set_user_online(
            user_id=self.shop_user.id, conversation_id=self.conversation.id
        )

        # Set shop user offline
        PresenceService.set_user_offline(
            user_id=self.shop_user.id, conversation_id=self.conversation.id
        )

        # Get presence map
        presence_map = PresenceService.get_conversation_presence(
            conversation_id=self.conversation.id
        )

        self.assertTrue(presence_map[str(self.customer.id)]["is_online"])
        self.assertFalse(presence_map[str(self.shop_user.id)]["is_online"])

    def test_cleanup_stale_presence(self):
        """Test cleaning up stale presence records"""
        # Set customer as online
        presence = PresenceService.set_user_online(
            user_id=self.customer.id, conversation_id=self.conversation.id
        )

        # Manually set last_seen to an old time
        old_time = timezone.now() - timezone.timedelta(minutes=40)
        Presence.objects.filter(id=presence.id).update(last_seen=old_time)

        # Run cleanup (30 minute threshold)
        count = PresenceService.cleanup_stale_presence(idle_minutes=30)

        # Should have marked one record as offline
        self.assertEqual(count, 1)

        # Verify in database
        presence.refresh_from_db()
        self.assertFalse(presence.is_online)
