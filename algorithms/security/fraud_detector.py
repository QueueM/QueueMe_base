import logging
from datetime import datetime, timedelta
from typing import Dict, List

logger = logging.getLogger(__name__)


class FraudDetector:
    """
    Advanced fraud detection algorithm for identifying potentially
    fraudulent transactions and suspicious account activity.

    This algorithm enhances security by:
    1. Analyzing transaction patterns and anomalies
    2. Detecting suspicious user behavior
    3. Implementing velocity checks
    4. Identifying unusual device or location activities
    5. Calculating risk scores for transactions
    """

    def __init__(
        self,
        transaction_velocity_threshold: int = 10,
        unusual_amount_factor: float = 3.0,
        location_change_threshold_km: float = 500,
        new_device_score: float = 0.7,
        new_payment_method_score: float = 0.6,
        high_risk_threshold: float = 0.8,
        medium_risk_threshold: float = 0.5,
    ):
        """
        Initialize the fraud detector with configurable parameters.

        Args:
            transaction_velocity_threshold: Max transactions in short period
            unusual_amount_factor: Multiple of average amount to flag as unusual
            location_change_threshold_km: Distance threshold for location change
            new_device_score: Risk score for new device usage
            new_payment_method_score: Risk score for new payment method
            high_risk_threshold: Score threshold for high risk transactions
            medium_risk_threshold: Score threshold for medium risk transactions
        """
        self.transaction_velocity_threshold = transaction_velocity_threshold
        self.unusual_amount_factor = unusual_amount_factor
        self.location_change_threshold_km = location_change_threshold_km
        self.new_device_score = new_device_score
        self.new_payment_method_score = new_payment_method_score
        self.high_risk_threshold = high_risk_threshold
        self.medium_risk_threshold = medium_risk_threshold

    def assess_transaction_risk(
        self, transaction: Dict, user_history: Dict, include_factors: bool = False
    ) -> Dict:
        """
        Assess the risk level of a transaction based on various factors.

        Args:
            transaction: Transaction object with fields:
                - id: Transaction ID
                - user_id: User making the transaction
                - amount: Transaction amount
                - payment_method_id: Payment method used
                - device_info: Device information
                - ip_address: IP address
                - location: Optional location data
                - timestamp: Transaction time
                - merchant_id: Merchant receiving payment
                - transaction_type: Type of transaction
            user_history: User's transaction and behavior history:
                - previous_transactions: List of past transactions
                - known_devices: List of known devices
                - usual_locations: List of usual locations
                - known_payment_methods: List of known payment methods
                - account_age: Age of account in days
                - usual_merchants: List of frequently used merchants
                - usual_transaction_amounts: Stats about usual amounts
            include_factors: Whether to include detailed risk factors

        Returns:
            Dictionary containing:
            - risk_score: Normalized risk score (0-1, higher = riskier)
            - risk_level: Risk category (low, medium, high)
            - risk_factors: List of risk factors (if requested)
            - recommended_action: Suggested action
        """
        # Initialize result
        result = {
            "risk_score": 0.0,
            "risk_level": "low",
            "recommended_action": "approve",
        }

        # Initialize risk factors
        risk_factors = []

        # Step 1: Check transaction velocity (too many transactions too quickly)
        velocity_score = self._check_velocity(transaction, user_history)
        if velocity_score > 0:
            risk_factors.append(
                {
                    "type": "high_velocity",
                    "score": velocity_score,
                    "description": "Unusual number of transactions in a short time",
                }
            )

        # Step 2: Check for unusual amount
        amount_score = self._check_unusual_amount(transaction, user_history)
        if amount_score > 0:
            risk_factors.append(
                {
                    "type": "unusual_amount",
                    "score": amount_score,
                    "description": "Transaction amount significantly different from user's usual pattern",
                }
            )

        # Step 3: Check for new device or location
        device_location_score = self._check_device_location(transaction, user_history)
        if device_location_score > 0:
            risk_factors.append(
                {
                    "type": "device_location",
                    "score": device_location_score,
                    "description": "Transaction from new device or unusual location",
                }
            )

        # Step 4: Check for new payment method
        payment_method_score = self._check_payment_method(transaction, user_history)
        if payment_method_score > 0:
            risk_factors.append(
                {
                    "type": "new_payment_method",
                    "score": payment_method_score,
                    "description": "Transaction using new payment method",
                }
            )

        # Step 5: Check for unusual merchant/service
        merchant_score = self._check_unusual_merchant(transaction, user_history)
        if merchant_score > 0:
            risk_factors.append(
                {
                    "type": "unusual_merchant",
                    "score": merchant_score,
                    "description": "Transaction with unusual merchant for this user",
                }
            )

        # Step 6: Check for account age risk
        account_age_score = self._check_account_age(user_history)
        if account_age_score > 0:
            risk_factors.append(
                {
                    "type": "new_account",
                    "score": account_age_score,
                    "description": "Account is relatively new",
                }
            )

        # Calculate overall risk score (normalize to 0-1)
        if risk_factors:
            # Max score would be if all factors returned maximum risk
            max_possible_score = 6.0  # Six checks, each with max score of 1.0

            # Sum actual risk scores
            total_risk = sum(factor["score"] for factor in risk_factors)

            # Normalize
            normalized_risk = min(1.0, total_risk / max_possible_score)

            result["risk_score"] = normalized_risk
        else:
            result["risk_score"] = 0.0

        # Determine risk level based on score
        if result["risk_score"] >= self.high_risk_threshold:
            result["risk_level"] = "high"
            result["recommended_action"] = "block"
        elif result["risk_score"] >= self.medium_risk_threshold:
            result["risk_level"] = "medium"
            result["recommended_action"] = "review"
        else:
            result["risk_level"] = "low"
            result["recommended_action"] = "approve"

        # Include risk factors in result if requested
        if include_factors:
            result["risk_factors"] = risk_factors

        return result

    def _check_velocity(self, transaction: Dict, user_history: Dict) -> float:
        """
        Check for transaction velocity issues (too many transactions too quickly).
        Returns a risk score from 0 to 1.
        """
        # Get current transaction time
        current_time = transaction.get("timestamp")
        if not current_time:
            return 0.0

        # Convert to datetime if it's a string
        if isinstance(current_time, str):
            try:
                current_time = datetime.fromisoformat(
                    current_time.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                return 0.0

        # Define time window for velocity check (last hour)
        time_window = timedelta(hours=1)
        window_start = current_time - time_window

        # Count transactions in the time window
        recent_transactions = [
            t
            for t in user_history.get("previous_transactions", [])
            if t.get("timestamp") and t.get("timestamp") > window_start
        ]

        transaction_count = len(recent_transactions)

        # Check against threshold
        if transaction_count > self.transaction_velocity_threshold:
            # Calculate how much over threshold
            overage = transaction_count / self.transaction_velocity_threshold

            # Cap at 1.0 for max risk score
            return min(1.0, overage - 1.0)

        return 0.0

    def _check_unusual_amount(self, transaction: Dict, user_history: Dict) -> float:
        """
        Check if transaction amount is unusually high for this user.
        Returns a risk score from 0 to 1.
        """
        amount = transaction.get("amount")
        if not amount:
            return 0.0

        # Get user's usual transaction stats
        usual_amounts = user_history.get("usual_transaction_amounts", {})
        avg_amount = usual_amounts.get("average", 0)
        max_amount = usual_amounts.get("max", 0)

        # New user without history gets medium score
        if not avg_amount and not max_amount:
            return 0.5

        # Calculate risk based on deviation from average
        if avg_amount > 0:
            multiple = amount / avg_amount

            if multiple > self.unusual_amount_factor:
                # Normalize to 0-1 scale
                # At 2x threshold, score is 0.5; at 4x threshold, score is near 1.0
                normalized_risk = min(
                    1.0,
                    (multiple - self.unusual_amount_factor)
                    / self.unusual_amount_factor,
                )
                return normalized_risk

        # Also check against user's max historical amount
        if max_amount > 0 and amount > max_amount:
            # Calculate how much over max
            overage = amount / max_amount

            # Normalize to 0-1 scale
            normalized_risk = min(1.0, (overage - 1.0) / 2.0)
            return normalized_risk

        return 0.0

    def _check_device_location(self, transaction: Dict, user_history: Dict) -> float:
        """
        Check if transaction is from a new device or unusual location.
        Returns a risk score from 0 to 1.
        """
        device_info = transaction.get("device_info", {})
        device_id = device_info.get("device_id")
        location = transaction.get("location", {})

        device_risk = 0.0
        location_risk = 0.0

        # Check device
        if device_id:
            known_devices = user_history.get("known_devices", [])

            if device_id not in known_devices:
                device_risk = self.new_device_score

        # Check location
        if location:
            lat = location.get("latitude")
            lng = location.get("longitude")

            if lat and lng:
                # Check against usual locations
                usual_locations = user_history.get("usual_locations", [])

                if usual_locations:
                    # Find closest usual location
                    min_distance = float("inf")
                    for usual_location in usual_locations:
                        usual_lat = usual_location.get("latitude")
                        usual_lng = usual_location.get("longitude")

                        if usual_lat and usual_lng:
                            distance = self._calculate_distance(
                                lat, lng, usual_lat, usual_lng
                            )

                            min_distance = min(min_distance, distance)

                    # If distance exceeds threshold, calculate risk
                    if min_distance > self.location_change_threshold_km:
                        # Normalize to 0-1 scale
                        location_risk = min(
                            1.0,
                            (min_distance - self.location_change_threshold_km) / 1000.0,
                        )
                else:
                    # No usual locations - new user gets medium risk
                    location_risk = 0.5

        # Return the higher of the two risks
        return max(device_risk, location_risk)

    def _calculate_distance(
        self, lat1: float, lng1: float, lat2: float, lng2: float
    ) -> float:
        """
        Calculate distance between two points using Haversine formula.
        """
        from math import atan2, cos, radians, sin, sqrt

        # Earth radius in kilometers
        earth_radius = 6371.0

        # Convert latitude and longitude from degrees to radians
        lat1_rad = radians(float(lat1))
        lng1_rad = radians(float(lng1))
        lat2_rad = radians(float(lat2))
        lng2_rad = radians(float(lng2))

        # Haversine formula
        dlng = lng2_rad - lng1_rad
        dlat = lat2_rad - lat1_rad

        a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        # Distance in kilometers
        distance = earth_radius * c

        return distance

    def _check_payment_method(self, transaction: Dict, user_history: Dict) -> float:
        """
        Check if transaction uses a new payment method.
        Returns a risk score from 0 to 1.
        """
        payment_method_id = transaction.get("payment_method_id")

        if not payment_method_id:
            return 0.0

        known_payment_methods = user_history.get("known_payment_methods", [])

        if payment_method_id not in known_payment_methods:
            return self.new_payment_method_score

        return 0.0

    def _check_unusual_merchant(self, transaction: Dict, user_history: Dict) -> float:
        """
        Check if transaction is with an unusual merchant for this user.
        Returns a risk score from 0 to 1.
        """
        merchant_id = transaction.get("merchant_id")

        if not merchant_id:
            return 0.0

        usual_merchants = user_history.get("usual_merchants", [])

        if not usual_merchants:
            # New user gets small risk score
            return 0.2

        if merchant_id not in usual_merchants:
            # Transaction with new merchant
            # Look at transaction type
            transaction_type = transaction.get("transaction_type")

            # Higher risk for certain transaction types
            if transaction_type in ["subscription", "high_value_purchase"]:
                return 0.6
            else:
                return 0.3

        return 0.0

    def _check_account_age(self, user_history: Dict) -> float:
        """
        Check risk based on account age.
        Returns a risk score from 0 to 1.
        """
        account_age_days = user_history.get("account_age", 0)

        # Very new accounts are higher risk
        if account_age_days < 1:
            return 0.9  # Same-day account
        elif account_age_days < 7:
            return 0.7  # Less than a week
        elif account_age_days < 30:
            return 0.5  # Less than a month
        elif account_age_days < 90:
            return 0.3  # Less than three months

        return 0.0  # Established account

    def detect_suspicious_activity(
        self, user_id: str, recent_actions: List[Dict], user_profile: Dict
    ) -> Dict:
        """
        Detect suspicious account activity beyond transactions.

        Args:
            user_id: User identifier
            recent_actions: List of recent user actions:
                - action_type: Type of action
                - timestamp: When action occurred
                - details: Additional details
            user_profile: User profile information

        Returns:
            Dictionary containing:
            - is_suspicious: Whether activity is suspicious
            - risk_score: Risk score for the activity
            - suspicious_patterns: List of detected suspicious patterns
            - recommended_action: Suggested action
        """
        # Initialize result
        result = {
            "is_suspicious": False,
            "risk_score": 0.0,
            "suspicious_patterns": [],
            "recommended_action": "monitor",
        }

        # Check for various suspicious patterns

        # Pattern 1: Rapid account changes
        account_changes_score = self._check_rapid_account_changes(recent_actions)
        if account_changes_score > 0:
            result["suspicious_patterns"].append(
                {
                    "type": "rapid_account_changes",
                    "score": account_changes_score,
                    "description": "Unusual number of account setting changes in short period",
                }
            )

        # Pattern 2: Multiple failed login attempts
        login_attempts_score = self._check_failed_logins(recent_actions)
        if login_attempts_score > 0:
            result["suspicious_patterns"].append(
                {
                    "type": "multiple_failed_logins",
                    "score": login_attempts_score,
                    "description": "Multiple failed login attempts",
                }
            )

        # Pattern 3: Unusual browsing patterns
        browsing_score = self._check_unusual_browsing(recent_actions, user_profile)
        if browsing_score > 0:
            result["suspicious_patterns"].append(
                {
                    "type": "unusual_browsing",
                    "score": browsing_score,
                    "description": "Browsing pattern differs from user's usual behavior",
                }
            )

        # Pattern 4: Suspicious access patterns
        access_score = self._check_access_patterns(recent_actions, user_profile)
        if access_score > 0:
            result["suspicious_patterns"].append(
                {
                    "type": "suspicious_access",
                    "score": access_score,
                    "description": "Suspicious access patterns detected",
                }
            )

        # Calculate overall risk score
        if result["suspicious_patterns"]:
            total_score = sum(
                pattern["score"] for pattern in result["suspicious_patterns"]
            )
            result["risk_score"] = min(1.0, total_score / 4.0)  # Normalize to 0-1

            # Determine if suspicious and recommended action
            if result["risk_score"] >= self.high_risk_threshold:
                result["is_suspicious"] = True
                result["recommended_action"] = "lockout"
            elif result["risk_score"] >= self.medium_risk_threshold:
                result["is_suspicious"] = True
                result["recommended_action"] = "additional_verification"

        return result

    def _check_rapid_account_changes(self, recent_actions: List[Dict]) -> float:
        """
        Check for suspicious pattern of rapid account changes.
        """
        # Define account change actions
        change_actions = [
            "change_password",
            "change_email",
            "change_phone",
            "update_payment_method",
            "update_profile",
        ]

        # Count relevant actions in the last 24 hours
        yesterday = datetime.now() - timedelta(hours=24)

        relevant_actions = [
            action
            for action in recent_actions
            if action.get("action_type") in change_actions
            and action.get("timestamp", datetime.now()) >= yesterday
        ]

        # Determine risk score based on count
        count = len(relevant_actions)

        if count >= 5:
            return 1.0  # High risk
        elif count >= 3:
            return 0.7  # Medium-high risk
        elif count >= 2:
            return 0.4  # Medium risk

        return 0.0

    def _check_failed_logins(self, recent_actions: List[Dict]) -> float:
        """
        Check for suspicious pattern of failed login attempts.
        """
        # Get recent failed logins
        failed_logins = [
            action
            for action in recent_actions
            if action.get("action_type") == "failed_login"
        ]

        # Count failed logins in last 1 hour
        hour_ago = datetime.now() - timedelta(hours=1)

        recent_failed = [
            login
            for login in failed_logins
            if login.get("timestamp", datetime.now()) >= hour_ago
        ]

        # Determine risk score based on count
        count = len(recent_failed)

        if count >= 5:
            return 1.0  # High risk
        elif count >= 3:
            return 0.7  # Medium-high risk

        return 0.0

    def _check_unusual_browsing(
        self, recent_actions: List[Dict], user_profile: Dict
    ) -> float:
        """
        Check for unusual browsing or activity patterns.
        """
        # This would use behavioral analytics in a real implementation
        # For this simplified version, just check for basic anomalies

        # Get browsing actions
        browsing_actions = [
            action
            for action in recent_actions
            if action.get("action_type") in ["view_page", "search"]
        ]

        # Check if user is browsing categories they never browsed before
        usual_categories = set(user_profile.get("usual_categories", []))

        viewed_categories = set()
        for action in browsing_actions:
            details = action.get("details", {})
            category = details.get("category")
            if category:
                viewed_categories.add(category)

        # Find categories that are new for this user
        new_categories = viewed_categories - usual_categories

        # Calculate score based on proportion of new categories
        if viewed_categories:
            new_ratio = len(new_categories) / len(viewed_categories)

            # If more than 80% of browsing is in new categories, it's suspicious
            if new_ratio > 0.8:
                return 0.6
            elif new_ratio > 0.5:
                return 0.3

        return 0.0

    def _check_access_patterns(
        self, recent_actions: List[Dict], user_profile: Dict
    ) -> float:
        """
        Check for suspicious access patterns such as impossible travel.
        """
        # Look for location changes in logins
        login_actions = [
            action
            for action in recent_actions
            if action.get("action_type") == "login"
            and action.get("details", {}).get("location")
        ]

        if len(login_actions) < 2:
            return 0.0

        # Sort by timestamp
        login_actions.sort(key=lambda x: x.get("timestamp", datetime.now()))

        # Check for impossible travel
        for i in range(1, len(login_actions)):
            prev_login = login_actions[i - 1]
            curr_login = login_actions[i]

            prev_time = prev_login.get("timestamp")
            curr_time = curr_login.get("timestamp")

            if not prev_time or not curr_time:
                continue

            # Calculate time difference in hours
            time_diff = (curr_time - prev_time).total_seconds() / 3600

            # Get locations
            prev_location = prev_login.get("details", {}).get("location", {})
            curr_location = curr_login.get("details", {}).get("location", {})

            prev_lat = prev_location.get("latitude")
            prev_lng = prev_location.get("longitude")
            curr_lat = curr_location.get("latitude")
            curr_lng = curr_location.get("longitude")

            if not all([prev_lat, prev_lng, curr_lat, curr_lng]):
                continue

            # Calculate distance
            distance_km = self._calculate_distance(
                prev_lat, prev_lng, curr_lat, curr_lng
            )

            # Check if travel is impossible
            # Assume maximum travel speed of 900 km/h (fast commercial flight)
            max_possible_distance = time_diff * 900

            if distance_km > max_possible_distance and distance_km > 100:
                return 1.0  # Impossible travel

        return 0.0
