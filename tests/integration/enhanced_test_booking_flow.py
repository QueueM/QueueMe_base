"""
End-to-end booking flow tests for QueueMe backend

This module provides comprehensive test coverage for the complete booking flow,
from user authentication to appointment creation and payment processing.
"""

import json
from datetime import datetime, timedelta
from unittest import mock

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.authapp.models import OTP, User
from apps.bookingapp.models import BookingSlot
from apps.companiesapp.models import Branch, Company
from apps.employeeapp.models import Employee
from apps.payment.models import PaymentMethod
from apps.serviceapp.models import Service
from apps.specialistsapp.models import Specialist


class EndToEndBookingFlowTest(TestCase):
    """
    End-to-end test cases for the complete booking flow.

    This test suite provides comprehensive coverage for:
    - User authentication and verification
    - Service discovery and selection
    - Specialist and time slot selection
    - Appointment creation
    - Payment processing
    - Appointment confirmation and updates
    """

    def setUp(self):
        """Set up test environment with all required entities"""
        self.client = Client()

        # Create test user
        self.user = User.objects.create(
            phone_number="966501234567",
            email="customer@example.com",
            first_name="Test",
            last_name="Customer",
            user_type="customer",
            is_verified=True,
            profile_completed=True,
        )
        self.user.set_password("testpassword")
        self.user.save()

        # Create company and branch
        self.company = Company.objects.create(
            name="Test Salon",
            description="A test salon for booking flow tests",
            logo="test_logo.png",
            status="active",
            is_verified=True,
        )

        self.branch = Branch.objects.create(
            company=self.company,
            name="Main Branch",
            address="123 Test Street",
            city="Test City",
            latitude=24.7136,
            longitude=46.6753,  # Riyadh coordinates
            status="active",
        )

        # Create services
        self.service = Service.objects.create(
            company=self.company,
            name="Haircut",
            description="Standard haircut service",
            duration=30,  # 30 minutes
            price=100.00,
            status="active",
        )

        # Create specialist and employee
        self.employee = Employee.objects.create(
            company=self.company,
            branch=self.branch,
            first_name="Test",
            last_name="Specialist",
            email="specialist@example.com",
            phone_number="966509876543",
            status="active",
        )

        self.specialist = Specialist.objects.create(
            employee=self.employee, bio="Experienced hair stylist", status="active"
        )

        # Add service to specialist
        self.specialist.services.add(self.service)

        # Create booking slots for the next 7 days
        start_date = timezone.now().date()
        for day in range(7):
            date = start_date + timedelta(days=day)
            # Create slots from 9 AM to 5 PM
            for hour in range(9, 17):
                start_time = datetime.combine(date, datetime.min.time()) + timedelta(
                    hours=hour
                )
                end_time = start_time + timedelta(minutes=30)

                BookingSlot.objects.create(
                    specialist=self.specialist,
                    branch=self.branch,
                    start_time=timezone.make_aware(start_time),
                    end_time=timezone.make_aware(end_time),
                    is_available=True,
                    status="active",
                )

        # Create payment method for the user
        self.payment_method = PaymentMethod.objects.create(
            user=self.user,
            type="creditcard",
            token="tok_test_valid",
            last_digits="1234",
            is_default=True,
        )

        # Set up API key patch for Moyasar
        self.moyasar_api_keys_patcher = mock.patch(
            "apps.payment.services.moyasar_service.settings.MOYASAR_API_KEYS",
            {
                "merchant": "sk_test_merchant",
                "subscription": "sk_test_subscription",
                "ads": "sk_test_ads",
            },
        )
        self.moyasar_api_keys_patcher.start()
        self.addCleanup(self.moyasar_api_keys_patcher.stop)

    def test_complete_booking_flow_with_saved_card(self):
        """Test the complete booking flow from authentication to confirmation using a saved card"""
        # Step 1: User Authentication
        login_data = {"phone_number": "966501234567", "password": "testpassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.json().get("access")
        self.assertIsNotNone(token)

        # Set authorization header for subsequent requests
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        # Step 2: Browse companies and services
        response = self.client.get(reverse("api:companies:list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        companies = response.json().get("results", [])
        self.assertTrue(len(companies) > 0)

        # Get company details
        response = self.client.get(
            reverse("api:companies:detail", kwargs={"pk": str(self.company.id)})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Step 3: Browse services
        response = self.client.get(
            reverse("api:services:list"), {"company_id": str(self.company.id)}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        services = response.json().get("results", [])
        self.assertTrue(len(services) > 0)

        # Step 4: Select service and get specialists
        response = self.client.get(
            reverse("api:specialists:list"), {"service_id": str(self.service.id)}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        specialists = response.json().get("results", [])
        self.assertTrue(len(specialists) > 0)

        # Step 5: Get available slots for the specialist
        tomorrow = timezone.now().date() + timedelta(days=1)
        response = self.client.get(
            reverse("api:booking:available_slots"),
            {
                "specialist_id": str(self.specialist.id),
                "service_id": str(self.service.id),
                "date": tomorrow.strftime("%Y-%m-%d"),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slots = response.json().get("slots", [])
        self.assertTrue(len(slots) > 0)

        # Select the first available slot
        selected_slot = slots[0]

        # Step 6: Create appointment
        appointment_data = {
            "service_id": str(self.service.id),
            "specialist_id": str(self.specialist.id),
            "branch_id": str(self.branch.id),
            "slot_id": selected_slot["id"],
            "date": tomorrow.strftime("%Y-%m-%d"),
            "start_time": selected_slot["start_time"],
            "end_time": selected_slot["end_time"],
            "notes": "Test appointment for end-to-end flow",
        }

        response = self.client.post(
            reverse("api:booking:create"),
            data=json.dumps(appointment_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        appointment_id = response.json().get("id")
        self.assertIsNotNone(appointment_id)

        # Step 7: Process payment with saved card
        with mock.patch("requests.post") as mock_post:
            # Mock successful payment response
            mock_post.return_value = mock.Mock(
                status_code=200,
                json=lambda: {
                    "id": "test_payment_id",
                    "status": "initiated",
                    "amount": 10000,  # 100.00 SAR in halalas
                    "source": {"type": "creditcard"},
                },
            )

            payment_data = {
                "appointment_id": appointment_id,
                "payment_method": "saved_card",
                "payment_method_id": str(self.payment_method.id),
            }

            response = self.client.post(
                reverse("api:payment:process"),
                data=json.dumps(payment_data),
                content_type="application/json",
            )

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            transaction_id = response.json().get("transaction_id")
            self.assertIsNotNone(transaction_id)

        # Step 8: Verify payment status
        with mock.patch("requests.get") as mock_get:
            # Mock successful payment verification
            mock_get.return_value = mock.Mock(
                status_code=200,
                json=lambda: {
                    "id": transaction_id,
                    "status": "paid",
                    "amount": 10000,
                    "source": {"type": "creditcard"},
                },
            )

            response = self.client.get(
                reverse("api:payment:verify", kwargs={"transaction_id": transaction_id})
            )

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            payment_status = response.json().get("status")
            self.assertEqual(payment_status, "succeeded")

        # Step 9: Check appointment status after payment
        response = self.client.get(
            reverse("api:booking:detail", kwargs={"pk": appointment_id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        appointment_status = response.json().get("status")
        self.assertEqual(appointment_status, "confirmed")

        # Step 10: Get user's upcoming appointments
        response = self.client.get(reverse("api:booking:upcoming"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        appointments = response.json().get("results", [])
        self.assertTrue(len(appointments) > 0)
        self.assertTrue(any(appt["id"] == appointment_id for appt in appointments))

    def test_booking_flow_with_new_card(self):
        """Test the booking flow using a new card for payment"""
        # Authenticate user
        login_data = {"phone_number": "966501234567", "password": "testpassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        token = response.json().get("access")
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        # Create appointment (simplified for this test)
        tomorrow = timezone.now().date() + timedelta(days=1)
        slots = BookingSlot.objects.filter(
            specialist=self.specialist, start_time__date=tomorrow, is_available=True
        )
        selected_slot = slots.first()

        appointment_data = {
            "service_id": str(self.service.id),
            "specialist_id": str(self.specialist.id),
            "branch_id": str(self.branch.id),
            "slot_id": str(selected_slot.id),
            "date": tomorrow.strftime("%Y-%m-%d"),
            "start_time": selected_slot.start_time.strftime("%H:%M:%S"),
            "end_time": selected_slot.end_time.strftime("%H:%M:%S"),
            "notes": "Test appointment with new card",
        }

        response = self.client.post(
            reverse("api:booking:create"),
            data=json.dumps(appointment_data),
            content_type="application/json",
        )

        appointment_id = response.json().get("id")

        # Process payment with new card
        with mock.patch("requests.post") as mock_post:
            # Mock successful payment response
            mock_post.return_value = mock.Mock(
                status_code=200,
                json=lambda: {
                    "id": "new_card_payment_id",
                    "status": "initiated",
                    "amount": 10000,
                    "source": {"type": "creditcard"},
                },
            )

            payment_data = {
                "appointment_id": appointment_id,
                "payment_method": "creditcard",
                "card_data": {"token": "tok_new_test_card", "save_card": True},
            }

            response = self.client.post(
                reverse("api:payment:process"),
                data=json.dumps(payment_data),
                content_type="application/json",
            )

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response.json().get("transaction_id")

        # Verify a new payment method was saved
        new_payment_methods = PaymentMethod.objects.filter(
            user=self.user, token="tok_new_test_card"
        )
        self.assertEqual(new_payment_methods.count(), 1)

    def test_booking_flow_with_failed_payment(self):
        """Test the booking flow with a failed payment"""
        # Authenticate user
        login_data = {"phone_number": "966501234567", "password": "testpassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        token = response.json().get("access")
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        # Create appointment (simplified for this test)
        tomorrow = timezone.now().date() + timedelta(days=1)
        slots = BookingSlot.objects.filter(
            specialist=self.specialist, start_time__date=tomorrow, is_available=True
        )
        selected_slot = slots.first()

        appointment_data = {
            "service_id": str(self.service.id),
            "specialist_id": str(self.specialist.id),
            "branch_id": str(self.branch.id),
            "slot_id": str(selected_slot.id),
            "date": tomorrow.strftime("%Y-%m-%d"),
            "start_time": selected_slot.start_time.strftime("%H:%M:%S"),
            "end_time": selected_slot.end_time.strftime("%H:%M:%S"),
            "notes": "Test appointment with failed payment",
        }

        response = self.client.post(
            reverse("api:booking:create"),
            data=json.dumps(appointment_data),
            content_type="application/json",
        )

        appointment_id = response.json().get("id")

        # Process payment that will fail
        with mock.patch("requests.post") as mock_post:
            # Mock failed payment response
            mock_post.return_value = mock.Mock(
                status_code=400,
                json=lambda: {
                    "message": "Invalid card",
                    "type": "invalid_request_error",
                },
            )

            payment_data = {
                "appointment_id": appointment_id,
                "payment_method": "creditcard",
                "card_data": {"token": "tok_invalid_card"},
            }

            response = self.client.post(
                reverse("api:payment:process"),
                data=json.dumps(payment_data),
                content_type="application/json",
            )

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Check appointment status after failed payment
        response = self.client.get(
            reverse("api:booking:detail", kwargs={"pk": appointment_id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        appointment_status = response.json().get("status")
        self.assertEqual(appointment_status, "pending_payment")

    def test_booking_flow_with_cancellation(self):
        """Test the booking flow with appointment cancellation"""
        # Authenticate user
        login_data = {"phone_number": "966501234567", "password": "testpassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        token = response.json().get("access")
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        # Create and pay for appointment
        tomorrow = timezone.now().date() + timedelta(days=1)
        slots = BookingSlot.objects.filter(
            specialist=self.specialist, start_time__date=tomorrow, is_available=True
        )
        selected_slot = slots.first()

        # Create appointment
        appointment_data = {
            "service_id": str(self.service.id),
            "specialist_id": str(self.specialist.id),
            "branch_id": str(self.branch.id),
            "slot_id": str(selected_slot.id),
            "date": tomorrow.strftime("%Y-%m-%d"),
            "start_time": selected_slot.start_time.strftime("%H:%M:%S"),
            "end_time": selected_slot.end_time.strftime("%H:%M:%S"),
            "notes": "Test appointment for cancellation",
        }

        response = self.client.post(
            reverse("api:booking:create"),
            data=json.dumps(appointment_data),
            content_type="application/json",
        )

        appointment_id = response.json().get("id")

        # Process payment
        with mock.patch("requests.post") as mock_post:
            mock_post.return_value = mock.Mock(
                status_code=200,
                json=lambda: {
                    "id": "cancel_test_payment_id",
                    "status": "initiated",
                    "amount": 10000,
                    "source": {"type": "creditcard"},
                },
            )

            payment_data = {
                "appointment_id": appointment_id,
                "payment_method": "saved_card",
                "payment_method_id": str(self.payment_method.id),
            }

            response = self.client.post(
                reverse("api:payment:process"),
                data=json.dumps(payment_data),
                content_type="application/json",
            )

            transaction_id = response.json().get("transaction_id")

        # Verify payment
        with mock.patch("requests.get") as mock_get:
            mock_get.return_value = mock.Mock(
                status_code=200,
                json=lambda: {
                    "id": transaction_id,
                    "status": "paid",
                    "amount": 10000,
                    "source": {"type": "creditcard"},
                },
            )

            self.client.get(
                reverse("api:payment:verify", kwargs={"transaction_id": transaction_id})
            )

        # Cancel the appointment
        cancellation_data = {"reason": "Test cancellation reason"}

        response = self.client.post(
            reverse("api:booking:cancel", kwargs={"pk": appointment_id}),
            data=json.dumps(cancellation_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check appointment status after cancellation
        response = self.client.get(
            reverse("api:booking:detail", kwargs={"pk": appointment_id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        appointment_status = response.json().get("status")
        self.assertEqual(appointment_status, "cancelled")

        # Verify the slot is available again
        slot = BookingSlot.objects.get(id=selected_slot.id)
        self.assertTrue(slot.is_available)

        # Check if refund was initiated
        with mock.patch("requests.post") as mock_post:
            mock_post.return_value = mock.Mock(
                status_code=200,
                json=lambda: {
                    "id": "refund_id",
                    "status": "initiated",
                    "amount": 10000,
                },
            )

            # Trigger refund processing (this would normally happen automatically)
            response = self.client.post(
                reverse("api:payment:refund"),
                data=json.dumps(
                    {
                        "appointment_id": appointment_id,
                        "reason": "Appointment cancelled",
                    }
                ),
                content_type="application/json",
            )

            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_authentication_flow_with_otp(self):
        """Test the authentication flow using OTP verification"""
        # Create a new user that needs verification
        new_user = User.objects.create(
            phone_number="966505555555",
            email="newuser@example.com",
            first_name="New",
            last_name="User",
            user_type="customer",
            is_verified=False,
        )

        # Request OTP
        otp_request_data = {"phone_number": "966505555555"}

        response = self.client.post(
            reverse("api:auth:request_otp"),
            data=json.dumps(otp_request_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get the OTP from the database (in a real scenario, this would be sent via SMS)
        otp = (
            OTP.objects.filter(phone_number="966505555555", is_used=False)
            .order_by("-created_at")
            .first()
        )

        self.assertIsNotNone(otp)

        # Verify OTP
        verify_data = {"phone_number": "966505555555", "code": otp.code}

        response = self.client.post(
            reverse("api:auth:verify_otp"),
            data=json.dumps(verify_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.json().get("access")
        self.assertIsNotNone(token)

        # Check that user is now verified
        new_user.refresh_from_db()
        self.assertTrue(new_user.is_verified)

        # Verify OTP is marked as used
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

    def test_concurrent_booking_handling(self):
        """Test handling of concurrent bookings for the same slot"""
        # Create two users
        user1 = self.user  # Already created in setUp

        user2 = User.objects.create(
            phone_number="966502222222",
            email="user2@example.com",
            first_name="Second",
            last_name="User",
            user_type="customer",
            is_verified=True,
            profile_completed=True,
        )
        user2.set_password("testpassword")
        user2.save()

        # Authenticate first user
        login_data = {"phone_number": "966501234567", "password": "testpassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        token1 = response.json().get("access")

        # Authenticate second user with a different client
        client2 = Client()
        response = client2.post(
            reverse("api:auth:login"),
            data=json.dumps(
                {"phone_number": "966502222222", "password": "testpassword"}
            ),
            content_type="application/json",
        )

        token2 = response.json().get("access")

        # Find an available slot
        tomorrow = timezone.now().date() + timedelta(days=1)
        slots = BookingSlot.objects.filter(
            specialist=self.specialist, start_time__date=tomorrow, is_available=True
        )
        selected_slot = slots.first()

        # First user creates an appointment
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token1}"
        appointment_data = {
            "service_id": str(self.service.id),
            "specialist_id": str(self.specialist.id),
            "branch_id": str(self.branch.id),
            "slot_id": str(selected_slot.id),
            "date": tomorrow.strftime("%Y-%m-%d"),
            "start_time": selected_slot.start_time.strftime("%H:%M:%S"),
            "end_time": selected_slot.end_time.strftime("%H:%M:%S"),
            "notes": "First user's appointment",
        }

        response = self.client.post(
            reverse("api:booking:create"),
            data=json.dumps(appointment_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Process payment for first user
        with mock.patch("requests.post") as mock_post:
            mock_post.return_value = mock.Mock(
                status_code=200,
                json=lambda: {
                    "id": "user1_payment_id",
                    "status": "initiated",
                    "amount": 10000,
                    "source": {"type": "creditcard"},
                },
            )

            payment_data = {
                "appointment_id": response.json().get("id"),
                "payment_method": "saved_card",
                "payment_method_id": str(self.payment_method.id),
            }

            response = self.client.post(
                reverse("api:payment:process"),
                data=json.dumps(payment_data),
                content_type="application/json",
            )

            transaction_id = response.json().get("transaction_id")

        # Verify payment for first user
        with mock.patch("requests.get") as mock_get:
            mock_get.return_value = mock.Mock(
                status_code=200,
                json=lambda: {
                    "id": transaction_id,
                    "status": "paid",
                    "amount": 10000,
                    "source": {"type": "creditcard"},
                },
            )

            self.client.get(
                reverse("api:payment:verify", kwargs={"transaction_id": transaction_id})
            )

        # Second user tries to book the same slot
        client2.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token2}"
        appointment_data["notes"] = "Second user's appointment"

        response = client2.post(
            reverse("api:booking:create"),
            data=json.dumps(appointment_data),
            content_type="application/json",
        )

        # Should fail because slot is no longer available
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("slot", response.json())

        # Verify the slot is still marked as unavailable
        selected_slot.refresh_from_db()
        self.assertFalse(selected_slot.is_available)


class EndToEndReschedulingTest(TestCase):
    """Test cases for appointment rescheduling flow"""

    def setUp(self):
        """Set up test environment"""
        # Reuse setup from the main test class
        self.booking_test = EndToEndBookingFlowTest()
        self.booking_test.setUp()

        # Use their client and user
        self.client = self.booking_test.client
        self.user = self.booking_test.user

        # Authenticate
        login_data = {"phone_number": "966501234567", "password": "testpassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        token = response.json().get("access")
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        # Create a confirmed appointment
        tomorrow = timezone.now().date() + timedelta(days=1)
        self.original_slot = BookingSlot.objects.filter(
            specialist=self.booking_test.specialist,
            start_time__date=tomorrow,
            is_available=True,
        ).first()

        # Create appointment
        appointment_data = {
            "service_id": str(self.booking_test.service.id),
            "specialist_id": str(self.booking_test.specialist.id),
            "branch_id": str(self.booking_test.branch.id),
            "slot_id": str(self.original_slot.id),
            "date": tomorrow.strftime("%Y-%m-%d"),
            "start_time": self.original_slot.start_time.strftime("%H:%M:%S"),
            "end_time": self.original_slot.end_time.strftime("%H:%M:%S"),
            "notes": "Appointment for rescheduling test",
        }

        response = self.client.post(
            reverse("api:booking:create"),
            data=json.dumps(appointment_data),
            content_type="application/json",
        )

        self.appointment_id = response.json().get("id")

        # Process payment
        with mock.patch("requests.post") as mock_post:
            mock_post.return_value = mock.Mock(
                status_code=200,
                json=lambda: {
                    "id": "reschedule_test_payment_id",
                    "status": "initiated",
                    "amount": 10000,
                    "source": {"type": "creditcard"},
                },
            )

            payment_data = {
                "appointment_id": self.appointment_id,
                "payment_method": "saved_card",
                "payment_method_id": str(self.booking_test.payment_method.id),
            }

            response = self.client.post(
                reverse("api:payment:process"),
                data=json.dumps(payment_data),
                content_type="application/json",
            )

            transaction_id = response.json().get("transaction_id")

        # Verify payment
        with mock.patch("requests.get") as mock_get:
            mock_get.return_value = mock.Mock(
                status_code=200,
                json=lambda: {
                    "id": transaction_id,
                    "status": "paid",
                    "amount": 10000,
                    "source": {"type": "creditcard"},
                },
            )

            self.client.get(
                reverse("api:payment:verify", kwargs={"transaction_id": transaction_id})
            )

        # Find a new slot for rescheduling
        day_after_tomorrow = timezone.now().date() + timedelta(days=2)
        self.new_slot = BookingSlot.objects.filter(
            specialist=self.booking_test.specialist,
            start_time__date=day_after_tomorrow,
            is_available=True,
        ).first()

    def test_appointment_rescheduling(self):
        """Test the complete appointment rescheduling flow"""
        # Verify original appointment is confirmed
        response = self.client.get(
            reverse("api:booking:detail", kwargs={"pk": self.appointment_id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json().get("status"), "confirmed")

        # Reschedule the appointment
        reschedule_data = {
            "slot_id": str(self.new_slot.id),
            "date": self.new_slot.start_time.date().strftime("%Y-%m-%d"),
            "start_time": self.new_slot.start_time.strftime("%H:%M:%S"),
            "end_time": self.new_slot.end_time.strftime("%H:%M:%S"),
            "reason": "Testing rescheduling flow",
        }

        response = self.client.post(
            reverse("api:booking:reschedule", kwargs={"pk": self.appointment_id}),
            data=json.dumps(reschedule_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify appointment has been rescheduled
        response = self.client.get(
            reverse("api:booking:detail", kwargs={"pk": self.appointment_id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        appointment_data = response.json()

        # Check new slot details
        self.assertEqual(appointment_data.get("slot_id"), str(self.new_slot.id))
        self.assertEqual(
            appointment_data.get("start_time"),
            self.new_slot.start_time.strftime("%H:%M:%S"),
        )

        # Verify original slot is available again
        self.original_slot.refresh_from_db()
        self.assertTrue(self.original_slot.is_available)

        # Verify new slot is no longer available
        self.new_slot.refresh_from_db()
        self.assertFalse(self.new_slot.is_available)

        # Check rescheduling history
        response = self.client.get(
            reverse(
                "api:booking:reschedule_history", kwargs={"pk": self.appointment_id}
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        history = response.json()

        self.assertTrue(len(history) > 0)
        self.assertEqual(history[0].get("reason"), "Testing rescheduling flow")
