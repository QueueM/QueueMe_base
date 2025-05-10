from django.test import TestCase

from apps.authapp.models import User
from apps.chatapp.models import Conversation, Message, Presence, TypingStatus
from apps.companiesapp.models import Company
from apps.employeeapp.models import Employee
from apps.shopapp.models import Shop


class ConversationModelTest(TestCase):
    """Test cases for Conversation model"""

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

        # Create conversation
        self.conversation = Conversation.objects.create(
            customer=self.customer, shop=self.shop
        )

    def test_conversation_creation(self):
        """Test that conversation is created with correct attributes"""
        self.assertEqual(self.conversation.customer, self.customer)
        self.assertEqual(self.conversation.shop, self.shop)
        self.assertTrue(self.conversation.is_active)
        self.assertIsNotNone(self.conversation.created_at)
        self.assertIsNotNone(self.conversation.updated_at)

    def test_conversation_str_representation(self):
        """Test the string representation of a conversation"""
        expected_str = f"{self.customer.phone_number} - {self.shop.name}"
        self.assertEqual(str(self.conversation), expected_str)

    def test_conversation_unique_constraint(self):
        """Test that a customer can't have multiple conversations with the same shop"""
        # Attempt to create another conversation with same customer and shop
        with self.assertRaises(Exception):
            Conversation.objects.create(customer=self.customer, shop=self.shop)


class MessageModelTest(TestCase):
    """Test cases for Message model"""

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

        # Create conversation
        self.conversation = Conversation.objects.create(
            customer=self.customer, shop=self.shop
        )

        # Create customer message
        self.customer_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.customer,
            content="Hello, I'd like to book an appointment",
        )

        # Create employee message
        self.employee_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.shop_user,
            employee=self.employee,
            content="Sure, I can help you with that",
        )

    def test_message_creation(self):
        """Test that messages are created with correct attributes"""
        # Test customer message
        self.assertEqual(self.customer_message.conversation, self.conversation)
        self.assertEqual(self.customer_message.sender, self.customer)
        self.assertIsNone(self.customer_message.employee)
        self.assertEqual(
            self.customer_message.content, "Hello, I'd like to book an appointment"
        )
        self.assertEqual(self.customer_message.message_type, "text")
        self.assertFalse(self.customer_message.is_read)
        self.assertIsNone(self.customer_message.read_at)

        # Test employee message
        self.assertEqual(self.employee_message.conversation, self.conversation)
        self.assertEqual(self.employee_message.sender, self.shop_user)
        self.assertEqual(self.employee_message.employee, self.employee)
        self.assertEqual(
            self.employee_message.content, "Sure, I can help you with that"
        )
        self.assertEqual(self.employee_message.message_type, "text")
        self.assertFalse(self.employee_message.is_read)
        self.assertIsNone(self.employee_message.read_at)

    def test_message_str_representation(self):
        """Test the string representation of a message"""
        expected_str = f"{self.customer.phone_number} - {self.customer_message.created_at.strftime('%Y-%m-%d %H:%M')}"
        self.assertEqual(str(self.customer_message), expected_str)

    def test_message_ordering(self):
        """Test that messages are ordered by created_at"""
        messages = Message.objects.filter(conversation=self.conversation)
        self.assertEqual(messages[0], self.customer_message)
        self.assertEqual(messages[1], self.employee_message)


class PresenceModelTest(TestCase):
    """Test cases for Presence model"""

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

        # Create conversation
        self.conversation = Conversation.objects.create(
            customer=self.customer, shop=self.shop
        )

        # Create presence records
        self.customer_presence = Presence.objects.create(
            user=self.customer, conversation=self.conversation, is_online=True
        )

        self.employee_presence = Presence.objects.create(
            user=self.shop_user, conversation=self.conversation, is_online=False
        )

    def test_presence_creation(self):
        """Test that presence records are created with correct attributes"""
        # Test customer presence
        self.assertEqual(self.customer_presence.user, self.customer)
        self.assertEqual(self.customer_presence.conversation, self.conversation)
        self.assertTrue(self.customer_presence.is_online)
        self.assertIsNotNone(self.customer_presence.last_seen)

        # Test employee presence
        self.assertEqual(self.employee_presence.user, self.shop_user)
        self.assertEqual(self.employee_presence.conversation, self.conversation)
        self.assertFalse(self.employee_presence.is_online)
        self.assertIsNotNone(self.employee_presence.last_seen)

    def test_presence_str_representation(self):
        """Test the string representation of a presence record"""
        expected_str = f"{self.customer.phone_number} - Online"
        self.assertEqual(str(self.customer_presence), expected_str)

        expected_str = f"{self.shop_user.phone_number} - Offline"
        self.assertEqual(str(self.employee_presence), expected_str)

    def test_presence_unique_constraint(self):
        """Test that a user can't have multiple presence records for the same conversation"""
        # Attempt to create another presence record for the same user and conversation
        with self.assertRaises(Exception):
            Presence.objects.create(
                user=self.customer, conversation=self.conversation, is_online=False
            )


class TypingStatusModelTest(TestCase):
    """Test cases for TypingStatus model"""

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

        # Create conversation
        self.conversation = Conversation.objects.create(
            customer=self.customer, shop=self.shop
        )

        # Create typing status records
        self.customer_typing = TypingStatus.objects.create(
            user=self.customer, conversation=self.conversation, is_typing=True
        )

        self.employee_typing = TypingStatus.objects.create(
            user=self.shop_user, conversation=self.conversation, is_typing=False
        )

    def test_typing_status_creation(self):
        """Test that typing status records are created with correct attributes"""
        # Test customer typing status
        self.assertEqual(self.customer_typing.user, self.customer)
        self.assertEqual(self.customer_typing.conversation, self.conversation)
        self.assertTrue(self.customer_typing.is_typing)
        self.assertIsNotNone(self.customer_typing.updated_at)

        # Test employee typing status
        self.assertEqual(self.employee_typing.user, self.shop_user)
        self.assertEqual(self.employee_typing.conversation, self.conversation)
        self.assertFalse(self.employee_typing.is_typing)
        self.assertIsNotNone(self.employee_typing.updated_at)

    def test_typing_status_str_representation(self):
        """Test the string representation of a typing status record"""
        expected_str = f"{self.customer.phone_number} - Typing"
        self.assertEqual(str(self.customer_typing), expected_str)

        expected_str = f"{self.shop_user.phone_number} - Not typing"
        self.assertEqual(str(self.employee_typing), expected_str)

    def test_typing_status_unique_constraint(self):
        """Test that a user can't have multiple typing status records for the same conversation"""
        # Attempt to create another typing status record for the same user and conversation
        with self.assertRaises(Exception):
            TypingStatus.objects.create(
                user=self.customer, conversation=self.conversation, is_typing=False
            )
