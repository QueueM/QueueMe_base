from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.categoriesapp.models import Category
from apps.companiesapp.models import Company
from apps.queueapp.models import Queue, QueueTicket
from apps.queueapp.services.queue_service import QueueService
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop


class QueueServiceTest(TestCase):
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

        # Create a category
        self.category = Category.objects.create(name="Test Category")

        # Create a service
        self.service = Service.objects.create(
            name="Test Service",
            shop=self.shop,
            category=self.category,
            price=100.00,
            duration=30,
            service_location="in_shop",
        )

    @patch("apps.queueapp.services.queue_service.NotificationService")
    def test_join_queue(self, mock_notification_service):
        """Test joining a queue"""
        mock_notification_service.send_notification = MagicMock(return_value=True)

        # Join queue
        result = QueueService.join_queue(
            queue_id=self.queue.id, customer_id=self.user.id, service_id=self.service.id
        )

        # Check result is a QueueTicket
        self.assertIsInstance(result, QueueTicket)

        # Check ticket properties
        self.assertEqual(result.queue_id, self.queue.id)
        self.assertEqual(result.customer_id, self.user.id)
        self.assertEqual(result.service_id, self.service.id)
        self.assertEqual(result.status, "waiting")
        self.assertEqual(result.position, 1)

        # Notification should have been sent
        mock_notification_service.send_notification.assert_called_once()

    @patch("apps.queueapp.services.queue_service.NotificationService")
    def test_join_queue_closed(self, mock_notification_service):
        """Test joining a closed queue"""
        # Close the queue
        self.queue.status = "closed"
        self.queue.save()

        # Try to join
        result = QueueService.join_queue(
            queue_id=self.queue.id, customer_id=self.user.id
        )

        # Should return error
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

        # No notification should be sent
        mock_notification_service.send_notification.assert_not_called()

    @patch("apps.queueapp.services.queue_service.NotificationService")
    def test_join_queue_at_capacity(self, mock_notification_service):
        """Test joining a queue at capacity"""
        # Set capacity
        self.queue.max_capacity = 1
        self.queue.save()

        # Add a ticket to reach capacity
        QueueTicket.objects.create(
            queue=self.queue,
            ticket_number="Q-123456-001",
            customer=User.objects.create(
                phone_number="9876543210", user_type="customer"
            ),
            position=1,
            status="waiting",
        )

        # Try to join
        result = QueueService.join_queue(
            queue_id=self.queue.id, customer_id=self.user.id
        )

        # Should return error
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("capacity", result["error"])

        # No notification should be sent
        mock_notification_service.send_notification.assert_not_called()

    @patch("apps.queueapp.services.queue_service.NotificationService")
    def test_call_next(self, mock_notification_service):
        """Test calling next customer"""
        mock_notification_service.send_notification = MagicMock(return_value=True)

        # Add a ticket
        ticket = QueueTicket.objects.create(
            queue=self.queue,
            ticket_number="Q-123456-001",
            customer=self.user,
            position=1,
            status="waiting",
        )

        # Call next
        result = QueueService.call_next(self.queue.id)

        # Check result
        self.assertIsInstance(result, QueueTicket)
        self.assertEqual(result.id, ticket.id)
        self.assertEqual(result.status, "called")
        self.assertIsNotNone(result.called_time)

        # Notification should have been sent
        mock_notification_service.send_notification.assert_called_once()

    @patch("apps.queueapp.services.queue_service.NotificationService")
    def test_call_next_empty_queue(self, mock_notification_service):
        """Test calling next when queue is empty"""
        # Call next on empty queue
        result = QueueService.call_next(self.queue.id)

        # Should return error
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

        # No notification should be sent
        mock_notification_service.send_notification.assert_not_called()

    def test_mark_serving(self):
        """Test marking a ticket as serving"""
        # Add a ticket in 'called' status
        ticket = QueueTicket.objects.create(
            queue=self.queue,
            ticket_number="Q-123456-001",
            customer=self.user,
            position=1,
            status="called",
            called_time=timezone.now(),
        )

        # Mark as serving
        result = QueueService.mark_serving(ticket.id)

        # Check result
        self.assertIsInstance(result, QueueTicket)
        self.assertEqual(result.id, ticket.id)
        self.assertEqual(result.status, "serving")
        self.assertIsNotNone(result.serve_time)
        self.assertIsNotNone(result.actual_wait_time)

    def test_mark_serving_invalid_status(self):
        """Test marking a ticket that's not in 'called' status"""
        # Add a ticket in 'waiting' status
        ticket = QueueTicket.objects.create(
            queue=self.queue,
            ticket_number="Q-123456-001",
            customer=self.user,
            position=1,
            status="waiting",
        )

        # Try to mark as serving
        result = QueueService.mark_serving(ticket.id)

        # Should return error
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

    @patch("apps.queueapp.services.queue_service.NotificationService")
    def test_mark_served(self, mock_notification_service):
        """Test marking a ticket as served"""
        mock_notification_service.send_notification = MagicMock(return_value=True)

        # Add a ticket in 'serving' status
        ticket = QueueTicket.objects.create(
            queue=self.queue,
            ticket_number="Q-123456-001",
            customer=self.user,
            position=1,
            status="serving",
            called_time=timezone.now(),
            serve_time=timezone.now(),
        )

        # Mock recalculate_wait_times to avoid DB queries
        with patch(
            "apps.queueapp.services.queue_service.QueueService.recalculate_wait_times"
        ) as mock_recalc:
            mock_recalc.return_value = True

            # Mark as served
            result = QueueService.mark_served(ticket.id)

            # Check result
            self.assertIsInstance(result, QueueTicket)
            self.assertEqual(result.id, ticket.id)
            self.assertEqual(result.status, "served")
            self.assertIsNotNone(result.complete_time)

            # recalculate_wait_times should have been called
            mock_recalc.assert_called_once_with(self.queue.id)

            # Notification should have been sent
            mock_notification_service.send_notification.assert_called_once()

    @patch("apps.queueapp.services.queue_service.NotificationService")
    def test_cancel_ticket(self, mock_notification_service):
        """Test cancelling a ticket"""
        mock_notification_service.send_notification = MagicMock(return_value=True)

        # Add multiple tickets
        ticket1 = QueueTicket.objects.create(
            queue=self.queue,
            ticket_number="Q-123456-001",
            customer=self.user,
            position=1,
            status="waiting",
        )

        ticket2 = QueueTicket.objects.create(
            queue=self.queue,
            ticket_number="Q-123456-002",
            customer=User.objects.create(
                phone_number="9876543210", user_type="customer"
            ),
            position=2,
            status="waiting",
        )

        # Mock recalculate_wait_times to avoid DB queries
        with patch(
            "apps.queueapp.services.queue_service.QueueService.recalculate_wait_times"
        ) as mock_recalc:
            mock_recalc.return_value = True

            # Cancel ticket1
            result = QueueService.cancel_ticket(ticket1.id)

            # Check result
            self.assertIsInstance(result, QueueTicket)
            self.assertEqual(result.id, ticket1.id)
            self.assertEqual(result.status, "cancelled")

            # Refresh ticket2 from DB
            ticket2.refresh_from_db()

            # Position of ticket2 should now be 1
            self.assertEqual(ticket2.position, 1)

            # recalculate_wait_times should have been called
            mock_recalc.assert_called_once_with(self.queue.id)

            # Notification should have been sent
            mock_notification_service.send_notification.assert_called_once()
