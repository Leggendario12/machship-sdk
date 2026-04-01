"""Asynchronous FusedShip client implementation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar
from time import perf_counter
from urllib.parse import urlencode

import httpx

from .._core import build_url
from .._version import __version__
from .._logging import emit_log
from ..retries import RetryPolicy, run_async_with_retry
from ..serialization import dump_json_payload, load_json_payload
from ..telemetry import request_span, set_span_attributes
from .config import FusedShipConfig
from .exceptions import FusedShipAPIError, FusedShipError, FusedShipHTTPError
from .models import (
    FusedShipLivePricingRequest,
    FusedShipLivePricingResponse,
    FusedShipRequestTokenRequest,
    FusedShipRequestTokenResponse,
)

ResponseModelT = TypeVar("ResponseModelT")


def _build_headers(
    *,
    user_agent: str,
    token: str | None = None,
    integration_id: str | None = None,
    extra_headers: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """
    Build HTTP headers for FusedShip API requests.

    Args:
        user_agent: The user agent string.
        token: The API token for live pricing.
        integration_id: The integration ID for live pricing.
        extra_headers: Additional headers to include.

    Returns:
        A dictionary of HTTP headers.
    """
    headers = {
        "accept": "application/json",
        "user-agent": user_agent,
    }
    if token:
        headers["token"] = token
    if integration_id:
        headers["integration_id"] = integration_id
    if extra_headers:
        headers.update(extra_headers)
    return headers


class AsyncFusedShipClient:
    """
    An asynchronous client for the FusedShip API.

    This client handles authentication and provides methods for interacting
    with FusedShip's live pricing and e-commerce features.
    """

    def __init__(
        self,
        config: FusedShipConfig,
        *,
        client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_policy: RetryPolicy | None = None,
        logger: Any | None = None,
        tracer: Any | None = None,
    ) -> None:
        """
        Initialize the asynchronous FusedShip client.

        Args:
            config: Configuration for the client.
            client: An optional pre-configured HTTPX AsyncClient.
            transport: An optional HTTPX AsyncBaseTransport to use.
            retry_policy: Optional retry policy for transient failures.
            logger: Optional logger for request events.
            tracer: Optional OpenTelemetry tracer for request spans.

        Raises:
            ValueError: If both client and transport are provided.
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
    def config(self) -> FusedShipConfig:
        """The configuration used by this client."""
        return self._config

    @property
    def http_client(self) -> httpx.AsyncClient:
        """The underlying HTTPX AsyncClient."""
        return self._client

    @classmethod
    def from_env(cls, **kwargs: Any) -> "AsyncFusedShipClient":
        """
        Create a client instance from environment variables.

        Args:
            **kwargs: Arguments passed to FusedShipConfig.from_env.

        Returns:
            A new AsyncFusedShipClient instance.
        """
        client = kwargs.pop("client", None)
        transport = kwargs.pop("transport", None)
        retry_policy = kwargs.pop("retry_policy", None)
        logger = kwargs.pop("logger", None)
        tracer = kwargs.pop("tracer", None)
        return cls(
            FusedShipConfig.from_env(**kwargs),
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
        json: Any | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Build request URL, headers, and payload kwargs."""
        url = build_url(self._config.base_url, path)
        request_headers = _build_headers(
            user_agent=f"machship-sdk/{__version__}",
            token=self._config.token,
            integration_id=self._config.integration_id,
            extra_headers={**self._config.headers, **(headers or {})},
        )
        request_kwargs: dict[str, Any] = {
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
        """Close the underlying HTTPX client if it was created by this client."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "AsyncFusedShipClient":
        """Enter an asynchronous context manager for the client."""
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Exit the asynchronous context manager and close the client."""
        await self.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        response_model: type[ResponseModelT] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> ResponseModelT | Any:
        """
        Perform an internal asynchronous HTTP request to the FusedShip API.

        Args:
            method: The HTTP method (e.g., GET, POST).
            path: The API path.
            json: The JSON payload, if any.
            response_model: The Pydantic model to use for the response.
            headers: Additional headers for this request.

        Returns:
            The parsed response, either as a model instance or a raw dict/list.

        Raises:
            FusedShipError: If the request fails at the transport level.
            FusedShipHTTPError: If the API returns an HTTP error status.
            FusedShipAPIError: If the API returns a structured error message.
        """
        url, request_kwargs = self._prepare_request(
            path,
            json=json,
            headers=headers,
        )
        request_name = f"{method.upper()} {path}"
        start = perf_counter()
        with request_span(
            self._tracer,
            f"FusedShip {request_name}",
            service="fusedship",
            method=method.upper(),
            path=path,
            url=url,
        ) as span:
            emit_log(
                self._logger,
                "debug",
                "request.start",
                service="fusedship",
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
                    service="fusedship",
                    method=method.upper(),
                    path=path,
                    url=url,
                    error=str(exc),
                    duration_ms=round((perf_counter() - start) * 1000, 2),
                )
                raise FusedShipError(f"{method.upper()} {url} failed: {exc}") from exc

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
                    service="fusedship",
                    method=method.upper(),
                    path=path,
                    url=url,
                    status_code=response.status_code,
                    duration_ms=round((perf_counter() - start) * 1000, 2),
                )
                raise FusedShipHTTPError(
                    method=method,
                    url=str(response.request.url),
                    status_code=response.status_code,
                    response_text=response.text[:2000] or None,
                )

            if not response.content:
                set_span_attributes(
                    span,
                    http_status_code=response.status_code,
                    response_length=0,
                )
                return None

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
                    service="fusedship",
                    method=method.upper(),
                    path=path,
                    url=url,
                    status_code=response.status_code,
                    duration_ms=round((perf_counter() - start) * 1000, 2),
                )
                raise FusedShipHTTPError(
                    method=method,
                    url=str(response.request.url),
                    status_code=response.status_code,
                    response_text=response.text[:2000] or None,
                ) from exc

            if isinstance(payload, dict) and payload.get("error"):
                set_span_attributes(
                    span,
                    http_status_code=response.status_code,
                    response_length=len(response.content),
                    error=True,
                )
                emit_log(
                    self._logger,
                    "warning",
                    "request.api_error",
                    service="fusedship",
                    method=method.upper(),
                    path=path,
                    url=url,
                    status_code=response.status_code,
                    duration_ms=round((perf_counter() - start) * 1000, 2),
                )
                raise FusedShipAPIError(str(payload["error"]))

            if response_model is None:
                set_span_attributes(
                    span,
                    http_status_code=response.status_code,
                    response_length=len(response.content),
                )
                emit_log(
                    self._logger,
                    "debug",
                    "request.success",
                    service="fusedship",
                    method=method.upper(),
                    path=path,
                    url=url,
                    status_code=response.status_code,
                    duration_ms=round((perf_counter() - start) * 1000, 2),
                )
                return payload

            parsed = response_model.model_validate(payload)
            set_span_attributes(
                span,
                http_status_code=response.status_code,
                response_length=len(response.content),
            )
            emit_log(
                self._logger,
                "debug",
                "request.success",
                service="fusedship",
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
        json: Any | None = None,
        response_model: type[ResponseModelT] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> ResponseModelT | Any:
        """
        Perform an asynchronous HTTP request to the FusedShip API.

        Args:
            method: The HTTP method (e.g., GET, POST).
            path: The API path.
            json: The JSON payload, if any.
            response_model: The Pydantic model to use for the response.
            headers: Additional headers for this request.

        Returns:
            The parsed response.
        """
        return await run_async_with_retry(
            self._retry_policy,
            self._request,
            method,
            path,
            json=json,
            response_model=response_model,
            headers=headers,
        )

    async def request_token(
        self,
        request: FusedShipRequestTokenRequest | None = None,
        *,
        client_token: str | None = None,
        store_id: str | None = None,
    ) -> FusedShipRequestTokenResponse:
        """
        Request a session token for e-commerce integration.

        Args:
            request: A pre-built FusedShipRequestTokenRequest instance.
            client_token: The client token (if not in config or request).
            store_id: The store ID (if not in config or request).

        Returns:
            A FusedShipRequestTokenResponse containing the session key.

        Raises:
            ValueError: If credentials are not provided.
        """
        if request is None:
            client_token = client_token or self._config.client_token
            store_id = store_id or self._config.store_id
            if not client_token or not store_id:
                raise ValueError("FusedShip client_token and store_id are required")
            request = FusedShipRequestTokenRequest(
                client_token=client_token,
                store_id=store_id,
            )

        return await self.request(
            "POST",
            "/ecommerce/request-token",
            json=request,
            response_model=FusedShipRequestTokenResponse,
        )

    def build_ecommerce_url(
        self,
        session_key: str,
        *,
        active_tab: str | None = None,
    ) -> str:
        """
        Build the URL for the e-commerce app.

        Args:
            session_key: The session key obtained via request_token.
            active_tab: The tab to open in the e-commerce app.

        Returns:
            The full URL to the e-commerce app.
        """
        query_params: dict[str, str] = {"session_key": session_key}
        if active_tab:
            query_params["active_tab"] = active_tab
        return f"{self._config.base_url}/ecommerce/app?{urlencode(query_params)}"

    async def quote_live_pricing(
        self,
        platform: str,
        request: FusedShipLivePricingRequest | Mapping[str, Any] | Any,
        *,
        token: str | None = None,
        integration_id: str | None = None,
    ) -> FusedShipLivePricingResponse:
        """
        Get live shipping rates for a quote.

        Args:
            platform: The platform name (e.g., 'shopify', 'magento').
            request: The quote details.
            token: The live pricing token (if not in config).
            integration_id: The integration ID (if not in config).

        Returns:
            A FusedShipLivePricingResponse containing the rates.

        Raises:
            ValueError: If live pricing credentials are missing.
        """
        resolved_token = token or self._config.token
        resolved_integration_id = integration_id or self._config.integration_id
        if not resolved_token:
            raise ValueError("FusedShip live pricing token is required")
        if not resolved_integration_id:
            raise ValueError("FusedShip integration_id is required")

        return await self.request(
            "POST",
            f"/live-pricing/{platform.strip('/')}",
            json=request,
            response_model=FusedShipLivePricingResponse,
            headers={
                "token": resolved_token,
                "integration_id": resolved_integration_id,
            },
        )
