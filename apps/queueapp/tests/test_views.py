import uuid
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.authapp.models import User
from apps.categoriesapp.models import Category
from apps.companiesapp.models import Company
from apps.queueapp.models import Queue, QueueTicket
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop


class QueueViewsTest(TestCase):
    def setUp(self):
        # Create API client
        self.client = APIClient()

        # Create a user with permission
        self.user = User.objects.create(
            phone_number="1234567890",
            user_type="admin",
            is_staff=True,
            is_superuser=True,  # Superuser has all permissions
        )

        # Create a customer user
        self.customer = User.objects.create(phone_number="9876543210", user_type="customer")

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
        self.queue = Queue.objects.create(name="Test Queue", shop=self.shop, status="open")

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

        # Create a ticket
        self.ticket = QueueTicket.objects.create(
            queue=self.queue,
            ticket_number="Q-123456-001",
            customer=self.customer,
            position=1,
            status="waiting",
            estimated_wait_time=15,
        )

        # Set up authentication
        self.client.force_authenticate(user=self.user)

    def test_queue_list_view(self):
        """Test listing queues"""
        url = reverse("queueapp:queue-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Test Queue")

    def test_queue_detail_view(self):
        """Test retrieving a single queue"""
        url = reverse("queueapp:queue-detail", args=[self.queue.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test Queue")
        self.assertEqual(response.data["status"], "open")

    def test_shop_queue_list_view(self):
        """Test listing queues for a specific shop"""
        url = reverse("queueapp:shop-queues", args=[self.shop.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Test Queue")

    def test_queue_ticket_list_view(self):
        """Test listing queue tickets"""
        url = reverse("queueapp:ticket-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["ticket_number"], "Q-123456-001")

    def test_queue_ticket_detail_view(self):
        """Test retrieving a single queue ticket"""
        url = reverse("queueapp:ticket-detail", args=[self.ticket.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["ticket_number"], "Q-123456-001")
        self.assertEqual(response.data["status"], "waiting")

    @patch("apps.queueapp.views.QueueService")
    def test_join_queue_view(self, mock_queue_service):
        """Test joining a queue"""
        mock_queue_service.join_queue.return_value = self.ticket

        url = reverse("queueapp:join-queue")
        data = {
            "queue_id": str(self.queue.id),
            "customer_id": str(self.customer.id),
            "service_id": str(self.service.id),
        }

        # Force authenticate as customer
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["ticket_number"], "Q-123456-001")

        # QueueService.join_queue should have been called with the right args
        mock_queue_service.join_queue.assert_called_once_with(
            str(self.queue.id), str(self.customer.id), str(self.service.id)
        )

    @patch("apps.queueapp.views.QueueService")
    def test_call_next_view(self, mock_queue_service):
        """Test calling next customer"""
        mock_queue_service.call_next.return_value = QueueTicket(
            id=uuid.uuid4(),
            queue=self.queue,
            ticket_number="Q-123456-001",
            customer=self.customer,
            position=1,
            status="called",
            called_time=timezone.now(),
        )

        url = reverse("queueapp:call-next")
        data = {"queue_id": str(self.queue.id)}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "called")

        # QueueService.call_next should have been called with the right args
        mock_queue_service.call_next.assert_called_once_with(str(self.queue.id), None)

    @patch("apps.queueapp.views.QueueService")
    def test_mark_serving_view(self, mock_queue_service):
        """Test marking a ticket as serving"""
        mock_queue_service.mark_serving.return_value = QueueTicket(
            id=uuid.uuid4(),
            queue=self.queue,
            ticket_number="Q-123456-001",
            customer=self.customer,
            position=1,
            status="serving",
            called_time=timezone.now(),
            serve_time=timezone.now(),
            actual_wait_time=15,
        )

        url = reverse("queueapp:mark-serving")
        data = {"ticket_id": str(self.ticket.id)}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "serving")

        # QueueService.mark_serving should have been called with the right args
        mock_queue_service.mark_serving.assert_called_once_with(str(self.ticket.id), None)

    @patch("apps.queueapp.views.QueueService")
    def test_mark_served_view(self, mock_queue_service):
        """Test marking a ticket as served"""
        mock_queue_service.mark_served.return_value = QueueTicket(
            id=uuid.uuid4(),
            queue=self.queue,
            ticket_number="Q-123456-001",
            customer=self.customer,
            position=1,
            status="served",
            called_time=timezone.now(),
            serve_time=timezone.now(),
            complete_time=timezone.now(),
            actual_wait_time=15,
        )

        url = reverse("queueapp:mark-served")
        data = {"ticket_id": str(self.ticket.id)}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "served")

        # QueueService.mark_served should have been called with the right args
        mock_queue_service.mark_served.assert_called_once_with(str(self.ticket.id))

    @patch("apps.queueapp.views.QueueService")
    def test_cancel_ticket_view(self, mock_queue_service):
        """Test cancelling a ticket"""
        mock_queue_service.cancel_ticket.return_value = QueueTicket(
            id=uuid.uuid4(),
            queue=self.queue,
            ticket_number="Q-123456-001",
            customer=self.customer,
            position=1,
            status="cancelled",
        )

        url = reverse("queueapp:cancel-ticket")
        data = {"ticket_id": str(self.ticket.id)}

        # Force authenticate as customer (ticket owner)
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "cancelled")

        # QueueService.cancel_ticket should have been called with the right args
        mock_queue_service.cancel_ticket.assert_called_once_with(str(self.ticket.id))

    def test_queue_status_view(self):
        """Test getting queue status"""
        url = reverse("queueapp:queue-status", args=[self.queue.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["queue"]["name"], "Test Queue")
        self.assertEqual(len(response.data["active_tickets"]), 1)
        self.assertEqual(response.data["counts"]["waiting"], 1)

    def test_check_position_view(self):
        """Test checking position in queue"""
        url = reverse("queueapp:check-position")
        data = {"ticket_number": "Q-123456-001", "queue_id": str(self.queue.id)}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["position"], 1)
        self.assertEqual(response.data["tickets_ahead"], 0)

    def test_customer_active_tickets_view(self):
        """Test getting customer's active tickets"""
        url = reverse("queueapp:customer-active-tickets", args=[self.customer.id])

        # Force authenticate as customer (accessing own tickets)
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["ticket_number"], "Q-123456-001")
