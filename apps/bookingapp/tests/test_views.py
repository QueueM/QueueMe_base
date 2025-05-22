# apps/bookingapp/tests/test_views.py
import uuid
from datetime import datetime, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.authapp.models import User
from apps.bookingapp.models import Appointment, MultiServiceBooking
from apps.serviceapp.models import Service
from apps.shopapp.models import ShopHours
from apps.specialistsapp.models import Specialist, SpecialistService

from .test_fix import create_test_shop


class AppointmentViewSetTest(TestCase):
    """Test cases for the AppointmentViewSet"""

    def setUp(self):
        """Set up test data"""
        # Create test users
        self.customer = User.objects.create_user(
            phone_number="1234567890", user_type="customer", password="testpass123"
        )

        self.employee = User.objects.create_user(
            phone_number="9876543210", user_type="employee", password="testpass123"
        )

        self.admin = User.objects.create_user(
            phone_number="5555555555",
            user_type="admin",
            password="testpass123",
            is_staff=True,
            is_superuser=True,
        )

        # Create test shop using the helper
        self.shop = create_test_shop(name="Test Shop", username="testshop")

        # Create shop hours
        for weekday in range(7):
            ShopHours.objects.create(
                shop=self.shop,
                weekday=weekday,
                from_hour=time(9, 0),
                to_hour=time(17, 0),
                is_closed=False,
            )

        # Create test service
        self.service = Service.objects.create(
            id=uuid.uuid4(),
            name="Test Service",
            shop=self.shop,
            price=100.00,
            duration=60,
            buffer_before=5,
            buffer_after=5,
            slot_granularity=30,
        )

        # Create test specialist
        self.specialist = Specialist.objects.create(id=uuid.uuid4())

        # Link specialist to service
        SpecialistService.objects.create(
            specialist=self.specialist, service=self.service
        )

        # Create specialist working hours
        from apps.specialistsapp.models import SpecialistWorkingHours

        for weekday in range(7):
            SpecialistWorkingHours.objects.create(
                specialist=self.specialist,
                weekday=weekday,
                from_hour=time(9, 0),
                to_hour=time(17, 0),
                is_off=False,
            )

        # Link employee to shop
        from apps.employeeapp.models import Employee

        self.employee_obj = Employee.objects.create(
            user=self.employee, shop=self.shop, first_name="Test", last_name="Employee"
        )

        # Set up test date (tomorrow)
        self.test_date = timezone.now().date() + timedelta(days=1)
        self.test_date_str = self.test_date.strftime("%Y-%m-%d")

        # Create test appointment
        start_time = datetime.combine(self.test_date, time(10, 0))
        end_time = datetime.combine(self.test_date, time(11, 0))

        # Make timezone aware
        self.start_time = timezone.make_aware(start_time)
        self.end_time = timezone.make_aware(end_time)

        self.appointment = Appointment.objects.create(
            customer=self.customer,
            service=self.service,
            specialist=self.specialist,
            shop=self.shop,
            start_time=self.start_time,
            end_time=self.end_time,
            status="scheduled",
        )

        # Set up API client
        self.client = APIClient()

    def test_list_appointments(self):
        """Test listing appointments with different user roles"""
        url = reverse("appointment-list")

        # Test as customer
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

        # Test as employee
        self.client.force_authenticate(user=self.employee)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

        # Test as admin
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_retrieve_appointment(self):
        """Test retrieving a single appointment"""
        url = reverse("appointment-detail", args=[self.appointment.id])

        # Test as customer
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.appointment.id))

        # Test as employee
        self.client.force_authenticate(user=self.employee)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Create another customer
        other_customer = User.objects.create_user(
            phone_number="9999999999", user_type="customer", password="testpass123"
        )

        # Test as other customer (should be denied)
        self.client.force_authenticate(user=other_customer)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_appointment(self):
        """Test creating an appointment"""
        url = reverse("appointment-list")

        # Use BookingCreateSerializer format
        data = {
            "service_id": str(self.service.id),
            "specialist_id": str(self.specialist.id),
            "date": self.test_date_str,
            "start_time": "14:00",
            "notes": "Test appointment",
        }

        # Test as customer
        self.client.force_authenticate(user=self.customer)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify appointment created
        self.assertEqual(Appointment.objects.count(), 2)

        # Check appointment details
        new_appointment = Appointment.objects.exclude(id=self.appointment.id).first()
        self.assertEqual(new_appointment.customer, self.customer)
        self.assertEqual(new_appointment.service, self.service)
        self.assertEqual(new_appointment.specialist, self.specialist)
        self.assertEqual(new_appointment.notes, "Test appointment")

        # Check start time
        self.assertEqual(new_appointment.start_time.hour, 14)
        self.assertEqual(new_appointment.start_time.minute, 0)

    def test_cancel_appointment(self):
        """Test cancelling an appointment"""
        url = reverse("appointment-cancel", args=[self.appointment.id])

        data = {"reason": "Test cancellation"}

        # Test as customer
        self.client.force_authenticate(user=self.customer)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify appointment cancelled
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "cancelled")
        self.assertEqual(self.appointment.cancellation_reason, "Test cancellation")
        self.assertEqual(self.appointment.cancelled_by, self.customer)

    def test_availability_endpoint(self):
        """Test getting service availability"""
        url = reverse("appointment-availability")

        # Add query params
        url += f"?service_id={self.service.id}&date={self.test_date_str}"

        # Test as customer
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify response format
        self.assertIsInstance(response.data, list)
        if len(response.data) > 0:
            self.assertIn("start", response.data[0])
            self.assertIn("end", response.data[0])
            self.assertIn("duration", response.data[0])

        # Test with missing params
        url = reverse("appointment-availability")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MultiServiceBookingViewSetTest(TestCase):
    """Test cases for the MultiServiceBookingViewSet"""

    def setUp(self):
        """Set up test data"""
        # Similar setup as AppointmentViewSetTest
        # Create test user
        self.customer = User.objects.create_user(
            phone_number="1234567890", user_type="customer", password="testpass123"
        )

        # Create test shop using the helper
        self.shop = create_test_shop(name="Test Shop", username="testshop")

        # Create test services
        self.service1 = Service.objects.create(
            id=uuid.uuid4(),
            name="Test Service 1",
            shop=self.shop,
            price=100.00,
            duration=60,
        )

        self.service2 = Service.objects.create(
            id=uuid.uuid4(),
            name="Test Service 2",
            shop=self.shop,
            price=150.00,
            duration=45,
        )

        # Create test specialist
        self.specialist = Specialist.objects.create(id=uuid.uuid4())

        # Link specialist to services
        SpecialistService.objects.create(
            specialist=self.specialist, service=self.service1
        )

        SpecialistService.objects.create(
            specialist=self.specialist, service=self.service2
        )

        # Set up test date (tomorrow)
        self.test_date = timezone.now().date() + timedelta(days=1)

        # Create test appointments
        start_time1 = datetime.combine(self.test_date, time(10, 0))
        end_time1 = datetime.combine(self.test_date, time(11, 0))

        start_time2 = datetime.combine(self.test_date, time(14, 0))
        end_time2 = datetime.combine(self.test_date, time(14, 45))

        # Make timezone aware
        start_time1 = timezone.make_aware(start_time1)
        end_time1 = timezone.make_aware(end_time1)
        start_time2 = timezone.make_aware(start_time2)
        end_time2 = timezone.make_aware(end_time2)

        self.appointment1 = Appointment.objects.create(
            customer=self.customer,
            service=self.service1,
            specialist=self.specialist,
            shop=self.shop,
            start_time=start_time1,
            end_time=end_time1,
            status="scheduled",
            total_price=100.00,
        )

        self.appointment2 = Appointment.objects.create(
            customer=self.customer,
            service=self.service2,
            specialist=self.specialist,
            shop=self.shop,
            start_time=start_time2,
            end_time=end_time2,
            status="scheduled",
            total_price=150.00,
        )

        # Create multi-service booking
        self.multi_booking = MultiServiceBooking.objects.create(
            customer=self.customer, shop=self.shop, total_price=250.00
        )

        self.multi_booking.appointments.add(self.appointment1)
        self.multi_booking.appointments.add(self.appointment2)

        # Set up API client
        self.client = APIClient()

    def test_list_multi_bookings(self):
        """Test listing multi-service bookings"""
        url = reverse("multiservicebooking-list")

        # Test as customer
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_retrieve_multi_booking(self):
        """Test retrieving a single multi-service booking"""
        url = reverse("multiservicebooking-detail", args=[self.multi_booking.id])

        # Test as customer
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.multi_booking.id))

        # Check appointments included
        self.assertEqual(len(response.data["appointments"]), 2)
