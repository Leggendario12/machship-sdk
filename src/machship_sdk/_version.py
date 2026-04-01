"""Version metadata for the MachShip SDK."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("machship-sdk")
except PackageNotFoundError:  # pragma: no cover - local source checkout fallback
    __version__ = "0.0.0"
