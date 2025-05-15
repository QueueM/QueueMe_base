"""
Revenue Forecasting Module

ML-based algorithms for forecasting revenue with various models:
- ARIMA time series forecasting
- Prophet model for trend and seasonality analysis
- Deep learning models for complex pattern recognition
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from django.db.models import Avg, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from sklearn.ensemble import RandomForestRegressor
from statsmodels.tsa.arima.model import ARIMA

from apps.bookingapp.models import Booking
from apps.payment.models import Transaction


class RevenueForecaster:
    """Forecast future revenue using ML time series models."""

    def __init__(self, shop_id=None, forecast_model="arima", history_days=180):
        """
        Initialize the revenue forecaster.

        Args:
            shop_id: Optional shop ID for shop-specific forecasting
            forecast_model: Model type ('arima', 'prophet', 'ml')
            history_days: Number of days of historical data to use
        """
        self.shop_id = shop_id
        self.forecast_model = forecast_model
        self.history_days = history_days
        self.model = None
        self.scaler = None
        self.features = None

    def get_historical_data(self, granularity="day"):
        """
        Get historical revenue data.

        Args:
            granularity: Data aggregation level ('day', 'week', 'month')

        Returns:
            Pandas DataFrame with revenue data
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=self.history_days)

        # Base query
        query = Transaction.objects.filter(
            created_at__date__gte=start_date, created_at__date__lte=end_date, status="completed"
        )

        # Filter by shop if specified
        if self.shop_id:
            query = query.filter(shop_id=self.shop_id)

        # Aggregate by specified granularity
        if granularity == "day":
            query = query.annotate(period=TruncDate("created_at"))
        elif granularity == "week":
            query = query.annotate(period=TruncWeek("created_at"))
        elif granularity == "month":
            query = query.annotate(period=TruncMonth("created_at"))
        else:
            raise ValueError(f"Unsupported granularity: {granularity}")

        # Group by period and sum amounts
        revenue_data = query.values("period").annotate(revenue=Sum("amount")).order_by("period")

        # Convert to DataFrame
        df = pd.DataFrame(list(revenue_data))

        # Handle missing dates by creating a complete date range
        if granularity == "day":
            all_dates = pd.date_range(start=start_date, end=end_date, freq="D")
        elif granularity == "week":
            all_dates = pd.date_range(start=start_date, end=end_date, freq="W")
        elif granularity == "month":
            all_dates = pd.date_range(start=start_date, end=end_date, freq="MS")

        # Create complete date series with zeros for missing dates
        full_df = pd.DataFrame({"period": all_dates})
        if not df.empty:
            # Merge with actual data
            full_df = full_df.merge(df, on="period", how="left")
            full_df["revenue"] = full_df["revenue"].fillna(0)
        else:
            full_df["revenue"] = 0

        return full_df

    def train_arima_model(self, data=None):
        """Train ARIMA model for revenue forecasting."""
        if data is None:
            data = self.get_historical_data()

        # Extract revenue series
        revenue_series = pd.Series(data["revenue"].values, index=data["period"])

        # Fit ARIMA model
        try:
            # Use simple ARIMA parameters suited for revenue data
            model = ARIMA(revenue_series, order=(5, 1, 2))
            self.model = model.fit()
            return self.model
        except Exception as e:
            raise ValueError(f"Error fitting ARIMA model: {str(e)}")

    def train_ml_model(self, data=None):
        """Train machine learning model with additional features."""
        if data is None:
            data = self.get_historical_data()

        # Engineer features
        df = data.copy()
        df["dayofweek"] = df["period"].dt.dayofweek
        df["month"] = df["period"].dt.month
        df["day"] = df["period"].dt.day
        df["quarter"] = df["period"].dt.quarter

        # Add lag features
        for lag in [1, 2, 3, 7]:
            df[f"revenue_lag_{lag}"] = df["revenue"].shift(lag)

        # Add rolling statistics
        for window in [3, 7, 14]:
            df[f"revenue_rolling_mean_{window}"] = df["revenue"].rolling(window=window).mean()
            df[f"revenue_rolling_std_{window}"] = df["revenue"].rolling(window=window).std()

        # Drop rows with NaN due to lag/rolling features
        df = df.dropna()

        if len(df) < 30:
            raise ValueError("Insufficient data for ML model training after feature engineering")

        # Define features and target
        feature_cols = [col for col in df.columns if col not in ["period", "revenue"]]
        X = df[feature_cols]
        y = df["revenue"]

        # Train Random Forest model
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)

        self.model = model
        self.features = feature_cols
        return model

    def forecast_revenue(self, days_ahead=30, granularity="day"):
        """
        Forecast future revenue.

        Args:
            days_ahead: Number of days to forecast
            granularity: Data granularity ('day', 'week', 'month')

        Returns:
            DataFrame with forecasted revenue
        """
        # Train model if not already trained
        if self.model is None:
            if self.forecast_model == "arima":
                self.train_arima_model()
            elif self.forecast_model == "ml":
                self.train_ml_model()
            else:
                raise ValueError(f"Unsupported model type: {self.forecast_model}")

        # Generate forecast
        if self.forecast_model == "arima":
            # Generate ARIMA forecast
            forecast = self.model.forecast(steps=days_ahead)

            # Create date range for future predictions
            historical_data = self.get_historical_data(granularity)
            last_date = historical_data["period"].iloc[-1]

            if granularity == "day":
                future_dates = pd.date_range(
                    start=last_date + timedelta(days=1), periods=days_ahead
                )
            elif granularity == "week":
                future_dates = pd.date_range(
                    start=last_date + timedelta(days=7), periods=days_ahead, freq="W"
                )
            elif granularity == "month":
                future_dates = pd.date_range(
                    start=last_date + timedelta(days=32), periods=days_ahead, freq="MS"
                )

            # Combine into DataFrame
            result = pd.DataFrame({"date": future_dates, "forecasted_revenue": forecast.values})

            # Ensure revenues are not negative
            result["forecasted_revenue"] = result["forecasted_revenue"].apply(lambda x: max(0, x))

            return result

        elif self.forecast_model == "ml":
            # Generate features for future dates
            historical_data = self.get_historical_data(granularity)
            last_date = historical_data["period"].iloc[-1]

            if granularity == "day":
                future_dates = pd.date_range(
                    start=last_date + timedelta(days=1), periods=days_ahead
                )
            elif granularity == "week":
                future_dates = pd.date_range(
                    start=last_date + timedelta(days=7), periods=days_ahead, freq="W"
                )
            elif granularity == "month":
                future_dates = pd.date_range(
                    start=last_date + timedelta(days=32), periods=days_ahead, freq="MS"
                )

            # Create future dataframe with engineered features
            future_df = pd.DataFrame({"period": future_dates})
            future_df["dayofweek"] = future_df["period"].dt.dayofweek
            future_df["month"] = future_df["period"].dt.month
            future_df["day"] = future_df["period"].dt.day
            future_df["quarter"] = future_df["period"].dt.quarter

            # For lag and rolling features, we need historical data
            combined_df = pd.concat(
                [historical_data[["period", "revenue"]], future_df[["period"]]]
            ).reset_index(drop=True)

            combined_df["revenue"] = combined_df["revenue"].fillna(0)

            # Add lag features
            for lag in [1, 2, 3, 7]:
                combined_df[f"revenue_lag_{lag}"] = combined_df["revenue"].shift(lag)

            # Add rolling statistics
            for window in [3, 7, 14]:
                combined_df[f"revenue_rolling_mean_{window}"] = (
                    combined_df["revenue"].rolling(window=window).mean()
                )
                combined_df[f"revenue_rolling_std_{window}"] = (
                    combined_df["revenue"].rolling(window=window).std()
                )

            # Get only future rows with all features
            future_df_with_features = combined_df.tail(days_ahead)

            # Make predictions
            X_future = future_df_with_features[self.features]
            predictions = self.model.predict(X_future)

            # Create result DataFrame
            result = pd.DataFrame({"date": future_dates, "forecasted_revenue": predictions})

            # Ensure revenues are not negative
            result["forecasted_revenue"] = result["forecasted_revenue"].apply(lambda x: max(0, x))

            return result

    def calculate_growth_rate(self, forecasted_data, historical_data=None):
        """Calculate growth rate from historical to forecasted period."""
        if historical_data is None:
            historical_data = self.get_historical_data()

        # Calculate total historical revenue
        historical_total = historical_data["revenue"].sum()

        # Calculate total forecasted revenue
        forecasted_total = forecasted_data["forecasted_revenue"].sum()

        # Calculate average daily values for more accurate comparison
        historical_daily_avg = historical_total / len(historical_data)
        forecasted_daily_avg = forecasted_total / len(forecasted_data)

        # Calculate growth rate
        if historical_daily_avg > 0:
            growth_rate = (
                (forecasted_daily_avg - historical_daily_avg) / historical_daily_avg
            ) * 100
        else:
            growth_rate = float("inf") if forecasted_daily_avg > 0 else 0

        return round(growth_rate, 2)


