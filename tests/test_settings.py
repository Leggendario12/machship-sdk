"""Tests for application settings helpers."""

from __future__ import annotations

from machship_sdk.settings import MachShipSDKSettings


def test_settings_load_from_environment(monkeypatch) -> None:
    """Load SDK settings from environment variables."""
    monkeypatch.setenv("MACHSHIP_BASE_URL", "https://mach.example.com/")
    monkeypatch.setenv("MACHSHIP_API_TOKEN", "mach-token")
    monkeypatch.setenv("FUSEDSHIP_BASE_URL", "https://fused.example.com/")
    monkeypatch.setenv("FUSEDSHIP_TOKEN", "fused-token")
    monkeypatch.setenv("FUSEDSHIP_INTEGRATION_ID", "integration-123")
    monkeypatch.setenv("FUSEDSHIP_CLIENT_TOKEN", "client-456")
    monkeypatch.setenv("FUSEDSHIP_STORE_ID", "store-789")

    settings = MachShipSDKSettings.from_env(_env_file=None)

    machship_config = settings.to_machship_config(timeout=15.0)
    fusedship_config = settings.to_fusedship_config(follow_redirects=True)

    assert settings.machship_token == "mach-token"
    assert machship_config.base_url == "https://mach.example.com"
    assert machship_config.timeout == 15.0
    assert fusedship_config.base_url == "https://fused.example.com"
    assert fusedship_config.token == "fused-token"
    assert fusedship_config.integration_id == "integration-123"
    assert fusedship_config.client_token == "client-456"
    assert fusedship_config.store_id == "store-789"
    assert fusedship_config.follow_redirects is True
