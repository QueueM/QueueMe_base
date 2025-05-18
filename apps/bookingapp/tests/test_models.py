# apps/bookingapp/tests/test_models.py
import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.bookingapp.models import Appointment, AppointmentReminder, MultiServiceBooking
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist


class AppointmentModelTest(TestCase):
    """Test cases for the Appointment model"""

    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create(phone_number="1234567890", user_type="customer")

        # Create test shop
        self.shop = Shop.objects.create(id=uuid.uuid4(), name="Test Shop", username="testshop")

        # Create test service
        self.service = Service.objects.create(
            id=uuid.uuid4(),
            name="Test Service",
            shop=self.shop,
            price=100.00,
            duration=60,
            buffer_before=5,
            buffer_after=5,
        )

        # Create test specialist
        self.specialist = Specialist.objects.create(id=uuid.uuid4())

        # Make sure specialist can provide the service
        from apps.specialistsapp.models import SpecialistService

        SpecialistService.objects.create(specialist=self.specialist, service=self.service)

        # Set up times for appointment
        self.start_time = timezone.now() + timedelta(days=1)
        self.end_time = self.start_time + timedelta(hours=1)

    def test_appointment_creation(self):
        """Test creating an appointment"""
        appointment = Appointment.objects.create(
            customer=self.user,
            service=self.service,
            specialist=self.specialist,
            shop=self.shop,
            start_time=self.start_time,
            end_time=self.end_time,
            status="scheduled",
        )

        self.assertIsNotNone(appointment.id)
        self.assertEqual(appointment.status, "scheduled")
        self.assertEqual(appointment.payment_status, "pending")
        self.assertEqual(appointment.total_price, 0)  # Should be updated to service price

        # Fetch from DB to check save logic worked
        appointment_db = Appointment.objects.get(id=appointment.id)
        self.assertEqual(appointment_db.duration, self.service.duration)
        self.assertEqual(appointment_db.buffer_before, self.service.buffer_before)
        self.assertEqual(appointment_db.buffer_after, self.service.buffer_after)

    def test_appointment_status_methods(self):
        """Test appointment status change methods"""
        appointment = Appointment.objects.create(
            customer=self.user,
            service=self.service,
            specialist=self.specialist,
            shop=self.shop,
            start_time=self.start_time,
            end_time=self.end_time,
            status="scheduled",
        )

        # Test mark_confirmed
        appointment.mark_confirmed()
        self.assertEqual(appointment.status, "confirmed")

        # Test mark_in_progress
        appointment.mark_in_progress()
        self.assertEqual(appointment.status, "in_progress")

        # Test mark_completed
        appointment.mark_completed()
        self.assertEqual(appointment.status, "completed")

        # Test mark_cancelled
        appointment = Appointment.objects.create(
            customer=self.user,
            service=self.service,
            specialist=self.specialist,
            shop=self.shop,
            start_time=self.start_time,
            end_time=self.end_time,
            status="scheduled",
        )

        appointment.mark_cancelled(self.user, "Test reason")
        self.assertEqual(appointment.status, "cancelled")
        self.assertEqual(appointment.cancelled_by, self.user)
        self.assertEqual(appointment.cancellation_reason, "Test reason")

        # Test mark_no_show
        appointment = Appointment.objects.create(
            customer=self.user,
            service=self.service,
            specialist=self.specialist,
            shop=self.shop,
            start_time=self.start_time,
            end_time=self.end_time,
            status="scheduled",
        )

        appointment.mark_no_show()
        self.assertEqual(appointment.status, "no_show")

        # Test mark_paid
        appointment.mark_paid("test-transaction-123")
        self.assertEqual(appointment.payment_status, "paid")
        self.assertEqual(appointment.transaction_id, "test-transaction-123")


