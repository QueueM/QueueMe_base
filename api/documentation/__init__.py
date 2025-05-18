"""
Documentation modules for Queue Me API.
This package contains utilities for generating and serving API documentation.
"""

from api.documentation.api_doc_decorators import document_api_endpoint, document_api_viewset
from api.documentation.swagger import schema_view, swagger_urlpatterns

__all__ = [
    "document_api_endpoint",
    "document_api_viewset",
    "schema_view",
    "swagger_urlpatterns",
]
