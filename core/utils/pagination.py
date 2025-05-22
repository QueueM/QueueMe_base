"""
Pagination utilities for the Queue Me platform.

This module provides custom pagination classes for DRF APIs.
"""

from collections import OrderedDict

from rest_framework.pagination import (
    CursorPagination,
    LimitOffsetPagination,
    PageNumberPagination,
)
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination for most API endpoints.

    Features:
    - Page size parameter
    - Max page size limit
    - Consistent response format
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        """
        Custom pagination response format.

        Args:
            data: The paginated data

        Returns:
            Response: Paginated response
        """
        return Response(
            OrderedDict(
                [
                    ("count", self.page.paginator.count),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("page_size", self.get_page_size(self.request)),
                    ("current_page", self.page.number),
                    ("total_pages", self.page.paginator.num_pages),
                    ("results", data),
                ]
            )
        )

    def get_paginated_response_schema(self, schema):
        """
        Custom pagination response schema for OpenAPI.

        Args:
            schema: The schema for a single result

        Returns:
            dict: Schema for the paginated response
        """
        return {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Total number of items",
                    "example": 123,
                },
                "next": {
                    "type": "string",
                    "nullable": True,
                    "format": "uri",
                    "description": "URL for the next page",
                    "example": "http://api.example.org/accounts/?page=4",
                },
                "previous": {
                    "type": "string",
                    "nullable": True,
                    "format": "uri",
                    "description": "URL for the previous page",
                    "example": "http://api.example.org/accounts/?page=2",
                },
                "page_size": {
                    "type": "integer",
                    "description": "Number of items per page",
                    "example": 20,
                },
                "current_page": {
                    "type": "integer",
                    "description": "Current page number",
                    "example": 3,
                },
                "total_pages": {
                    "type": "integer",
                    "description": "Total number of pages",
                    "example": 6,
                },
                "results": schema,
            },
        }


class LargeResultsSetPagination(PageNumberPagination):
    """
    Pagination for endpoints that need larger page sizes.
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 500

    def get_paginated_response(self, data):
        """
        Custom pagination response format.

        Args:
            data: The paginated data

        Returns:
            Response: Paginated response
        """
        return Response(
            OrderedDict(
                [
                    ("count", self.page.paginator.count),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("page_size", self.get_page_size(self.request)),
                    ("current_page", self.page.number),
                    ("total_pages", self.page.paginator.num_pages),
                    ("results", data),
                ]
            )
        )


class SmallResultsSetPagination(PageNumberPagination):
    """
    Pagination for endpoints that need smaller page sizes.
    """

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50

    def get_paginated_response(self, data):
        """
        Custom pagination response format.

        Args:
            data: The paginated data

        Returns:
            Response: Paginated response
        """
        return Response(
            OrderedDict(
                [
                    ("count", self.page.paginator.count),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("page_size", self.get_page_size(self.request)),
                    ("current_page", self.page.number),
                    ("total_pages", self.page.paginator.num_pages),
                    ("results", data),
                ]
            )
        )


class CustomLimitOffsetPagination(LimitOffsetPagination):
    """
    Limit-offset pagination for API endpoints.

    Features:
    - Limit parameter
    - Offset parameter
    - Default and max limits
    """

    default_limit = 20
    limit_query_param = "limit"
    offset_query_param = "offset"
    max_limit = 100

    def get_paginated_response(self, data):
        """
        Custom pagination response format.

        Args:
            data: The paginated data

        Returns:
            Response: Paginated response
        """
        return Response(
            OrderedDict(
                [
                    ("count", self.count),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("limit", self.limit),
                    ("offset", self.offset),
                    ("results", data),
                ]
            )
        )


class TimeCursorPagination(CursorPagination):
    """
    Cursor pagination for time-ordered data (e.g., feeds).

    Features:
    - Cursor-based pagination (more efficient for large datasets)
    - Based on created_at field
    - Reverse order (newest first)
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-created_at"  # Newest first
    cursor_query_param = "cursor"

    def get_paginated_response(self, data):
        """
        Custom pagination response format.

        Args:
            data: The paginated data

        Returns:
            Response: Paginated response
        """
        return Response(
            OrderedDict(
                [
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("page_size", self.get_page_size(self.request)),
                    ("results", data),
                ]
            )
        )


class InfinitePagination(CursorPagination):
    """
    Infinite scroll pagination for feeds and timelines.

    Features:
    - Cursor-based pagination (efficient for infinite scroll)
    - Based on id field
    - Can handle both ascending and descending orders
    """

    page_size = 15
    page_size_query_param = "page_size"
    max_page_size = 50
    ordering = "-id"  # Default to newest first
    cursor_query_param = "cursor"
