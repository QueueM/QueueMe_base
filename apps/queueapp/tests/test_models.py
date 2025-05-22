from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.companiesapp.models import Company
from apps.queueapp.models import Queue, QueueTicket
from apps.shopapp.models import Shop


class QueueModelTest(TestCase):
    def setUp(self):
        # Create a user
        self.user = User.objects.create(phone_number="1234567890", user_type="admin")

        # Create a company
        self.company = Company.objects.create(
            name="Test Company", owner=self.user, contact_phone="1234567890"
        )

        # Create a shop
        self.shop = Shop.objects.create(
            name="Test Shop",
            company=self.company,
            phone_number="1234567890",
            username="testshop",
        )

        # Create a queue
        self.queue = Queue.objects.create(
            name="Test Queue", shop=self.shop, status="open", max_capacity=50
        )

    def test_queue_str_representation(self):
        """Test the string representation of a Queue"""
        self.assertEqual(str(self.queue), "Test Shop - Test Queue")

    def test_is_at_capacity(self):
        """Test the is_at_capacity method"""
        # Create 50 tickets (max capacity)
        for i in range(50):
            QueueTicket.objects.create(
                queue=self.queue,
                ticket_number=f"Q-123456-{i:03d}",
                customer=self.user,
                position=i + 1,
                status="waiting",
            )

        # Queue should be at capacity
        self.assertTrue(self.queue.is_at_capacity())

        # Set max_capacity to 0 (unlimited)
        self.queue.max_capacity = 0
        self.queue.save()

        # Queue should not be at capacity anymore
        self.assertFalse(self.queue.is_at_capacity())


class QueueTicketModelTest(TestCase):
    def setUp(self):
        # Create a user
        self.user = User.objects.create(phone_number="1234567890", user_type="customer")

        # Create a company
        self.company = Company.objects.create(
            name="Test Company", owner=self.user, contact_phone="1234567890"
        )

        # Create a shop
        self.shop = Shop.objects.create(
            name="Test Shop",
            company=self.company,
            phone_number="1234567890",
            username="testshop",
        )

        # Create a queue
        self.queue = Queue.objects.create(
            name="Test Queue", shop=self.shop, status="open"
        )

        # Create a ticket
        self.ticket = QueueTicket.objects.create(
            queue=self.queue,
            ticket_number="Q-123456-001",
            customer=self.user,
            position=1,
            status="waiting",
            estimated_wait_time=15,
        )

    def test_ticket_str_representation(self):
        """Test the string representation of a QueueTicket"""
        self.assertEqual(str(self.ticket), "Test Shop - Q-123456-001 - 1234567890")

    def test_status_transitions(self):
        """Test ticket status transitions"""
        # Initial status should be waiting
        self.assertEqual(self.ticket.status, "waiting")

        # Update to called
        self.ticket.status = "called"
        self.ticket.called_time = timezone.now()
        self.ticket.save()

        # Refresh from database
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "called")
        self.assertIsNotNone(self.ticket.called_time)

        # Update to serving
        self.ticket.status = "serving"
        self.ticket.serve_time = timezone.now()
        self.ticket.save()

        # Refresh from database
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "serving")
        self.assertIsNotNone(self.ticket.serve_time)

        # Update to served
        self.ticket.status = "served"
        self.ticket.complete_time = timezone.now()
        self.ticket.save()

        # Refresh from database
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "served")
        self.assertIsNotNone(self.ticket.complete_time)
