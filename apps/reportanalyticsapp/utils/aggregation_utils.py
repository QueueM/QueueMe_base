# apps/reportanalyticsapp/utils/aggregation_utils.py

from datetime import timedelta

import numpy as np
import pandas as pd


class AggregationUtils:
    """
    Utility class for advanced data aggregation and statistical operations.
    Provides methods for trend analysis, moving averages, and anomaly detection.
    """

    @staticmethod
    def calculate_moving_average(data, window=7):
        """
        Calculate moving average for time series data.

        Args:
            data: Dictionary with dates as keys and values as values
            window: Window size for moving average

        Returns:
            dict: Moving average time series
        """
        if not data:
            return {}

        # Convert dictionary to pandas Series
        try:
            # Try to parse dates from string keys
            df = pd.Series(data)
            if isinstance(list(data.keys())[0], str):
                df.index = pd.to_datetime(df.index)
        except Exception:
            # If date parsing fails, just use the original indices
            df = pd.Series(data)

        # Calculate moving average
        ma = df.rolling(window=window, min_periods=1).mean()

        # Convert back to dictionary
        return {
            str(idx): round(val, 2) if isinstance(val, (int, float)) else val
            for idx, val in ma.items()
        }

    @staticmethod
    def detect_anomalies(data, z_score_threshold=2.0):
        """
        Detect anomalies in time series data using Z-score method.

        Args:
            data: Dictionary with dates as keys and values as values
            z_score_threshold: Z-score threshold for anomaly detection

        Returns:
            dict: Dictionary with anomalies
        """
        if not data:
            return {}

        # Convert to numpy array for calculations
        values = np.array(list(data.values()))

        # Calculate mean and standard deviation
        mean = np.mean(values)
        std = np.std(values)

        if std == 0:
            return {}  # No variation, no anomalies

        # Calculate Z-scores
        z_scores = {k: (v - mean) / std for k, v in data.items()}

        # Detect anomalies
        anomalies = {k: v for k, v in data.items() if abs(z_scores[k]) > z_score_threshold}

        return anomalies

    @staticmethod
    def calculate_growth_rates(current_period_data, previous_period_data):
        """
        Calculate growth rates between two periods.

        Args:
            current_period_data: Dictionary with metrics for current period
            previous_period_data: Dictionary with metrics for previous period

        Returns:
            dict: Growth rates for each metric
        """
        growth_rates = {}

        for key, current_value in current_period_data.items():
            if key in previous_period_data:
                previous_value = previous_period_data[key]

                # Avoid division by zero
                if previous_value == 0:
                    if current_value > 0:
                        growth_rates[key] = 100.0  # 100% growth from zero
                    else:
                        growth_rates[key] = 0.0  # No growth
                else:
                    # Calculate percentage change
                    growth_rates[key] = round(
                        ((current_value - previous_value) / previous_value) * 100, 2
                    )

        return growth_rates

    @staticmethod
    def calculate_distribution_metrics(values):
        """
        Calculate distribution metrics for a set of values.

        Args:
            values: List of numeric values

        Returns:
            dict: Distribution metrics
        """
        if not values:
            return {
                "count": 0,
                "mean": 0,
                "median": 0,
                "std": 0,
                "min": 0,
                "max": 0,
                "p25": 0,
                "p75": 0,
                "p90": 0,
            }

        values_array = np.array(values)

        return {
            "count": len(values),
            "mean": float(np.mean(values_array)),
            "median": float(np.median(values_array)),
            "std": float(np.std(values_array)),
            "min": float(np.min(values_array)),
            "max": float(np.max(values_array)),
            "p25": float(np.percentile(values_array, 25)),
            "p75": float(np.percentile(values_array, 75)),
            "p90": float(np.percentile(values_array, 90)),
        }

    @staticmethod
    def fill_time_series_gaps(data, start_date, end_date, fill_value=0):
        """
        Fill gaps in time series data with a default value.

        Args:
            data: Dictionary with dates as keys and values as values
            start_date: Start date for the time series
            end_date: End date for the time series
            fill_value: Value to use for filling gaps

        Returns:
            dict: Complete time series without gaps
        """
        # Create a date range
        date_range = pd.date_range(start=start_date, end=end_date)

        # Create a Series with the date range as index
        series = pd.Series(fill_value, index=date_range)

        # Convert input data to Series
        input_series = pd.Series(data)
        if input_series.index.dtype == "O":  # Object dtype means strings
            input_series.index = pd.to_datetime(input_series.index)

        # Update series with input data
        series.update(input_series)

        # Convert back to dictionary
        return {date.strftime("%Y-%m-%d"): value for date, value in series.items()}

    @staticmethod
    def find_correlations(metrics_data):
        """
        Find correlations between different metrics.

        Args:
            metrics_data: Dictionary with metric names as keys and time series as values

        Returns:
            dict: Correlation matrix
        """
        # Create a DataFrame from the metrics data
        dataframes = {}

        for metric_name, time_series in metrics_data.items():
            # Convert to Series
            series = pd.Series(time_series)
            if series.index.dtype == "O":  # Object dtype means strings
                series.index = pd.to_datetime(series.index)

            dataframes[metric_name] = series

        # Create a DataFrame
        df = pd.DataFrame(dataframes)

        # Calculate correlation matrix
        corr_matrix = df.corr().round(2)

        # Convert to dictionary
        return corr_matrix.to_dict()

    @staticmethod
    def forecast_simple(time_series, periods=7):
        """
        Simple forecasting using exponential smoothing.

        Args:
            time_series: Dictionary with dates as keys and values as values
            periods: Number of periods to forecast

        Returns:
            dict: Forecasted time series
        """
        if not time_series:
            return {}

        # Convert to Series
        series = pd.Series(time_series)
        if series.index.dtype == "O":  # Object dtype means strings
            series.index = pd.to_datetime(series.index)

        # Sort by index
        series = series.sort_index()

        # Create date range for forecast
        last_date = series.index[-1]
        forecast_dates = pd.date_range(start=last_date + timedelta(days=1), periods=periods)

        # Simple exponential smoothing
        alpha = 0.3  # Smoothing factor

        # Initialize forecast with last value
        last_value = series.iloc[-1]
        forecast = [last_value]

        # Generate forecast
        for _ in range(periods - 1):
            next_value = alpha * series.iloc[-1] + (1 - alpha) * forecast[-1]
            forecast.append(next_value)

        # Create forecast Series
        forecast_series = pd.Series(forecast, index=forecast_dates)

        # Combine historical and forecast data
        combined = pd.concat([series, forecast_series])

        # Convert back to dictionary
        return {date.strftime("%Y-%m-%d"): round(value, 2) for date, value in combined.items()}
