"""Additional tests to drive client-module coverage to 100%."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from machship_sdk import (
    AsyncMachShipClient,
    MachShipClient,
    MachShipConfig,
)
from machship_sdk.exceptions import MachShipHTTPError
from machship_sdk.models import (
    CreateConsignmentComplexRequest,
    CreateConsignmentItemV2,
    CreateConsignmentRequest,
    LocationSearchOptions,
    LocationSearchOptionsV2,
    RawLocation,
    RawLocationsWithLocationSearchOptions,
    RouteRequest,
    RouteRequestComplex,
)
from machship_sdk.models.generated import (
    BookedManifestV2,
    CreateConsignmentItemComplexV2,
    ManifestRebooking,
    ManualTrackingStatus,
)
from machship_sdk.fusedship import (
    AsyncFusedShipClient,
    FusedShipAPIError,
    FusedShipAddress,
    FusedShipClient,
    FusedShipConfig,
    FusedShipHTTPError,
    FusedShipLivePricingRequest,
    FusedShipQuote,
    FusedShipQuoteItem,
    FusedShipRequestTokenRequest,
)


def _machship_request_handler(request: httpx.Request) -> httpx.Response:
    """Return responses that exercise MachShip request edge cases."""
    path = request.url.path
    if path == "/raw":
        return httpx.Response(200, json={"answer": 1})
    if path == "/bytes-ok":
        return httpx.Response(200, content=b"binary-payload")
    if path == "/invalid":
        return httpx.Response(200, content=b"not-json")
    if path == "/http-error":
        return httpx.Response(500, text="boom")
    if path == "/bytes-error":
        return httpx.Response(500, text="boom")
    if path == "/apiv2/authenticate/ping":
        return httpx.Response(
            200,
            json={
                "object": True,
                "errors": [
                    {
                        "errorMessage": "validation failed",
                    }
                ],
            },
        )
    raise AssertionError(f"unexpected path: {path}")


def _fusedship_request_handler(request: httpx.Request) -> httpx.Response:
    """Return responses that exercise FusedShip request edge cases."""
    path = request.url.path
    if path == "/raw":
        return httpx.Response(200, json={"answer": 1})
    if path == "/empty":
        return httpx.Response(204)
    if path == "/invalid":
        return httpx.Response(200, content=b"not-json")
    if path == "/http-error":
        return httpx.Response(500, text="boom")
    if path == "/api-error":
        return httpx.Response(200, json={"error": "bad request"})
    if path == "/ecommerce/request-token":
        return httpx.Response(200, json={"session_key": "jwt-token"})
    if path.startswith("/live-pricing/"):
        return httpx.Response(
            200,
            json={
                "rates": [],
                "quoted_items": [],
            },
        )
    raise AssertionError(f"unexpected path: {path}")


def _record_request(
    call_log: list[dict[str, object]],
    method: str,
    path: str,
    **kwargs,
):
    """Capture a request call and return a sentinel payload."""
    response_model = kwargs.pop("response_model", None)
    call_log.append(
        {
            "method": method,
            "path": path,
            "response_model": getattr(response_model, "__name__", None),
            **kwargs,
        }
    )
    return {"method": method, "path": path}


def _record_bytes(
    call_log: list[dict[str, object]],
    method: str,
    path: str,
    **kwargs,
):
    """Capture a bytes request call and return a sentinel payload."""
    call_log.append(
        {
            "method": method,
            "path": path,
            **kwargs,
        }
    )
    return b"binary-payload"


def _machship_route_request() -> RouteRequest:
    """Return a minimal MachShip route request model."""
    return RouteRequest(items=[CreateConsignmentItemV2()])


def _machship_route_request_complex() -> RouteRequestComplex:
    """Return a minimal MachShip complex route request model."""
    return RouteRequestComplex(items=[CreateConsignmentItemComplexV2()])


def _machship_create_consignment_request() -> CreateConsignmentRequest:
    """Return a minimal MachShip consignment request model."""
    return CreateConsignmentRequest(items=[CreateConsignmentItemV2()])


def _machship_create_consignment_complex_request() -> CreateConsignmentComplexRequest:
    """Return a minimal MachShip complex consignment request model."""
    return CreateConsignmentComplexRequest(
        items=[CreateConsignmentItemComplexV2()]
    )


def _machship_manual_tracking_statuses() -> list[ManualTrackingStatus]:
    """Return minimal tracking status payloads."""
    return [ManualTrackingStatus(), ManualTrackingStatus()]


def _machship_booked_manifests() -> list[BookedManifestV2]:
    """Return a minimal booked manifest payload."""
    return [BookedManifestV2(consignment_ids=[1], company_id=1)]


def _machship_manifest_rebooking() -> ManifestRebooking:
    """Return a minimal manifest rebooking payload."""
    return ManifestRebooking(manifest_id=1)


def _machship_location_lookup_request() -> RawLocationsWithLocationSearchOptions:
    """Return a minimal location lookup payload."""
    return RawLocationsWithLocationSearchOptions(
        raw_locations=[RawLocation(suburb="Melbourne", postcode="3000")],
        location_search_options=LocationSearchOptions(company_id=1),
    )


def _machship_location_search_request() -> LocationSearchOptionsV2:
    """Return a minimal location search payload."""
    return LocationSearchOptionsV2(company_id=1, retrieval_size=10)


def _fusedship_request_token_request() -> FusedShipRequestTokenRequest:
    """Return a minimal FusedShip request-token payload."""
    return FusedShipRequestTokenRequest(
        client_token="client-456",
        store_id="store-789",
    )


def _fusedship_live_pricing_request() -> FusedShipLivePricingRequest:
    """Return a minimal FusedShip live-pricing payload."""
    return FusedShipLivePricingRequest(
        quote=FusedShipQuote(
            warehouse=FusedShipAddress(),
            shipping_address=FusedShipAddress(),
            items=[FusedShipQuoteItem()],
        )
    )


def _assert_machship_wrapper_paths(
    request_calls: list[dict[str, object]],
    byte_calls: list[dict[str, object]],
) -> None:
    """Verify the sync and async wrapper paths stay aligned."""
    assert [call["path"] for call in request_calls] == [
        "/apiv2/authenticate/ping",
        "/apiv2/companies/getAll",
        "/apiv2/companies/getAvailableCarriersAccountsAndServices",
        "/apiv2/locations/returnLocations",
        "/apiv2/locations/returnLocationsWithSearchOptions",
        "/apiv2/routes/returnroutes",
        "/apiv2/routes/returnroutes",
        "/apiv2/routes/returnmultipleroutes",
        "/apiv2/routes/returnrouteswithcomplexitems",
        "/apiv2/routes/returnrouteswithcomplexitems",
        "/apiv2/consignments/createConsignment",
        "/apiv2/consignments/createConsignment",
        "/apiv2/consignments/createConsignmentwithComplexItems",
        "/apiv2/consignments/getConsignment",
        "/apiv2/consignments/returnConsignmentStatuses",
        "/apiv2/consignments/updateConsignmentStatuses",
        "/apiv2/labels/getConsignmentPdfFileInfo",
        "/apiv2/labels/getConsignmentPdfFileInfo",
        "/apiv2/labels/getManifestPdfFileInfo",
        "/apiv2/manifests/getAll",
        "/apiv2/manifests/groupConsignmentsForManifest",
        "/apiv2/manifests/groupAllUnmanifestedConsignmentsForManifest",
        "/apiv2/manifests/manifest",
        "/apiv2/manifests/rebookPickup",
        "/apiv2/companyLocations/getAll",
        "/apiv2/companyLocations/getAll",
        "/apiv2/companyLocations/get",
        "/apiv2/companyLocations/getPermanentPickupsForCompanyLocation",
    ]
    assert [call["path"] for call in byte_calls] == [
        "/apiv2/labels/getConsignmentPdf",
        "/apiv2/labels/getConsignmentPdf",
        "/apiv2/labels/getManifestPdf",
    ]


class EmptyAsyncRetryer:
    """Async iterator that yields no retry attempts."""

    def __aiter__(self):
        """Return the iterator itself."""
        return self

    async def __anext__(self):
        """Stop iteration immediately."""
        raise StopAsyncIteration


def test_client_constructors_reject_client_and_transport() -> None:
    """Cover the constructor guard in each client implementation."""
    with httpx.Client() as sync_client:
        with pytest.raises(
            ValueError,
            match="Pass either client or transport, not both",
        ):
            MachShipClient(
                MachShipConfig(
                    base_url="https://example.com",
                    token="secret",
                ),
                client=sync_client,
                transport=httpx.MockTransport(lambda request: httpx.Response(200)),
            )

        with pytest.raises(
            ValueError,
            match="Pass either client or transport, not both",
        ):
            FusedShipClient(
                FusedShipConfig(),
                client=sync_client,
                transport=httpx.MockTransport(lambda request: httpx.Response(200)),
            )

    async def exercise_async() -> None:
        """Exercise the async constructor guard."""
        async with httpx.AsyncClient() as async_client:
            with pytest.raises(
                ValueError,
                match="Pass either client or transport, not both",
            ):
                AsyncMachShipClient(
                    MachShipConfig(
                        base_url="https://example.com",
                        token="secret",
                    ),
                    client=async_client,
                    transport=httpx.MockTransport(
                        lambda request: httpx.Response(200)
                    ),
                )

            with pytest.raises(
                ValueError,
                match="Pass either client or transport, not both",
            ):
                AsyncFusedShipClient(
                    FusedShipConfig(),
                    client=async_client,
                    transport=httpx.MockTransport(
                        lambda request: httpx.Response(200)
                    ),
                )

    asyncio.run(exercise_async())


def test_machship_client_from_env_and_wrappers(monkeypatch) -> None:
    """Cover MachShip sync client factories, properties, and wrappers."""
    monkeypatch.setenv("MACHSHIP_BASE_URL", "https://mach.example.com/")
    monkeypatch.setenv("MACHSHIP_TOKEN", "mach-token")

    request_calls: list[dict[str, object]] = []
    byte_calls: list[dict[str, object]] = []

    with MachShipClient.from_env() as client:
        assert client.config.base_url == "https://mach.example.com"
        assert client.http_client is not None

        monkeypatch.setattr(
            client,
            "request",
            lambda method, path, **kwargs: _record_request(
                request_calls,
                method,
                path,
                **kwargs,
            ),
        )
        monkeypatch.setattr(
            client,
            "request_bytes",
            lambda method, path, **kwargs: _record_bytes(
                byte_calls,
                method,
                path,
                **kwargs,
            ),
        )

        assert client.ping()["path"] == "/apiv2/authenticate/ping"
        assert client.get_companies(at_or_below_company_id=10)["path"] == (
            "/apiv2/companies/getAll"
        )
        assert client.get_available_carriers_accounts_and_services(
            company_id=11,
        )["path"] == "/apiv2/companies/getAvailableCarriersAccountsAndServices"
        assert client.return_locations(
            _machship_location_lookup_request(),
        )["path"] == "/apiv2/locations/returnLocations"
        assert client.return_locations_with_search_options(
            _machship_location_search_request(),
            search="Mel 3000",
        )["path"] == "/apiv2/locations/returnLocationsWithSearchOptions"
        assert client.return_routes(_machship_route_request())["path"] == (
            "/apiv2/routes/returnroutes"
        )
        assert client.get_rates(_machship_route_request())["path"] == (
            "/apiv2/routes/returnroutes"
        )
        assert client.return_multiple_routes(
            [_machship_route_request(), _machship_route_request()]
        )[
            "path"
        ] == "/apiv2/routes/returnmultipleroutes"
        assert client.return_routes_with_complex_items(
            _machship_route_request_complex()
        )["path"] == (
            "/apiv2/routes/returnrouteswithcomplexitems"
        )
        assert client.get_rates_with_complex_items(
            _machship_route_request_complex()
        )["path"] == (
            "/apiv2/routes/returnrouteswithcomplexitems"
        )
        assert client.create_consignment(_machship_create_consignment_request())[
            "path"
        ] == (
            "/apiv2/consignments/createConsignment"
        )
        assert client.create_shipment(_machship_create_consignment_request())[
            "path"
        ] == (
            "/apiv2/consignments/createConsignment"
        )
        assert client.create_consignment_with_complex_items(
            _machship_create_consignment_complex_request(),
        )["path"] == "/apiv2/consignments/createConsignmentwithComplexItems"
        assert client.get_consignment(
            123,
            include_deleted=True,
            include_request_guids=True,
        )["path"] == "/apiv2/consignments/getConsignment"
        assert client.return_consignment_statuses(
            since_date_created_utc="2026-01-01",
        )["path"] == "/apiv2/consignments/returnConsignmentStatuses"
        assert client.update_consignment_statuses(
            _machship_manual_tracking_statuses(),
        )["path"] == "/apiv2/consignments/updateConsignmentStatuses"
        assert client.get_consignment_pdf(100) == b"binary-payload"
        assert client.get_label_pdf(101) == b"binary-payload"
        assert client.get_consignment_pdf_file_info(102)["path"] == (
            "/apiv2/labels/getConsignmentPdfFileInfo"
        )
        assert client.get_label_file_info(103)["path"] == (
            "/apiv2/labels/getConsignmentPdfFileInfo"
        )
        assert client.get_manifest_pdf(200) == b"binary-payload"
        assert client.get_manifest_pdf_file_info(201)["path"] == (
            "/apiv2/labels/getManifestPdfFileInfo"
        )
        assert client.list_manifests(
            company_id=1,
            start_index=2,
            retrieve_size=3,
            carrier_id=4,
            include_child_companies=True,
            start_date="2026-01-01",
            end_date="2026-01-31",
        )["path"] == "/apiv2/manifests/getAll"
        assert client.group_consignments_for_manifest([1, 2])["path"] == (
            "/apiv2/manifests/groupConsignmentsForManifest"
        )
        assert client.group_all_unmanifested_consignments_for_manifest(5)[
            "path"
        ] == "/apiv2/manifests/groupAllUnmanifestedConsignmentsForManifest"
        assert client.book_manifest(_machship_booked_manifests())["path"] == (
            "/apiv2/manifests/manifest"
        )
        assert client.rebook_pickup(_machship_manifest_rebooking())["path"] == (
            "/apiv2/manifests/rebookPickup"
        )
        assert client.get_company_locations(company_id=6)["path"] == (
            "/apiv2/companyLocations/getAll"
        )
        assert client.list_company_locations(company_id=7)["path"] == (
            "/apiv2/companyLocations/getAll"
        )
        assert client.get_company_location(8)["path"] == (
            "/apiv2/companyLocations/get"
        )
        assert client.get_company_location_permanent_pickups(9)["path"] == (
            "/apiv2/companyLocations/getPermanentPickupsForCompanyLocation"
        )

        _assert_machship_wrapper_paths(request_calls, byte_calls)
    assert request_calls[1]["params"] == {"atOrBelowCompanyId": 10}
    assert request_calls[3]["json"] == _machship_location_lookup_request()
    assert request_calls[4]["params"] == {"s": "Mel 3000"}
    assert request_calls[4]["json"] == _machship_location_search_request()
    assert request_calls[7]["json"] == [
        _machship_route_request(),
        _machship_route_request(),
    ]


def test_async_machship_client_from_env_and_wrappers(monkeypatch) -> None:
    """Cover MachShip async client factories, properties, and wrappers."""

    async def exercise() -> None:
        """Exercise the async wrapper path coverage."""
        monkeypatch.setenv("MACHSHIP_BASE_URL", "https://mach.example.com/")
        monkeypatch.setenv("MACHSHIP_TOKEN", "mach-token")

        request_calls: list[dict[str, object]] = []
        byte_calls: list[dict[str, object]] = []

        async with AsyncMachShipClient.from_env() as client:
            assert client.config.base_url == "https://mach.example.com"
            assert client.http_client is not None

            async def fake_request(method: str, path: str, **kwargs):
                """Record async request calls for wrapper assertions."""
                return _record_request(request_calls, method, path, **kwargs)

            async def fake_request_bytes(method: str, path: str, **kwargs):
                """Record async byte-request calls for wrapper assertions."""
                return _record_bytes(byte_calls, method, path, **kwargs)

            monkeypatch.setattr(client, "request", fake_request)
            monkeypatch.setattr(client, "request_bytes", fake_request_bytes)

            assert (await client.ping())["path"] == "/apiv2/authenticate/ping"
            assert (
                await client.get_companies(at_or_below_company_id=10)
            )["path"] == "/apiv2/companies/getAll"
            assert (
                await client.get_available_carriers_accounts_and_services(
                    company_id=11,
                )
            )["path"] == "/apiv2/companies/getAvailableCarriersAccountsAndServices"
            assert (
                await client.return_locations(
                    _machship_location_lookup_request(),
                )
            )["path"] == "/apiv2/locations/returnLocations"
            assert (
                await client.return_locations_with_search_options(
                    _machship_location_search_request(),
                    search="Mel 3000",
                )
            )["path"] == (
                "/apiv2/locations/returnLocationsWithSearchOptions"
            )
            assert (await client.return_routes(_machship_route_request()))["path"] == (
                "/apiv2/routes/returnroutes"
            )
            assert (await client.get_rates(_machship_route_request()))["path"] == (
                "/apiv2/routes/returnroutes"
            )
            assert (
                await client.return_multiple_routes(
                    [_machship_route_request(), _machship_route_request()],
                )
            )["path"] == "/apiv2/routes/returnmultipleroutes"
            assert (
                await client.return_routes_with_complex_items(
                    _machship_route_request_complex(),
                )
            )["path"] == "/apiv2/routes/returnrouteswithcomplexitems"
            assert (
                await client.get_rates_with_complex_items(
                    _machship_route_request_complex(),
                )
            )["path"] == "/apiv2/routes/returnrouteswithcomplexitems"
            assert (
                await client.create_consignment(
                    _machship_create_consignment_request(),
                )
            )["path"] == (
                "/apiv2/consignments/createConsignment"
            )
            assert (
                await client.create_shipment(
                    _machship_create_consignment_request(),
                )
            )["path"] == (
                "/apiv2/consignments/createConsignment"
            )
            assert (
                await client.create_consignment_with_complex_items(
                    _machship_create_consignment_complex_request(),
                )
            )["path"] == "/apiv2/consignments/createConsignmentwithComplexItems"
            assert (
                await client.get_consignment(
                    123,
                    include_deleted=True,
                    include_request_guids=True,
                )
            )["path"] == "/apiv2/consignments/getConsignment"
            assert (
                await client.return_consignment_statuses(
                    since_date_created_utc="2026-01-01",
                )
            )["path"] == "/apiv2/consignments/returnConsignmentStatuses"
            assert (
                await client.update_consignment_statuses(
                    _machship_manual_tracking_statuses(),
                )
            )["path"] == "/apiv2/consignments/updateConsignmentStatuses"
            assert await client.get_consignment_pdf(100) == b"binary-payload"
            assert await client.get_label_pdf(101) == b"binary-payload"
            assert (
                await client.get_consignment_pdf_file_info(102)
            )["path"] == "/apiv2/labels/getConsignmentPdfFileInfo"
            assert (await client.get_label_file_info(103))["path"] == (
                "/apiv2/labels/getConsignmentPdfFileInfo"
            )
            assert await client.get_manifest_pdf(200) == b"binary-payload"
            assert (
                await client.get_manifest_pdf_file_info(201)
            )["path"] == "/apiv2/labels/getManifestPdfFileInfo"
            assert (
                await client.list_manifests(
                    company_id=1,
                    start_index=2,
                    retrieve_size=3,
                    carrier_id=4,
                    include_child_companies=True,
                    start_date="2026-01-01",
                    end_date="2026-01-31",
                )
            )["path"] == "/apiv2/manifests/getAll"
            assert (
                await client.group_consignments_for_manifest(
                    [1, 2],
                )
            )["path"] == "/apiv2/manifests/groupConsignmentsForManifest"
            assert (
                await client.group_all_unmanifested_consignments_for_manifest(
                    5,
                )
            )["path"] == (
                "/apiv2/manifests/groupAllUnmanifestedConsignmentsForManifest"
            )
            assert (await client.book_manifest(_machship_booked_manifests()))[
                "path"
            ] == (
                "/apiv2/manifests/manifest"
            )
            assert (await client.rebook_pickup(_machship_manifest_rebooking()))[
                "path"
            ] == (
                "/apiv2/manifests/rebookPickup"
            )
            assert (await client.get_company_locations(company_id=6))["path"] == (
                "/apiv2/companyLocations/getAll"
            )
            assert (await client.list_company_locations(company_id=7))["path"] == (
                "/apiv2/companyLocations/getAll"
            )
            assert (await client.get_company_location(8))["path"] == (
                "/apiv2/companyLocations/get"
            )
            assert (
                await client.get_company_location_permanent_pickups(9)
            )["path"] == "/apiv2/companyLocations/getPermanentPickupsForCompanyLocation"

            _assert_machship_wrapper_paths(request_calls, byte_calls)

    asyncio.run(exercise())


def test_machship_client_request_edge_cases() -> None:
    """Cover MachShip request parsing and error branches."""
    client = MachShipClient(
        MachShipConfig(
            base_url="https://example.com",
            token="secret",
            raise_on_api_errors=False,
        ),
        transport=httpx.MockTransport(_machship_request_handler),
    )

    assert client.request("GET", "/raw", response_model=None) == {"answer": 1}
    with pytest.raises(MachShipHTTPError):
        client.request("GET", "/http-error")

    with pytest.raises(MachShipHTTPError):
        client.request("GET", "/invalid")

    with pytest.raises(MachShipHTTPError):
        client.request_bytes("GET", "/bytes-error")

    assert client.request_bytes("GET", "/bytes-ok") == b"binary-payload"

    assert client.ping().object is True


def test_async_machship_client_request_edge_cases() -> None:
    """Cover MachShip async request parsing and error branches."""

    async def exercise() -> None:
        client = AsyncMachShipClient(
            MachShipConfig(
                base_url="https://example.com",
                token="secret",
                raise_on_api_errors=False,
            ),
            transport=httpx.MockTransport(_machship_request_handler),
        )

        assert await client.request("GET", "/raw", response_model=None) == {
            "answer": 1
        }
        with pytest.raises(MachShipHTTPError):
            await client.request("GET", "/http-error")

        with pytest.raises(MachShipHTTPError):
            await client.request("GET", "/invalid")

        with pytest.raises(MachShipHTTPError):
            await client.request_bytes("GET", "/bytes-error")

        assert await client.request_bytes("GET", "/bytes-ok") == b"binary-payload"

        assert (await client.ping()).object is True
        await client.aclose()

    asyncio.run(exercise())


def test_fusedship_client_from_env_and_wrappers(monkeypatch) -> None:
    """Cover FusedShip sync client factories, properties, and wrappers."""
    monkeypatch.setenv("FUSEDSHIP_BASE_URL", "https://fused.example.com/")
    monkeypatch.setenv("FUSEDSHIP_TOKEN", "fused-token")
    monkeypatch.setenv("FUSEDSHIP_INTEGRATION_ID", "integration-123")
    monkeypatch.setenv("FUSEDSHIP_CLIENT_TOKEN", "client-456")
    monkeypatch.setenv("FUSEDSHIP_STORE_ID", "store-789")

    request_calls: list[dict[str, object]] = []

    with FusedShipClient.from_env() as client:
        assert client.config.base_url == "https://fused.example.com"
        assert client.http_client is not None

        monkeypatch.setattr(
            client,
            "request",
            lambda method, path, **kwargs: _record_request(
                request_calls,
                method,
                path,
                **kwargs,
            ),
        )

        assert client.request_token(request=_fusedship_request_token_request())[
            "path"
        ] == (
            "/ecommerce/request-token"
        )
        assert client.build_ecommerce_url("session") == (
            "https://fused.example.com/ecommerce/app?session_key=session"
        )
        assert client.build_ecommerce_url(
            "session",
            active_tab="quote",
        ) == (
            "https://fused.example.com/ecommerce/app?"
            "session_key=session&active_tab=quote"
        )
        assert client.quote_live_pricing(
            "shopify",
            _fusedship_live_pricing_request(),
        )["path"] == "/live-pricing/shopify"

    assert [call["path"] for call in request_calls] == [
        "/ecommerce/request-token",
        "/live-pricing/shopify",
    ]
    assert request_calls[1]["headers"] == {
        "token": "fused-token",
        "integration_id": "integration-123",
    }


def test_fusedship_client_missing_credentials() -> None:
    """Cover the FusedShip sync credential validation branches."""
    client = FusedShipClient(FusedShipConfig())

    with pytest.raises(
        ValueError,
        match="FusedShip client_token and store_id are required",
    ):
        client.request_token()

    with pytest.raises(ValueError, match="FusedShip live pricing token is required"):
        client.quote_live_pricing(
            "shopify",
            _fusedship_live_pricing_request(),
            integration_id="iid",
        )

    with pytest.raises(ValueError, match="FusedShip integration_id is required"):
        client.quote_live_pricing(
            "shopify",
            _fusedship_live_pricing_request(),
            token="tok",
        )


def test_fusedship_client_request_edge_cases() -> None:
    """Cover FusedShip sync request parsing and error branches."""
    client = FusedShipClient(
        FusedShipConfig(
            token="fused-token",
            integration_id="integration-123",
            headers={"x-request-id": "abc123"},
        ),
        transport=httpx.MockTransport(_fusedship_request_handler),
    )

    assert client.request("GET", "/raw", response_model=None) == {"answer": 1}
    assert client.request("GET", "/empty") is None

    with pytest.raises(FusedShipHTTPError):
        client.request("GET", "/http-error")

    with pytest.raises(FusedShipHTTPError):
        client.request("GET", "/invalid")

    with pytest.raises(FusedShipAPIError):
        client.request("GET", "/api-error")


def test_async_fusedship_client_missing_credentials() -> None:
    """Cover the FusedShip async credential validation branches."""

    async def exercise() -> None:
        """Exercise the async FusedShip credential checks."""
        client = AsyncFusedShipClient(FusedShipConfig())

        with pytest.raises(
            ValueError,
            match="FusedShip client_token and store_id are required",
        ):
            await client.request_token()

        with pytest.raises(
            ValueError,
            match="FusedShip live pricing token is required",
        ):
            await client.quote_live_pricing(
                "shopify",
                _fusedship_live_pricing_request(),
                integration_id="iid",
            )

        with pytest.raises(
            ValueError,
            match="FusedShip integration_id is required",
        ):
            await client.quote_live_pricing(
                "shopify",
                _fusedship_live_pricing_request(),
                token="tok",
            )

        await client.aclose()

    asyncio.run(exercise())


def test_async_fusedship_client_from_env_and_wrappers(monkeypatch) -> None:
    """Cover FusedShip async client factories, properties, and wrappers."""

    async def exercise() -> None:
        """Exercise the async wrapper path coverage."""
        monkeypatch.setenv("FUSEDSHIP_BASE_URL", "https://fused.example.com/")
        monkeypatch.setenv("FUSEDSHIP_TOKEN", "fused-token")
        monkeypatch.setenv("FUSEDSHIP_INTEGRATION_ID", "integration-123")
        monkeypatch.setenv("FUSEDSHIP_CLIENT_TOKEN", "client-456")
        monkeypatch.setenv("FUSEDSHIP_STORE_ID", "store-789")

        request_calls: list[dict[str, object]] = []

        async with AsyncFusedShipClient.from_env() as client:
            assert client.config.base_url == "https://fused.example.com"
            assert client.http_client is not None

            async def fake_request(method: str, path: str, **kwargs):
                """Record async request calls for wrapper assertions."""
                return _record_request(request_calls, method, path, **kwargs)

            monkeypatch.setattr(client, "request", fake_request)

            assert (
                await client.request_token(
                    request=_fusedship_request_token_request(),
                )
            )["path"] == "/ecommerce/request-token"
            assert client.build_ecommerce_url("session") == (
                "https://fused.example.com/ecommerce/app?session_key=session"
            )
            assert client.build_ecommerce_url(
                "session",
                active_tab="quote",
            ) == (
                "https://fused.example.com/ecommerce/app?"
                "session_key=session&active_tab=quote"
            )
            assert (
                await client.quote_live_pricing(
                    "shopify",
                    _fusedship_live_pricing_request(),
                )
            )["path"] == "/live-pricing/shopify"

        assert [call["path"] for call in request_calls] == [
            "/ecommerce/request-token",
            "/live-pricing/shopify",
        ]

    asyncio.run(exercise())


def test_async_fusedship_client_request_edge_cases() -> None:
    """Cover FusedShip async request parsing and error branches."""

    async def exercise() -> None:
        """Exercise the async request edge-case branches."""
        client = AsyncFusedShipClient(
            FusedShipConfig(
                token="fused-token",
                integration_id="integration-123",
                headers={"x-request-id": "abc123"},
            ),
            transport=httpx.MockTransport(_fusedship_request_handler),
        )

        assert await client.request("GET", "/raw", response_model=None) == {
            "answer": 1
        }
        assert await client.request("GET", "/empty") is None

        with pytest.raises(FusedShipHTTPError):
            await client.request("GET", "/http-error")

        with pytest.raises(FusedShipHTTPError):
            await client.request("GET", "/invalid")

        with pytest.raises(FusedShipAPIError):
            await client.request("GET", "/api-error")

        await client.aclose()

    asyncio.run(exercise())
