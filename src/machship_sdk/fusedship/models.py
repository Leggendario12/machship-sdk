"""Pydantic models for FusedShip payloads and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FusedShipBaseModel(BaseModel):
    """Base Pydantic model for FusedShip with extra fields allowed."""

    model_config = ConfigDict(extra="allow")


class FusedShipAddress(FusedShipBaseModel):
    """Represents a physical address in FusedShip."""

    country: str | None = None
    postal_code: str | None = None
    province: str | None = None
    city: str | None = None
    address1: str | None = None
    address2: str | None = None
    address: str | None = None
    name: str | None = None
    contact: str | None = None
    phone: str | None = None
    email: str | None = None
    warehouse_id: str | None = None


class FusedShipShippingOptions(FusedShipBaseModel):
    """Options for shipping, such as authority to leave and residential flags."""

    authority_to_leave: bool | None = None
    residential: bool | None = None
    despatch_datetime_utc: datetime | None = None


class FusedShipShippingItem(FusedShipBaseModel):
    """Represents the dimensions and weight of a shipping item."""

    weight: float | None = None
    length: float | None = None
    width: float | None = None
    height: float | None = None
    item_type: str | None = None


class FusedShipQuoteItem(FusedShipBaseModel):
    """Represents an item in a quote request."""

    name: str | None = None
    sku: str | None = None
    quantity: int | None = None
    price: float | None = None
    categories: list[str] | None = None
    shipping_items: list[FusedShipShippingItem] | None = None
    product_meta: dict[str, Any] | None = None


class FusedShipQuotedItem(FusedShipQuoteItem):
    """Represents an item as returned in a quote response."""


class FusedShipQuote(FusedShipBaseModel):
    """Represents a full quote request including warehouse and destination."""

    warehouse: FusedShipAddress
    shipping_address: FusedShipAddress
    shipping_options: FusedShipShippingOptions | None = None
    items: list[FusedShipQuoteItem]


class FusedShipLivePricingRequest(FusedShipBaseModel):
    """Request payload for live pricing."""

    quote: FusedShipQuote


class FusedShipLivePricingRate(FusedShipBaseModel):
    """A single shipping rate returned by live pricing."""

    service_name: str | None = None
    service_description: str | None = None
    carrier_id: str | int | None = None
    carrier_name: str | None = None
    carrier_service_id: str | int | None = None
    carrier_service_name: str | None = None
    question_ids: list[str | int] | None = None
    total_price_exc_tax: float | None = None
    total_price: float | None = None
    currency: str | None = None
    eta: datetime | None = None


class FusedShipLivePricingResponse(FusedShipBaseModel):
    """Response payload for live pricing."""

    rates: list[FusedShipLivePricingRate] = Field(default_factory=list)
    quoted_items: list[FusedShipQuotedItem] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _unwrap_list_response(cls, value: Any) -> Any:
        """Handle the list-wrapped live pricing payload returned by FusedShip."""
        if isinstance(value, list):
            if not value:
                return {}
            return value[0]
        return value


class FusedShipRequestTokenRequest(FusedShipBaseModel):
    """Request payload to obtain a session token."""

    client_token: str
    store_id: str


class FusedShipRequestTokenResponse(FusedShipBaseModel):
    """Response payload containing a session token."""

    session_key: str
