"""Asynchronous MachShip client implementation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypeVar
from time import perf_counter

import httpx

from ._core import (
    build_headers,
    build_url,
    maybe_raise_for_api_errors,
    parse_response_model,
    serialize_query_params,
)
from ._version import __version__
from .config import MachShipConfig
from .exceptions import MachShipError, MachShipHTTPError
from .retries import RetryPolicy, run_async_with_retry
from .serialization import dump_json_payload, load_json_payload
from ._logging import emit_log
from .telemetry import request_span, set_span_attributes
from .models.generated import (
    BooleanBaseDomainEntityV2,
    BookedManifestV2,
    BookedManifestV2ICollectionBaseDomainEntityV2,
    CarrierWithAccountsAndServicesLiteIEnumerableBaseDomainEntityV2,
    CompanyLocationV2BaseDomainEntityV2,
    CompanyLocationV2GridDomainEntityV2,
    CompanyLocationV2PermanentPickupsBaseDomainEntityV2,
    CompanyV2WithParentIdIEnumerableBaseDomainEntityV2,
    ConsignmentIdWithTrackingHistoryV2IEnumerableBaseDomainEntity,
    ConsignmentV2BaseDomainEntityV2,
    CreateConsignmentComplexItemsV2,
    CreateConsignmentResponseV2BaseDomainEntityV2,
    CreateConsignmentV2,
    EmptyDomainEntityV2,
    FileInfoBaseDomainEntityV2,
    LocationSearchOptionsV2,
    LocationV2ICollectionBaseDomainEntityV2,
    LocationV2IEnumerableBaseDomainEntityV2,
    ManifestForListWithConsignmentsGridDomainEntityV2,
    ManifestRebooking,
    ManualTrackingStatus,
    RebookedPickupBaseDomainEntityV2,
    ReturnBookedManifestV2ICollectionBaseDomainEntityV2,
    RawLocationsWithLocationSearchOptions,
    RouteRequestComplexItemsV2,
    RouteRequestV2,
    RoutesResponseV2ArrayBaseDomainEntityV2,
    RoutesResponseV2BaseDomainEntityV2,
)

ResponseModelT = TypeVar("ResponseModelT")


class AsyncMachShipClient:
    """Asynchronous MachShip client implementation."""

    def __init__(
        self,
        config: MachShipConfig,
        *,
        client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_policy: RetryPolicy | None = None,
        logger: Any | None = None,
        tracer: Any | None = None,
    ) -> None:
        """Initialize the asynchronous MachShip client.

        Args:
            config: The client configuration.
            client: An optional HTTPX asynchronous client to use.
            transport: An optional HTTPX asynchronous transport to use.
            retry_policy: Optional retry policy for transient failures.
            logger: Optional logger for request events.
            tracer: Optional OpenTelemetry tracer for request spans.
        """
        if client is not None and transport is not None:
            raise ValueError("Pass either client or transport, not both")

        self._config = config
        self._client = client or httpx.AsyncClient(
            timeout=config.timeout,
            verify=config.verify,
            follow_redirects=config.follow_redirects,
            transport=transport,
        )
        self._owns_client = client is None
        self._retry_policy = retry_policy
        self._logger = logger
        self._tracer = tracer

    @property
    def config(self) -> MachShipConfig:
        """Get the client configuration."""
        return self._config

    @property
    def http_client(self) -> httpx.AsyncClient:
        """Get the underlying HTTPX asynchronous client."""
        return self._client

    @classmethod
    def from_env(cls, **kwargs: Any) -> "AsyncMachShipClient":
        """Create an asynchronous client from environment variables.

        Args:
            **kwargs: Additional arguments passed to MachShipConfig.from_env.
        """
        client = kwargs.pop("client", None)
        transport = kwargs.pop("transport", None)
        retry_policy = kwargs.pop("retry_policy", None)
        logger = kwargs.pop("logger", None)
        tracer = kwargs.pop("tracer", None)
        return cls(
            MachShipConfig.from_env(**kwargs),
            client=client,
            transport=transport,
            retry_policy=retry_policy,
            logger=logger,
            tracer=tracer,
        )

    def _prepare_request(
        self,
        path: str,
        *,
        params: Any | None = None,
        json: Any | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Build request URL, headers, and payload kwargs."""
        url = build_url(self._config.base_url, path)
        request_headers = build_headers(
            token=self._config.token,
            extra_headers={**self._config.headers, **(headers or {})},
            user_agent=f"machship-sdk/{__version__}",
        )
        request_kwargs: dict[str, Any] = {
            "params": serialize_query_params(params),
            "headers": request_headers,
        }
        if json is not None:
            request_kwargs["content"] = dump_json_payload(json)
            request_kwargs["headers"] = {
                **request_headers,
                "content-type": "application/json",
            }
        return url, request_kwargs

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "AsyncMachShipClient":
        """Enter the runtime context."""
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Exit the runtime context."""
        await self.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Any | None = None,
        json: Any | None = None,
        response_model: type[ResponseModelT] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> ResponseModelT | Any:
        url, request_kwargs = self._prepare_request(
            path,
            params=params,
            json=json,
            headers=headers,
        )
        request_name = f"{method.upper()} {path}"
        start = perf_counter()
        with request_span(
            self._tracer,
            f"MachShip {request_name}",
            service="machship",
            method=method.upper(),
            path=path,
            url=url,
        ) as span:
            emit_log(
                self._logger,
                "debug",
                "request.start",
                service="machship",
                method=method.upper(),
                path=path,
                url=url,
            )
            try:
                response = await self._client.request(
                    method,
                    url,
                    **request_kwargs,
                )
            except httpx.RequestError as exc:  # pragma: no cover - transport failure
                emit_log(
                    self._logger,
                    "warning",
                    "request.transport_error",
                    service="machship",
                    method=method.upper(),
                    path=path,
                    url=url,
                    error=str(exc),
                    duration_ms=round((perf_counter() - start) * 1000, 2),
                )
                raise MachShipError(f"{method.upper()} {url} failed: {exc}") from exc

            if response.is_error:
                set_span_attributes(
                    span,
                    http_status_code=response.status_code,
                    response_length=len(response.content),
                    error=True,
                )
                emit_log(
                    self._logger,
                    "warning",
                    "request.http_error",
                    service="machship",
                    method=method.upper(),
                    path=path,
                    url=url,
                    status_code=response.status_code,
                    duration_ms=round((perf_counter() - start) * 1000, 2),
                )
                raise MachShipHTTPError(
                    method=method,
                    url=str(response.request.url),
                    status_code=response.status_code,
                    response_text=response.text[:2000] or None,
                )

            try:
                payload = load_json_payload(response.content)
            except ValueError as exc:
                set_span_attributes(
                    span,
                    http_status_code=response.status_code,
                    response_length=len(response.content),
                    error=True,
                )
                emit_log(
                    self._logger,
                    "warning",
                    "request.json_error",
                    service="machship",
                    method=method.upper(),
                    path=path,
                    url=url,
                    status_code=response.status_code,
                    duration_ms=round((perf_counter() - start) * 1000, 2),
                )
                raise MachShipHTTPError(
                    method=method,
                    url=str(response.request.url),
                    status_code=response.status_code,
                    response_text=response.text[:2000] or None,
                ) from exc

            parsed = parse_response_model(payload, response_model)
            maybe_raise_for_api_errors(
                parsed,
                context=request_name,
                raise_on_api_errors=self._config.raise_on_api_errors,
            )
            set_span_attributes(
                span,
                http_status_code=response.status_code,
                response_length=len(response.content),
            )
            emit_log(
                self._logger,
                "debug",
                "request.success",
                service="machship",
                method=method.upper(),
                path=path,
                url=url,
                status_code=response.status_code,
                duration_ms=round((perf_counter() - start) * 1000, 2),
            )
            return parsed

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Any | None = None,
        json: Any | None = None,
        response_model: type[ResponseModelT] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> ResponseModelT | Any:
        """Perform an HTTP request.

        Args:
            method: The HTTP method.
            path: The API path.
            params: Optional query parameters.
            json: Optional JSON payload.
            response_model: Optional model to parse the response into.
            headers: Optional extra headers.
        """
        return await run_async_with_retry(
            self._retry_policy,
            self._request,
            method,
            path,
            params=params,
            json=json,
            response_model=response_model,
            headers=headers,
        )

    async def request_bytes(
        self,
        method: str,
        path: str,
        *,
        params: Any | None = None,
        json: Any | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> bytes:
        """Perform an HTTP request and return the raw bytes.

        Args:
            method: The HTTP method.
            path: The API path.
            params: Optional query parameters.
            json: Optional JSON payload.
            headers: Optional extra headers.
        """
        return await run_async_with_retry(
            self._retry_policy,
            self._request_bytes,
            method,
            path,
            params=params,
            json=json,
            headers=headers,
        )

    async def _request_bytes(
        self,
        method: str,
        path: str,
        *,
        params: Any | None = None,
        json: Any | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> bytes:
        """Perform an HTTP request and return the raw bytes."""
        url, request_kwargs = self._prepare_request(
            path,
            params=params,
            json=json,
            headers=headers,
        )
        request_name = f"{method.upper()} {path}"
        start = perf_counter()
        with request_span(
            self._tracer,
            f"MachShip {request_name}",
            service="machship",
            method=method.upper(),
            path=path,
            url=url,
        ) as span:
            emit_log(
                self._logger,
                "debug",
                "request.start",
                service="machship",
                method=method.upper(),
                path=path,
                url=url,
            )
            try:
                response = await self._client.request(
                    method,
                    url,
                    **request_kwargs,
                )
            except httpx.RequestError as exc:  # pragma: no cover - transport failure
                emit_log(
                    self._logger,
                    "warning",
                    "request.transport_error",
                    service="machship",
                    method=method.upper(),
                    path=path,
                    url=url,
                    error=str(exc),
                    duration_ms=round((perf_counter() - start) * 1000, 2),
                )
                raise MachShipError(f"{method.upper()} {url} failed: {exc}") from exc

            if response.is_error:
                set_span_attributes(
                    span,
                    http_status_code=response.status_code,
                    response_length=len(response.content),
                    error=True,
                )
                emit_log(
                    self._logger,
                    "warning",
                    "request.http_error",
                    service="machship",
                    method=method.upper(),
                    path=path,
                    url=url,
                    status_code=response.status_code,
                    duration_ms=round((perf_counter() - start) * 1000, 2),
                )
                raise MachShipHTTPError(
                    method=method,
                    url=str(response.request.url),
                    status_code=response.status_code,
                    response_text=response.text[:2000] or None,
                )

            set_span_attributes(
                span,
                http_status_code=response.status_code,
                response_length=len(response.content),
            )
            emit_log(
                self._logger,
                "debug",
                "request.success",
                service="machship",
                method=method.upper(),
                path=path,
                url=url,
                status_code=response.status_code,
                duration_ms=round((perf_counter() - start) * 1000, 2),
            )
            return response.content

    async def ping(self) -> BooleanBaseDomainEntityV2:
        """Ping the MachShip API to verify authentication."""
        return await self.request(
            "POST",
            "/apiv2/authenticate/ping",
            response_model=BooleanBaseDomainEntityV2,
        )

    async def get_companies(
        self,
        *,
        at_or_below_company_id: int | None = None,
    ) -> CompanyV2WithParentIdIEnumerableBaseDomainEntityV2:
        """Retrieve all companies.

        Args:
            at_or_below_company_id: Optional company ID filter.
        """
        return await self.request(
            "GET",
            "/apiv2/companies/getAll",
            params={"atOrBelowCompanyId": at_or_below_company_id},
            response_model=CompanyV2WithParentIdIEnumerableBaseDomainEntityV2,
        )

    async def get_available_carriers_accounts_and_services(
        self,
        *,
        company_id: int | None = None,
    ) -> CarrierWithAccountsAndServicesLiteIEnumerableBaseDomainEntityV2:
        """Retrieve available carriers, accounts, and services for a company.

        Args:
            company_id: Optional company ID filter.
        """
        return await self.request(
            "GET",
            "/apiv2/companies/getAvailableCarriersAccountsAndServices",
            params={"companyId": company_id},
            response_model=(
                CarrierWithAccountsAndServicesLiteIEnumerableBaseDomainEntityV2
            ),
        )

    async def return_locations(
        self,
        request: RawLocationsWithLocationSearchOptions,
    ) -> LocationV2ICollectionBaseDomainEntityV2:
        """Return MachShip locations that exactly match suburb and postcode pairs."""
        return await self.request(
            "POST",
            "/apiv2/locations/returnLocations",
            json=request,
            response_model=LocationV2ICollectionBaseDomainEntityV2,
        )

    async def return_locations_with_search_options(
        self,
        request: LocationSearchOptionsV2,
        *,
        search: str | None = None,
    ) -> LocationV2IEnumerableBaseDomainEntityV2:
        """Search for MachShip locations using a search string and filter options."""
        return await self.request(
            "POST",
            "/apiv2/locations/returnLocationsWithSearchOptions",
            params={"s": search},
            json=request,
            response_model=LocationV2IEnumerableBaseDomainEntityV2,
        )

    async def return_routes(
        self,
        request: RouteRequestV2,
    ) -> RoutesResponseV2BaseDomainEntityV2:
        """Retrieve available routes for a given request.

        Args:
            request: The route request details.
        """
        return await self.request(
            "POST",
            "/apiv2/routes/returnroutes",
            json=request,
            response_model=RoutesResponseV2BaseDomainEntityV2,
        )

    async def get_rates(
        self,
        request: RouteRequestV2,
    ) -> RoutesResponseV2BaseDomainEntityV2:
        """Alias for return_routes.

        Args:
            request: The route request details.
        """
        return await self.return_routes(request)

    async def return_multiple_routes(
        self,
        requests: Sequence[RouteRequestV2],
    ) -> RoutesResponseV2ArrayBaseDomainEntityV2:
        """Retrieve available routes for multiple requests.

        Args:
            requests: A sequence of route requests.
        """
        return await self.request(
            "POST",
            "/apiv2/routes/returnmultipleroutes",
            json=list(requests),
            response_model=RoutesResponseV2ArrayBaseDomainEntityV2,
        )

    async def return_routes_with_complex_items(
        self,
        request: RouteRequestComplexItemsV2,
    ) -> RoutesResponseV2BaseDomainEntityV2:
        """Retrieve available routes with complex items.

        Args:
            request: The route request details with complex items.
        """
        return await self.request(
            "POST",
            "/apiv2/routes/returnrouteswithcomplexitems",
            json=request,
            response_model=RoutesResponseV2BaseDomainEntityV2,
        )

    async def get_rates_with_complex_items(
        self,
        request: RouteRequestComplexItemsV2,
    ) -> RoutesResponseV2BaseDomainEntityV2:
        """Alias for return_routes_with_complex_items.

        Args:
            request: The route request details with complex items.
        """
        return await self.return_routes_with_complex_items(request)

    async def create_consignment(
        self,
        request: CreateConsignmentV2,
    ) -> CreateConsignmentResponseV2BaseDomainEntityV2:
        """Create a new consignment.

        Args:
            request: The consignment creation details.
        """
        return await self.request(
            "POST",
            "/apiv2/consignments/createConsignment",
            json=request,
            response_model=CreateConsignmentResponseV2BaseDomainEntityV2,
        )

    async def create_shipment(
        self,
        request: CreateConsignmentV2,
    ) -> CreateConsignmentResponseV2BaseDomainEntityV2:
        """Alias for create_consignment.

        Args:
            request: The consignment creation details.
        """
        return await self.create_consignment(request)

    async def create_consignment_with_complex_items(
        self,
        request: CreateConsignmentComplexItemsV2,
    ) -> CreateConsignmentResponseV2BaseDomainEntityV2:
        """Create a new consignment with complex items.

        Args:
            request: The consignment creation details with complex items.
        """
        return await self.request(
            "POST",
            "/apiv2/consignments/createConsignmentwithComplexItems",
            json=request,
            response_model=CreateConsignmentResponseV2BaseDomainEntityV2,
        )

    async def get_consignment(
        self,
        consignment_id: int,
        *,
        include_deleted: bool = False,
        include_request_guids: bool = False,
    ) -> ConsignmentV2BaseDomainEntityV2:
        """Retrieve a consignment by ID.

        Args:
            consignment_id: The ID of the consignment.
            include_deleted: Whether to include deleted consignments.
            include_request_guids: Whether to include request GUIDs.
        """
        return await self.request(
            "GET",
            "/apiv2/consignments/getConsignment",
            params={
                "id": consignment_id,
                "includeDeleted": include_deleted,
                "includeRequestGuids": include_request_guids,
            },
            response_model=ConsignmentV2BaseDomainEntityV2,
        )

    async def return_consignment_statuses(
        self,
        *,
        since_date_created_utc: str | None = None,
    ) -> ConsignmentIdWithTrackingHistoryV2IEnumerableBaseDomainEntity:
        """Retrieve consignment statuses since a given date.

        Args:
            since_date_created_utc: Optional filter for date created in UTC.
        """
        return await self.request(
            "POST",
            "/apiv2/consignments/returnConsignmentStatuses",
            params={"sinceDateCreatedUtc": since_date_created_utc},
            response_model=(
                ConsignmentIdWithTrackingHistoryV2IEnumerableBaseDomainEntity
            ),
        )

    async def update_consignment_statuses(
        self,
        statuses: Sequence[ManualTrackingStatus],
    ) -> EmptyDomainEntityV2:
        """Update the status of multiple consignments.

        Args:
            statuses: A sequence of statuses to update.
        """
        return await self.request(
            "POST",
            "/apiv2/consignments/updateConsignmentStatuses",
            json=list(statuses),
            response_model=EmptyDomainEntityV2,
        )

    async def get_consignment_pdf(self, consignment_id: int) -> bytes:
        """Retrieve the PDF label for a consignment.

        Args:
            consignment_id: The ID of the consignment.
        """
        return await self.request_bytes(
            "GET",
            "/apiv2/labels/getConsignmentPdf",
            params={"consignmentId": consignment_id},
        )

    async def get_label_pdf(self, consignment_id: int) -> bytes:
        """Alias for get_consignment_pdf.

        Args:
            consignment_id: The ID of the consignment.
        """
        return await self.get_consignment_pdf(consignment_id)

    async def get_consignment_pdf_file_info(
        self,
        consignment_id: int,
    ) -> FileInfoBaseDomainEntityV2:
        """Retrieve file information for a consignment PDF label.

        Args:
            consignment_id: The ID of the consignment.
        """
        return await self.request(
            "GET",
            "/apiv2/labels/getConsignmentPdfFileInfo",
            params={"consignmentId": consignment_id},
            response_model=FileInfoBaseDomainEntityV2,
        )

    async def get_label_file_info(
        self,
        consignment_id: int,
    ) -> FileInfoBaseDomainEntityV2:
        """Alias for get_consignment_pdf_file_info.

        Args:
            consignment_id: The ID of the consignment.
        """
        return await self.get_consignment_pdf_file_info(consignment_id)

    async def get_manifest_pdf(self, manifest_id: int) -> bytes:
        """Retrieve the PDF manifest.

        Args:
            manifest_id: The ID of the manifest.
        """
        return await self.request_bytes(
            "GET",
            "/apiv2/labels/getManifestPdf",
            params={"manifestId": manifest_id},
        )

    async def get_manifest_pdf_file_info(
        self,
        manifest_id: int,
    ) -> FileInfoBaseDomainEntityV2:
        """Retrieve file information for a manifest PDF.

        Args:
            manifest_id: The ID of the manifest.
        """
        return await self.request(
            "GET",
            "/apiv2/labels/getManifestPdfFileInfo",
            params={"manifestId": manifest_id},
            response_model=FileInfoBaseDomainEntityV2,
        )

    async def list_manifests(
        self,
        *,
        company_id: int | None = None,
        start_index: int | None = None,
        retrieve_size: int | None = None,
        carrier_id: int | None = None,
        include_child_companies: bool | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> ManifestForListWithConsignmentsGridDomainEntityV2:
        """List manifests with optional filtering.

        Args:
            company_id: Optional company ID filter.
            start_index: Optional start index for pagination.
            retrieve_size: Optional number of records to retrieve.
            carrier_id: Optional carrier ID filter.
            include_child_companies: Whether to include child companies.
            start_date: Optional start date filter.
            end_date: Optional end date filter.
        """
        return await self.request(
            "GET",
            "/apiv2/manifests/getAll",
            params={
                "companyId": company_id,
                "startIndex": start_index,
                "retrieveSize": retrieve_size,
                "carrierId": carrier_id,
                "includeChildCompanies": include_child_companies,
                "startDate": start_date,
                "endDate": end_date,
            },
            response_model=ManifestForListWithConsignmentsGridDomainEntityV2,
        )

    async def group_consignments_for_manifest(
        self,
        consignment_ids: Sequence[int],
    ) -> BookedManifestV2ICollectionBaseDomainEntityV2:
        """Group specific consignments for manifesting.

        Args:
            consignment_ids: A sequence of consignment IDs to group.
        """
        return await self.request(
            "POST",
            "/apiv2/manifests/groupConsignmentsForManifest",
            json=list(consignment_ids),
            response_model=BookedManifestV2ICollectionBaseDomainEntityV2,
        )

    async def group_all_unmanifested_consignments_for_manifest(
        self,
        company_id: int,
    ) -> BookedManifestV2ICollectionBaseDomainEntityV2:
        """Group all unmanifested consignments for manifesting.

        Args:
            company_id: The ID of the company.
        """
        return await self.request(
            "POST",
            "/apiv2/manifests/groupAllUnmanifestedConsignmentsForManifest",
            json=company_id,
            response_model=BookedManifestV2ICollectionBaseDomainEntityV2,
        )

    async def book_manifest(
        self,
        manifests: Sequence[BookedManifestV2],
    ) -> ReturnBookedManifestV2ICollectionBaseDomainEntityV2:
        """Book a manifest.

        Args:
            manifests: A sequence of manifests to book.
        """
        return await self.request(
            "POST",
            "/apiv2/manifests/manifest",
            json=list(manifests),
            response_model=ReturnBookedManifestV2ICollectionBaseDomainEntityV2,
        )

    async def rebook_pickup(
        self,
        rebooking: ManifestRebooking,
    ) -> RebookedPickupBaseDomainEntityV2:
        """Rebook a pickup for a manifest.

        Args:
            rebooking: The rebooking details.
        """
        return await self.request(
            "POST",
            "/apiv2/manifests/rebookPickup",
            json=rebooking,
            response_model=RebookedPickupBaseDomainEntityV2,
        )

    async def get_company_locations(
        self,
        *,
        company_id: int | None = None,
    ) -> CompanyLocationV2GridDomainEntityV2:
        """Retrieve company locations.

        Args:
            company_id: Optional company ID filter.
        """
        return await self.request(
            "GET",
            "/apiv2/companyLocations/getAll",
            params={"companyId": company_id},
            response_model=CompanyLocationV2GridDomainEntityV2,
        )

    async def list_company_locations(
        self,
        *,
        company_id: int | None = None,
    ) -> CompanyLocationV2GridDomainEntityV2:
        """Alias for get_company_locations.

        Args:
            company_id: Optional company ID filter.
        """
        return await self.get_company_locations(company_id=company_id)

    async def get_company_location(
        self,
        location_id: int,
    ) -> CompanyLocationV2BaseDomainEntityV2:
        """Retrieve a specific company location by ID.

        Args:
            location_id: The ID of the location.
        """
        return await self.request(
            "GET",
            "/apiv2/companyLocations/get",
            params={"id": location_id},
            response_model=CompanyLocationV2BaseDomainEntityV2,
        )

    async def get_company_location_permanent_pickups(
        self,
        location_id: int,
    ) -> CompanyLocationV2PermanentPickupsBaseDomainEntityV2:
        """Retrieve permanent pickups for a company location.

        Args:
            location_id: The ID of the location.
        """
        return await self.request(
            "GET",
            "/apiv2/companyLocations/getPermanentPickupsForCompanyLocation",
            params={"id": location_id},
            response_model=CompanyLocationV2PermanentPickupsBaseDomainEntityV2,
        )
