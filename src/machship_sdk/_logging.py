"""Structured logging helpers for MachShip SDK integrations."""

from __future__ import annotations

from logging import getLogger as stdlibGetLogger
from typing import Any


def get_logger(name: str = "machship_sdk", *, structured: bool = True) -> Any:
    """Return a structlog logger when available, otherwise stdlib logging."""
    if structured:
        try:
            import structlog
        except ImportError:  # pragma: no cover - optional dependency
            return stdlibGetLogger(name)
        return structlog.get_logger(name)
    return stdlibGetLogger(name)


def emit_log(logger: Any | None, level: str, event: str, **fields: Any) -> None:
    """Emit a structured or plain log event if a logger is configured."""
    if logger is None:
        return

    bind = getattr(logger, "bind", None)
    if callable(bind):
        structured_logger = bind(**fields)
        log_method = getattr(structured_logger, level, None)
        if callable(log_method):
            log_method(event)
            return

    log_method = getattr(logger, level, None)
    if callable(log_method):
        if fields:
            formatted_fields = ", ".join(
                f"{key}={value!r}"
                for key, value in sorted(fields.items())
            )
            log_method(f"{event} | {formatted_fields}")
        else:
            log_method(event)
