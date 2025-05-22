"""
Fraud Detection Module

Machine learning algorithms for detecting potential fraud:
- Anomaly detection in payment patterns
- Unusual booking behavior detection
- Velocity checks for rapid transactions
- Device and location anomalies
"""

from datetime import timedelta

import pandas as pd
from django.db.models import Count
from django.utils import timezone
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from apps.authapp.models import UserSession
from apps.bookingapp.models import Booking
from apps.payment.models import PaymentTransaction


class AnomalyDetector:
    """
    Anomaly detection system using machine learning to identify potential fraud.
    Uses isolation forest algorithm to detect outliers in various behaviors.
    """

    def __init__(self, contamination=0.05, random_state=42):
        """
        Initialize the anomaly detector.

        Args:
            contamination: Expected proportion of anomalies in the data (0-0.5)
            random_state: Random seed for reproducibility
        """
        self.contamination = contamination
        self.random_state = random_state
        self.model = None
        self.scaler = None
        self.features = None

    def get_transaction_features(self, days_lookback=60):
        """
        Extract transaction features for anomaly detection.

        Args:
            days_lookback: Number of days to look back for data collection

        Returns:
            DataFrame with transaction features
        """
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days_lookback)

        # Get all transactions in the period
        transactions = PaymentTransaction.objects.filter(
            created_at__gte=start_date, created_at__lte=end_date
        ).select_related("user")

        # Create transaction features
        transaction_features = []

        for tx in transactions:
            # Basic transaction info
            features = {
                "transaction_id": str(tx.id),
                "user_id": str(tx.user_id) if tx.user_id else None,
                "amount": tx.amount,
                "created_at": tx.created_at,
                "status": tx.status,
            }

            # Add device and location info if available
            if hasattr(tx, "metadata") and tx.metadata:
                metadata = tx.metadata
                features.update(
                    {
                        "device_id": metadata.get("device_id"),
                        "ip_address": metadata.get("ip_address"),
                        "country": metadata.get("country"),
                        "city": metadata.get("city"),
                        "browser": metadata.get("browser"),
                        "os": metadata.get("os"),
                    }
                )

            transaction_features.append(features)

        # Convert to DataFrame
        tx_df = pd.DataFrame(transaction_features)

        # Skip if not enough transactions
        if len(tx_df) < 10:
            return pd.DataFrame()

        # Add user activity features
        if not tx_df.empty and "user_id" in tx_df.columns:
            user_ids = tx_df["user_id"].dropna().unique().tolist()

            # Get user sessions
            user_sessions = UserSession.objects.filter(
                user_id__in=user_ids, created_at__gte=start_date
            )

            # Create user location mapping
            user_locations = {}
            user_devices = {}

            for session in user_sessions:
                user_id = str(session.user_id)
                if session.ip_address:
                    if user_id not in user_locations:
                        user_locations[user_id] = set()
                    user_locations[user_id].add(session.ip_address)

                if session.device_id:
                    if user_id not in user_devices:
                        user_devices[user_id] = set()
                    user_devices[user_id].add(session.device_id)

            # Add location and device counts to transactions
            def get_location_count(user_id):
                if user_id and user_id in user_locations:
                    return len(user_locations[user_id])
                return 0

            def get_device_count(user_id):
                if user_id and user_id in user_devices:
                    return len(user_devices[user_id])
                return 0

            tx_df["user_location_count"] = tx_df["user_id"].apply(get_location_count)
            tx_df["user_device_count"] = tx_df["user_id"].apply(get_device_count)

            # Add new IP/device flags
            def is_new_location(row):
                user_id = row["user_id"]
                ip = row.get("ip_address")
                if user_id and ip and user_id in user_locations:
                    # Check if this is first time from this IP
                    return 1 if ip not in user_locations[user_id] else 0
                return 0

            def is_new_device(row):
                user_id = row["user_id"]
                device = row.get("device_id")
                if user_id and device and user_id in user_devices:
                    # Check if this is first time from this device
                    return 1 if device not in user_devices[user_id] else 0
                return 0

            tx_df["is_new_location"] = tx_df.apply(is_new_location, axis=1)
            tx_df["is_new_device"] = tx_df.apply(is_new_device, axis=1)

        # Add velocity features (time since last transaction)
        if not tx_df.empty and "user_id" in tx_df.columns:
            # Sort by user and time
            tx_df = tx_df.sort_values(["user_id", "created_at"])

            # Calculate time difference between consecutive transactions by the same user
            tx_df["prev_tx_time"] = tx_df.groupby("user_id")["created_at"].shift(1)
            tx_df["time_since_last_tx"] = (
                tx_df["created_at"] - tx_df["prev_tx_time"]
            ).dt.total_seconds() / 60  # minutes

            # Fill NaN values (first transaction for user)
            tx_df["time_since_last_tx"] = tx_df["time_since_last_tx"].fillna(
                days_lookback * 24 * 60
            )  # max value

            # Add rolling transaction count and amount in last X hours
            for hours in [1, 24]:  # 1 hour and 24 hours
                # For each transaction, count transactions in the past X hours
                tx_df[f"tx_count_last_{hours}h"] = 0
                tx_df[f"tx_amount_last_{hours}h"] = 0

                for idx, row in tx_df.iterrows():
                    user_id = row["user_id"]
                    curr_time = row["created_at"]
                    time_window = curr_time - timedelta(hours=hours)

                    # Get transactions in the time window
                    prev_txs = tx_df[
                        (tx_df["user_id"] == user_id)
                        & (tx_df["created_at"] >= time_window)
                        & (tx_df["created_at"] < curr_time)
                    ]

                    tx_df.at[idx, f"tx_count_last_{hours}h"] = len(prev_txs)
                    tx_df.at[idx, f"tx_amount_last_{hours}h"] = prev_txs["amount"].sum()

        # Create anomaly detection features
        if not tx_df.empty:
            # Calculate z-scores for numerical features
            for col in [
                "amount",
                "time_since_last_tx",
                "tx_count_last_1h",
                "tx_count_last_24h",
                "tx_amount_last_1h",
                "tx_amount_last_24h",
            ]:
                if col in tx_df.columns:
                    tx_df[f"{col}_zscore"] = stats.zscore(tx_df[col], nan_policy="omit")

            # Create combined feature for anomaly detection
            features = [
                "amount_zscore",
                "time_since_last_tx_zscore",
                "tx_count_last_1h_zscore",
                "tx_count_last_24h_zscore",
                "tx_amount_last_1h_zscore",
                "tx_amount_last_24h_zscore",
                "is_new_location",
                "is_new_device",
            ]

            # Keep only features that exist in the DataFrame
            self.features = [f for f in features if f in tx_df.columns]

            # Handle missing data
            for feature in self.features:
                tx_df[feature] = tx_df[feature].fillna(0)

        return tx_df

    def train_model(self, features_df=None):
        """
        Train the anomaly detection model.

        Args:
            features_df: Optional pre-computed feature DataFrame

        Returns:
            Trained model and anomaly scores
        """
        if features_df is None:
            features_df = self.get_transaction_features()

        if features_df.empty or len(features_df) < 10:
            raise ValueError("Not enough data for anomaly detection")

        # Extract features for anomaly detection
        X = features_df[self.features].copy()

        # Scale the features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Train Isolation Forest model
        self.model = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=100,
            max_samples="auto",
        )

        # Fit the model
        self.model.fit(X_scaled)

        # Generate anomaly scores (-1 for anomalies, 1 for normal points)
        scores = self.model.predict(X_scaled)

        # Convert to anomaly score (higher = more anomalous)
        anomaly_scores = self.model.decision_function(X_scaled)
        # Invert and rescale to 0-1 range where 1 is most anomalous
        anomaly_scores = 1 - (
            (anomaly_scores - anomaly_scores.min())
            / (anomaly_scores.max() - anomaly_scores.min())
        )

        # Add results back to DataFrame
        features_df["is_anomaly"] = [1 if s == -1 else 0 for s in scores]
        features_df["anomaly_score"] = anomaly_scores

        return self.model, features_df

    def detect_anomalies(self, threshold=0.8, features_df=None):
        """
        Detect anomalies in transaction data.

        Args:
            threshold: Threshold for anomaly score (0-1)
            features_df: Optional pre-computed feature DataFrame

        Returns:
            DataFrame with detected anomalies
        """
        if features_df is None:
            features_df = self.get_transaction_features()

        if self.model is None:
            self.train_model(features_df)

        # Extract anomalies above threshold
        anomalies = features_df[features_df["anomaly_score"] >= threshold].copy()

        # Sort by anomaly score (highest first)
        anomalies = anomalies.sort_values("anomaly_score", ascending=False)

        # Add anomaly reason
        anomalies["anomaly_reason"] = anomalies.apply(self.get_anomaly_reason, axis=1)

        return anomalies

    def get_anomaly_reason(self, row):
        """Generate a human-readable reason for why a transaction is anomalous."""
        reasons = []

        # Check for unusual amount
        if "amount_zscore" in row and abs(row["amount_zscore"]) > 2.5:
            if row["amount_zscore"] > 0:
                reasons.append("Unusually large transaction amount")
            else:
                reasons.append("Unusually small transaction amount")

        # Check for velocity anomalies
        if "time_since_last_tx_zscore" in row and row["time_since_last_tx_zscore"] < -2:
            reasons.append("Rapid succession of transactions")

        if "tx_count_last_1h_zscore" in row and row["tx_count_last_1h_zscore"] > 2:
            reasons.append("High number of transactions in the past hour")

        if "tx_count_last_24h_zscore" in row and row["tx_count_last_24h_zscore"] > 2:
            reasons.append("High number of transactions in the past 24 hours")

        if "tx_amount_last_1h_zscore" in row and row["tx_amount_last_1h_zscore"] > 2:
            reasons.append("High total spend in the past hour")

        # Check for new location/device
        if "is_new_location" in row and row["is_new_location"] == 1:
            reasons.append("Transaction from a new location")

        if "is_new_device" in row and row["is_new_device"] == 1:
            reasons.append("Transaction from a new device")

        # If no specific reasons found, provide a generic reason
        if not reasons:
            reasons.append("Unusual transaction pattern detected")

        return ", ".join(reasons)

    def score_transaction(self, transaction_data):
        """
        Score a single transaction for fraud probability.

        Args:
            transaction_data: Dictionary with transaction data

        Returns:
            Dictionary with fraud score and reasons
        """
        if not self.model or not self.scaler:
            raise ValueError("Model not trained. Call train_model() first.")

        # Create a DataFrame with this transaction
        tx_df = pd.DataFrame([transaction_data])

        # Ensure all required features are present
        for feature in self.features:
            if feature not in tx_df.columns:
                # For zscore features, handle specially
                if feature.endswith("_zscore"):
                    base_feature = feature.replace("_zscore", "")
                    if base_feature in tx_df.columns:
                        # Compute z-score based on the value and our training distribution
                        # This assumes the scaler was fit on non-z-scored data
                        # In practice, you'd need to store the mean and std from training
                        # For this example, we'll just set it to 0
                        tx_df[feature] = 0
                    else:
                        tx_df[feature] = 0
                else:
                    tx_df[feature] = 0

        # Extract features
        X = tx_df[self.features].copy()

        # Scale features
        X_scaled = self.scaler.transform(X)

        # Calculate anomaly score
        score = 1 - self.model.decision_function(X_scaled)[0]
        is_anomaly = self.model.predict(X_scaled)[0] == -1

        # Generate reasons
        tx_df["anomaly_score"] = score
        reason = self.get_anomaly_reason(tx_df.iloc[0])

        return {
            "transaction_id": transaction_data.get("transaction_id"),
            "fraud_score": float(score),
            "is_suspicious": is_anomaly,
            "reason": reason,
        }


