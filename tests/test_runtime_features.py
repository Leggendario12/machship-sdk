"""Tests for optional runtime helpers."""

from __future__ import annotations

from contextlib import contextmanager

import httpx
import pytest

from machship_sdk import MachShipClient, MachShipConfig
from machship_sdk.cache import ttl_cache
from machship_sdk.logging import emit_log
from machship_sdk.retries import RetryPolicy
from machship_sdk.telemetry import request_span, set_span_attributes


class DummyStructuredLogger:
    """Simple structured logger used to exercise ``emit_log``."""

    def __init__(self) -> None:
        """Initialize the structured logger stub."""
        self.bound_fields: list[dict[str, object]] = []
        self.events: list[str] = []

    def bind(self, **fields: object) -> "DummyStructuredLogger":
        self.bound_fields.append(fields)
        return self

    def debug(self, event: str) -> None:
        self.events.append(event)


class DummySpan:
    """Simple span object for telemetry tests."""

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
    """Tracer stub that yields a single dummy span."""

    def __init__(self) -> None:
        """Initialize the tracer stub."""
        self.span_name: str | None = None
        self.span: DummySpan | None = None

    @contextmanager
    def start_as_current_span(self, span_name: str):
        self.span_name = span_name
        span = DummySpan()
        self.span = span
        yield span


def test_emit_log_uses_structured_logger() -> None:
    """Emit a structured event when the logger supports ``bind``."""
    logger = DummyStructuredLogger()

    emit_log(
        logger,
        "debug",
        "request.start",
        service="machship",
        path="/apiv2/authenticate/ping",
    )

    assert logger.bound_fields == [
        {
            "service": "machship",
            "path": "/apiv2/authenticate/ping",
        }
    ]
    assert logger.events == ["request.start"]


def test_request_span_records_exception_and_attributes() -> None:
    """Record span metadata and exception state for outbound requests."""
    tracer = DummyTracer()

    with pytest.raises(RuntimeError), request_span(
        tracer,
        "MachShip GET /apiv2/authenticate/ping",
        service="machship",
    ) as span:
        assert span is not None
        set_span_attributes(
            span,
            http_status_code=500,
            response_length=12,
            skip=None,
        )
        raise RuntimeError("boom")

    assert tracer.span_name == "MachShip GET /apiv2/authenticate/ping"
    assert tracer.span is not None
    assert tracer.span.attributes["service"] == "machship"
    assert tracer.span.attributes["http_status_code"] == 500
    assert tracer.span.attributes["response_length"] == 12
    assert len(tracer.span.exceptions) == 1
    assert isinstance(tracer.span.exceptions[0], RuntimeError)


def test_ttl_cache_caches_calls() -> None:
    """Cache repeated function calls when cachetools is installed."""
    calls = 0

    @ttl_cache(maxsize=16, ttl=60)
    def double(value: int) -> int:
        nonlocal calls
        calls += 1
        return value * 2

    assert double(4) == 8
    assert double(4) == 8
    assert calls == 1


def test_retry_policy_retries_on_http_500() -> None:
    """Retry one transient HTTP failure before returning a success."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(500, text="temporary failure")
        return httpx.Response(200, json={"object": True, "errors": []})

    client = MachShipClient(
        MachShipConfig(base_url="https://example.com", token="secret"),
        transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(attempts=2, min_wait=0.01, max_wait=0.01),
    )

    assert client.ping().object is True
    assert calls == 2
