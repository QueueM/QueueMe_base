import random
import time

from locust import HttpUser, between, task

# Sample test data
SERVICES = ["service_id_1", "service_id_2", "service_id_3"]
SHOPS = ["shop_id_1", "shop_id_2", "shop_id_3"]
SPECIALISTS = ["specialist_id_1", "specialist_id_2", "specialist_id_3"]


class BookingUser(HttpUser):
    """
    Simulates user behavior for booking appointments
    """

    wait_time = between(1, 5)  # Wait between 1 and 5 seconds between tasks
    token = None  # Will store auth token after login

    def on_start(self):
        """Login before starting tests"""
        response = self.client.post(
            "/api/v1/auth/login/",
            json={
                "phone_number": f"+9665{random.randint(10000000, 99999999)}",
                "password": "test_password",
            },
        )
        if response.status_code == 200:
            self.token = response.json().get("token")
            self.client.headers.update({"Authorization": f"Token {self.token}"})
        else:
            # If login fails, create a test user
            phone = f"+9665{random.randint(10000000, 99999999)}"
            self.client.post(
                "/api/v1/auth/register/",
                json={"phone_number": phone, "password": "test_password"},
            )
            # Try login again
            response = self.client.post(
                "/api/v1/auth/login/",
                json={"phone_number": phone, "password": "test_password"},
            )
            if response.status_code == 200:
                self.token = response.json().get("token")
                self.client.headers.update({"Authorization": f"Token {self.token}"})

    @task(3)  # Weight 3 - most common action
    def browse_services(self):
        """Browse available services at a shop"""
        shop_id = random.choice(SHOPS)
        self.client.get(f"/api/v1/services/?shop_id={shop_id}")

    @task(2)
    def check_availability(self):
        """Check service availability for booking"""
        shop_id = random.choice(SHOPS)
        service_id = random.choice(SERVICES)
        specialist_id = random.choice(SPECIALISTS)

        # Generate a random date in next 10 days
        date = time.strftime(
            "%Y-%m-%d", time.localtime(time.time() + random.randint(86400, 864000))
        )

        self.client.get(
            f"/api/v1/availability/?shop_id={shop_id}&service_id={service_id}"
            f"&specialist_id={specialist_id}&date={date}"
        )

    @task(1)
    def create_booking(self):
        """Create a new booking"""
        shop_id = random.choice(SHOPS)
        service_id = random.choice(SERVICES)
        specialist_id = random.choice(SPECIALISTS)

        # Create random appointment time
        date = time.strftime(
            "%Y-%m-%d", time.localtime(time.time() + random.randint(86400, 864000))
        )
        hour = random.randint(9, 16)
        minute = random.choice([0, 30])
        time_str = f"{hour:02d}:{minute:02d}"

        self.client.post(
            "/api/v1/bookings/",
            json={
                "shop_id": shop_id,
                "service_id": service_id,
                "specialist_id": specialist_id,
                "date": date,
                "time": time_str,
                "notes": "Load test booking",
            },
        )

    @task(1)
    def get_my_bookings(self):
        """View a user's booked appointments"""
        self.client.get("/api/v1/bookings/my-bookings/")

    @task(0.5)  # Weight 0.5 - less common action
    def cancel_booking(self):
        """Cancel a booking"""
        # First get all bookings
        response = self.client.get("/api/v1/bookings/my-bookings/")

        if response.status_code == 200:
            bookings = response.json().get("bookings", [])
            # If there are any bookings, cancel one
            if bookings:
                booking_id = random.choice(bookings)["id"]
                self.client.post(
                    f"/api/v1/bookings/{booking_id}/cancel/",
                    json={"reason": "Load test cancellation"},
                )
