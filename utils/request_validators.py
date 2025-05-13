import json
import logging
import re
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

from django.http import JsonResponse
from rest_framework import status

logger = logging.getLogger(__name__)


class RequestValidationError(Exception):
    """
    Exception raised when request validation fails.
    """

    def __init__(self, message, errors=None):
        super().__init__(message)
        self.message = message
        self.errors = errors or {}


class InputSanitizer:
    """
    Class for sanitizing user input to prevent common security issues.
    """

    @staticmethod
    def sanitize_string(value: str) -> str:
        """
        Sanitize a string input to prevent XSS attacks.

        Args:
            value (str): The string to sanitize

        Returns:
            str: The sanitized string
        """
        if not isinstance(value, str):
            return value

        # Replace potentially dangerous characters
        value = value.replace("<", "&lt;").replace(">", "&gt;")
        value = value.replace('"', "&quot;").replace("'", "&#x27;")
        value = value.replace("(", "&#40;").replace(")", "&#41;")
        value = value.replace("/", "&#x2F;")

        return value

    @staticmethod
    def sanitize_item(item: Any) -> Any:
        """
        Sanitize a single item based on its type.

        Args:
            item (Any): The item to sanitize

        Returns:
            Any: The sanitized item
        """
        if isinstance(item, str):
            return InputSanitizer.sanitize_string(item)
        elif isinstance(item, (int, float, bool, type(None))):
            return item
        elif isinstance(item, dict):
            return InputSanitizer.sanitize_dict(item)
        elif isinstance(item, list):
            return InputSanitizer.sanitize_list(item)
        else:
            return str(item)  # Convert other types to string

    @staticmethod
    def sanitize_dict(data: Dict) -> Dict:
        """
        Recursively sanitize all string values in a dictionary.

        Args:
            data (Dict): The dictionary to sanitize

        Returns:
            Dict: The sanitized dictionary
        """
        if not isinstance(data, dict):
            return data

        sanitized = {}
        for key, value in data.items():
            sanitized[key] = InputSanitizer.sanitize_item(value)

        return sanitized

    @staticmethod
    def sanitize_list(data: List) -> List:
        """
        Recursively sanitize all items in a list.

        Args:
            data (List): The list to sanitize

        Returns:
            List: The sanitized list
        """
        if not isinstance(data, list):
            return data

        return [InputSanitizer.sanitize_item(item) for item in data]


def validate_request_schema(schema: Dict, schema_id: str = None) -> Callable:
    """
    Decorator for validating request data against a schema.

    Args:
        schema (Dict): The validation schema
        schema_id (str, optional): An identifier for the schema for logging and debugging

    Returns:
        Callable: Decorator function
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                # Get request data based on method
                if request.method in ("POST", "PUT", "PATCH"):
                    try:
                        data = request.data
                    except AttributeError:
                        # If it's not a REST framework request
                        try:
                            data = json.loads(request.body.decode("utf-8"))
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            data = request.POST
                elif request.method == "GET":
                    data = request.GET
                else:
                    data = {}

                # Sanitize input data
                sanitized_data = InputSanitizer.sanitize_dict(data)

                # Validate against schema
                errors = validate_data(sanitized_data, schema)

                log_prefix = f"[{schema_id}] " if schema_id else ""

                if errors:
                    logger.warning(f"{log_prefix}Request validation failed: {errors}")
                    return JsonResponse(
                        {
                            "success": False,
                            "message": "Invalid request data",
                            "errors": errors,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Replace request data with sanitized data
                if hasattr(request, "data"):
                    request._mutable = True
                    request.data.clear()
                    request.data.update(sanitized_data)
                    request._mutable = False

                return view_func(request, *args, **kwargs)

            except Exception as e:
                log_prefix = f"[{schema_id}] " if schema_id else ""
                logger.exception(f"{log_prefix}Error during request validation: {str(e)}")
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Error processing request",
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return wrapper

    return decorator


def validate_data(data: Dict, schema: Dict) -> Dict:
    """
    Validate data against a schema.

    Args:
        data (Dict): The data to validate
        schema (Dict): The validation schema

    Returns:
        Dict: Dictionary of validation errors, empty if valid
    """
    errors = {}

    for field, rules in schema.items():
        field_value = data.get(field)
        field_errors = []

        # Check required
        if rules.get("required", False) and field_value is None:
            field_errors.append("This field is required")
            errors[field] = field_errors
            continue

        # Skip validation if field is not present and not required
        if field_value is None and not rules.get("required", False):
            continue

        # Validate type
        field_type = rules.get("type")
        if field_type and not validate_type(field_value, field_type):
            field_errors.append(f"Must be of type {field_type}")

        # Validate min length
        min_length = rules.get("min_length")
        if (
            min_length is not None
            and isinstance(field_value, str)
            and len(field_value) < min_length
        ):
            field_errors.append(f"Must be at least {min_length} characters long")

        # Validate max length
        max_length = rules.get("max_length")
        if (
            max_length is not None
            and isinstance(field_value, str)
            and len(field_value) > max_length
        ):
            field_errors.append(f"Must be at most {max_length} characters long")

        # Validate minimum value
        min_value = rules.get("min_value")
        if (
            min_value is not None
            and isinstance(field_value, (int, float))
            and field_value < min_value
        ):
            field_errors.append(f"Must be at least {min_value}")

        # Validate maximum value
        max_value = rules.get("max_value")
        if (
            max_value is not None
            and isinstance(field_value, (int, float))
            and field_value > max_value
        ):
            field_errors.append(f"Must be at most {max_value}")

        # Validate regex pattern
        pattern = rules.get("pattern")
        if (
            pattern is not None
            and isinstance(field_value, str)
            and not re.match(pattern, field_value)
        ):
            field_errors.append("Invalid format")

        # Validate choices
        choices = rules.get("choices")
        if choices is not None and field_value not in choices:
            field_errors.append(f'Must be one of: {", ".join(map(str, choices))}')

        # Add field errors to main errors dict
        if field_errors:
            errors[field] = field_errors

    return errors


def validate_type(value: Any, expected_type: str) -> bool:
    """
    Validate that a value is of the expected type.

    Args:
        value (Any): The value to check
        expected_type (str): The expected type

    Returns:
        bool: True if valid, False otherwise
    """
    if expected_type == "string":
        return isinstance(value, str)
    elif expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    elif expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    elif expected_type == "boolean":
        return isinstance(value, bool)
    elif expected_type == "array":
        return isinstance(value, list)
    elif expected_type == "object":
        return isinstance(value, dict)
    elif expected_type == "null":
        return value is None
    else:
        return True  # Unknown type, assume valid
