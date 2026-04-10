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
from machship_sdk.models import (
    CreateConsignmentV2,
    CreateConsignmentItemV2,
    LocationSearchOptions,
    LocationSearchOptionsV2,
    RawLocation,
    RawLocationsWithLocationSearchOptions,
    RouteRequest,
)
from machship_sdk.models.generated import ItemType, MachshipValidationType


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


def test_route_request_parses_local_despatch_datetimes() -> None:
    """Verify MachShip local timestamps parse without timezone info."""
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

    client = MachShipClient(
        MachShipConfig(base_url="https://example.com", token="secret"),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "object": {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "routes": [
                            {
                                "despatchOptions": [
                                    {
                                        "despatchDateLocal": "2026-04-02T00:00:00",
                                        "despatchDateUtc": "2026-04-02T00:00:00Z",
                                        "etaLocal": "2026-04-07T23:59:59",
                                        "etaUtc": "2026-04-07T23:59:59Z",
                                    }
                                ]
                            }
                        ],
                        "results": [],
                    },
                    "errors": [],
                },
            )
        ),
    )

    response = client.get_rates(request_body)

    assert response.object is not None
    assert response.object.routes is not None
    despatch_option = response.object.routes[0].despatch_options[0]
    assert despatch_option.despatch_date_local is not None
    assert despatch_option.despatch_date_local.tzinfo is None
    assert despatch_option.eta_local is not None
    assert despatch_option.eta_local.tzinfo is None
    assert despatch_option.despatch_date_utc is not None
    assert despatch_option.despatch_date_utc.tzinfo is not None
    assert despatch_option.eta_utc is not None
    assert despatch_option.eta_utc.tzinfo is not None


def test_location_lookup_serializes_and_parses_response() -> None:
    """Verify location lookup requests serialize and parse cleanly."""
    lookup_request = RawLocationsWithLocationSearchOptions(
        raw_locations=[
            RawLocation(suburb="Melbourne", postcode="3000"),
        ],
        location_search_options=LocationSearchOptions(
            company_id=123,
            include_post_office_boxes=False,
        ),
    )
    search_request = LocationSearchOptionsV2(
        company_id=456,
        include_post_office_boxes=True,
        retrieval_size=10,
    )

    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        """Capture the outgoing request and return a valid location response."""
        if request.url.path == "/apiv2/locations/returnLocations":
            seen["lookup_method"] = request.method
            seen["lookup_url"] = str(request.url)
            seen["lookup_payload"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={
                    "object": [
                        {
                            "id": 1,
                            "postcode": "3000",
                            "suburb": "Melbourne",
                            "locationType": 0,
                        }
                    ],
                    "errors": [],
                },
            )
        if request.url.path == "/apiv2/locations/returnLocationsWithSearchOptions":
            seen["search_method"] = request.method
            seen["search_url"] = str(request.url)
            seen["search_params"] = dict(request.url.params)
            seen["search_payload"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={
                    "object": [
                        {
                            "id": 2,
                            "postcode": "3000",
                            "suburb": "Melbourne",
                            "locationType": 0,
                        }
                    ],
                    "errors": [],
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    client = MachShipClient(
        MachShipConfig(base_url="https://example.com", token="secret"),
        transport=httpx.MockTransport(handler),
    )

    lookup_response = client.return_locations(lookup_request)
    search_response = client.return_locations_with_search_options(
        search_request,
        search="Mel 3000",
    )

    assert seen["lookup_method"] == "POST"
    assert seen["lookup_url"] == "https://example.com/apiv2/locations/returnLocations"
    assert seen["lookup_payload"]["rawLocations"][0]["suburb"] == "Melbourne"
    assert seen["lookup_payload"]["locationSearchOptions"]["companyId"] == 123
    assert seen["search_method"] == "POST"
    assert seen["search_url"] == (
        "https://example.com/apiv2/locations/returnLocationsWithSearchOptions"
        "?s=Mel+3000"
    )
    assert seen["search_params"] == {"s": "Mel 3000"}
    assert seen["search_payload"]["retrievalSize"] == 10
    assert lookup_response.object is not None
    assert lookup_response.object[0].id == 1
    assert search_response.object is not None
    assert search_response.object[0].id == 2


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


def test_validation_errors_accept_string_validation_type() -> None:
    """Verify MachShip's string validation labels parse into enum values."""
    client = MachShipClient(
        MachShipConfig(
            base_url="https://example.com",
            token="secret",
            raise_on_api_errors=False,
        ),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "object": True,
                    "errors": [
                        {
                            "memberNames": ["companyId"],
                            "errorMessage": "Company is required",
                            "validationType": "Error",
                        }
                    ],
                },
            )
        ),
    )

    response = client.ping()

    assert response.errors is not None
    assert response.errors[0].validation_type == MachshipValidationType.integer_1


