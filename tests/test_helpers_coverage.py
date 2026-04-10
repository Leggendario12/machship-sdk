"""Additional tests to drive helper-module coverage to 100%."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timezone
from enum import Enum
from types import SimpleNamespace
from uuid import UUID
from typing import Annotated

import httpx
import pytest
from pydantic import AwareDatetime, BaseModel, Field

from machship_sdk._core import (
    build_headers,
    build_url,
    maybe_raise_for_api_errors,
    parse_response_model,
    serialize_json_payload,
    serialize_query_params,
)
from machship_sdk.cache import make_ttl_cache
from machship_sdk.config import MachShipConfig, _first_environment_value
from machship_sdk.exceptions import (
    MachShipAPIError,
    MachShipError,
    MachShipHTTPError,
    MachShipValidationError,
)
from machship_sdk.fusedship.config import FusedShipConfig, _first_env_value
from machship_sdk.fusedship.exceptions import (
    FusedShipAPIError,
    FusedShipError,
    FusedShipHTTPError,
)
from machship_sdk.models.base import (
    MachShipBaseModel,
    _annotation_requires_aware_datetime,
    _coerce_aware_datetime,
    _normalize_utc_datetime_fields,
)
from machship_sdk.logging import emit_log, get_logger
from machship_sdk.retries import RetryPolicy, run_async_with_retry, run_sync_with_retry
from machship_sdk.serialization import dump_json_payload, load_json_payload
from machship_sdk import serialization as serialization_module
from machship_sdk.telemetry import (
    get_tracer,
    record_span_exception,
    request_span,
    set_span_attributes,
)


class SampleModel(BaseModel):
    """Simple model used to exercise JSON conversion."""

    value: int


class SampleEnum(Enum):
    """Enum used to exercise JSON conversion."""

    RED = "red"


class PlainLogger:
    """Minimal stdlib-style logger used by ``emit_log`` tests."""

    def __init__(self) -> None:
        """Initialize the logger stub."""
        self.messages: list[str] = []

    def info(self, message: str) -> None:
        self.messages.append(message)

    def warning(self, message: str) -> None:
        self.messages.append(message)


class DummySpan:
    """Simple span object used in telemetry tests."""

    def __init__(self) -> None:
        """Initialize the span stub."""
        self.attributes: dict[str, object] = {}
        self.exceptions: list[BaseException] = []
        self.status: object | None = None

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def record_exception(self, exc: BaseException) -> None:
        self.exceptions.append(exc)

    def set_status(self, status: object) -> None:
        self.status = status


class DummyTracer:
    """Tracer stub for exercising the request span context manager."""

    def __init__(self) -> None:
        """Initialize the tracer stub."""
        self.span_name: str | None = None
        self.span: DummySpan | None = None

    def start_as_current_span(self, span_name: str):
        self.span_name = span_name
        span = DummySpan()
        self.span = span

        class _SpanContext:
            def __enter__(self_inner):
                return span

            def __exit__(self_inner, exc_type, exc, tb):
                return False

        return _SpanContext()


class EmptyAsyncRetryer:
    """Async iterator that yields no retry attempts."""

    def __aiter__(self):
        """Return the iterator itself."""
        return self

    async def __anext__(self):
        """Stop iteration immediately."""
        raise StopAsyncIteration


def test_core_helpers_cover_serialization_branches() -> None:
    """Exercise JSON helpers and generic response parsing branches."""
    payload = {
        "model": SampleModel(value=1),
        "mapping": {"keep": "yes", "drop": None},
        "sequence": [
            SampleEnum.RED,
            date(2026, 3, 31),
            datetime(2026, 3, 31, 12, 30, tzinfo=timezone.utc),
            time(8, 15, tzinfo=timezone.utc),
            UUID("123e4567-e89b-12d3-a456-426614174000"),
        ],
    }

    assert build_url("https://example.com", "/ping") == (
        "https://example.com/ping"
    )
    assert build_url(
        "https://example.com",
        "https://other.example.com/ping",
    ) == "https://other.example.com/ping"
    assert build_headers(
        token="secret",
        user_agent="machship-sdk/test",
        extra_headers={"x-trace-id": "abc123"},
    ) == {
        "token": "secret",
        "accept": "application/json",
        "user-agent": "machship-sdk/test",
        "x-trace-id": "abc123",
    }

    serialized = serialize_json_payload(payload)
    params = serialize_query_params(payload)

    assert serialization_module.serialize_json_payload(payload)["model"] == {
        "value": 1
    }
    assert serialization_module.serialize_query_params(payload)["sequence"][0] == (
        "red"
    )
    assert serialized["model"] == {"value": 1}
    assert serialized["mapping"] == {"keep": "yes"}
    assert serialized["sequence"][0] == "red"
    assert serialized["sequence"][4] == "123e4567-e89b-12d3-a456-426614174000"
    assert params["sequence"][1] == "2026-03-31"
    assert params["sequence"][2] == "2026-03-31T12:30:00+00:00"
    assert params["sequence"][3] == "08:15:00+00:00"

    assert parse_response_model({"value": 2}, SampleModel).value == 2
    assert parse_response_model({"value": 3}, None) == {"value": 3}

    maybe_raise_for_api_errors(
        SimpleNamespace(errors=[{"errorMessage": "ignored"}]),
        context="test",
        raise_on_api_errors=False,
    )


def test_machship_datetime_helpers_cover_edge_cases() -> None:
    """Exercise the shared datetime normalization helper branches."""
    aware = _coerce_aware_datetime(datetime(2026, 4, 10, 12, 30))
    parsed = _coerce_aware_datetime("2026-04-10T12:30:00")
    invalid = _coerce_aware_datetime("not-a-datetime")
    passthrough = object()

    normalized = _normalize_utc_datetime_fields(
        (
            {
                "dateCreatedUtc": "2026-04-10T12:30:00",
                "nested": [
                    {"etaUtc": "2026-04-10T13:30:00"},
                ],
            },
        )
    )

    assert aware.tzinfo is not None
    assert parsed.tzinfo is not None
    assert invalid == "not-a-datetime"
    assert _coerce_aware_datetime(passthrough) is passthrough
    assert normalized[0]["dateCreatedUtc"].tzinfo is not None
    assert normalized[0]["nested"][0]["etaUtc"].tzinfo is not None

    assert _annotation_requires_aware_datetime(AwareDatetime) is True
    assert _annotation_requires_aware_datetime(
        Annotated[AwareDatetime | None, Field(alias="example")]
    ) is True
    assert _annotation_requires_aware_datetime(datetime | None) is False

    assert (
        MachShipBaseModel._normalize_aware_datetime_fields(  # type: ignore[misc]
            "kept",
            SimpleNamespace(field_name=None),
        )
        == "kept"
    )
    assert (
        MachShipBaseModel._normalize_aware_datetime_fields(  # type: ignore[misc]
            "kept",
            SimpleNamespace(field_name="missing"),
        )
        == "kept"
    )


def test_json_helpers_cover_orjson_and_fallback(monkeypatch) -> None:
    """Exercise both the accelerated and pure-Python JSON helpers."""
    payload = {"answer": 42}

    assert load_json_payload(dump_json_payload(payload)) == payload

    monkeypatch.setattr(serialization_module, "orjson", None)

    dumped = serialization_module.dump_json_payload(payload)
    loaded = serialization_module.load_json_payload(dumped)

    assert dumped == b'{"answer":42}'
    assert loaded == payload


def test_environment_helper_functions(monkeypatch) -> None:
    """Exercise the first-value environment helpers directly."""
    assert _first_environment_value(("MISSING_ONE", "MISSING_TWO")) is None
    assert _first_env_value(("MISSING_ONE", "MISSING_TWO")) is None

    monkeypatch.setenv("FIRST_MATCH", "selected")
    monkeypatch.setenv("SECOND_MATCH", "ignored")

    assert _first_environment_value(("FIRST_MATCH", "SECOND_MATCH")) == "selected"
    assert _first_env_value(("FIRST_MATCH", "SECOND_MATCH")) == "selected"


def test_machship_config_from_env_and_validation(monkeypatch) -> None:
    """Load MachShip config from env and cover validation failures."""
    monkeypatch.setenv("MACHSHIP_BASE_URL", "https://mach.example.com/")
    monkeypatch.setenv("MACHSHIP_TOKEN", "primary-token")
    monkeypatch.setenv("MACHSHIP_API_TOKEN", "secondary-token")

    config = MachShipConfig.from_env(
        headers={"x-request-id": "abc123"},
        follow_redirects=True,
        raise_on_api_errors=False,
    )

    assert config.base_url == "https://mach.example.com"
    assert config.token == "primary-token"
    assert config.headers == {"x-request-id": "abc123"}
    assert config.follow_redirects is True
    assert config.raise_on_api_errors is False

    with pytest.raises(ValueError, match="MachShipConfig.base_url is required"):
        MachShipConfig(base_url=" ", token="secret")

    with pytest.raises(ValueError, match="MachShipConfig.token is required"):
        MachShipConfig(base_url="https://example.com", token=" ")

    monkeypatch.delenv("MACHSHIP_BASE_URL", raising=False)
    with pytest.raises(ValueError, match="Missing MachShip base URL"):
        MachShipConfig.from_env()

    monkeypatch.setenv("MACHSHIP_BASE_URL", "https://mach.example.com")
    monkeypatch.delenv("MACHSHIP_TOKEN", raising=False)
    monkeypatch.delenv("MACHSHIP_API_TOKEN", raising=False)
    with pytest.raises(ValueError, match="Missing MachShip token"):
        MachShipConfig.from_env()


def test_fusedship_config_helpers(monkeypatch) -> None:
    """Load FusedShip config from env and cover credential guards."""
    monkeypatch.setenv(
        "FUSEDSHIP_BASE_URL",
        "https://fused.example.com/live-pricing/generic-liverates/",
    )
    monkeypatch.setenv("FUSEDSHIP_TOKEN", "fused-token")
    monkeypatch.setenv("FUSEDSHIP_INTEGRATION_ID", "integration-123")
    monkeypatch.setenv("FUSEDSHIP_CLIENT_TOKEN", "client-456")
    monkeypatch.setenv("FUSEDSHIP_STORE_ID", "store-789")

    config = FusedShipConfig.from_env(headers={"x-request-id": "abc123"})

    assert config.base_url == "https://fused.example.com"
    assert config.token == "fused-token"
    assert config.integration_id == "integration-123"
    assert config.client_token == "client-456"
    assert config.store_id == "store-789"
    assert config.headers == {"x-request-id": "abc123"}
    assert config.require_live_pricing_credentials() == (
        "fused-token",
        "integration-123",
    )
    assert config.require_ecommerce_credentials() == (
        "client-456",
        "store-789",
    )

    with pytest.raises(ValueError, match="FusedShip live pricing token is required"):
        FusedShipConfig().require_live_pricing_credentials()

    with pytest.raises(ValueError, match="FusedShip integration_id is required"):
        FusedShipConfig(token="fused-token").require_live_pricing_credentials()

    with pytest.raises(ValueError, match="FusedShip client_token is required"):
        FusedShipConfig().require_ecommerce_credentials()

    with pytest.raises(ValueError, match="FusedShip store_id is required"):
        FusedShipConfig(client_token="client-456").require_ecommerce_credentials()


def test_exception_classes_cover_string_and_factory_behaviour() -> None:
    """Exercise exception constructors and string representations."""
    http_error = MachShipHTTPError(
        method="GET",
        url="https://example.com",
        status_code=500,
        response_text="failure",
    )
    api_error = MachShipAPIError("machship failed", errors=[{"code": 1}])
    validation_error = MachShipValidationError.from_errors(
        [SimpleNamespace(error_message="bad"), {"errorMessage": "broken"}],
        context="request",
    )
    fused_http_error = FusedShipHTTPError(
        method="POST",
        url="https://example.com",
        status_code=503,
    )
    fused_api_error = FusedShipAPIError("fusedship failed")

    assert str(http_error) == "GET https://example.com returned HTTP 500: failure"
    assert str(MachShipHTTPError("GET", "https://example.com", 404)) == (
        "GET https://example.com returned HTTP 404"
    )
    assert str(api_error) == "machship failed"
    assert api_error.errors == ({"code": 1},)
    assert str(validation_error) == "request: bad; broken"
    assert str(MachShipValidationError.from_errors([])) == (
        "MachShip validation failed"
    )
    assert str(fused_http_error) == "POST https://example.com returned HTTP 503"
    assert str(
        FusedShipHTTPError(
            method="POST",
            url="https://example.com",
            status_code=503,
            response_text="failure",
        )
    ) == "POST https://example.com returned HTTP 503: failure"
    assert str(fused_api_error) == "fusedship failed"
    assert isinstance(MachShipError("boom"), Exception)
    assert isinstance(FusedShipError("boom"), Exception)


def test_logging_helpers_cover_structured_and_plain_logging() -> None:
    """Exercise both logger factories and logging output paths."""
    structured_logger = get_logger("machship-sdk-test", structured=True)
    plain_logger = get_logger("machship-sdk-plain", structured=False)

    assert hasattr(structured_logger, "bind")
    assert isinstance(plain_logger, logging.Logger)

    logger = PlainLogger()
    emit_log(
        logger,
        "info",
        "request.success",
        path="/apiv2/authenticate/ping",
        status_code=200,
    )
    emit_log(logger, "warning", "request.failed")
    emit_log(None, "info", "ignored", foo="bar")

    assert logger.messages[0] == (
        "request.success | path='/apiv2/authenticate/ping', status_code=200"
    )
    assert logger.messages[1] == "request.failed"


def test_telemetry_helpers_cover_all_branches() -> None:
    """Exercise tracing helpers with and without a real tracer."""
    tracer = get_tracer("machship-sdk-test")
    assert tracer is not None

    with request_span(None, "span-without-tracer") as span:
        assert span is None

    with request_span(object(), "span-without-hook") as span:
        assert span is None

    span = DummySpan()
    set_span_attributes(None, ignored=True)
    set_span_attributes(span, one=1, two=None)
    record_span_exception(None, RuntimeError("ignored"))
    record_span_exception(span, RuntimeError("boom"))

    assert span.attributes == {"one": 1}
    assert len(span.exceptions) == 1
    assert isinstance(span.exceptions[0], RuntimeError)
    assert span.status is not None


def test_retry_helpers_cover_retry_policy_and_fallbacks(monkeypatch) -> None:
    """Exercise retry decisions, retryer fallbacks, and empty retryers."""
    request = httpx.Request("GET", "https://example.com")
    policy = RetryPolicy(attempts=3, min_wait=0.01, max_wait=0.01)
    retryable = httpx.RequestError("boom", request=request)
    wrapped_error = MachShipError("wrapped")
    wrapped_error.__cause__ = retryable

    assert policy.should_retry(retryable) is True
    assert policy.should_retry(MachShipHTTPError("GET", "https://example.com", 500))
    assert not policy.should_retry(MachShipHTTPError("GET", "https://example.com", 404))
    assert policy.should_retry(wrapped_error) is True
    assert policy.should_retry(Exception("plain")) is False
    assert policy.build_sync_retryer() is not None
    assert policy.build_async_retryer() is not None

    policy_no_retry = RetryPolicy(attempts=1)
    assert run_sync_with_retry(policy_no_retry, lambda: "sync") == "sync"

    async def async_value() -> str:
        return "async"

    assert asyncio.run(run_async_with_retry(policy, async_value)) == "async"
    assert asyncio.run(run_async_with_retry(policy_no_retry, async_value)) == "async"

    monkeypatch.setattr(
        RetryPolicy,
        "build_sync_retryer",
        lambda self: iter(()),
    )
    assert run_sync_with_retry(policy, lambda: "empty-sync") == "empty-sync"

    monkeypatch.setattr(
        RetryPolicy,
        "build_async_retryer",
        lambda self: EmptyAsyncRetryer(),
    )
    assert asyncio.run(run_async_with_retry(policy, async_value)) == "async"


def test_make_ttl_cache_creates_cache_instance() -> None:
    """Cover the reusable TTL cache constructor."""
    cache = make_ttl_cache(maxsize=4, ttl=2)

    assert cache.maxsize == 4
    assert cache.ttl == 2
