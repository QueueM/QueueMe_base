"""
Time Series Analysis Module

Provides algorithms for time-based predictions and forecasting:
- Booking prediction
- Revenue forecasting
- Seasonal trend analysis
"""

from . import booking_prediction, revenue_forecasting

__all__ = [
    "booking_prediction",
    "revenue_forecasting",
]
