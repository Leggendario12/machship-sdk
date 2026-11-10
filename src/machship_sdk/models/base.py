"""Shared Pydantic base models for MachShip API objects."""

from __future__ import annotations

import logging
import types
from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Union, get_args, get_origin

from pydantic import AwareDatetime, BaseModel, ConfigDict
from pydantic import ValidationInfo, field_validator, model_validator
from pydantic.alias_generators import to_camel

logger = logging.getLogger(__name__)


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


def _annotation_requires_aware_datetime(annotation: Any) -> bool:
    """Return ``True`` when a field annotation expects a timezone-aware datetime."""
    if annotation is AwareDatetime:
        return True

    origin = get_origin(annotation)
    if origin is Annotated:
        args = get_args(annotation)
        return bool(args) and _annotation_requires_aware_datetime(args[0])
    if origin is None:
        return False

    return any(
        _annotation_requires_aware_datetime(argument)
        for argument in get_args(annotation)
        if argument is not type(None)
    )


def _optional_enum_type(annotation: Any) -> type[Enum] | None:
    """Return the enum an optional field holds, or ``None`` for any other field.

    Only ``Enum | None`` fields qualify. Pydantic hands over the annotation
    with any outer ``Annotated`` already stripped. A required enum field is left
    alone, so an unknown value there still fails loudly.
    """
    if get_origin(annotation) not in (Union, types.UnionType):
        return None
    arguments = get_args(annotation)
    if type(None) not in arguments:
        return None
    members = [argument for argument in arguments if argument is not type(None)]
    if len(members) == 1:
        member = members[0]
        if get_origin(member) is Annotated:
            member = get_args(member)[0]
        if isinstance(member, type) and issubclass(member, Enum):
            return member
    return None


def _is_enum_value(enum_type: type[Enum], value: Any) -> bool:
    """Return whether ``value`` is a member of ``enum_type`` or a member's value."""
    if isinstance(value, enum_type):
        return True
    try:
        enum_type(value)
    except (ValueError, TypeError):
        return False
    return True


class MachShipBaseModel(BaseModel):
    """Base model for all MachShip API objects with camelCase aliasing."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    @field_validator("*", mode="before")
    @classmethod
    def _normalize_aware_datetime_fields(
        cls,
        value: Any,
        info: ValidationInfo,
    ) -> Any:
        """Coerce naive timestamps to UTC and unknown optional enum values to None."""
        field_name = info.field_name
        if field_name is None:
            return value
        field = cls.model_fields.get(field_name)
        if field is None:
            return value
        if _annotation_requires_aware_datetime(field.annotation):
            return _coerce_aware_datetime(value)
        enum_type = _optional_enum_type(field.annotation)
        if (
            enum_type is not None
            and value is not None
            and not _is_enum_value(enum_type, value)
        ):
            # MachShip sends values its schema does not list (companyType 0 on
            # getCompleted). One unknown code on an optional field must not
            # fail the whole response, so it reads as unset and is logged.
            logger.warning(
                "Unknown %s value %r on %s.%s; reading it as None.",
                enum_type.__name__,
                value,
                cls.__name__,
                field_name,
            )
            return None
        return value

    @model_validator(mode="before")
    @classmethod
    def _normalize_utc_fields(cls, value: Any) -> Any:
        """Normalize provider payloads before field validation runs."""
        return _normalize_utc_datetime_fields(value)