class AppointmentReminderTest(TestCase):
    """Test cases for the AppointmentReminder model"""

    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create(phone_number="1234567890", user_type="customer")

        # Create test shop
        self.shop = Shop.objects.create(id=uuid.uuid4(), name="Test Shop", username="testshop")

        # Create test service
        self.service = Service.objects.create(
            id=uuid.uuid4(),
            name="Test Service",
            shop=self.shop,
            price=100.00,
            duration=60,
        )

        # Create test specialist
        self.specialist = Specialist.objects.create(id=uuid.uuid4())

        # Set up times for appointment
        self.start_time = timezone.now() + timedelta(days=1)
        self.end_time = self.start_time + timedelta(hours=1)

        # Create test appointment
        self.appointment = Appointment.objects.create(
            customer=self.user,
            service=self.service,
            specialist=self.specialist,
            shop=self.shop,
            start_time=self.start_time,
            end_time=self.end_time,
            status="scheduled",
        )

    def test_reminder_creation(self):
        """Test creating a reminder"""
        reminder = AppointmentReminder.objects.create(
            appointment=self.appointment,
            reminder_type="sms",
            scheduled_time=timezone.now() + timedelta(hours=2),
            content="Test reminder content",
        )

        self.assertIsNotNone(reminder.id)
        self.assertEqual(reminder.reminder_type, "sms")
        self.assertFalse(reminder.is_sent)
        self.assertIsNone(reminder.sent_at)

    def test_mark_sent(self):
        """Test marking a reminder as sent"""
        reminder = AppointmentReminder.objects.create(
            appointment=self.appointment,
            reminder_type="sms",
            scheduled_time=timezone.now() + timedelta(hours=2),
            content="Test reminder content",
        )

        reminder.mark_sent()

        self.assertTrue(reminder.is_sent)
        self.assertIsNotNone(reminder.sent_at)

        # Check if appointment was updated
        self.appointment.refresh_from_db()
        self.assertTrue(self.appointment.is_reminder_sent)


class MultiServiceBookingTest(TestCase):
    """Test cases for the MultiServiceBooking model"""

    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create(phone_number="1234567890", user_type="customer")

        # Create test shop
        self.shop = Shop.objects.create(id=uuid.uuid4(), name="Test Shop", username="testshop")

        # Create test service
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

        # Set up times for appointments
        self.start_time1 = timezone.now() + timedelta(days=1, hours=10)
        self.end_time1 = self.start_time1 + timedelta(hours=1)

        self.start_time2 = timezone.now() + timedelta(days=1, hours=14)
        self.end_time2 = self.start_time2 + timedelta(minutes=45)

        # Create test appointments
        self.appointment1 = Appointment.objects.create(
            customer=self.user,
            service=self.service1,
            specialist=self.specialist,
            shop=self.shop,
            start_time=self.start_time1,
            end_time=self.end_time1,
            status="scheduled",
            total_price=100.00,
        )

        self.appointment2 = Appointment.objects.create(
            customer=self.user,
            service=self.service2,
            specialist=self.specialist,
            shop=self.shop,
            start_time=self.start_time2,
            end_time=self.end_time2,
            status="scheduled",
            total_price=150.00,
        )

    def test_multi_booking_creation(self):
        """Test creating a multi-service booking"""
        multi_booking = MultiServiceBooking.objects.create(customer=self.user, shop=self.shop)

        multi_booking.appointments.add(self.appointment1)
        multi_booking.appointments.add(self.appointment2)

        self.assertIsNotNone(multi_booking.id)
        self.assertEqual(multi_booking.appointments.count(), 2)
        self.assertEqual(multi_booking.payment_status, "pending")

        # Test update_total_price method
        multi_booking.update_total_price()
        self.assertEqual(multi_booking.total_price, 250.00)

    def test_mark_paid(self):
        """Test marking a multi-service booking as paid"""
        multi_booking = MultiServiceBooking.objects.create(customer=self.user, shop=self.shop)

        multi_booking.appointments.add(self.appointment1)
        multi_booking.appointments.add(self.appointment2)

        # Test mark_paid method
        multi_booking.mark_paid("test-transaction-456")
        self.assertEqual(multi_booking.payment_status, "paid")
        self.assertEqual(multi_booking.transaction_id, "test-transaction-456")

        # Check if appointments were updated
        self.appointment1.refresh_from_db()
        self.appointment2.refresh_from_db()

        self.assertEqual(self.appointment1.payment_status, "paid")
        self.assertEqual(self.appointment1.transaction_id, "test-transaction-456")
        self.assertEqual(self.appointment2.payment_status, "paid")
        self.assertEqual(self.appointment2.transaction_id, "test-transaction-456")
