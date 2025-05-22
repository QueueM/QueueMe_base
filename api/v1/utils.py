# api/v1/utils.py
import logging

from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Wrap DRF’s default exception handler so we can
    * add extra diagnostics to the response
    * push the error to Sentry / log file / Prometheus, …
    """
    response = drf_exception_handler(exc, context)

    # Example: add the HTTP status code to the payload
    if response is not None and isinstance(response.data, dict):
        response.data["status_code"] = response.status_code

    # You can plug in whatever monitoring you like here:
    logger.exception("API exception", exc_info=exc, extra={"view": context.get("view")})

    return response
