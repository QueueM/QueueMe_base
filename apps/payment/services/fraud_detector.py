import logging
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from ..constants import (
    HIGH_RISK_THRESHOLD,
    LARGE_AMOUNT_RISK_SCORE,
    LARGE_AMOUNT_THRESHOLD,
    NEW_PAYMENT_METHOD_RISK_SCORE,
    UNUSUAL_TRANSACTION_THRESHOLD,
    VELOCITY_RISK_SCORE,
    VELOCITY_THRESHOLD,
)
from ..models import FraudDetectionRule, Transaction

logger = logging.getLogger(__name__)


class FraudDetector:
    """
    Advanced fraud detection system for payment transactions
    """

    @staticmethod
    def assess_fraud_risk(transaction):
        """
        Assess fraud risk for a transaction

        Args:
            transaction: Transaction object

        Returns:
            dict: Risk assessment with score and flagged factors
        """
        # Get transaction details
        user_id = transaction.user_id
        amount = transaction.amount
        payment_method = transaction.payment_method
        # unused_unused_payment_type = transaction.payment_type
        device_fingerprint = transaction.device_fingerprint
        ip_address = transaction.ip_address

        # Get customer history (past 90 days)
        start_date = timezone.now() - timedelta(days=90)
        customer_history = Transaction.objects.filter(
            user_id=user_id, created_at__gte=start_date
        )

        # Initialize risk score and flagged factors
        risk_score = 0
        flagged_factors = []

        # 1. Amount factor (unusually large amounts are suspicious)
        avg_amount = customer_history.exclude(id=transaction.id).values_list(
            "amount", flat=True
        )
        if avg_amount:
            avg_transaction_amount = sum(avg_amount) / len(avg_amount)

            if amount > max(avg_transaction_amount * 5, LARGE_AMOUNT_THRESHOLD):
                risk_score += LARGE_AMOUNT_RISK_SCORE
                flagged_factors.append("unusual_amount")

            if amount > UNUSUAL_TRANSACTION_THRESHOLD:
                risk_score += 0.2
                flagged_factors.append("very_large_amount")

        # 2. New payment method factor
        if payment_method:
            # Check if this is a newly added payment method
            if payment_method.created_at >= timezone.now() - timedelta(days=7):
                risk_score += NEW_PAYMENT_METHOD_RISK_SCORE
                flagged_factors.append("new_payment_method")

            # Check payment method usage history
            method_usage = customer_history.filter(
                payment_method=payment_method
            ).count()
            if method_usage == 0:
                risk_score += 0.1
                flagged_factors.append("first_use_of_payment_method")
        else:
            # Guest checkout or new method
            risk_score += 0.15
            flagged_factors.append("guest_checkout")

        # 3. Device factor
        if device_fingerprint:
            device_usage = customer_history.filter(
                device_fingerprint=device_fingerprint
            ).count()
            if device_usage == 0:
                risk_score += 0.2
                flagged_factors.append("new_device")

        # 4. Velocity factor (many transactions in short time)
        recent_window = timezone.now() - timedelta(hours=1)
        recent_transactions = customer_history.filter(
            created_at__gte=recent_window
        ).count()

        if recent_transactions > VELOCITY_THRESHOLD:
            risk_score += VELOCITY_RISK_SCORE
            flagged_factors.append("high_velocity")

        # 5. Location factor
        if ip_address:
            # Check if IP address has been used before by this user
            ip_usage = customer_history.filter(ip_address=ip_address).count()
            if ip_usage == 0:
                risk_score += 0.2
                flagged_factors.append("new_location")

            # Here you would integrate with a geolocation service to check
            # if the IP location makes sense for this user

        # 6. Apply active fraud detection rules from database
        for rule in FraudDetectionRule.objects.filter(is_active=True):
            if FraudDetector._evaluate_rule(rule, transaction, customer_history):
                risk_score += float(rule.risk_score)
                flagged_factors.append(rule.rule_type)

        # Determine risk level based on score
        risk_level = (
            "high"
            if risk_score >= HIGH_RISK_THRESHOLD
            else "medium" if risk_score >= 0.3 else "low"
        )

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "flagged_factors": flagged_factors,
        }

    @staticmethod
    def _evaluate_rule(rule, transaction, history):
        """
        Evaluate a fraud detection rule against transaction

        Args:
            rule: FraudDetectionRule object
            transaction: Transaction to evaluate
            history: User's transaction history

        Returns:
            bool: Whether rule was triggered
        """
        # This is where you'd implement rule evaluation logic
        # Based on the rule_type and parameters

        rule_type = rule.rule_type
        params = rule.parameters

        if rule_type == "amount_threshold":
            threshold = params.get("threshold", 5000)
            return transaction.amount > threshold

        elif rule_type == "time_of_day":
            high_risk_start = params.get("start_hour", 0)
            high_risk_end = params.get("end_hour", 5)
            current_hour = timezone.now().hour
            return high_risk_start <= current_hour < high_risk_end

        elif rule_type == "multiple_countries":
            # Would require IP geolocation data
            return False

        elif rule_type == "payment_type_mismatch":
            # Check if user suddenly switched payment types
            usual_types = (
                history.values("payment_type")
                .annotate(count=Count("payment_type"))
                .order_by("-count")
            )

            if (
                usual_types
                and usual_types[0]["payment_type"] != transaction.payment_type
            ):
                return True

        return False

    @staticmethod
    def is_high_risk_transaction(transaction):
        """
        Quick check if transaction is high risk

        Args:
            transaction: Transaction to check

        Returns:
            bool: Whether transaction is high risk
        """
        assessment = FraudDetector.assess_fraud_risk(transaction)
        return assessment["risk_level"] == "high"
