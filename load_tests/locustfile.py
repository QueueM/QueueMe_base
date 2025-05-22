"""
Load testing script for QueueMe API using Locust.

Usage:
    - Install dependencies: pip install locust
    - Run: locust -f load_tests/locustfile.py --host=https://api.queueme.net
"""

import random
import time

from locust import HttpUser, between, tag, task


class QueueMeUser(HttpUser):
    """
    Base user class for QueueMe load testing.

    This simulates a user interacting with the QueueMe API.
    """

    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks

    # User credentials for testing
    phone_number = None
    access_token = None
    refresh_token = None
    user_id = None
    shop_id = None
    service_id = None
    booking_id = None

    def on_start(self):
        """
        Initialize user session before tests begin.

        This simulates a user logging in and setting up their session.
        """
        # Generate a random phone number for this user
        self.phone_number = f"+9665{random.randint(10000000, 99999999)}"

        # Request OTP
        self.request_otp()

        # Verify OTP (simulated) and get tokens
        self.verify_otp()

        # Get user details
        self.get_user_details()

        # Add some randomness to create separate user behaviors
        self.user_type = random.choice(["customer", "business"])

        if self.user_type == "business":
            self.get_shop_details()

    def request_otp(self):
        """Request an OTP for authentication."""
        response = self.client.post(
            "/api/v1/auth/request-otp/", json={"phone_number": self.phone_number}
        )

        if response.status_code != 200:
            self.environment.events.request_failure.fire(
                request_type="POST",
                name="Request OTP",
                response_time=0,
                exception=Exception(f"Failed to request OTP: {response.text}"),
            )

    def verify_otp(self):
        """
        Simulate OTP verification.

        In a real test, we would use a real OTP, but for load testing
        we use a direct token endpoint with a simulated OTP.
        """
        # For load testing purposes, we use a test endpoint that accepts any OTP
        response = self.client.post(
            "/api/v1/auth/verify-otp/",
            json={
                "phone_number": self.phone_number,
                "otp_code": "123456",
            },  # Test OTP code
        )

        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get("access")
            self.refresh_token = data.get("refresh")

            # Set the Authorization header for future requests
            self.client.headers.update({"Authorization": f"Bearer {self.access_token}"})
        else:
            self.environment.events.request_failure.fire(
                request_type="POST",
                name="Verify OTP",
                response_time=0,
                exception=Exception(f"Failed to verify OTP: {response.text}"),
            )

    def get_user_details(self):
        """Get user details after authentication."""
        response = self.client.get("/api/v1/auth/me/")

        if response.status_code == 200:
            data = response.json()
            self.user_id = data.get("id")
        else:
            self.environment.events.request_failure.fire(
                request_type="GET",
                name="Get User Details",
                response_time=0,
                exception=Exception(f"Failed to get user details: {response.text}"),
            )

    def get_shop_details(self):
        """Get shop details for business users."""
        response = self.client.get("/api/v1/shops/")

        if response.status_code == 200:
            data = response.json()
            if data.get("results") and len(data["results"]) > 0:
                self.shop_id = data["results"][0].get("id")

                # Get services for this shop
                self.get_shop_services()
        else:
            self.environment.events.request_failure.fire(
                request_type="GET",
                name="Get Shop Details",
                response_time=0,
                exception=Exception(f"Failed to get shop details: {response.text}"),
            )

    def get_shop_services(self):
        """Get services for a shop."""
        if not self.shop_id:
            return

        response = self.client.get(f"/api/v1/shops/{self.shop_id}/services/")

        if response.status_code == 200:
            data = response.json()
            if data.get("results") and len(data["results"]) > 0:
                self.service_id = data["results"][0].get("id")
        else:
            self.environment.events.request_failure.fire(
                request_type="GET",
                name="Get Shop Services",
                response_time=0,
                exception=Exception(f"Failed to get shop services: {response.text}"),
            )

    def refresh_auth_token(self):
        """Refresh the authentication token."""
        if not self.refresh_token:
            return

        response = self.client.post(
            "/api/v1/auth/token/refresh/", json={"refresh": self.refresh_token}
        )

        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get("access")

            # Update the Authorization header
            self.client.headers.update({"Authorization": f"Bearer {self.access_token}"})
        else:
            self.environment.events.request_failure.fire(
                request_type="POST",
                name="Refresh Token",
                response_time=0,
                exception=Exception(f"Failed to refresh token: {response.text}"),
            )

    @tag("common")
    @task(10)
    def view_shops(self):
        """View list of shops."""
        self.client.get("/api/v1/shops/?page=1&page_size=10")

    @tag("common")
    @task(5)
    def search_shops(self):
        """Search for shops."""
        search_terms = ["salon", "barber", "spa", "beauty", "nail", "hair", "massage"]
        term = random.choice(search_terms)
        self.client.get(f"/api/v1/shops/search/?q={term}&page=1&page_size=10")

    @tag("common")
    @task(3)
    def view_shop_details(self):
        """View details of a specific shop."""
        # Use a predefined list of shop IDs for testing
        shop_ids = ["1", "2", "3", "4", "5"]
        shop_id = random.choice(shop_ids)
        self.client.get(f"/api/v1/shops/{shop_id}/")

    @tag("common")
    @task(2)
    def view_services(self):
        """View services of a shop."""
        # Use a predefined list of shop IDs for testing
        shop_ids = ["1", "2", "3", "4", "5"]
        shop_id = random.choice(shop_ids)
        self.client.get(f"/api/v1/shops/{shop_id}/services/")

    @tag("customer")
    @task(1)
    def create_booking(self):
        """Create a booking as a customer."""
        if self.user_type != "customer" or not self.user_id:
            return

        # Use predefined IDs for testing
        shop_id = "1"
        service_id = "1"
        specialist_id = "1"

        # Random date in the next 7 days
        days_ahead = random.randint(1, 7)
        random.choice([10, 11, 12, 13, 14, 15, 16, 17])
        random.choice([0, 30])

        now = time.time()
        booking_time = time.strftime(
            "%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(now + (days_ahead * 86400))
        )

        data = {
            "service": service_id,
            "specialist": specialist_id,
            "date": booking_time,
            "notes": "Load test booking",
        }

        response = self.client.post(f"/api/v1/shops/{shop_id}/bookings/", json=data)

        if response.status_code == 201:
            booking_data = response.json()
            self.booking_id = booking_data.get("id")
        else:
            self.environment.events.request_failure.fire(
                request_type="POST",
                name="Create Booking",
                response_time=0,
                exception=Exception(f"Failed to create booking: {response.text}"),
            )

    @tag("customer")
    @task(2)
    def view_bookings(self):
        """View customer bookings."""
        if self.user_type != "customer" or not self.user_id:
            return

        self.client.get("/api/v1/bookings/")

    @tag("business")
    @task(3)
    def view_shop_bookings(self):
        """View bookings for a shop (business users)."""
        if self.user_type != "business" or not self.shop_id:
            return

        self.client.get(f"/api/v1/shops/{self.shop_id}/bookings/")

    @tag("business")
    @task(1)
    def view_shop_queue(self):
        """View current queue for a shop (business users)."""
        if self.user_type != "business" or not self.shop_id:
            return

        self.client.get(f"/api/v1/shops/{self.shop_id}/queue/")

    @tag("auth")
    @task(1)
    def refresh_token_task(self):
        """Task to refresh the auth token periodically."""
        self.refresh_auth_token()


class CustomerUser(QueueMeUser):
    """
    User class that simulates customer behavior.

    This user type focuses on booking services, viewing shops, etc.
    """

    def on_start(self):
        """Set up as a customer user."""
        super().on_start()
        self.user_type = "customer"

    # All tasks are inherited from the base class


class BusinessUser(QueueMeUser):
    """
    User class that simulates business owner behavior.

    This user type focuses on managing bookings, viewing queues, etc.
    """

    def on_start(self):
        """Set up as a business user."""
        super().on_start()
        self.user_type = "business"
        self.get_shop_details()

    # All tasks are inherited from the base class