def forecast_shop_revenue(shop_id, days_ahead=30, model_type="arima"):
    """
    Utility function to forecast revenue for a specific shop.

    Args:
        shop_id: Shop ID to forecast revenue for
        days_ahead: Number of days to forecast
        model_type: Type of forecasting model to use

    Returns:
        Dictionary with forecast data and growth rate
    """
    try:
        forecaster = RevenueForecaster(shop_id=shop_id, forecast_model=model_type)
        forecast_data = forecaster.forecast_revenue(days_ahead=days_ahead)
        growth_rate = forecaster.calculate_growth_rate(forecast_data)

        return {
            "success": True,
            "forecast": forecast_data.to_dict("records"),
            "growth_rate": growth_rate,
            "model_type": model_type,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_platform_revenue_forecast(days_ahead=30):
    """
    Forecast overall platform revenue.

    Args:
        days_ahead: Number of days to forecast

    Returns:
        Dictionary with forecast data and insights
    """
    try:
        # Use more sophisticated model for platform-wide forecasting
        forecaster = RevenueForecaster(forecast_model="ml", history_days=365)
        forecast_data = forecaster.forecast_revenue(days_ahead=days_ahead)
        growth_rate = forecaster.calculate_growth_rate(forecast_data)

        # Calculate additional insights
        historical_data = forecaster.get_historical_data()

        # Monthly trend
        monthly_data = forecaster.get_historical_data(granularity="month")
        monthly_trend = []

        for _, row in monthly_data.iterrows():
            monthly_trend.append(
                {"month": row["period"].strftime("%b %Y"), "revenue": row["revenue"]}
            )

        # Identify seasonality
        seasonal_analysis = analyze_revenue_seasonality(historical_data)

        return {
            "success": True,
            "forecast": forecast_data.to_dict("records"),
            "growth_rate": growth_rate,
            "monthly_trend": monthly_trend,
            "seasonality": seasonal_analysis,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def analyze_revenue_seasonality(historical_data):
    """
    Analyze seasonal patterns in revenue data.

    Args:
        historical_data: DataFrame with historical revenue data

    Returns:
        Dictionary with seasonal patterns
    """
    df = historical_data.copy()

    # Add day of week and month columns
    df["dayofweek"] = df["period"].dt.dayofweek
    df["month"] = df["period"].dt.month

    # Analyze day of week patterns
    dow_means = df.groupby("dayofweek")["revenue"].mean().to_dict()
    overall_mean = df["revenue"].mean()

    dow_patterns = {}
    for day, avg in dow_means.items():
        day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][
            day
        ]
        relative_strength = (avg / overall_mean) if overall_mean else 0
        dow_patterns[day_name] = {
            "average_revenue": round(avg, 2),
            "relative_strength": round(relative_strength, 2),
        }

    # Analyze monthly patterns
    month_means = df.groupby("month")["revenue"].mean().to_dict()

    month_patterns = {}
    for month, avg in month_means.items():
        month_name = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ][month - 1]
        relative_strength = (avg / overall_mean) if overall_mean else 0
        month_patterns[month_name] = {
            "average_revenue": round(avg, 2),
            "relative_strength": round(relative_strength, 2),
        }

    # Identify peak periods
    strongest_dow = max(dow_patterns.items(), key=lambda x: x[1]["relative_strength"])
    strongest_month = max(month_patterns.items(), key=lambda x: x[1]["relative_strength"])

    return {
        "day_of_week_patterns": dow_patterns,
        "monthly_patterns": month_patterns,
        "peak_day": strongest_dow[0],
        "peak_month": strongest_month[0],
        "weekday_weekend_ratio": calculate_weekday_weekend_ratio(df),
    }


def calculate_weekday_weekend_ratio(data):
    """Calculate the ratio of weekday revenue to weekend revenue."""
    weekday_revenue = data[data["dayofweek"] < 5]["revenue"].mean()
    weekend_revenue = data[data["dayofweek"] >= 5]["revenue"].mean()

    if weekend_revenue > 0:
        ratio = weekday_revenue / weekend_revenue
    else:
        ratio = float("inf") if weekday_revenue > 0 else 0

    return round(ratio, 2)
