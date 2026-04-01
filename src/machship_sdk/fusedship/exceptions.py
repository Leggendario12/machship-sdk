"""Exceptions raised by the FusedShip integration."""

from __future__ import annotations


class FusedShipError(Exception):
    """Base exception for FusedShip integration failures."""


class FusedShipHTTPError(FusedShipError):
    """Raised when an HTTP request to FusedShip fails."""

    def __init__(
        self,
        method: str,
        url: str,
        status_code: int,
        response_text: str | None = None,
    ) -> None:
        """
        Store HTTP request details for the failure.

        Args:
            method: The HTTP method (e.g., GET, POST).
            url: The requested URL.
            status_code: The HTTP status code.
            response_text: The response body, if any.
        """
        super().__init__(method, url, status_code, response_text)
        self.method = method
        self.url = url
        self.status_code = status_code
        self.response_text = response_text

    def __str__(self) -> str:
        """Return a descriptive error message."""
        message = f"{self.method.upper()} {self.url} returned HTTP {self.status_code}"
        if self.response_text:
            message = f"{message}: {self.response_text}"
        return message


class FusedShipAPIError(FusedShipError):
    """Raised when FusedShip returns an application-level error."""

    def __init__(self, message: str) -> None:
        """
        Store the API error message.

        Args:
            message: The API error message.
        """
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        """Return the API error message."""
        return self.message
