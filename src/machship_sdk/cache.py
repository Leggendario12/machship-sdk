"""Caching helpers for expensive MachShip lookups."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

ResponseT = TypeVar("ResponseT")


def ttl_cache(
    *,
    maxsize: int = 128,
    ttl: int = 300,
) -> Callable[[Callable[..., ResponseT]], Callable[..., ResponseT]]:
    """Return a TTL cache decorator backed by ``cachetools`` when installed."""
    try:
        from cachetools import TTLCache, cached
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "Install machship-sdk[cache] to use machship_sdk.cache.ttl_cache"
        ) from exc

    cache = TTLCache(maxsize=maxsize, ttl=ttl)

    def decorator(func: Callable[..., ResponseT]) -> Callable[..., ResponseT]:
        """Decorate ``func`` with a TTL cache."""
        return wraps(func)(cached(cache)(func))

    return decorator


def make_ttl_cache(*, maxsize: int = 128, ttl: int = 300) -> Any:
    """Construct a reusable TTLCache instance when cachetools is installed."""
    try:
        from cachetools import TTLCache
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "Install machship-sdk[cache] to use machship_sdk.cache.make_ttl_cache"
        ) from exc

    return TTLCache(maxsize=maxsize, ttl=ttl)
