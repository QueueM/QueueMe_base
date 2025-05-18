"""
Pagination utilities for Queue Me platform.

This module defines custom pagination classes for use in API views,
allowing for consistent and configurable pagination across the platform.
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .constants import DEFAULT_PAGE_SIZE, LARGE_PAGE_SIZE, MAX_PAGE_SIZE, SMALL_PAGE_SIZE


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination for most API endpoints.

    Features:
    - Configurable page size via 'page_size' query parameter
    - Default page size from settings
    - Maximum page size limit
    - Consistent response format
    """

    page_size = DEFAULT_PAGE_SIZE
    page_size_query_param = "page_size"
    max_page_size = MAX_PAGE_SIZE

    def get_paginated_response(self, data):
        """
        Return paginated response with standardized metadata.

        Args:
            data: Data to include in response

        Returns:
            Response object
        """
        return Response(
            {
                "count": self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages,
                "current_page": self.page.number,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        """
        Get schema for paginated responses.

        Args:
            schema: Base schema

        Returns:
            Schema with pagination fields
        """
        return {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Total number of items",
                },
                "total_pages": {
                    "type": "integer",
                    "description": "Total number of pages",
                },
                "current_page": {
                    "type": "integer",
                    "description": "Current page number",
                },
                "next": {
                    "type": "string",
                    "format": "uri",
                    "nullable": True,
                    "description": "Link to next page",
                },
                "previous": {
                    "type": "string",
                    "format": "uri",
                    "nullable": True,
                    "description": "Link to previous page",
                },
                "results": schema,
            },
        }


class SmallResultsSetPagination(StandardResultsSetPagination):
    """
    Pagination for endpoints that return smaller result sets.

    Suitable for dropdowns, autocomplete, and other UI elements that
    display fewer items.
    """

    page_size = SMALL_PAGE_SIZE


class LargeResultsSetPagination(StandardResultsSetPagination):
    """
    Pagination for endpoints that can handle larger result sets.

    Suitable for data tables, exports, and other views that can
    display more items at once.
    """

    page_size = LARGE_PAGE_SIZE


class CursorPaginationWithCount(PageNumberPagination):
    """
    Cursor-based pagination with item count.

    This is a hybrid between cursor-based pagination (efficient for large datasets)
    and traditional pagination (provides total count).
    """

    page_size = DEFAULT_PAGE_SIZE
    page_size_query_param = "page_size"
    max_page_size = MAX_PAGE_SIZE

    def paginate_queryset(self, queryset, request, view=None):
        """
        Paginate a queryset and calculate total count.

        Args:
            queryset: Queryset to paginate
            request: Request object
            view: View object

        Returns:
            Paginated queryset
        """
        # Store the original queryset for count
        self.total_count = queryset.count()

        # Perform standard pagination
        return super().paginate_queryset(queryset, request, view)

    def get_paginated_response(self, data):
        """
        Return paginated response with count information.

        Args:
            data: Data to include in response

        Returns:
            Response object
        """
        return Response(
            {
                "count": self.total_count,
                "total_pages": self.page.paginator.num_pages,
                "current_page": self.page.number,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )


class NoCountPagination(PageNumberPagination):
    """
    Pagination without count for very large datasets.

    This pagination class skips the expensive COUNT query, making it
    more efficient for very large datasets.
    """

    page_size = DEFAULT_PAGE_SIZE
    page_size_query_param = "page_size"
    max_page_size = MAX_PAGE_SIZE

    def paginate_queryset(self, queryset, request, view=None):
        """
        Paginate a queryset without counting total items.

        Args:
            queryset: Queryset to paginate
            request: Request object
            view: View object

        Returns:
            Paginated queryset
        """
        self.page_size = self.get_page_size(request)
        self.request = request

        # Get page number from request
        page_number = request.query_params.get(self.page_query_param, 1)
        try:
            page_number = int(page_number)
            if page_number < 1:
                page_number = 1
        except (ValueError, TypeError):
            page_number = 1

        # Calculate offset
        offset = (page_number - 1) * self.page_size

        # Get one extra item to determine if there's a next page
        self.page_data = list(queryset[offset : offset + self.page_size + 1])

        # Check if there's a next page
        self.has_next = len(self.page_data) > self.page_size
        if self.has_next:
            self.page_data = self.page_data[:-1]  # Remove the extra item

        # Store page number for response
        self.page_number = page_number

        return self.page_data

    def get_paginated_response(self, data):
        """
        Return paginated response without count information.

        Args:
            data: Data to include in response

        Returns:
            Response object
        """
        # Build next link if there's a next page
        next_link = None
        if self.has_next:
            next_link = self.get_next_link()

        # Build previous link if not on first page
        previous_link = None
        if self.page_number > 1:
            previous_link = self.get_previous_link()

        return Response(
            {
                "next": next_link,
                "previous": previous_link,
                "current_page": self.page_number,
                "results": data,
            }
        )

    def get_next_link(self):
        """
        Get link to next page.

        Returns:
            URL for next page or None
        """
        if not self.has_next:
            return None

        url = self.request.build_absolute_uri()
        page_number = self.page_number + 1

        return self.replace_query_param(url, self.page_query_param, page_number)

    def get_previous_link(self):
        """
        Get link to previous page.

        Returns:
            URL for previous page or None
        """
        if self.page_number <= 1:
            return None

        url = self.request.build_absolute_uri()
        page_number = self.page_number - 1

        if page_number == 1:
            return self.remove_query_param(url, self.page_query_param)

        return self.replace_query_param(url, self.page_query_param, page_number)
