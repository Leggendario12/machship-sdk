"""Configuration models for the FusedShip integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from os import getenv
from typing import Mapping, Sequence

import httpx

DEFAULT_BASE_URL = "https://sync.fusedship.com"


def _first_env_value(keys: Sequence[str]) -> str | None:
    """
    Get the value of the first environment variable that is set.

    Args:
        keys: A sequence of environment variable names to check.

    Returns:
        The value of the first environment variable that is set, or None.
    """
    for key in keys:
        value = getenv(key)
        if value:
            return value
    return None


@dataclass(slots=True, frozen=True)
class FusedShipConfig:
    """
    Configuration for the FusedShip client.

    Attributes:
        base_url: The base URL for the FusedShip API.
        token: The API token for live pricing.
        integration_id: The integration ID for live pricing.
        client_token: The client token for e-commerce.
        store_id: The store ID for e-commerce.
        timeout: The timeout for HTTP requests.
        verify: Whether to verify SSL certificates.
        follow_redirects: Whether to follow HTTP redirects.
        headers: Additional HTTP headers to include in requests.
    """

    base_url: str = DEFAULT_BASE_URL
    token: str | None = None
    integration_id: str | None = None
    client_token: str | None = None
    store_id: str | None = None
    timeout: float | httpx.Timeout = 30.0
    verify: bool | str = True
    follow_redirects: bool = False
    headers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Post-initialization to normalize the base URL."""
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))

    @classmethod
    def from_env(
        cls,
        *,
        base_url_env: str = "FUSEDSHIP_BASE_URL",
        token_env: str = "FUSEDSHIP_TOKEN",
        integration_id_env: str = "FUSEDSHIP_INTEGRATION_ID",
        client_token_env: str = "FUSEDSHIP_CLIENT_TOKEN",
        store_id_env: str = "FUSEDSHIP_STORE_ID",
        timeout: float | httpx.Timeout = 30.0,
        verify: bool | str = True,
        follow_redirects: bool = False,
        headers: Mapping[str, str] | None = None,
    ) -> "FusedShipConfig":
        """
        Create a FusedShipConfig instance from environment variables.

        Args:
            base_url_env: Environment variable for the base URL.
            token_env: Environment variable for the live pricing token.
            integration_id_env: Environment variable for the integration ID.
            client_token_env: Environment variable for the client token.
            store_id_env: Environment variable for the store ID.
            timeout: The timeout for HTTP requests.
            verify: Whether to verify SSL certificates.
            follow_redirects: Whether to follow HTTP redirects.
            headers: Additional HTTP headers to include in requests.

        Returns:
            A new FusedShipConfig instance.
        """
        return cls(
            base_url=getenv(base_url_env, DEFAULT_BASE_URL),
            token=getenv(token_env),
            integration_id=getenv(integration_id_env),
            client_token=getenv(client_token_env),
            store_id=getenv(store_id_env),
            timeout=timeout,
            verify=verify,
            follow_redirects=follow_redirects,
            headers=headers or {},
        )

    def require_live_pricing_credentials(self) -> tuple[str, str]:
        """
        Ensure that live pricing credentials are provided.

        Returns:
            A tuple of (token, integration_id).

        Raises:
            ValueError: If either token or integration_id is missing.
        """
        if not self.token:
            raise ValueError("FusedShip live pricing token is required")
        if not self.integration_id:
            raise ValueError("FusedShip integration_id is required")
        return self.token, self.integration_id

    def require_ecommerce_credentials(self) -> tuple[str, str]:
        """
        Ensure that e-commerce credentials are provided.

        Returns:
            A tuple of (client_token, store_id).

        Raises:
            ValueError: If either client_token or store_id is missing.
        """
        if not self.client_token:
            raise ValueError("FusedShip client_token is required")
        if not self.store_id:
            raise ValueError("FusedShip store_id is required")
        return self.client_token, self.store_id
