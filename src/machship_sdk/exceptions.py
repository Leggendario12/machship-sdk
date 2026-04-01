"""Exceptions raised by the MachShip SDK."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


class MachShipError(Exception):
    """Base exception for MachShip SDK failures."""


class MachShipHTTPError(MachShipError):
    """Raised when an HTTP request to MachShip fails."""

    def __init__(
        self,
        method: str,
        url: str,
        status_code: int,
        response_text: str | None = None,
    ) -> None:
        """Store HTTP request details for the failure."""
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


class MachShipAPIError(MachShipError):
    """Raised when MachShip returns an application-level error."""

    def __init__(
        self,
        message: str,
        errors: Sequence[Any] | None = None,
    ) -> None:
        """Store the API error payload alongside the message."""
        super().__init__(message, errors)
        self.message = message
        self.errors = tuple(errors or ())

    def __str__(self) -> str:
        """Return the API error message."""
        return self.message


class MachShipValidationError(MachShipAPIError):
    """Raised when MachShip validation fails."""

    @classmethod
    def from_errors(
        cls,
        errors: Sequence[Any],
        *,
        context: str | None = None,
    ) -> "MachShipValidationError":
        """Build an error message from the provided validation errors."""
        message_parts: list[str] = []
        for error in errors:
            error_message = getattr(error, "error_message", None)
            if error_message is None and isinstance(error, dict):
                error_message = error.get("errorMessage")
            if error_message:
                message_parts.append(str(error_message))

        message = "; ".join(message_parts)
        if not message:
            message = "MachShip validation failed"
        if context:
            message = f"{context}: {message}"
        return cls(message, errors=errors)
