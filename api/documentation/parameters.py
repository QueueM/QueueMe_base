"""
Centralized parameter definitions for QueueMe API documentation.

This module contains reusable OpenAPI parameter definitions to ensure
consistency across the API and prevent duplication issues.
"""

from drf_yasg import openapi

# --------------------------------------------------
# Common Query Parameters
# --------------------------------------------------

SEARCH_PARAM = openapi.Parameter(
    "search",
    openapi.IN_QUERY,
    description="Search term to filter results",
    type=openapi.TYPE_STRING,
    required=False,
)

ORDERING_PARAM = openapi.Parameter(
    "ordering",
    openapi.IN_QUERY,
    description="Order results by field. Prefix with - for descending.",
    type=openapi.TYPE_STRING,
    required=False,
)

PAGE_PARAM = openapi.Parameter(
    "page",
    openapi.IN_QUERY,
    description="Page number for pagination",
    type=openapi.TYPE_INTEGER,
    required=False,
    default=1,
)

PAGE_SIZE_PARAM = openapi.Parameter(
    "page_size",
    openapi.IN_QUERY,
    description="Number of results per page",
    type=openapi.TYPE_INTEGER,
    required=False,
    default=20,
)

DATE_PARAM = openapi.Parameter(
    "date",
    openapi.IN_QUERY,
    description="Date in YYYY-MM-DD format",
    type=openapi.TYPE_STRING,
    format=openapi.FORMAT_DATE,
    required=False,
)

# --------------------------------------------------
# Common ID Parameters
# --------------------------------------------------

UUID_PARAM = openapi.Parameter(
    "id",
    openapi.IN_PATH,
    description="Unique UUID of the resource",
    type=openapi.TYPE_STRING,
    format=openapi.FORMAT_UUID,
    required=True,
)

SERVICE_ID_PARAM = openapi.Parameter(
    "service_id",
    openapi.IN_QUERY,
    description="Service UUID",
    type=openapi.TYPE_STRING,
    format=openapi.FORMAT_UUID,
    required=True,
)

SPECIALIST_ID_PARAM = openapi.Parameter(
    "specialist_id",
    openapi.IN_QUERY,
    description="Specialist UUID (optional)",
    type=openapi.TYPE_STRING,
    format=openapi.FORMAT_UUID,
    required=False,
)

SHOP_ID_PARAM = openapi.Parameter(
    "shop_id",
    openapi.IN_QUERY,
    description="Shop UUID",
    type=openapi.TYPE_STRING,
    format=openapi.FORMAT_UUID,
    required=True,
)

# --------------------------------------------------
# Parameter Collections
# --------------------------------------------------

PAGINATION_PARAMETERS = [PAGE_PARAM, PAGE_SIZE_PARAM]

LIST_PARAMETERS = PAGINATION_PARAMETERS + [SEARCH_PARAM, ORDERING_PARAM]

SERVICE_AVAILABILITY_PARAMETERS = [SERVICE_ID_PARAM, DATE_PARAM]

# --------------------------------------------------
# End of file
# --------------------------------------------------
