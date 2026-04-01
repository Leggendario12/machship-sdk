"""Shared Pydantic base models for MachShip API objects."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class MachShipBaseModel(BaseModel):
    """Base model for all MachShip API objects with camelCase aliasing."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        extra="ignore",
    )
