"""Public package exports for the MachShip SDK."""

from __future__ import annotations

import sys

from ._version import __version__
from . import _logging as _logging_module
from .async_client import AsyncMachShipClient
from .client import MachShipClient
from .config import MachShipConfig
from .exceptions import (
    MachShipAPIError,
    MachShipError,
    MachShipHTTPError,
    MachShipValidationError,
)
from .fusedship import (
    AsyncFusedShipClient,
    FusedShipAPIError,
    FusedShipClient,
    FusedShipConfig,
    FusedShipError,
    FusedShipHTTPError,
)

sys.modules.setdefault(__name__ + ".logging", _logging_module)
logging = _logging_module

__all__ = [
    "__version__",
    "AsyncMachShipClient",
    "AsyncFusedShipClient",
    "MachShipAPIError",
    "MachShipClient",
    "MachShipConfig",
    "MachShipError",
    "MachShipHTTPError",
    "MachShipValidationError",
    "FusedShipAPIError",
    "FusedShipClient",
    "FusedShipConfig",
    "FusedShipError",
    "FusedShipHTTPError",
]
