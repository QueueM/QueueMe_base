# apps/bookingapp/tests/test_services.py
import uuid
from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.bookingapp.models import Appointment, AppointmentReminder
from apps.bookingapp.services.availability_service import AvailabilityService
from apps.bookingapp.services.booking_service import BookingService
from apps.bookingapp.services.conflict_service import ConflictService
from apps.bookingapp.services.reminder_service import ReminderService
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop, ShopHours
from apps.specialistsapp.models import Specialist, SpecialistService

from .test_fix import create_test_shop


class AvailabilityServiceTest(TestCase):
    """Test cases for the AvailabilityService"""

    def setUp(self):
        """Set up test data"""
        # Create test shop using the helper
        self.shop = create_test_shop(name="Test Shop", username="testshop")

        # Create shop hours (open 9 AM to 5 PM all days)
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
        SpecialistService.objects.create(specialist=self.specialist, service=self.service)

        # Create specialist working hours (same as shop hours)
        from apps.specialistsapp.models import SpecialistWorkingHours

        for weekday in range(7):
            SpecialistWorkingHours.objects.create(
                specialist=self.specialist,
                weekday=weekday,
                from_hour=time(9, 0),
                to_hour=time(17, 0),
                is_off=False,
            )

        # Set up test user
        self.user = User.objects.create(phone_number="1234567890", user_type="customer")

        # Set up test date (tomorrow)
        self.test_date = timezone.now().date() + timedelta(days=1)

        # Appointment time range for tests
        self.start_time = datetime.combine(self.test_date, time(10, 0))
        self.end_time = datetime.combine(self.test_date, time(11, 0))

        # Make timezone aware
        self.start_time = timezone.make_aware(self.start_time)
        self.end_time = timezone.make_aware(self.end_time)

    def test_get_service_availability(self):
        """Test getting service availability"""
        # Get availability
        availability = AvailabilityService.get_service_availability(
            service_id=self.service.id, date=self.test_date
        )

        # Should have multiple slots throughout the day
        self.assertTrue(len(availability) > 0)

        # Verify slot format
        self.assertIn("start", availability[0])
        self.assertIn("end", availability[0])
        self.assertIn("duration", availability[0])
        self.assertIn("buffer_before", availability[0])
        self.assertIn("buffer_after", availability[0])
        self.assertIn("specialist_id", availability[0])

        # Verify first slot should be around 9 AM (accounting for buffer)
        first_slot_time = datetime.strptime(availability[0]["start"], "%H:%M").time()
        self.assertEqual(first_slot_time.hour, 9)

        # Create a booking to test conflict handling
        start_time = datetime.combine(self.test_date, time(10, 0))
        end_time = datetime.combine(self.test_date, time(11, 0))

        # Make timezone aware
        start_time = timezone.make_aware(start_time)
        end_time = timezone.make_aware(end_time)

        Appointment.objects.create(
            customer=self.user,
            service=self.service,
            specialist=self.specialist,
            shop=self.shop,
            start_time=start_time,
            end_time=end_time,
            status="scheduled",
        )

        # Get availability again
        availability_after_booking = AvailabilityService.get_service_availability(
            service_id=self.service.id, date=self.test_date
        )

        # Should no longer have the 10 AM slot
        has_10am_slot = any(slot["start"] == "10:00" for slot in availability_after_booking)
        self.assertFalse(has_10am_slot)

    def test_is_specialist_available(self):
        """Test checking specialist availability"""
        # Check availability at 10 AM (should be available)
        is_available = AvailabilityService.is_specialist_available(
            specialist=self.specialist,
            date=self.test_date,
            start_time=time(10, 0),
            end_time=time(11, 0),
            buffer_before=5,
            buffer_after=5,
        )

        self.assertTrue(is_available)

        # Create a booking at 10 AM
        start_time = datetime.combine(self.test_date, time(10, 0))
        end_time = datetime.combine(self.test_date, time(11, 0))

        # Make timezone aware
        start_time = timezone.make_aware(start_time)
        end_time = timezone.make_aware(end_time)

        Appointment.objects.create(
            customer=self.user,
            service=self.service,
            specialist=self.specialist,
            shop=self.shop,
            start_time=start_time,
            end_time=end_time,
            status="scheduled",
        )

        # Check availability again (should be unavailable)
        is_available = AvailabilityService.is_specialist_available(
            specialist=self.specialist,
            date=self.test_date,
            start_time=time(10, 0),
            end_time=time(11, 0),
            buffer_before=5,
            buffer_after=5,
        )

        self.assertFalse(is_available)

        # Check availability for 11:30 AM (should be available)
        is_available = AvailabilityService.is_specialist_available(
            specialist=self.specialist,
            date=self.test_date,
            start_time=time(11, 30),
            end_time=time(12, 30),
            buffer_before=5,
            buffer_after=5,
        )

        self.assertTrue(is_available)


