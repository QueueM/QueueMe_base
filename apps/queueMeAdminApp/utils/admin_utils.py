import csv
import json

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone


def export_to_csv(queryset, fields, filename):
    """
    Export a queryset to CSV file.

    Args:
        queryset: The queryset to export
        fields: List of (field_name, display_name) tuples
        filename: The filename for the CSV

    Returns:
        HttpResponse with CSV attachment
    """
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'

    writer = csv.writer(response)

    # Write header row
    header = [display_name for field_name, display_name in fields]
    writer.writerow(header)

    # Write data rows
    for obj in queryset:
        row = []
        for field_name, _ in fields:
            # Handle nested fields (e.g., 'shop.name')
            if "." in field_name:
                parts = field_name.split(".")
                value = obj
                for part in parts:
                    if value is None:
                        break
                    value = getattr(value, part, None)
            else:
                value = getattr(obj, field_name, None)

            # Format value if needed
            if isinstance(value, timezone.datetime):
                value = value.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(value, dict) or isinstance(value, list):
                value = json.dumps(value)

            row.append(value)

        writer.writerow(row)

    return response


def get_client_ip(request):
    """
    Get client IP address from request.

    Args:
        request: The HTTP request

    Returns:
        str: Client IP address
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


class AdminSearchMixin:
    """
    Mixin for adding advanced search capabilities to admin views.
    """

    search_fields = []

    def get_search_results(self, request, queryset, search_term):
        """
        Return filtered queryset based on search term.

        Args:
            request: The HTTP request
            queryset: The base queryset
            search_term: The search term

        Returns:
            tuple: (filtered_queryset, use_distinct)
        """
        if not search_term or not self.search_fields:
            return queryset, False

        # Build complex query
        query = Q()
        for field in self.search_fields:
            # Handle nested field lookups
            lookup = f"{field}__icontains"
            query |= Q(**{lookup: search_term})

        return queryset.filter(query), True


def format_phone_for_display(phone_number):
    """
    Format phone number for display.

    Args:
        phone_number: Raw phone number

    Returns:
        str: Formatted phone number
    """
    if not phone_number:
        return ""

    # Remove any non-digit characters
    digits = "".join(c for c in phone_number if c.isdigit())

    # Format based on length and country code
    if digits.startswith("966") and len(digits) >= 12:
        # Saudi number: +966 5X XXX XXXX
        return f"+{digits[:3]} {digits[3:5]} {digits[5:8]} {digits[8:]}"
    elif len(digits) == 10:
        # Generic 10-digit number: XXX-XXX-XXXX
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    else:
        # Return as is if we can't recognize the format
        return phone_number


def generate_report_filename(report_type, file_format="pdf"):
    """
    Generate a filename for a report.

    Args:
        report_type: Type of report
        file_format: File format (default: pdf)

    Returns:
        str: Generated filename
    """
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    return f"{report_type}_{timestamp}.{file_format}"
