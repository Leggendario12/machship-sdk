"""JSON serialization helpers with optional ``orjson`` acceleration."""

from __future__ import annotations

import json
from typing import Any

from ._core import _jsonable

try:
    import orjson
except ImportError:  # pragma: no cover - optional dependency
    orjson = None


def serialize_json_payload(payload: Any) -> Any:
    """Convert payloads into JSON-serializable Python objects."""
    return _jsonable(payload)


def serialize_query_params(params: Any) -> Any:
    """Convert query parameters into JSON-serializable Python objects."""
    return _jsonable(params)


def dump_json_payload(payload: Any) -> bytes:
    """Serialize a payload to JSON bytes."""
    data = _jsonable(payload)
    if orjson is not None:
        return orjson.dumps(data)
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode()


def load_json_payload(payload: bytes) -> Any:
    """Deserialize JSON bytes into Python objects."""
    if orjson is not None:
        return orjson.loads(payload)
    return json.loads(payload.decode())
