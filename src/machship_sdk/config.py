"""Configuration models for the MachShip SDK."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import httpx

DEFAULT_BASE_URL_ENV_VAR = "MACHSHIP_BASE_URL"
DEFAULT_TOKEN_ENV_VARS = ("MACHSHIP_TOKEN", "MACHSHIP_API_TOKEN")


def _first_environment_value(keys: Sequence[str]) -> str | None:
    """Check environment variables for the first available key."""
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return None


@dataclass(slots=True, frozen=True)
class MachShipConfig:
    """Configuration options for MachShipClient and AsyncMachShipClient."""

    base_url: str
    token: str
    timeout: float | httpx.Timeout = 30.0
    verify: bool | str = True
    follow_redirects: bool = False
    headers: Mapping[str, str] = field(default_factory=dict)
    raise_on_api_errors: bool = True

    def __post_init__(self) -> None:
        """Validate configuration values after initialization."""
        base_url = self.base_url.strip()
        token = self.token.strip()
        if not base_url:
            raise ValueError("MachShipConfig.base_url is required")
        if not token:
            raise ValueError("MachShipConfig.token is required")

        object.__setattr__(self, "base_url", base_url.rstrip("/"))
        object.__setattr__(self, "token", token)

    @classmethod
    def from_env(
        cls,
        *,
        base_url_env: str = DEFAULT_BASE_URL_ENV_VAR,
        token_envs: Sequence[str] = DEFAULT_TOKEN_ENV_VARS,
        timeout: float | httpx.Timeout = 30.0,
        verify: bool | str = True,
        follow_redirects: bool = False,
        headers: Mapping[str, str] | None = None,
        raise_on_api_errors: bool = True,
    ) -> MachShipConfig:
        """Load configuration from environment variables."""
        base_url = os.getenv(base_url_env)
        if not base_url:
            raise ValueError(
                f"Missing MachShip base URL environment variable: {base_url_env}"
            )

        token = _first_environment_value(token_envs)
        if not token:
            joined = ", ".join(token_envs)
            raise ValueError(
                f"Missing MachShip token environment variable. Checked: {joined}"
            )

        return cls(
            base_url=base_url,
            token=token,
            timeout=timeout,
            verify=verify,
            follow_redirects=follow_redirects,
            headers=headers or {},
            raise_on_api_errors=raise_on_api_errors,
        )