class BookingAnomalyDetector:
    """
    Detect anomalies in booking patterns to prevent reservation fraud.
    """

    def __init__(self, lookback_days=60):
        """
        Initialize the booking anomaly detector.

        Args:
            lookback_days: Number of days of historical data to use
        """
        self.lookback_days = lookback_days

    def get_booking_statistics(self, shop_id=None):
        """
        Calculate booking statistics to establish normal patterns.

        Args:
            shop_id: Optional shop ID to filter statistics

        Returns:
            Dictionary with booking statistics
        """
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=self.lookback_days)

        # Base query
        bookings = Booking.objects.filter(
            created_at__gte=start_date, created_at__lte=end_date
        )

        # Filter by shop if provided
        if shop_id:
            bookings = bookings.filter(shop_id=shop_id)

        # Count bookings
        booking_count = bookings.count()

        if booking_count == 0:
            return {"success": False, "error": "No booking data available"}

        # Calculate statistics
        avg_bookings_per_day = booking_count / self.lookback_days

        # Bookings per user
        user_booking_counts = bookings.values("user_id").annotate(count=Count("id"))
        if user_booking_counts:
            avg_bookings_per_user = sum(
                item["count"] for item in user_booking_counts
            ) / len(user_booking_counts)
            max_bookings_per_user = max(item["count"] for item in user_booking_counts)
        else:
            avg_bookings_per_user = 0
            max_bookings_per_user = 0

        # Cancellation rate
        cancelled_count = bookings.filter(status__name="Cancelled").count()
        cancellation_rate = cancelled_count / booking_count if booking_count > 0 else 0

        # No-show rate
        no_show_count = bookings.filter(status__name="No-show").count()
        no_show_rate = no_show_count / booking_count if booking_count > 0 else 0

        # Calculate day-of-week distribution
        dow_distribution = {}

        for i in range(7):
            dow_count = bookings.filter(booking_date__week_day=i + 1).count()
            dow_distribution[i] = dow_count / booking_count if booking_count > 0 else 0

        # Calculate hour-of-day distribution
        hour_distribution = {}

        for i in range(24):
            hour_count = bookings.filter(booking_time__hour=i).count()
            hour_distribution[i] = (
                hour_count / booking_count if booking_count > 0 else 0
            )

        return {
            "success": True,
            "booking_count": booking_count,
            "avg_bookings_per_day": avg_bookings_per_day,
            "avg_bookings_per_user": avg_bookings_per_user,
            "max_bookings_per_user": max_bookings_per_user,
            "cancellation_rate": cancellation_rate,
            "no_show_rate": no_show_rate,
            "day_of_week_distribution": dow_distribution,
            "hour_of_day_distribution": hour_distribution,
        }

    def detect_booking_anomalies(self, shop_id=None, date_range=None):
        """
        Detect anomalies in booking patterns.

        Args:
            shop_id: Optional shop ID to filter bookings
            date_range: Optional tuple of (start_date, end_date) to analyze

        Returns:
            Dictionary with detected anomalies
        """
        # Calculate date range
        if date_range:
            start_date, end_date = date_range
        else:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=7)  # Default to 1 week

        # Get baseline statistics
        baseline_stats = self.get_booking_statistics(shop_id)

        if not baseline_stats["success"]:
            return {"success": False, "error": baseline_stats["error"]}

        # Get bookings for analysis period
        bookings = Booking.objects.filter(
            created_at__gte=start_date, created_at__lte=end_date
        )

        # Filter by shop if provided
        if shop_id:
            bookings = bookings.filter(shop_id=shop_id)

        # Count bookings
        booking_count = bookings.count()

        if booking_count == 0:
            return {
                "success": True,
                "anomalies": [],
                "message": "No bookings found in the specified date range",
            }

        # Calculate actual metrics for comparison
        days_in_range = (end_date - start_date).days or 1  # Avoid division by zero
        actual_avg_bookings_per_day = booking_count / days_in_range

        # Bookings per user
        user_booking_counts = bookings.values("user_id").annotate(count=Count("id"))
        if user_booking_counts:
            actual_avg_bookings_per_user = sum(
                item["count"] for item in user_booking_counts
            ) / len(user_booking_counts)
            actual_max_bookings_per_user = max(
                item["count"] for item in user_booking_counts
            )
            # Find user with max bookings
            max_user_id = next(
                (
                    item["user_id"]
                    for item in user_booking_counts
                    if item["count"] == actual_max_bookings_per_user
                ),
                None,
            )
        else:
            actual_max_bookings_per_user = 0
            max_user_id = None

        # Cancellation rate
        actual_cancelled_count = bookings.filter(status__name="Cancelled").count()
        actual_cancellation_rate = (
            actual_cancelled_count / booking_count if booking_count > 0 else 0
        )

        # No-show rate
        actual_no_show_count = bookings.filter(status__name="No-show").count()
        actual_no_show_rate = (
            actual_no_show_count / booking_count if booking_count > 0 else 0
        )

        # Detect anomalies
        anomalies = []

        # Check for unusual booking volume
        if actual_avg_bookings_per_day > baseline_stats["avg_bookings_per_day"] * 2:
            anomalies.append(
                {
                    "type": "volume",
                    "description": "Unusually high booking volume",
                    "severity": "medium",
                    "details": {
                        "actual": actual_avg_bookings_per_day,
                        "baseline": baseline_stats["avg_bookings_per_day"],
                        "percent_increase": (
                            (
                                actual_avg_bookings_per_day
                                / baseline_stats["avg_bookings_per_day"]
                            )
                            - 1
                        )
                        * 100,
                    },
                }
            )

        # Check for unusual user booking patterns
        if actual_max_bookings_per_user > baseline_stats["max_bookings_per_user"] * 1.5:
            anomalies.append(
                {
                    "type": "user_concentration",
                    "description": "User with unusually high number of bookings",
                    "severity": "high",
                    "details": {
                        "user_id": max_user_id,
                        "booking_count": actual_max_bookings_per_user,
                        "baseline_max": baseline_stats["max_bookings_per_user"],
                        "percent_increase": (
                            (
                                actual_max_bookings_per_user
                                / baseline_stats["max_bookings_per_user"]
                            )
                            - 1
                        )
                        * 100,
                    },
                }
            )

        # Check for unusual cancellation rate
        if (
            actual_cancellation_rate > baseline_stats["cancellation_rate"] * 2
            and actual_cancellation_rate > 0.1
        ):
            anomalies.append(
                {
                    "type": "cancellations",
                    "description": "Unusually high cancellation rate",
                    "severity": "medium",
                    "details": {
                        "actual_rate": actual_cancellation_rate,
                        "baseline_rate": baseline_stats["cancellation_rate"],
                        "cancelled_count": actual_cancelled_count,
                    },
                }
            )

        # Check for unusual no-show rate
        if (
            actual_no_show_rate > baseline_stats["no_show_rate"] * 2
            and actual_no_show_rate > 0.1
        ):
            anomalies.append(
                {
                    "type": "no_shows",
                    "description": "Unusually high no-show rate",
                    "severity": "medium",
                    "details": {
                        "actual_rate": actual_no_show_rate,
                        "baseline_rate": baseline_stats["no_show_rate"],
                        "no_show_count": actual_no_show_count,
                    },
                }
            )

        # Check for sequential bookings (potential bots or automated booking)
        sequential_threshold = (
            3  # Number of bookings in rapid succession to consider anomalous
        )
        rapid_booking_users = []

        # Group bookings by user and sort by time
        user_bookings = {}
        for booking in bookings:
            if booking.user_id not in user_bookings:
                user_bookings[booking.user_id] = []
            user_bookings[booking.user_id].append(booking.created_at)

        # Check for rapid sequential bookings
        for user_id, timestamps in user_bookings.items():
            if len(timestamps) < sequential_threshold:
                continue

            # Sort timestamps
            timestamps.sort()

            # Check for rapid succession (less than 60 seconds between bookings)
            rapid_sequences = 0
            for i in range(len(timestamps) - 1):
                time_diff = (timestamps[i + 1] - timestamps[i]).total_seconds()
                if time_diff < 60:
                    rapid_sequences += 1

            if rapid_sequences >= sequential_threshold - 1:
                rapid_booking_users.append(
                    {
                        "user_id": user_id,
                        "booking_count": len(timestamps),
                        "rapid_sequences": rapid_sequences,
                    }
                )

        if rapid_booking_users:
            anomalies.append(
                {
                    "type": "sequential_bookings",
                    "description": "Multiple users making bookings in rapid succession (potential bot activity)",
                    "severity": "high",
                    "details": {
                        "affected_users": rapid_booking_users,
                        "total_affected": len(rapid_booking_users),
                    },
                }
            )

        return {
            "success": True,
            "anomalies": anomalies,
            "booking_count": booking_count,
            "analysis_period": {
                "start_date": start_date,
                "end_date": end_date,
                "days": days_in_range,
            },
        }


