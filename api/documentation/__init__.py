"""
API Documentation Package

This package contains helpers and utilities for API documentation using drf-yasg.
"""

# Apply monkey patch for drf_yasg duplicate parameters issue
from api.documentation.api_doc_decorators import (
    document_api_endpoint,
    document_api_viewset,
)
from api.documentation.swagger import schema_view, swagger_urlpatterns

__all__ = [
    "document_api_endpoint",
    "document_api_viewset",
    "schema_view",
    "swagger_urlpatterns",
]
