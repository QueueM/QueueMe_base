"""
Machine learning algorithms for recommendations and predictions.

This package contains sophisticated machine learning algorithms for content
recommendation, wait time prediction, anomaly detection, and user preference extraction.

Key components:
- recommender: Content recommendation engine for personalized feed generation
- wait_time_predictor: Queue wait time prediction with historical learning
- anomaly_detector: Anomaly detection for business metrics
- preference_extractor: User preference extraction from behavior
"""

from .anomaly_detector import AnomalyDetector
from .preference_extractor import PreferenceExtractor
from .recommender import ContentRecommender, ServiceRecommender, SpecialistRecommender
from .wait_time_predictor import WaitTimePredictor

__all__ = [
    "ContentRecommender",
    "ServiceRecommender",
    "SpecialistRecommender",
    "WaitTimePredictor",
    "AnomalyDetector",
    "PreferenceExtractor",
]