def detect_payment_fraud(lookback_days=30, anomaly_threshold=0.8):
    """
    Utility function to detect payment fraud using anomaly detection.

    Args:
        lookback_days: Number of days to analyze
        anomaly_threshold: Threshold for anomaly detection (0-1)

    Returns:
        Dictionary with detected anomalies
    """
    try:
        detector = AnomalyDetector(contamination=0.05)
        features_df = detector.get_transaction_features(days_lookback=lookback_days)

        if features_df.empty:
            return {
                "success": False,
                "error": "Not enough transaction data for analysis",
            }

        # Train model and detect anomalies
        detector.train_model(features_df)
        anomalies = detector.detect_anomalies(
            threshold=anomaly_threshold, features_df=features_df
        )

        if anomalies.empty:
            return {
                "success": True,
                "message": "No suspicious transactions detected",
                "anomalies": [],
            }

        # Format results
        suspicious_transactions = []
        for _, row in anomalies.iterrows():
            suspicious_transactions.append(
                {
                    "transaction_id": row["transaction_id"],
                    "user_id": row["user_id"],
                    "amount": row["amount"],
                    "created_at": row["created_at"].isoformat(),
                    "fraud_score": row["anomaly_score"],
                    "reason": row["anomaly_reason"],
                }
            )

        return {
            "success": True,
            "transactions_analyzed": len(features_df),
            "suspicious_count": len(suspicious_transactions),
            "suspicious_transactions": suspicious_transactions,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def detect_booking_anomalies(shop_id=None, days=7):
    """
    Utility function to detect booking anomalies.

    Args:
        shop_id: Optional shop ID to analyze
        days: Number of recent days to analyze

    Returns:
        Dictionary with detected anomalies
    """
    try:
        detector = BookingAnomalyDetector(lookback_days=60)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        results = detector.detect_booking_anomalies(
            shop_id=shop_id, date_range=(start_date, end_date)
        )

        return results
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_account_takeover_risk(user_id):
    """
    Check for signs of account takeover or unauthorized access.

    Args:
        user_id: User ID to check

    Returns:
        Dictionary with risk assessment
    """
    try:
        # Get user sessions from the past 30 days
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)

        sessions = UserSession.objects.filter(
            user_id=user_id, created_at__gte=start_date
        ).order_by("created_at")

        if not sessions:
            return {
                "success": False,
                "error": "No session data available for this user",
            }

        # Get latest session
        latest_session = sessions.last()

        # Extract unique locations, devices, browsers
        locations = set()
        devices = set()
        browsers = set()

        for session in sessions:
            if session.ip_address:
                locations.add(session.ip_address)
            if session.device_id:
                devices.add(session.device_id)
            if session.browser:
                browsers.add(session.browser)

        # Calculate risk factors
        risk_factors = []
        risk_score = 0

        # Multiple locations
        if len(locations) > 3:
            risk_factors.append(
                {
                    "factor": "multiple_locations",
                    "description": f"User logged in from {len(locations)} different locations",
                    "severity": "medium",
                }
            )
            risk_score += 0.3

        # Multiple devices
        if len(devices) > 3:
            risk_factors.append(
                {
                    "factor": "multiple_devices",
                    "description": f"User used {len(devices)} different devices",
                    "severity": "medium",
                }
            )
            risk_score += 0.3

        # Recent location change
        if len(sessions) >= 2:
            previous_session = sessions[len(sessions) - 2]
            if (
                previous_session.ip_address
                and latest_session.ip_address
                and previous_session.ip_address != latest_session.ip_address
            ):
                # Location changed in most recent login
                risk_factors.append(
                    {
                        "factor": "location_change",
                        "description": "User location changed in most recent login",
                        "severity": "high",
                        "details": {
                            "previous_ip": previous_session.ip_address,
                            "current_ip": latest_session.ip_address,
                        },
                    }
                )
                risk_score += 0.5

        # Recent device change
        if len(sessions) >= 2:
            previous_session = sessions[len(sessions) - 2]
            if (
                previous_session.device_id
                and latest_session.device_id
                and previous_session.device_id != latest_session.device_id
            ):
                # Device changed in most recent login
                risk_factors.append(
                    {
                        "factor": "device_change",
                        "description": "User device changed in most recent login",
                        "severity": "high",
                        "details": {
                            "previous_device": previous_session.device_id,
                            "current_device": latest_session.device_id,
                        },
                    }
                )
                risk_score += 0.4

        # Check for rapid location changes (impossible travel)
        if len(sessions) >= 2:
            for i in range(len(sessions) - 1):
                curr_session = sessions[i]
                next_session = sessions[i + 1]

                # Skip if no location data
                if not curr_session.ip_address or not next_session.ip_address:
                    continue

                # If locations differ, check time difference
                if curr_session.ip_address != next_session.ip_address:
                    time_diff = (
                        next_session.created_at - curr_session.created_at
                    ).total_seconds() / 3600  # hours

                    # If less than 2 hours between logins from different locations, flag as suspicious
                    if time_diff < 2:
                        risk_factors.append(
                            {
                                "factor": "impossible_travel",
                                "description": "User logged in from different locations within a short timeframe",
                                "severity": "critical",
                                "details": {
                                    "first_location": curr_session.ip_address,
                                    "second_location": next_session.ip_address,
                                    "hours_between": round(time_diff, 2),
                                },
                            }
                        )
                        risk_score += 0.8  # High risk score for impossible travel

        # Determine overall risk level
        if risk_score >= 0.8:
            risk_level = "critical"
        elif risk_score >= 0.5:
            risk_level = "high"
        elif risk_score >= 0.3:
            risk_level = "medium"
        elif risk_score > 0:
            risk_level = "low"
        else:
            risk_level = "none"

        return {
            "success": True,
            "user_id": user_id,
            "risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "locations_count": len(locations),
            "devices_count": len(devices),
            "browsers_count": len(browsers),
            "sessions_analyzed": len(sessions),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
