"""
Booking Pattern Recognition System

This module uses machine learning to recognize patterns in booking data
and make predictions for future demand, customer behavior, and resource optimization.
"""

import logging
import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from django.core.cache import cache
from django.db import connection
from django.db.models import Avg, Case, Count, F, IntegerField, Sum, Value, When
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from apps.bookingapp.models import Appointment
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist

logger = logging.getLogger(__name__)


class BookingPatternRecognition:
    """
    Machine learning service for analyzing booking patterns and making predictions
    """

    # Constants
    BOOKING_HISTORY_DAYS = 90  # How many days of history to analyze
    MODEL_CACHE_TTL = 60 * 60 * 24  # 1 day
    PREDICTION_CACHE_TTL = 60 * 60 * 6  # 6 hours
    FEATURES = [
        "day_of_week",
        "hour_of_day",
        "month",
        "is_weekend",
        "is_holiday",
        "service_id",
        "service_duration",
        "service_price",
        "specialist_id",
    ]

    def __init__(self):
        self.models = {}
        self.encoders = {}
        self.scalers = {}

    def predict_demand(self, shop_id, date_range, granularity="day"):
        """
        Predict booking demand for a shop within a date range

        Args:
            shop_id: ID of the shop to predict for
            date_range: List of dates to predict for
            granularity: 'hour', 'day', or 'week'

        Returns:
            Dictionary mapping dates to predicted number of bookings
        """
        cache_key = f"booking_prediction:{shop_id}:{date_range[0]}:{date_range[-1]}:{granularity}"
        cached_prediction = cache.get(cache_key)

        if cached_prediction:
            return cached_prediction

        try:
            # Ensure model is trained
            self._ensure_model_trained(shop_id)

            # Prepare features for prediction
            prediction_features = self._prepare_prediction_features(
                shop_id, date_range, granularity
            )

            # Make prediction
            model = self.models.get(f"demand_{shop_id}")
            if not model:
                raise ValueError(f"No trained model for shop {shop_id}")

            # Transform features
            encoder = self.encoders.get(f"demand_{shop_id}")
            scaler = self.scalers.get(f"demand_{shop_id}")

            # Encode categorical features
            encoded_features = encoder.transform(
                prediction_features[["day_of_week", "month", "hour_of_day"]]
            )

            # Combine with numerical features
            numerical_features = prediction_features.drop(
                ["day_of_week", "month", "hour_of_day"], axis=1
            )
            if len(numerical_features.columns) > 0:
                scaled_numerical = scaler.transform(numerical_features)
                combined_features = np.hstack([encoded_features, scaled_numerical])
            else:
                combined_features = encoded_features

            # Make predictions
            predictions = model.predict(combined_features)

            # Organize results
            results = {}
            for i, date in enumerate(prediction_features["date"]):
                date_str = date.strftime("%Y-%m-%d")
                if granularity == "hour":
                    hour = prediction_features["hour_of_day"].iloc[i]
                    date_str = f"{date_str} {hour:02d}:00"

                results[date_str] = max(0, round(predictions[i]))  # Ensure non-negative

            # Cache the results
            cache.set(cache_key, results, self.PREDICTION_CACHE_TTL)

            return results

        except Exception as e:
            logger.error(f"Error predicting demand: {e}")
            # Return uniform distribution as fallback
            fallback = {}
            for date in date_range:
                date_str = date.strftime("%Y-%m-%d")
                fallback[date_str] = 5  # Default average number
            return fallback

    def predict_peak_hours(self, shop_id, date):
        """
        Predict peak hours for a given day

        Args:
            shop_id: ID of the shop to predict for
            date: Date to predict peak hours for

        Returns:
            Sorted list of hours with predicted booking counts
        """
        # Get hourly prediction for the date
        date_range = [date]
        hourly_prediction = self.predict_demand(shop_id, date_range, granularity="hour")

        # Organize by hour
        hours = []
        for timestamp, count in hourly_prediction.items():
            if timestamp.startswith(date.strftime("%Y-%m-%d")):
                hour = int(timestamp.split(" ")[1].split(":")[0])
                hours.append({"hour": hour, "predicted_bookings": count})

        # Sort by predicted count, descending
        sorted_hours = sorted(hours, key=lambda x: x["predicted_bookings"], reverse=True)

        return sorted_hours

    def predict_specialist_workload(self, specialist_id, date_range):
        """
        Predict workload for a specific specialist

        Args:
            specialist_id: ID of the specialist
            date_range: Range of dates to predict for

        Returns:
            Dictionary mapping dates to predicted hours of work
        """
        try:
            specialist = Specialist.objects.get(id=specialist_id)
            shop_id = specialist.shop_id

            # Get service types this specialist offers
            specialist_services = specialist.services.all()
            service_ids = [service.id for service in specialist_services]

            # Get shop-wide demand prediction
            shop_demand = self.predict_demand(shop_id, date_range, granularity="day")

            # Analyze historical allocation ratio for this specialist
            allocation_ratio = self._calculate_specialist_allocation_ratio(specialist_id, shop_id)

            # Apply ratio to shop demand
            specialist_demand = {}
            for date_str, booking_count in shop_demand.items():
                specialist_demand[date_str] = round(booking_count * allocation_ratio)

            # Convert booking counts to hours based on average service duration
            specialist_workload = {}
            avg_duration = self._calculate_average_service_duration(service_ids)

            for date_str, booking_count in specialist_demand.items():
                # Calculate hours of work (convert from minutes to hours)
                workload_hours = (booking_count * avg_duration) / 60
                specialist_workload[date_str] = round(workload_hours, 1)

            return specialist_workload

        except Exception as e:
            logger.error(f"Error predicting specialist workload: {e}")
            return {date.strftime("%Y-%m-%d"): 4 for date in date_range}  # Default fallback

    def detect_booking_anomalies(self, shop_id, lookback_days=30):
        """
        Detect anomalies in booking patterns

        Args:
            shop_id: ID of the shop to analyze
            lookback_days: Number of days to analyze

        Returns:
            List of detected anomalies with dates and descriptions
        """
        try:
            # Get booking history
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=lookback_days)

            bookings = Appointment.objects.filter(
                service__shop_id=shop_id,
                appointment_time__date__gte=start_date,
                appointment_time__date__lte=end_date,
            )

            # Group by date
            booking_counts = (
                bookings.values(date=F("appointment_time__date"))
                .annotate(count=Count("id"))
                .order_by("date")
            )

            # Convert to DataFrame for analysis
            df = pd.DataFrame(list(booking_counts))
            if df.empty:
                return []

            # Calculate moving average and standard deviation
            df["moving_avg"] = df["count"].rolling(window=7, min_periods=1).mean()
            df["moving_std"] = (
                df["count"].rolling(window=7, min_periods=1).std().fillna(df["count"].std())
            )

            # Detect anomalies (values more than 2 standard deviations from moving average)
            df["z_score"] = (df["count"] - df["moving_avg"]) / df["moving_std"].replace(0, 1)
            df["is_anomaly"] = abs(df["z_score"]) > 2

            # Extract anomalies
            anomalies = []
            for _, row in df[df["is_anomaly"]].iterrows():
                direction = "high" if row["z_score"] > 0 else "low"
                anomalies.append(
                    {
                        "date": row["date"],
                        "actual_bookings": int(row["count"]),
                        "expected_bookings": round(float(row["moving_avg"]), 1),
                        "z_score": round(float(row["z_score"]), 2),
                        "direction": direction,
                        "description": f"Unusually {direction} booking volume on {row['date'].strftime('%Y-%m-%d')}",
                    }
                )

            return anomalies

        except Exception as e:
            logger.error(f"Error detecting booking anomalies: {e}")
            return []

    def suggest_optimal_staffing(self, shop_id, date):
        """
        Suggest optimal staffing levels for a given day

        Args:
            shop_id: ID of the shop
            date: Date to generate suggestion for

        Returns:
            Dictionary with suggested staff count and distribution
        """
        try:
            # Get hourly prediction
            hourly_prediction = self.predict_demand(shop_id, [date], granularity="hour")

            # Organize by hour
            hourly_demand = []
            for timestamp, count in hourly_prediction.items():
                if timestamp.startswith(date.strftime("%Y-%m-%d")):
                    hour = int(timestamp.split(" ")[1].split(":")[0])
                    hourly_demand.append({"hour": hour, "predicted_bookings": count})

            # Sort by hour
            hourly_demand.sort(key=lambda x: x["hour"])

            # Get average service duration (in hours)
            services = Service.objects.filter(shop_id=shop_id)
            avg_duration_minutes = (
                services.aggregate(avg_duration=Avg("duration"))["avg_duration"] or 60
            )
            avg_duration_hours = avg_duration_minutes / 60

            # Calculate required staff per hour
            # Assuming 1 staff can handle 1/avg_duration_hours bookings per hour
            staff_required = []
            for hour_data in hourly_demand:
                bookings = hour_data["predicted_bookings"]
                # Add buffer of 20% to account for variation
                required = math.ceil(bookings * avg_duration_hours * 1.2)
                staff_required.append(
                    {
                        "hour": hour_data["hour"],
                        "required_staff": required,
                        "predicted_bookings": bookings,
                    }
                )

            # Generate shifts (simplistic approach)
            morning_shift = 0
            afternoon_shift = 0
            evening_shift = 0

            for item in staff_required:
                hour = item["hour"]
                if 8 <= hour < 12:
                    morning_shift = max(morning_shift, item["required_staff"])
                elif 12 <= hour < 17:
                    afternoon_shift = max(afternoon_shift, item["required_staff"])
                elif 17 <= hour < 22:
                    evening_shift = max(evening_shift, item["required_staff"])

            return {
                "date": date.strftime("%Y-%m-%d"),
                "staffing_by_hour": staff_required,
                "suggested_shifts": {
                    "morning_shift": morning_shift,
                    "afternoon_shift": afternoon_shift,
                    "evening_shift": evening_shift,
                },
                "total_staff_needed": max(morning_shift, afternoon_shift, evening_shift),
                "avg_service_duration": round(avg_duration_minutes, 1),
            }

        except Exception as e:
            logger.error(f"Error suggesting optimal staffing: {e}")
            return {
                "date": date.strftime("%Y-%m-%d"),
                "staffing_by_hour": [],
                "suggested_shifts": {
                    "morning_shift": 2,
                    "afternoon_shift": 2,
                    "evening_shift": 2,
                },
                "total_staff_needed": 2,
            }

    def _ensure_model_trained(self, shop_id):
        """
        Ensure that a model exists for the shop, training if necessary
        """
        model_key = f"demand_{shop_id}"
        if model_key not in self.models:
            self._train_demand_model(shop_id)

    def _train_demand_model(self, shop_id):
        """
        Train a predictive model for a shop's booking demand
        """
        try:
            # Get historical booking data
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=self.BOOKING_HISTORY_DAYS)

            bookings = Appointment.objects.filter(
                service__shop_id=shop_id,
                appointment_time__date__gte=start_date,
                appointment_time__date__lte=end_date,
            ).select_related("service", "specialist")

            if not bookings.exists():
                logger.warning(f"No booking data available for shop {shop_id}")
                return

            # Create a dataframe for analysis
            booking_data = []
            for booking in bookings:
                booking_time = booking.appointment_time
                booking_data.append(
                    {
                        "date": booking_time.date(),
                        "hour_of_day": booking_time.hour,
                        "day_of_week": booking_time.weekday(),
                        "month": booking_time.month,
                        "is_weekend": 1 if booking_time.weekday() >= 5 else 0,
                        "is_holiday": 0,  # Would need holiday data
                        "service_id": booking.service_id,
                        "service_duration": booking.service.duration,
                        "service_price": float(booking.service.price),
                        "specialist_id": (booking.specialist_id if booking.specialist else None),
                    }
                )

            df = pd.DataFrame(booking_data)

            # Aggregate to required granularity (daily by default)
            daily_counts = (
                df.groupby(["date", "day_of_week", "month"])
                .size()
                .reset_index(name="booking_count")
            )

            # Split into features and target
            X = daily_counts[["day_of_week", "month"]]
            y = daily_counts["booking_count"]

            # Add derived features
            X["is_weekend"] = X["day_of_week"].apply(lambda x: 1 if x >= 5 else 0)

            # Train-test split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            # Create and fit the model pipeline
            categorical_features = ["day_of_week", "month"]
            encoder = OneHotEncoder(sparse=False, handle_unknown="ignore")
            encoder.fit(X[categorical_features])

            encoded_train = encoder.transform(X_train[categorical_features])

            numerical_features = [col for col in X_train.columns if col not in categorical_features]
            if numerical_features:
                scaler = StandardScaler()
                scaler.fit(X_train[numerical_features])
                scaled_numerical_train = scaler.transform(X_train[numerical_features])
                X_train_processed = np.hstack([encoded_train, scaled_numerical_train])
            else:
                scaler = StandardScaler()
                X_train_processed = encoded_train

            # Train the model
            model = GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, random_state=42)
            model.fit(X_train_processed, y_train)

            # Evaluate the model
            encoded_test = encoder.transform(X_test[categorical_features])
            if numerical_features:
                scaled_numerical_test = scaler.transform(X_test[numerical_features])
                X_test_processed = np.hstack([encoded_test, scaled_numerical_test])
            else:
                X_test_processed = encoded_test

            y_pred = model.predict(X_test_processed)
            mae = mean_absolute_error(y_test, y_pred)

            logger.info(f"Trained demand model for shop {shop_id} with MAE: {mae:.2f}")

            # Save the model and transformers
            self.models[f"demand_{shop_id}"] = model
            self.encoders[f"demand_{shop_id}"] = encoder
            self.scalers[f"demand_{shop_id}"] = scaler

        except Exception as e:
            logger.error(f"Error training demand model: {e}")

    def _prepare_prediction_features(self, shop_id, date_range, granularity):
        """
        Prepare features for prediction

        Args:
            shop_id: ID of the shop
            date_range: List of dates to predict for
            granularity: 'hour', 'day', or 'week'

        Returns:
            DataFrame with features for prediction
        """
        features = []

        for date in date_range:
            if granularity == "hour":
                # Generate features for each hour
                for hour in range(8, 22):  # Assuming 8 AM to 10 PM
                    features.append(
                        {
                            "date": date,
                            "hour_of_day": hour,
                            "day_of_week": date.weekday(),
                            "month": date.month,
                            "is_weekend": 1 if date.weekday() >= 5 else 0,
                            "is_holiday": 0,  # Would need holiday data
                        }
                    )
            else:
                # Daily features
                features.append(
                    {
                        "date": date,
                        "hour_of_day": 12,  # Midday as representative
                        "day_of_week": date.weekday(),
                        "month": date.month,
                        "is_weekend": 1 if date.weekday() >= 5 else 0,
                        "is_holiday": 0,  # Would need holiday data
                    }
                )

        return pd.DataFrame(features)

    def _calculate_specialist_allocation_ratio(self, specialist_id, shop_id):
        """
        Calculate what portion of shop bookings this specialist typically handles
        """
        try:
            # Get total bookings for shop in last 30 days
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)

            total_bookings = Appointment.objects.filter(
                service__shop_id=shop_id,
                appointment_time__date__gte=start_date,
                appointment_time__date__lte=end_date,
            ).count()

            # Get bookings for this specialist
            specialist_bookings = Appointment.objects.filter(
                specialist_id=specialist_id,
                appointment_time__date__gte=start_date,
                appointment_time__date__lte=end_date,
            ).count()

            if total_bookings == 0:
                return 0.2  # Default ratio if no data

            ratio = specialist_bookings / total_bookings
            return ratio

        except Exception as e:
            logger.error(f"Error calculating specialist allocation: {e}")
            return 0.2  # Default fallback

    def _calculate_average_service_duration(self, service_ids):
        """
        Calculate average duration of a list of services
        """
        try:
            if not service_ids:
                return 60  # Default 60 minutes

            avg_duration = Service.objects.filter(id__in=service_ids).aggregate(
                avg_duration=Avg("duration")
            )["avg_duration"]

            return avg_duration or 60

        except Exception as e:
            logger.error(f"Error calculating service duration: {e}")
            return 60  # Default fallback
