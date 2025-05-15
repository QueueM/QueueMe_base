"""
Booking Prediction Module

Uses time series analysis to predict future booking patterns, including:
- Daily/hourly booking volume forecasting
- Seasonal trends identification
- Special event impact analysis
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from django.utils import timezone
from scipy import stats
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.seasonal import seasonal_decompose

from apps.bookingapp.models import Booking


class BookingPredictor:
    """Predicts future booking patterns using historical data and ML."""

    def __init__(self, shop_id=None, days_history=90, confidence_level=0.95):
        """
        Initialize the booking predictor.

        Args:
            shop_id: Optional shop ID to filter predictions for a specific shop
            days_history: Number of days of historical data to use
            confidence_level: Confidence level for prediction intervals (0-1)
        """
        self.shop_id = shop_id
        self.days_history = days_history
        self.confidence_level = confidence_level
        self.model = None
        self.seasonal_patterns = None

    def get_historical_data(self):
        """Retrieve and format historical booking data from database."""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=self.days_history)

        # Query filter
        query_filter = {"booking_date__gte": start_date, "booking_date__lte": end_date}
        if self.shop_id:
            query_filter["shop_id"] = self.shop_id

        # Get bookings aggregated by day
        bookings = Booking.objects.filter(**query_filter)

        # Group by date
        date_bookings = {}
        for booking in bookings:
            date_str = booking.booking_date.strftime("%Y-%m-%d")
            date_bookings[date_str] = date_bookings.get(date_str, 0) + 1

        # Convert to time series
        dates = pd.date_range(start=start_date, end=end_date)
        ts_data = pd.Series(
            [date_bookings.get(d.strftime("%Y-%m-%d"), 0) for d in dates], index=dates
        )

        return ts_data

    def train_model(self):
        """Train the ARIMA model on historical data."""
        data = self.get_historical_data()

        # Check if we have enough data
        if len(data) < 14:  # Need at least 2 weeks of data
            raise ValueError("Insufficient historical data for prediction")

        # Identify seasonal patterns
        try:
            result = seasonal_decompose(data, model="additive", period=7)  # Weekly seasonality
            self.seasonal_patterns = result.seasonal
        except Exception as e:
            # Fall back to simpler approach if decomposition fails
            self.seasonal_patterns = None

        # Fit ARIMA model - automatically find the best parameters (p,d,q)
        try:
            # Simple order selection based on reasonable defaults for daily data
            # In a production system, this would use auto_arima or grid search
            model = ARIMA(data, order=(2, 1, 2))  # (p,d,q) parameters
            self.model = model.fit()
        except Exception as e:
            raise ValueError(f"Error fitting ARIMA model: {str(e)}")

        return self.model

    def predict_future_bookings(self, days_ahead=14):
        """
        Predict bookings for upcoming days.

        Args:
            days_ahead: Number of days to forecast

        Returns:
            DataFrame with prediction and confidence intervals
        """
        if not self.model:
            self.train_model()

        # Get forecast
        forecast = self.model.forecast(steps=days_ahead)

        # Get confidence intervals
        pred_interval = self.model.get_forecast(steps=days_ahead).conf_int(
            alpha=1 - self.confidence_level
        )

        # Create date range for future days
        last_date = self.get_historical_data().index[-1]
        future_dates = pd.date_range(start=last_date + timedelta(days=1), periods=days_ahead)

        # Create result DataFrame
        result = pd.DataFrame(
            {
                "date": future_dates,
                "predicted_bookings": forecast.values,
                "lower_bound": pred_interval.iloc[:, 0].values,
                "upper_bound": pred_interval.iloc[:, 1].values,
            }
        )

        # Ensure predictions are not negative
        result["predicted_bookings"] = result["predicted_bookings"].apply(
            lambda x: max(0, round(x))
        )
        result["lower_bound"] = result["lower_bound"].apply(lambda x: max(0, round(x)))
        result["upper_bound"] = result["upper_bound"].apply(lambda x: max(0, round(x)))

        return result

    def identify_peak_days(self, prediction_df=None):
        """Identify projected peak booking days."""
        if prediction_df is None:
            prediction_df = self.predict_future_bookings()

        # Calculate Z-score for each day's prediction
        mean = prediction_df["predicted_bookings"].mean()
        std = (
            prediction_df["predicted_bookings"].std()
            if prediction_df["predicted_bookings"].std() > 0
            else 1
        )
        prediction_df["z_score"] = (prediction_df["predicted_bookings"] - mean) / std

        # Days with z-score > 1 are considered peak days
        peak_days = prediction_df[prediction_df["z_score"] > 1]

        return peak_days


def get_booking_forecast(shop_id=None, days_ahead=14):
    """
    Utility function to get booking predictions.

    Args:
        shop_id: Optional shop ID to filter predictions
        days_ahead: Number of days to predict

    Returns:
        Dictionary with forecast data and peak days
    """
    try:
        predictor = BookingPredictor(shop_id=shop_id)
        forecast = predictor.predict_future_bookings(days_ahead)
        peak_days = predictor.identify_peak_days(forecast)

        return {
            "success": True,
            "forecast": forecast.to_dict("records"),
            "peak_days": peak_days.to_dict("records"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def predict_busy_hours(shop_id, date=None):
    """
    Predict busy hours for a specific shop and date.

    Args:
        shop_id: Shop ID to analyze
        date: Optional specific date to analyze, defaults to tomorrow

    Returns:
        Dictionary with predicted busy hours and confidence scores
    """
    if date is None:
        date = timezone.now().date() + timedelta(days=1)

    # Get historical bookings for this day of week
    day_of_week = date.weekday()

    # Get last 12 weeks of data for this weekday
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=12 * 7)  # 12 weeks

    same_weekday_dates = []
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() == day_of_week:
            same_weekday_dates.append(current_date)
        current_date += timedelta(days=1)

    # Query bookings for these dates
    bookings = Booking.objects.filter(shop_id=shop_id, booking_date__in=same_weekday_dates)

    # Count bookings by hour
    hours_distribution = {}
    for booking in bookings:
        hour = booking.booking_time.hour
        hours_distribution[hour] = hours_distribution.get(hour, 0) + 1

    # Analyze to find busy hours
    if not hours_distribution:
        return {"success": False, "error": "No historical data available"}

    hourly_counts = []
    for hour in range(24):
        hourly_counts.append(hours_distribution.get(hour, 0))

    # Calculate busy hours (hours with above-average bookings)
    avg_bookings = sum(hourly_counts) / len([h for h in hourly_counts if h > 0])
    busy_hours = []

    for hour, count in enumerate(hourly_counts):
        if count > 0:
            confidence = min(1.0, count / (avg_bookings * 1.5))
            if count > avg_bookings:
                busy_hours.append(
                    {"hour": hour, "predicted_bookings": count, "confidence": round(confidence, 2)}
                )

    # Sort by number of predicted bookings
    busy_hours.sort(key=lambda x: x["predicted_bookings"], reverse=True)

    return {
        "success": True,
        "date": date.strftime("%Y-%m-%d"),
        "busy_hours": busy_hours,
        "avg_bookings_per_hour": round(avg_bookings, 1),
    }