class BookingServiceTest(TestCase):
    """Test cases for the BookingService"""

    def setUp(self):
        """Set up test data"""
        # Similar setup as AvailabilityServiceTest
        # Create test shop
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
        SpecialistService.objects.create(specialist=self.specialist, service=self.service)

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

        # Set up test user
        self.user = User.objects.create(phone_number="1234567890", user_type="customer")

        # Set up test date (tomorrow)
        self.test_date = timezone.now().date() + timedelta(days=1)
        self.test_date_str = self.test_date.strftime("%Y-%m-%d")

    @patch(
        "apps.notificationsapp.services.notification_service.NotificationService.send_appointment_confirmation"
    )
    def test_create_appointment(self, mock_send_confirmation):
        """Test creating an appointment"""
        # Create appointment
        appointment = BookingService.create_appointment(
            customer_id=self.user.id,
            service_id=self.service.id,
            specialist_id=self.specialist.id,
            start_time_str="10:00",
            date_str=self.test_date_str,
            notes="Test appointment",
        )

        # Verify appointment created
        self.assertIsNotNone(appointment.id)
        self.assertEqual(appointment.customer, self.user)
        self.assertEqual(appointment.service, self.service)
        self.assertEqual(appointment.specialist, self.specialist)
        self.assertEqual(appointment.shop, self.shop)
        self.assertEqual(appointment.status, "scheduled")
        self.assertEqual(appointment.notes, "Test appointment")

        # Check start and end times
        expected_start = datetime.combine(self.test_date, time(10, 0))
        expected_start = timezone.make_aware(expected_start)
        self.assertEqual(appointment.start_time, expected_start)

        expected_end = expected_start + timedelta(minutes=60)
        self.assertEqual(appointment.end_time, expected_end)

        # Check price, buffer, duration
        self.assertEqual(appointment.total_price, self.service.price)
        self.assertEqual(appointment.buffer_before, self.service.buffer_before)
        self.assertEqual(appointment.buffer_after, self.service.buffer_after)
        self.assertEqual(appointment.duration, self.service.duration)

        # Check reminders created
        reminders = appointment.reminders.all()
        self.assertEqual(reminders.count(), 2)

        # Check notification sent
        mock_send_confirmation.assert_called_once_with(appointment)

    @patch(
        "apps.notificationsapp.services.notification_service.NotificationService.send_appointment_cancellation"
    )
    def test_cancel_appointment(self, mock_send_cancellation):
        """Test cancelling an appointment"""
        # Create an appointment first
        start_time = datetime.combine(self.test_date, time(10, 0))
        end_time = datetime.combine(self.test_date, time(11, 0))

        # Make timezone aware
        start_time = timezone.make_aware(start_time)
        end_time = timezone.make_aware(end_time)

        appointment = Appointment.objects.create(
            customer=self.user,
            service=self.service,
            specialist=self.specialist,
            shop=self.shop,
            start_time=start_time,
            end_time=end_time,
            status="scheduled",
        )

        # Create some reminders
        AppointmentReminder.objects.create(
            appointment=appointment,
            reminder_type="sms",
            scheduled_time=start_time - timedelta(days=1),
            is_sent=False,
        )

        # Cancel the appointment
        cancelled = BookingService.cancel_appointment(
            appointment_id=appointment.id,
            cancelled_by_id=self.user.id,
            reason="Test cancellation",
        )

        # Verify cancellation
        self.assertEqual(cancelled.status, "cancelled")
        self.assertEqual(cancelled.cancelled_by, self.user)
        self.assertEqual(cancelled.cancellation_reason, "Test cancellation")

        # Check reminders deleted
        self.assertEqual(appointment.reminders.filter(is_sent=False).count(), 0)

        # Check notification sent
        mock_send_cancellation.assert_called_once_with(appointment)


