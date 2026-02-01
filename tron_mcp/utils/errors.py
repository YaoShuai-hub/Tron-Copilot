"""Custom exceptions for clearer control flow."""


class ValidationError(Exception):
    """Raised when client input is invalid."""


class UpstreamError(Exception):
    """Raised when TRONSCAN/TRONGRID returns a non-200 response."""

    def __init__(self, message: str, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body
