"""Tests for the FusedShip integration."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from machship_sdk.fusedship import (
    AsyncFusedShipClient,
    FusedShipAPIError,
    FusedShipAddress,
    FusedShipClient,
    FusedShipConfig,
    FusedShipLivePricingRequest,
    FusedShipQuote,
    FusedShipQuoteItem,
    FusedShipShippingItem,
    FusedShipShippingOptions,
)


def _build_request() -> FusedShipLivePricingRequest:
    return FusedShipLivePricingRequest(
        quote=FusedShipQuote(
            warehouse=FusedShipAddress(
                country="AU",
                postal_code="3076",
                province="VIC",
                city="Epping",
                address1="123 main st",
                name="ABC123",
            ),
            shipping_address=FusedShipAddress(
                country="AU",
                postal_code="6720",
                province="WA",
                city="Wickham",
                address1="123 main st",
                name="ABC123",
            ),
            shipping_options=FusedShipShippingOptions(
                authority_to_leave=True,
                residential=False,
            ),
            items=[
                FusedShipQuoteItem(
                    name="Banana Bottle 200ml",
                    sku="BCE345",
                    quantity=5,
                    price=328,
                    categories=["flavoured_drinks", "bottles"],
                    shipping_items=[
                        FusedShipShippingItem(
                            weight=240,
                            length=100,
                            width=20,
                            height=10,
                            item_type="Carton",
                        )
                    ],
                )
            ],
        )
    )


def test_live_pricing_serializes_and_parses_response() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        """Capture the outgoing request and return a valid MachShip response."""
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["token"] = request.headers.get("token")
        seen["integration_id"] = request.headers.get("integration_id")
        seen["payload"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "rates": [
                    {
                        "service_name": "Residential Shipping",
                        "carrier_id": "513",
                        "carrier_name": "GJ Freight (GJF)",
                        "carrier_service_id": "15329",
                        "carrier_service_name": "Semi",
                        "question_ids": ["13", "7"],
                        "total_price_exc_tax": 28.08,
                        "total_price": 28.08,
                        "currency": "AUD",
                        "eta": "2024-05-27T13:59:59Z",
                    }
                ],
                "quoted_items": [],
            },
        )

    client = FusedShipClient(
        FusedShipConfig(
            token="fused-token",
            integration_id="integration-123",
        ),
        transport=httpx.MockTransport(handler),
    )

    response = client.quote_live_pricing("your_platform", _build_request())

    assert seen["method"] == "POST"
    assert seen["url"] == "https://sync.fusedship.com/live-pricing/your_platform"
    assert seen["token"] == "fused-token"
    assert seen["integration_id"] == "integration-123"
    assert "quote" in seen["payload"]
    assert "shipping_options" in seen["payload"]["quote"]
    assert response.rates[0].carrier_id == "513"
    assert response.rates[0].carrier_name == "GJ Freight (GJF)"


def test_live_pricing_accepts_list_wrapped_response() -> None:
    """Object FusedShip can return the live-pricing payload wrapped in a list."""
    client = FusedShipClient(
        FusedShipConfig(
            token="fused-token",
            integration_id="integration-123",
        ),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=[
                    {
                        "rates": [
                            {
                                "service_name": "Residential Shipping",
                                "carrier_id": "513",
                                "carrier_name": "GJ Freight (GJF)",
                                "carrier_service_id": "15329",
                                "carrier_service_name": "Semi",
                                "questionIds": ["13", "7"],
                                "total_price_exc_tax": 28.08,
                                "total_price": 28.08,
                                "currency": "AUD",
                            }
                        ],
                        "quoted_items": [],
                        "is_error": False,
                        "error_message": None,
                    }
                ],
            )
        ),
    )

    response = client.quote_live_pricing("your_platform", _build_request())

    assert response.rates[0].carrier_id == "513"
    assert response.rates[0].carrier_name == "GJ Freight (GJF)"


def test_live_pricing_parses_error_response_payload() -> None:
    """Object FusedShip live-pricing errors should preserve provider messaging."""
    client = FusedShipClient(
        FusedShipConfig(
            token="fused-token",
            integration_id="integration-123",
        ),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "rates": [],
                    "quoted_items": [],
                    "is_error": True,
                    "error_message": "No prices were found.",
                },
            )
        ),
    )

    response = client.quote_live_pricing("your_platform", _build_request())

    assert response.rates == []
    assert response.quoted_items == []
    assert response.is_error is True
    assert response.error_message == "No prices were found."


def test_live_pricing_accepts_empty_list_wrapped_response() -> None:
    """An empty list payload should fall back to the default response model."""
    client = FusedShipClient(
        FusedShipConfig(
            token="fused-token",
            integration_id="integration-123",
        ),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=[])
        ),
    )

    response = client.quote_live_pricing("your_platform", _build_request())

    assert response.rates == []
    assert response.quoted_items == []


def test_request_token_and_iframe_url() -> None:
    client = FusedShipClient(
        FusedShipConfig(
            client_token="client-123",
            store_id="store-456",
        ),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"session_key": "jwt-token"})
        ),
    )

    session = client.request_token()
    iframe_url = client.build_ecommerce_url(session.session_key, active_tab="quote")

    assert session.session_key == "jwt-token"
    assert iframe_url == (
        "https://sync.fusedship.com/ecommerce/app?"
        "session_key=jwt-token&active_tab=quote"
    )


def test_error_body_raises_api_error() -> None:
    client = FusedShipClient(
        FusedShipConfig(
            token="fused-token",
            integration_id="integration-123",
        ),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"error": "Invalid from/to location"}
            )
        ),
    )

    with pytest.raises(FusedShipAPIError):
        client.quote_live_pricing("your_platform", _build_request())


def test_async_fusedship_client_smoke() -> None:
    async def run() -> None:
        """Execute the async client request against a mocked response."""
        def handler(request: httpx.Request) -> httpx.Response:
            """Assert the outgoing payload and return a valid response."""
            payload = json.loads(request.content.decode())
            assert payload["client_token"] == "client-123"
            assert payload["store_id"] == "store-456"
            return httpx.Response(200, json={"session_key": "jwt-token"})

        client = AsyncFusedShipClient(
            FusedShipConfig(
                client_token="client-123",
                store_id="store-456",
            ),
            transport=httpx.MockTransport(handler),
        )

        session = await client.request_token()
        assert session.session_key == "jwt-token"
        await client.aclose()

    asyncio.run(run())