class ConflictServiceTest(TestCase):
    """Test cases for the ConflictService"""

    def setUp(self):
        """Set up test data"""
        # Similar setup as previous tests
        # Create test shop
        self.shop = create_test_shop(name="Test Shop", username="testshop")

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

        # Link specialist to service
        SpecialistService.objects.create(specialist=self.specialist, service=self.service)

        # Set up test user
        self.user = User.objects.create(phone_number="1234567890", user_type="customer")

        # Set up test date (tomorrow)
        self.test_date = timezone.now().date() + timedelta(days=1)

        # Create test appointment
        start_time = datetime.combine(self.test_date, time(10, 0))
        end_time = datetime.combine(self.test_date, time(11, 0))

        # Make timezone aware
        self.start_time = timezone.make_aware(start_time)
        self.end_time = timezone.make_aware(end_time)

        self.appointment = Appointment.objects.create(
            customer=self.user,
            service=self.service,
            specialist=self.specialist,
            shop=self.shop,
            start_time=self.start_time,
            end_time=self.end_time,
            status="scheduled",
        )

    def test_check_appointment_conflict(self):
        """Test checking for appointment conflicts"""
        # Check conflict at same time
        has_conflict = ConflictService.check_appointment_conflict(
            specialist_id=self.specialist.id,
            start_time=self.start_time,
            end_time=self.end_time,
        )

        self.assertTrue(has_conflict)

        # Check conflict with overlap at start
        has_conflict = ConflictService.check_appointment_conflict(
            specialist_id=self.specialist.id,
            start_time=self.start_time - timedelta(minutes=30),
            end_time=self.start_time + timedelta(minutes=30),
        )

        self.assertTrue(has_conflict)

        # Check conflict with overlap at end
        has_conflict = ConflictService.check_appointment_conflict(
            specialist_id=self.specialist.id,
            start_time=self.end_time - timedelta(minutes=30),
            end_time=self.end_time + timedelta(minutes=30),
        )

        self.assertTrue(has_conflict)

        # Check no conflict before
        has_conflict = ConflictService.check_appointment_conflict(
            specialist_id=self.specialist.id,
            start_time=self.start_time - timedelta(hours=2),
            end_time=self.start_time - timedelta(hours=1),
        )

        self.assertFalse(has_conflict)

        # Check no conflict after
        has_conflict = ConflictService.check_appointment_conflict(
            specialist_id=self.specialist.id,
            start_time=self.end_time + timedelta(hours=1),
            end_time=self.end_time + timedelta(hours=2),
        )

        self.assertFalse(has_conflict)

        # Check excluding current appointment
        has_conflict = ConflictService.check_appointment_conflict(
            specialist_id=self.specialist.id,
            start_time=self.start_time,
            end_time=self.end_time,
            exclude_appointment_id=self.appointment.id,
        )

        self.assertFalse(has_conflict)

    def test_check_multi_appointment_conflicts(self):
        """Test checking for conflicts between multiple appointments"""
        # Create two non-conflicting appointments
        appt1 = {
            "specialist_id": str(self.specialist.id),
            "start_time": self.start_time - timedelta(hours=2),
            "end_time": self.start_time - timedelta(hours=1),
        }

        appt2 = {
            "specialist_id": str(self.specialist.id),
            "start_time": self.end_time + timedelta(hours=1),
            "end_time": self.end_time + timedelta(hours=2),
        }

        conflicts = ConflictService.check_multi_appointment_conflicts([appt1, appt2])
        self.assertEqual(len(conflicts), 0)

        # Create two conflicting appointments
        appt3 = {
            "specialist_id": str(self.specialist.id),
            "start_time": self.start_time - timedelta(minutes=30),
            "end_time": self.start_time + timedelta(minutes=30),
        }

        conflicts = ConflictService.check_multi_appointment_conflicts([appt1, appt3])
        self.assertEqual(len(conflicts), 0)  # Still no conflicts between these two

        # Create two appointments for same specialist with overlap
        appt4 = {
            "specialist_id": str(self.specialist.id),
            "start_time": self.start_time - timedelta(hours=2),
            "end_time": self.start_time - timedelta(hours=1),
        }

        appt5 = {
            "specialist_id": str(self.specialist.id),
            "start_time": self.start_time - timedelta(minutes=90),
            "end_time": self.start_time - timedelta(minutes=30),
        }

        conflicts = ConflictService.check_multi_appointment_conflicts([appt4, appt5])
        self.assertEqual(len(conflicts), 1)  # One conflict pair


