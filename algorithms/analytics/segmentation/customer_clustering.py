"""
Customer Clustering Module

AI-powered customer segmentation using machine learning algorithms:
- K-means clustering for behavioral segmentation
- RFM (Recency, Frequency, Monetary) analysis
- Customer lifetime value prediction
- Automated customer tagging
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from django.db.models import Avg, Count, DateTimeField, ExpressionWrapper, F, Sum
from django.db.models.functions import ExtractMonth, ExtractYear
from django.utils import timezone
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, StandardScaler

from apps.authapp.models import User
from apps.bookingapp.models import Booking
from apps.customersapp.models import Customer, CustomerTag
from apps.payment.models import Transaction


class CustomerSegmenter:
    """
    Advanced customer segmentation using machine learning algorithms.
    Creates behavioral clusters to group similar customers.
    """

    def __init__(self, n_clusters=5, random_state=42):
        """
        Initialize the customer segmentation model.

        Args:
            n_clusters: Number of customer segments to create
            random_state: Random seed for reproducibility
        """
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.model = None
        self.scaler = None
        self.pca = None
        self.feature_names = None
        self.cluster_profiles = None

    def get_customer_features(self, lookback_days=365, min_transactions=1):
        """
        Extract customer features from booking and transaction data.

        Args:
            lookback_days: Number of days to look back for data collection
            min_transactions: Minimum number of transactions required for inclusion

        Returns:
            DataFrame with customer features
        """
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=lookback_days)

        # Get all customers with bookings in the period
        bookings = Booking.objects.filter(
            created_at__gte=start_date, created_at__lte=end_date
        ).select_related("user")

        # Get all transactions in the period
        transactions = Transaction.objects.filter(
            created_at__gte=start_date, created_at__lte=end_date, status="completed"
        ).select_related("user")

        # Extract customer IDs
        customer_ids = set([b.user_id for b in bookings] + [t.user_id for t in transactions])

        # Build customer feature matrix
        customer_features = []

        for customer_id in customer_ids:
            customer_bookings = [b for b in bookings if b.user_id == customer_id]
            customer_transactions = [t for t in transactions if t.user_id == customer_id]

            # Skip if not enough transactions
            if len(customer_transactions) < min_transactions:
                continue

            # Calculate recency (days since last booking/transaction)
            if customer_bookings:
                last_booking_date = max([b.created_at for b in customer_bookings])
                recency_booking = (end_date - last_booking_date).days
            else:
                recency_booking = lookback_days

            if customer_transactions:
                last_transaction_date = max([t.created_at for t in customer_transactions])
                recency_transaction = (end_date - last_transaction_date).days
            else:
                recency_transaction = lookback_days

            # Calculate frequency
            booking_frequency = len(customer_bookings)
            transaction_frequency = len(customer_transactions)

            # Calculate monetary value
            total_spend = sum([t.amount for t in customer_transactions])
            avg_transaction_value = (
                total_spend / transaction_frequency if transaction_frequency > 0 else 0
            )

            # Time of day preference (0-23 scale)
            booking_hours = [b.booking_time.hour for b in customer_bookings if b.booking_time]
            preferred_hour = int(np.mean(booking_hours)) if booking_hours else -1

            # Day of week preference (0-6 scale, 0=Monday)
            booking_days = [b.booking_date.weekday() for b in customer_bookings if b.booking_date]
            preferred_day = int(np.mean(booking_days)) if booking_days else -1

            # Service category preference
            category_counts = {}
            for booking in customer_bookings:
                if booking.service and booking.service.category:
                    category = booking.service.category.name
                    category_counts[category] = category_counts.get(category, 0) + 1

            preferred_category = (
                max(category_counts.items(), key=lambda x: x[1])[0] if category_counts else None
            )

            # Calculate interval between bookings
            if len(customer_bookings) > 1:
                booking_dates = sorted([b.created_at for b in customer_bookings])
                intervals = [
                    (booking_dates[i + 1] - booking_dates[i]).days
                    for i in range(len(booking_dates) - 1)
                ]
                avg_interval = sum(intervals) / len(intervals)
            else:
                avg_interval = lookback_days

            # Engagement score (simple weighted sum)
            engagement_score = (
                (lookback_days - recency_booking) * 0.3
                + booking_frequency * 3  # More recent = better
                + transaction_frequency * 2  # More bookings = better
                + (total_spend / 100) * 0.5  # More transactions = better  # More spending = better
            )

            # Assemble feature vector
            features = {
                "customer_id": customer_id,
                "recency_booking": recency_booking,
                "recency_transaction": recency_transaction,
                "booking_frequency": booking_frequency,
                "transaction_frequency": transaction_frequency,
                "total_spend": total_spend,
                "avg_transaction_value": avg_transaction_value,
                "preferred_hour": preferred_hour,
                "preferred_day": preferred_day,
                "avg_interval": avg_interval,
                "engagement_score": engagement_score,
                "preferred_category": preferred_category,
            }

            customer_features.append(features)

        # Convert to DataFrame
        df = pd.DataFrame(customer_features)

        # Remove non-numerical columns for clustering
        self.feature_names = [
            "recency_booking",
            "recency_transaction",
            "booking_frequency",
            "transaction_frequency",
            "total_spend",
            "avg_transaction_value",
            "preferred_hour",
            "preferred_day",
            "avg_interval",
            "engagement_score",
        ]

        # Handle any missing values
        for col in self.feature_names:
            if col in df.columns:
                df[col] = df[col].fillna(df[col].median())

        return df

    def train_model(self, customer_features=None):
        """
        Train the clustering model on customer features.

        Args:
            customer_features: Optional DataFrame with pre-computed features

        Returns:
            Trained model and cluster assignments
        """
        if customer_features is None:
            customer_features = self.get_customer_features()

        if len(customer_features) < self.n_clusters:
            raise ValueError(
                f"Not enough customers for {self.n_clusters} clusters. Have {len(customer_features)}."
            )

        # Extract numerical features for clustering
        X = customer_features[self.feature_names].copy()

        # Create a pipeline with scaling, dimensionality reduction, and clustering
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=min(5, len(self.feature_names)), random_state=self.random_state)
        self.model = KMeans(n_clusters=self.n_clusters, random_state=self.random_state, n_init=10)

        # Fit the pipeline
        X_scaled = self.scaler.fit_transform(X)
        X_pca = self.pca.fit_transform(X_scaled)
        clusters = self.model.fit_predict(X_pca)

        # Add cluster assignments back to the data
        customer_features["cluster"] = clusters

        # Generate cluster profiles
        self.generate_cluster_profiles(customer_features)

        return self.model, customer_features

    def generate_cluster_profiles(self, segmented_customers):
        """
        Generate profiles describing each customer segment.

        Args:
            segmented_customers: DataFrame with cluster assignments

        Returns:
            Dictionary with cluster profiles
        """
        profiles = {}

        # Calculate aggregate statistics for each cluster
        cluster_stats = segmented_customers.groupby("cluster")[self.feature_names].mean()

        # Determine relative values (how much above/below average)
        overall_means = segmented_customers[self.feature_names].mean()
        relative_values = cluster_stats / overall_means

        # Define interpretations based on feature patterns
        for cluster_id in range(self.n_clusters):
            stats = cluster_stats.loc[cluster_id].to_dict()
            rel_vals = relative_values.loc[cluster_id].to_dict()

            # Count customers in this cluster
            customer_count = len(segmented_customers[segmented_customers["cluster"] == cluster_id])

            # Create customer categories based on patterns
            if rel_vals["recency_booking"] < 0.5 and rel_vals["booking_frequency"] > 1.5:
                category = "Loyal High-Frequency"
            elif rel_vals["total_spend"] > 1.5 and rel_vals["avg_transaction_value"] > 1.3:
                category = "High-Value"
            elif rel_vals["recency_booking"] > 1.5 and rel_vals["booking_frequency"] < 0.7:
                category = "At-Risk / Churned"
            elif (
                rel_vals["recency_booking"] < 0.7
                and rel_vals["recency_transaction"] < 0.7
                and rel_vals["booking_frequency"] < 0.7
            ):
                category = "New Customer"
            elif (
                0.7 <= rel_vals["booking_frequency"] <= 1.3
                and 0.7 <= rel_vals["total_spend"] <= 1.3
            ):
                category = "Average Customer"
            elif rel_vals["engagement_score"] > 1.3:
                category = "Highly Engaged"
            else:
                category = f"Segment {cluster_id+1}"

            # Determine preferred day name
            day_names = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
            if 0 <= stats["preferred_day"] <= 6:
                preferred_day = day_names[int(stats["preferred_day"])]
            else:
                preferred_day = "No preference"

            # Determine day part based on preferred hour
            if 5 <= stats["preferred_hour"] < 12:
                day_part = "Morning"
            elif 12 <= stats["preferred_hour"] < 17:
                day_part = "Afternoon"
            elif 17 <= stats["preferred_hour"] < 21:
                day_part = "Evening"
            else:
                day_part = "Night"

            # Store profile
            profiles[cluster_id] = {
                "id": cluster_id,
                "name": category,
                "customer_count": customer_count,
                "percentage": round((customer_count / len(segmented_customers)) * 100, 1),
                "avg_spend": round(stats["total_spend"], 2),
                "spend_relative": round(rel_vals["total_spend"], 2),
                "visit_frequency": round(stats["booking_frequency"], 1),
                "frequency_relative": round(rel_vals["booking_frequency"], 2),
                "recency_days": round(stats["recency_booking"]),
                "avg_transaction": round(stats["avg_transaction_value"], 2),
                "booking_interval_days": round(stats["avg_interval"]),
                "preferred_day": preferred_day,
                "preferred_time": day_part,
                "engagement_score": round(stats["engagement_score"], 1),
                "description": self.generate_cluster_description(category, stats, rel_vals),
                "marketing_recommendation": self.generate_marketing_recommendation(
                    category, stats, rel_vals
                ),
            }

        self.cluster_profiles = profiles
        return profiles

    def generate_cluster_description(self, category, stats, rel_vals):
        """Generate a human-readable description of a customer segment."""
        if category == "Loyal High-Frequency":
            return "Regular customers who book services frequently. They are the backbone of your business."
        elif category == "High-Value":
            return "Big spenders who make larger purchases but may book less frequently than loyal customers."
        elif category == "At-Risk / Churned":
            return "Customers who haven't booked in a while and may have switched to competitors."
        elif category == "New Customer":
            return "Recent additions to your customer base who haven't established a clear pattern yet."
        elif category == "Average Customer":
            return "Typical customers with moderate frequency and spending patterns."
        elif category == "Highly Engaged":
            return "Very active customers who engage frequently with your services."
        else:
            # Generate a description based on relative values
            descriptions = []
            if rel_vals["booking_frequency"] > 1.3:
                descriptions.append("book more frequently than average")
            elif rel_vals["booking_frequency"] < 0.7:
                descriptions.append("book less frequently than average")

            if rel_vals["total_spend"] > 1.3:
                descriptions.append("spend more than average")
            elif rel_vals["total_spend"] < 0.7:
                descriptions.append("spend less than average")

            if rel_vals["recency_booking"] < 0.7:
                descriptions.append("have booked recently")
            elif rel_vals["recency_booking"] > 1.3:
                descriptions.append("haven't booked in a while")

            if descriptions:
                return f"Customers who {', '.join(descriptions)}."
            else:
                return "Customers with mixed patterns."

    def generate_marketing_recommendation(self, category, stats, rel_vals):
        """Generate marketing recommendations for a customer segment."""
        if category == "Loyal High-Frequency":
            return "Reward loyalty with VIP perks, early access to new services, and personalized thank you messages."
        elif category == "High-Value":
            return "Focus on premium service offerings, upselling, and create exclusive high-value packages."
        elif category == "At-Risk / Churned":
            return "Send re-engagement campaigns with special offers to win them back before they're completely lost."
        elif category == "New Customer":
            return "Welcome series and onboarding communication to build relationship and encourage repeat bookings."
        elif category == "Average Customer":
            return "Encourage more frequent visits with punch cards or loyalty programs to increase engagement."
        elif category == "Highly Engaged":
            return "Leverage as brand ambassadors, encourage referrals, and provide exclusive community benefits."
        else:
            # Basic recommendation based on metrics
            if rel_vals["recency_booking"] > 1.3:
                return "Focus on re-engagement strategies with personalized offers."
            elif rel_vals["avg_transaction_value"] < 0.8:
                return "Use upselling techniques and package deals to increase average transaction value."
            elif rel_vals["booking_frequency"] < 0.8:
                return "Implement reminder marketing and loyalty incentives to increase booking frequency."
            else:
                return "Maintain relationship with consistent communication and occasional special offers."

    def predict_cluster(self, customer_id):
        """
        Predict which cluster a customer belongs to.

        Args:
            customer_id: Customer ID to classify

        Returns:
            Dictionary with cluster assignment and profile
        """
        if not self.model or not self.scaler or not self.pca:
            raise ValueError("Model not trained. Call train_model() first.")

        # Get customer features
        customer_features = self.get_customer_features(lookback_days=365, min_transactions=0)

        # Filter for just this customer
        customer_data = customer_features[customer_features["customer_id"] == customer_id]

        if customer_data.empty:
            return {"success": False, "error": f"No data found for customer ID {customer_id}"}

        # Extract features
        X = customer_data[self.feature_names].copy()

        # Apply the same transformation pipeline
        X_scaled = self.scaler.transform(X)
        X_pca = self.pca.transform(X_scaled)

        # Predict cluster
        cluster = self.model.predict(X_pca)[0]

        # Get profile for this cluster
        profile = self.cluster_profiles.get(
            cluster, {"id": cluster, "name": f"Segment {cluster+1}"}
        )

        return {
            "success": True,
            "customer_id": customer_id,
            "cluster": int(cluster),
            "profile": profile,
        }

    def auto_tag_customers(self, add_to_database=False):
        """
        Automatically tag customers based on their cluster assignments.

        Args:
            add_to_database: Whether to save tags to the database

        Returns:
            DataFrame with customer IDs and assigned tags
        """
        if not self.model or not self.cluster_profiles:
            raise ValueError("Model not trained. Call train_model() first.")

        # Get customer features with clusters
        customer_features = self.get_customer_features()
        if "cluster" not in customer_features.columns:
            _, customer_features = self.train_model(customer_features)

        # Assign tags based on cluster profiles
        customer_tags = []

        for _, row in customer_features.iterrows():
            cluster = row["cluster"]
            profile = self.cluster_profiles.get(cluster, {})
            segment_name = profile.get("name", f"Segment {cluster+1}")

            tags = [segment_name]

            # Add behavior-based tags
            if row["booking_frequency"] > 10:
                tags.append("Frequent Booker")
            if row["total_spend"] > 1000:
                tags.append("Big Spender")
            if row["recency_booking"] > 90:
                tags.append("Inactive")
            if row["engagement_score"] > 100:
                tags.append("Highly Engaged")
            if 0 <= row["preferred_day"] <= 4:  # Weekday preference
                tags.append("Weekday Customer")
            if 5 <= row["preferred_day"] <= 6:  # Weekend preference
                tags.append("Weekend Customer")

            # Add the tags to our results
            customer_tags.append(
                {"customer_id": row["customer_id"], "segment": segment_name, "tags": tags}
            )

            # Save to database if requested
            if add_to_database:
                try:
                    # Get or create customer record
                    customer, _ = Customer.objects.get_or_create(user_id=row["customer_id"])

                    # Add segment tag
                    segment_tag, _ = CustomerTag.objects.get_or_create(
                        name=segment_name,
                        defaults={"category": "segment", "created_by_algorithm": True},
                    )
                    customer.tags.add(segment_tag)

                    # Add behavior tags
                    for tag_name in tags:
                        if tag_name != segment_name:  # Don't duplicate segment tag
                            tag, _ = CustomerTag.objects.get_or_create(
                                name=tag_name,
                                defaults={"category": "behavior", "created_by_algorithm": True},
                            )
                            customer.tags.add(tag)
                except Exception as e:
                    # Log the error but continue processing other customers
                    print(f"Error adding tags for customer {row['customer_id']}: {str(e)}")

        return pd.DataFrame(customer_tags)


def segment_customers(n_segments=5, lookback_days=365, min_transactions=1):
    """
    Utility function to segment customers into behavioral clusters.

    Args:
        n_segments: Number of segments to create
        lookback_days: Number of days of historical data to use
        min_transactions: Minimum number of transactions required for inclusion

    Returns:
        Dictionary with segmentation results
    """
    try:
        segmenter = CustomerSegmenter(n_clusters=n_segments)
        _, segmented_customers = segmenter.train_model()

        profiles = segmenter.cluster_profiles

        # Get counts by segment
        segment_counts = segmented_customers["cluster"].value_counts().to_dict()
        segment_distributions = []

        for cluster_id, count in segment_counts.items():
            profile = profiles.get(cluster_id, {})
            segment_distributions.append(
                {
                    "segment_id": int(cluster_id),
                    "segment_name": profile.get("name", f"Segment {cluster_id+1}"),
                    "count": count,
                    "percentage": round((count / len(segmented_customers)) * 100, 2),
                }
            )

        return {
            "success": True,
            "total_customers_analyzed": len(segmented_customers),
            "number_of_segments": n_segments,
            "segment_distributions": segment_distributions,
            "segment_profiles": profiles,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_customer_lifetime_value(customer_id=None, prediction_days=365):
    """
    Calculate customer lifetime value (CLV) for a specific customer or all customers.

    Args:
        customer_id: Optional customer ID to calculate CLV for
        prediction_days: Number of days to predict forward

    Returns:
        Dictionary with CLV data
    """
    try:
        # Set date range for historical data (1 year lookback)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=365)

        # Base query to get transaction data
        query = Transaction.objects.filter(
            created_at__gte=start_date, created_at__lte=end_date, status="completed"
        )

        # Filter for specific customer if provided
        if customer_id:
            query = query.filter(user_id=customer_id)

        # Group by customer and calculate metrics
        customer_metrics = query.values("user_id").annotate(
            total_spend=Sum("amount"),
            transaction_count=Count("id"),
            avg_order_value=Avg("amount"),
            first_purchase=models.Min("created_at"),
            last_purchase=models.Max("created_at"),
        )

        # Calculate LTV for each customer
        results = []

        for metrics in customer_metrics:
            user_id = metrics["user_id"]

            # Calculate purchase frequency (transactions per day)
            if metrics["first_purchase"] and metrics["last_purchase"]:
                days_as_customer = (metrics["last_purchase"] - metrics["first_purchase"]).days + 1
                purchase_frequency = metrics["transaction_count"] / max(days_as_customer, 1)
            else:
                purchase_frequency = 0

            # Calculate churn probability
            days_since_last_purchase = (
                (end_date - metrics["last_purchase"]).days if metrics["last_purchase"] else 0
            )
            if days_since_last_purchase > 90:  # Consider churned if inactive for 90+ days
                churn_probability = min(0.9, days_since_last_purchase / 365)  # Cap at 90%
            else:
                # Lower churn probability for active customers
                churn_probability = max(0.05, days_since_last_purchase / 1000)

            # Calculate expected transactions in prediction period
            expected_transactions = (
                metrics["transaction_count"] * (prediction_days / 365) * (1 - churn_probability)
            )

            # Calculate LTV
            ltv = expected_transactions * metrics["avg_order_value"]

            # Store results
            results.append(
                {
                    "customer_id": user_id,
                    "total_historical_spend": metrics["total_spend"],
                    "transaction_count": metrics["transaction_count"],
                    "average_order_value": metrics["avg_order_value"],
                    "purchase_frequency": purchase_frequency,
                    "days_since_last_purchase": days_since_last_purchase,
                    "churn_probability": churn_probability,
                    "lifetime_value": ltv,
                    "ltv_confidence": 1
                    - (churn_probability / 2),  # Higher confidence for lower churn probability
                }
            )

        # Sort by LTV (highest first)
        results.sort(key=lambda x: x["lifetime_value"], reverse=True)

        # If specific customer was requested, return just their data
        if customer_id:
            if results:
                return {"success": True, "customer_id": customer_id, "ltv_data": results[0]}
            else:
                return {
                    "success": False,
                    "error": f"No transaction data found for customer {customer_id}",
                }

        # Otherwise return aggregated data
        return {
            "success": True,
            "customers_analyzed": len(results),
            "average_ltv": sum(r["lifetime_value"] for r in results) / len(results)
            if results
            else 0,
            "top_customers": results[:10] if len(results) > 10 else results,
            "ltv_distribution": calculate_ltv_distribution(results),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def calculate_ltv_distribution(ltv_results):
    """Calculate the distribution of LTV values across percentile buckets."""
    if not ltv_results:
        return []

    # Extract LTV values
    ltv_values = [r["lifetime_value"] for r in ltv_results]

    # Calculate percentiles
    percentiles = [0, 10, 25, 50, 75, 90, 95, 99, 100]
    percentile_values = np.percentile(ltv_values, percentiles)

    # Create distribution data
    distribution = []

    for i in range(len(percentiles) - 1):
        bucket = {
            "percentile_min": percentiles[i],
            "percentile_max": percentiles[i + 1],
            "ltv_min": percentile_values[i],
            "ltv_max": percentile_values[i + 1],
        }
        distribution.append(bucket)

    return distribution
