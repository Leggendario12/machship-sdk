"""Application settings helpers built on ``pydantic-settings``."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError(
        "Install machship-sdk[settings] to use machship_sdk.settings"
    ) from exc

from .config import MachShipConfig
from .fusedship.config import FusedShipConfig

DEFAULT_FUSEDSHIP_BASE_URL = "https://sync.fusedship.com"


class MachShipSDKSettings(BaseSettings):
    """App-level settings for both MachShip and FusedShip integrations."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    machship_base_url: str = Field(validation_alias="MACHSHIP_BASE_URL")
    machship_token: str = Field(
        validation_alias=AliasChoices(
            "MACHSHIP_TOKEN",
            "MACHSHIP_API_TOKEN",
        )
    )
    fusedship_base_url: str = Field(
        default=DEFAULT_FUSEDSHIP_BASE_URL,
        validation_alias="FUSEDSHIP_BASE_URL",
    )
    fusedship_token: str | None = Field(
        default=None,
        validation_alias="FUSEDSHIP_TOKEN",
    )
    fusedship_integration_id: str | None = Field(
        default=None,
        validation_alias="FUSEDSHIP_INTEGRATION_ID",
    )
    fusedship_client_token: str | None = Field(
        default=None,
        validation_alias="FUSEDSHIP_CLIENT_TOKEN",
    )
    fusedship_store_id: str | None = Field(
        default=None,
        validation_alias="FUSEDSHIP_STORE_ID",
    )

    @classmethod
    def from_env(cls, **kwargs: Any) -> "MachShipSDKSettings":
        """Load settings from the environment."""
        return cls(**kwargs)

    def to_machship_config(self, **kwargs: Any) -> MachShipConfig:
        """Build a MachShip client configuration from these settings."""
        return MachShipConfig(
            base_url=self.machship_base_url,
            token=self.machship_token,
            **kwargs,
        )

    def to_fusedship_config(self, **kwargs: Any) -> FusedShipConfig:
        """Build a FusedShip client configuration from these settings."""
        return FusedShipConfig(
            base_url=self.fusedship_base_url,
            token=self.fusedship_token,
            integration_id=self.fusedship_integration_id,
            client_token=self.fusedship_client_token,
            store_id=self.fusedship_store_id,
            **kwargs,
        )