class ReminderServiceTest(TestCase):
    """Test cases for the ReminderService"""

    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create(phone_number="1234567890", user_type="customer")

        # Create test shop
        self.shop = create_test_shop(name="Test Shop", username="testshop")

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

        # Set up test date (tomorrow)
        self.test_date = timezone.now().date() + timedelta(days=1)

        # Create test appointment
        start_time = datetime.combine(self.test_date, time(10, 0))
        end_time = datetime.combine(self.test_date, time(11, 0))

        # Make timezone aware
        self.start_time = timezone.make_aware(start_time)
        self.end_time = timezone.make_aware(end_time)

        self.appointment = Appointment.objects.create(
            customer=self.user,
            service=self.service,
            specialist=self.specialist,
            shop=self.shop,
            start_time=self.start_time,
            end_time=self.end_time,
            status="scheduled",
        )

    def test_create_appointment_reminders(self):
        """Test creating standard appointment reminders"""
        # Create reminders
        reminders = ReminderService.create_appointment_reminders(self.appointment)

        # Should have created 2 reminders
        self.assertEqual(len(reminders), 2)

        # Verify first reminder (1 day before)
        day_reminder = reminders[0]
        self.assertEqual(day_reminder.reminder_type, "sms")
        self.assertEqual(
            day_reminder.scheduled_time.date(),
            self.appointment.start_time.date() - timedelta(days=1),
        )

        # Verify second reminder (1 hour before)
        hour_reminder = reminders[1]
        self.assertEqual(hour_reminder.reminder_type, "push")
        scheduled_hour = hour_reminder.scheduled_time.hour
        appointment_hour = self.appointment.start_time.hour

        # Allow for DST differences
        self.assertTrue(
            scheduled_hour == appointment_hour - 1
            or (appointment_hour == 0 and scheduled_hour == 23)
        )

    @patch(
        "apps.notificationsapp.services.notification_service.NotificationService.send_sms_reminder"
    )
    @patch(
        "apps.notificationsapp.services.notification_service.NotificationService.send_push_reminder"
    )
    def test_process_due_reminders(self, mock_send_push, mock_send_sms):
        """Test processing due reminders"""
        # Create a due reminder
        now = timezone.now()

        due_reminder = AppointmentReminder.objects.create(
            appointment=self.appointment,
            reminder_type="sms",
            scheduled_time=now - timedelta(minutes=5),
            is_sent=False,
            content="Test reminder content",
        )

        # Create a future reminder
        future_reminder = AppointmentReminder.objects.create(
            appointment=self.appointment,
            reminder_type="push",
            scheduled_time=now + timedelta(hours=1),
            is_sent=False,
            content="Future reminder content",
        )

        # Process reminders
        count = ReminderService.process_due_reminders()

        # Should have processed 1 reminder
        self.assertEqual(count, 1)

        # Check SMS reminder was sent
        mock_send_sms.assert_called_once_with(due_reminder)
        mock_send_push.assert_not_called()

        # Verify reminder marked as sent
        due_reminder.refresh_from_db()
        self.assertTrue(due_reminder.is_sent)
        self.assertIsNotNone(due_reminder.sent_at)

        # Verify future reminder not processed
        future_reminder.refresh_from_db()
        self.assertFalse(future_reminder.is_sent)
        self.assertIsNone(future_reminder.sent_at)
