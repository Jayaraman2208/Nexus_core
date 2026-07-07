import logging

from rest_framework.views import exception_handler

logger = logging.getLogger("nexuscore")


class NIBIntegrationError(Exception):
    """Raised when the NIB (Network-in-a-Box) rejects or fails to process a request."""

    def __init__(self, message, code="nib_error", details=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


def standardized_exception_handler(exc, context):
    """
    Wraps DRF's default exception handler to always return a consistent,
    informative error shape instead of a bare 500/cryptic traceback:

        {"error": {"code": "...", "message": "...", "details": {...}}}
    """
    response = exception_handler(exc, context)

    if isinstance(exc, NIBIntegrationError):
        from rest_framework import status
        from rest_framework.response import Response

        logger.error("NIB integration error: %s", exc.message, extra={"details": exc.details})
        return Response(
            {"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    if response is not None:
        error_payload = {
            "error": {
                "code": getattr(exc, "default_code", "error"),
                "message": str(response.data) if not isinstance(response.data, dict) else response.data,
            }
        }
        response.data = error_payload

    return response
