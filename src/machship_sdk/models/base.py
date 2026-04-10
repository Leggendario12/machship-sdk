"""Shared Pydantic base models for MachShip API objects."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic import model_validator
from pydantic.alias_generators import to_camel


def _coerce_aware_datetime(value: Any) -> Any:
    """Convert naive UTC timestamps into timezone-aware UTC datetimes."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return value


def _normalize_utc_datetime_fields(value: Any) -> Any:
    """Recursively normalize MachShip UTC datetime fields."""
    if isinstance(value, Mapping):
        normalized: dict[Any, Any] = {}
        for key, item in value.items():
            normalized_item = _normalize_utc_datetime_fields(item)
            if isinstance(key, str) and key.casefold().endswith("utc"):
                normalized_item = _coerce_aware_datetime(normalized_item)
            normalized[key] = normalized_item
        return normalized
    if isinstance(value, list):
        return [_normalize_utc_datetime_fields(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_utc_datetime_fields(item) for item in value)
    return value


class MachShipBaseModel(BaseModel):
    """Base model for all MachShip API objects with camelCase aliasing."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_utc_fields(cls, value: Any) -> Any:
        """Normalize provider payloads before field validation runs."""
        return _normalize_utc_datetime_fields(value)