def test_validation_type_rejects_unknown_string_labels() -> None:
    """Verify unknown MachShip labels still fail validation."""
    with pytest.raises(ValueError):
        MachshipValidationType("Unknown")
    assert MachshipValidationType._missing_(99) is None


def test_create_consignment_accepts_string_item_type_and_naive_utc_response() -> None:
    """Verify create-consignment responses tolerate MachShip's payload shape."""
    request_body = CreateConsignmentV2(
        items=[
            CreateConsignmentItemV2(
                item_type=1,
                name="IKNG01526537_420gsm Artboard_stack_2",
                sku="SKU-001",
                quantity=1,
                height=30,
                weight=2.07,
                length=5.5,
                width=19.5,
            )
        ]
    )

    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        """Capture the outgoing request and return a valid MachShip response."""
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["payload"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "object": {
                    "id": 987654,
                    "consignmentNumber": "MACH-000123",
                    "despatchDateUtc": "2026-04-09T14:00:00",
                    "etaUtc": "2026-04-14T13:59:59",
                    "items": [
                        {
                            "itemType": "Carton",
                            "name": "IKNG01526537_420gsm Artboard_stack_2",
                            "sku": "SKU-001",
                            "quantity": 1,
                            "height": 30,
                            "weight": 2.07,
                            "length": 5.5,
                            "width": 19.5,
                        }
                    ],
                },
                "errors": [],
            },
        )

    client = MachShipClient(
        MachShipConfig(base_url="https://example.com", token="secret"),
        transport=httpx.MockTransport(handler),
    )

    response = client.create_consignment(request_body)

    assert seen["method"] == "POST"
    assert seen["url"] == "https://example.com/apiv2/consignments/createConsignment"
    assert seen["payload"]["items"][0]["itemType"] == 1
    assert response.object is not None
    assert response.object.despatch_date_utc is not None
    assert response.object.despatch_date_utc.tzinfo is not None
    assert response.object.eta_utc is not None
    assert response.object.eta_utc.tzinfo is not None
    assert response.object.items is not None
    assert response.object.items[0].item_type == ItemType.integer_1


def test_async_client_smoke() -> None:
    """Verify the async client path can send a route request successfully."""
    async def run() -> None:
        """Execute the async client request against a mocked response."""
        def handler(request: httpx.Request) -> httpx.Response:
            """Assert the outgoing payload and return a valid response."""
            if request.url.path == "/apiv2/routes/returnroutes":
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
            if request.url.path == "/apiv2/locations/returnLocations":
                payload = json.loads(request.content.decode())
                assert payload["rawLocations"][0]["suburb"] == "Melbourne"
                return httpx.Response(
                    200,
                    json={
                        "object": [
                            {
                                "id": 3,
                                "postcode": "3000",
                                "suburb": "Melbourne",
                                "locationType": 0,
                            }
                        ],
                        "errors": [],
                    },
                )
            if (
                request.url.path
                == "/apiv2/locations/returnLocationsWithSearchOptions"
            ):
                payload = json.loads(request.content.decode())
                assert payload["retrievalSize"] == 5
                assert request.url.params.get("s") == "Mel 3000"
                return httpx.Response(
                    200,
                    json={
                        "object": [
                            {
                                "id": 4,
                                "postcode": "3000",
                                "suburb": "Melbourne",
                                "locationType": 0,
                            }
                        ],
                        "errors": [],
                    },
                )
            raise AssertionError(f"unexpected path: {request.url.path}")

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
        lookup_response = await client.return_locations(
            RawLocationsWithLocationSearchOptions(
                raw_locations=[
                    RawLocation(suburb="Melbourne", postcode="3000"),
                ],
                location_search_options=LocationSearchOptions(company_id=123),
            )
        )
        assert lookup_response.object is not None
        assert lookup_response.object[0].id == 3
        search_response = await client.return_locations_with_search_options(
            LocationSearchOptionsV2(
                company_id=456,
                retrieval_size=5,
            ),
            search="Mel 3000",
        )
        assert search_response.object is not None
        assert search_response.object[0].id == 4
        await client.aclose()

    asyncio.run(run())
