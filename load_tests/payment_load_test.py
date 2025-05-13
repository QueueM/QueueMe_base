import json
import random
import uuid

from locust import HttpUser, between, task

# Sample test data
PAYMENT_METHODS = ["method_id_1", "method_id_2", "method_id_3"]
TRANSACTION_TYPES = ["booking", "subscription", "ad"]
PAYMENT_AMOUNTS = [50, 100, 150, 200, 250, 300, 350, 400]


class PaymentUser(HttpUser):
    """
    Simulates user behavior for payment processing
    """

    wait_time = between(2, 5)  # Wait between 2 and 5 seconds between tasks
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
    def process_payment(self):
        """Process a payment transaction"""
        payment_method_id = random.choice(PAYMENT_METHODS)
        amount = random.choice(PAYMENT_AMOUNTS)
        transaction_type = random.choice(TRANSACTION_TYPES)

        # Generate a unique idempotency key
        idempotency_key = str(uuid.uuid4())

        # Create payment
        self.client.post(
            "/api/v1/payments/process/",
            json={
                "payment_method_id": payment_method_id,
                "amount": amount,
                "currency": "SAR",
                "transaction_type": transaction_type,
                "description": f"Load test payment for {transaction_type}",
                "idempotency_key": idempotency_key,
            },
        )

    @task(2)
    def get_payment_methods(self):
        """Get user's saved payment methods"""
        self.client.get("/api/v1/payments/methods/")

    @task(1)
    def add_payment_method(self):
        """Add a new payment method"""
        # In production, this would include a token from a payment gateway
        # For testing, we'll just use a dummy token
        token = f"test_token_{random.randint(1000, 9999)}"

        self.client.post(
            "/api/v1/payments/methods/",
            json={
                "token": token,
                "payment_type": "card",
                "make_default": random.choice([True, False]),
            },
        )

    @task(1)
    def view_payment_history(self):
        """View payment transaction history"""
        self.client.get("/api/v1/payments/history/")

    @task(0.3)  # Weight 0.3 - less common action
    def refund_payment(self):
        """Request a refund for a transaction"""
        # First get payment history
        response = self.client.get("/api/v1/payments/history/")

        if response.status_code == 200:
            transactions = response.json().get("transactions", [])
            # Find a completed transaction to refund
            completed_transactions = [t for t in transactions if t.get("status") == "completed"]

            if completed_transactions:
                transaction = random.choice(completed_transactions)
                transaction_id = transaction.get("id")
                amount = float(transaction.get("amount")) / 2  # Request partial refund

                self.client.post(
                    f"/api/v1/payments/{transaction_id}/refund/",
                    json={"amount": amount, "reason": "Load test refund"},
                )
