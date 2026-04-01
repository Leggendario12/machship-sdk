"""Tests for the MachShip SDK client surface."""

from __future__ import annotations

import asyncio
import json
from uuid import UUID
from typing import Any

import httpx
import pytest

from machship_sdk import (
    AsyncMachShipClient,
    MachShipClient,
    MachShipConfig,
    MachShipValidationError,
)
from machship_sdk.models import CreateConsignmentItemV2, RouteRequest


def test_route_request_serializes_camel_case_and_parses_response() -> None:
    """Verify request models serialize with aliases and responses parse cleanly."""
    request_body = RouteRequest(
        companyId=123,
        fromCompanyLocationId=456,
        toCompanyLocationId=789,
        items=[
            CreateConsignmentItemV2(
                companyItemId=42,
                quantity=2,
                weight=3.5,
            )
        ],
    )

    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        """Capture the outgoing request and return a valid MachShip response."""
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["token"] = request.headers.get("token")
        payload = json.loads(request.content.decode())
        seen["payload"] = payload
        return httpx.Response(
            200,
            json={
                "object": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "routes": [{}],
                    "results": [],
                },
                "errors": [],
            },
        )

    client = MachShipClient(
        MachShipConfig(base_url="https://example.com", token="secret"),
        transport=httpx.MockTransport(handler),
    )

    response = client.get_rates(request_body)

    assert seen["method"] == "POST"
    assert seen["url"] == "https://example.com/apiv2/routes/returnroutes"
    assert seen["token"] == "secret"
    assert "companyId" in seen["payload"]
    assert "fromCompanyLocationId" in seen["payload"]
    assert "toCompanyLocationId" in seen["payload"]
    assert "company_id" not in seen["payload"]
    assert response.object is not None
    assert response.object.id == UUID("123e4567-e89b-12d3-a456-426614174000")


def test_download_endpoints_return_bytes() -> None:
    """Verify download endpoints return raw byte content."""
    client = MachShipClient(
        MachShipConfig(base_url="https://example.com", token="secret"),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"%PDF-1.4")
        ),
    )

    content = client.get_consignment_pdf(1001)

    assert content == b"%PDF-1.4"


def test_validation_errors_raise_by_default() -> None:
    """Verify API validation payloads raise the expected exception."""
    client = MachShipClient(
        MachShipConfig(base_url="https://example.com", token="secret"),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "object": True,
                    "errors": [
                        {
                            "memberNames": ["companyId"],
                            "errorMessage": "Company is required",
                            "validationType": 1,
                        }
                    ],
                },
            )
        ),
    )

    with pytest.raises(MachShipValidationError):
        client.ping()


def test_async_client_smoke() -> None:
    """Verify the async client path can send a route request successfully."""
    async def run() -> None:
        """Execute the async client request against a mocked response."""
        def handler(request: httpx.Request) -> httpx.Response:
            """Assert the outgoing payload and return a valid response."""
            payload = json.loads(request.content.decode())
            assert payload["companyId"] == 123
            return httpx.Response(
                200,
                json={
                    "object": {
                        "id": "123e4567-e89b-12d3-a456-426614174001",
                        "routes": [{}],
                        "results": [],
                    },
                    "errors": [],
                },
            )

        client = AsyncMachShipClient(
            MachShipConfig(base_url="https://example.com", token="secret"),
            transport=httpx.MockTransport(handler),
        )
        response = await client.get_rates(
            RouteRequest(
                companyId=123,
                fromCompanyLocationId=456,
                toCompanyLocationId=789,
                items=[],
            )
        )
        assert response.object is not None
        assert response.object.id == UUID("123e4567-e89b-12d3-a456-426614174001")
        await client.aclose()

    asyncio.run(run())
