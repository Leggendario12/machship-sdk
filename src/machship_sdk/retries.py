"""Retry helpers powered by ``tenacity`` when the extra is installed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypeVar

import httpx

try:
    from tenacity import AsyncRetrying, Retrying, retry_if_exception, stop_after_attempt
    from tenacity import wait_exponential
except ImportError:  # pragma: no cover - optional dependency
    AsyncRetrying = None
    Retrying = None
    retry_if_exception = None
    stop_after_attempt = None
    wait_exponential = None

ResponseT = TypeVar("ResponseT")

DEFAULT_RETRY_STATUS_CODES = (429, 500, 502, 503, 504)


@dataclass(slots=True, frozen=True)
class RetryPolicy:
    """Retry configuration for transient transport and server failures."""

    attempts: int = 3
    min_wait: float = 0.5
    max_wait: float = 5.0
    retry_status_codes: tuple[int, ...] = DEFAULT_RETRY_STATUS_CODES

    @property
    def enabled(self) -> bool:
        """Return ``True`` when retries should be attempted."""
        return self.attempts > 1 and Retrying is not None and AsyncRetrying is not None

    def should_retry(self, exc: BaseException) -> bool:
        """Return ``True`` for retryable transport and HTTP failures."""
        if isinstance(exc, httpx.RequestError):
            return True

        cause = exc.__cause__
        if isinstance(cause, httpx.RequestError):
            return True

        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int) and exc.__class__.__name__ in {
            "MachShipHTTPError",
            "FusedShipHTTPError",
        }:
            return status_code in self.retry_status_codes

        return False

    def build_sync_retryer(self) -> Any:
        """Build a synchronous tenacity retryer."""
        if not self.enabled or Retrying is None:
            return None
        return Retrying(
            stop=stop_after_attempt(max(1, self.attempts)),
            wait=wait_exponential(multiplier=self.min_wait, max=self.max_wait),
            retry=retry_if_exception(self.should_retry),
            reraise=True,
        )

    def build_async_retryer(self) -> Any:
        """Build an asynchronous tenacity retryer."""
        if not self.enabled or AsyncRetrying is None:
            return None
        return AsyncRetrying(
            stop=stop_after_attempt(max(1, self.attempts)),
            wait=wait_exponential(multiplier=self.min_wait, max=self.max_wait),
            retry=retry_if_exception(self.should_retry),
            reraise=True,
        )


def run_sync_with_retry(
    policy: RetryPolicy | None,
    func: Callable[..., ResponseT],
    *args: Any,
    **kwargs: Any,
) -> ResponseT:
    """Run a synchronous callable with retry support when configured."""
    if policy is None:
        return func(*args, **kwargs)
    retryer = policy.build_sync_retryer()

    if retryer is None:
        return func(*args, **kwargs)

    for attempt in retryer:
        with attempt:
            return func(*args, **kwargs)

    return func(*args, **kwargs)


async def run_async_with_retry(
    policy: RetryPolicy | None,
    func: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> ResponseT:
    """Run an async callable with retry support when configured."""
    if policy is None:
        return await func(*args, **kwargs)

    retryer = policy.build_async_retryer()
    if retryer is None:
        return await func(*args, **kwargs)

    async for attempt in retryer:
        with attempt:
            return await func(*args, **kwargs)

    return await func(*args, **kwargs)
