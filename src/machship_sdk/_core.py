"""Shared request and response helpers for the MachShip clients."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time
from enum import Enum
from typing import Any, TypeVar
from uuid import UUID

from pydantic import BaseModel

from .exceptions import MachShipValidationError

T = TypeVar("T")


def build_url(base_url: str, path: str) -> str:
    """Combine base URL and path into a full URL."""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def build_headers(
    *,
    token: str,
    extra_headers: Mapping[str, str] | None = None,
    user_agent: str,
) -> dict[str, str]:
    """Build request headers with authentication token and optional extra headers."""
    headers = {
        "token": token,
        "accept": "application/json",
        "user-agent": user_agent,
    }
    if extra_headers:
        headers.update(extra_headers)
    return headers


def _jsonable(value: Any) -> Any:
    """Recursively convert values to JSON-serializable types."""
    if value is None:
        return None
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", by_alias=True, exclude_none=True)
    if isinstance(value, Mapping):
        return {
            key: _jsonable(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return value


def serialize_json_payload(payload: Any) -> Any:
    """Serialize payload to JSON-serializable types."""
    return _jsonable(payload)


def serialize_query_params(params: Any) -> Any:
    """Serialize query parameters to JSON-serializable types."""
    return _jsonable(params)


def parse_response_model(response_json: Any, response_model: type[T] | None) -> T | Any:
    """Parse JSON response into the specified response model."""
    if response_model is None:
        return response_json
    return response_model.model_validate(response_json)


def maybe_raise_for_api_errors(
    response_model: Any,
    *,
    context: str,
    raise_on_api_errors: bool,
) -> None:
    """Check response model for errors and raise exception if found."""
    if not raise_on_api_errors:
        return

    errors = getattr(response_model, "errors", None)
    if errors:
        raise MachShipValidationError.from_errors(errors, context=context)
