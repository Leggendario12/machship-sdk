"""OpenTelemetry helpers for MachShip SDK integrations."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any, Callable, cast

try:
    from opentelemetry.trace import Status, StatusCode
except ImportError:  # pragma: no cover - optional dependency
    Status = None
    StatusCode = None


def get_tracer(name: str = "machship_sdk") -> Any | None:
    """Return an OpenTelemetry tracer when the dependency is installed."""
    try:
        from opentelemetry import trace
    except ImportError:  # pragma: no cover - optional dependency
        return None
    return trace.get_tracer(name)


def set_span_attributes(span: Any | None, **attributes: Any) -> None:
    """Attach attributes to a span if tracing is enabled."""
    if span is None:
        return

    set_attribute = getattr(span, "set_attribute", None)
    if callable(set_attribute):
        for key, value in attributes.items():
            if value is not None:
                set_attribute(key, value)


def record_span_exception(span: Any | None, exc: BaseException) -> None:
    """Record an exception and mark the span as failed."""
    if span is None:
        return

    record_exception = getattr(span, "record_exception", None)
    if callable(record_exception):
        record_exception(exc)

    if Status is not None and StatusCode is not None:
        set_status = getattr(span, "set_status", None)
        if callable(set_status):
            set_status(Status(StatusCode.ERROR))


@contextmanager
def request_span(
    tracer: Any | None,
    span_name: str,
    **attributes: Any,
) -> Iterator[Any | None]:
    """Create a span for an outbound SDK request when tracing is enabled."""
    if tracer is None:
        yield None
        return

    start_span = getattr(tracer, "start_as_current_span", None)
    if not callable(start_span):
        yield None
        return

    span_context = cast(
        Callable[[str], AbstractContextManager[Any]],
        start_span,
    )(span_name)
    with span_context as span:
        set_span_attributes(span, **attributes)
        try:
            yield span
        except BaseException as exc:
            record_span_exception(span, exc)
            raise
