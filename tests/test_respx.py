"""Tests that demonstrate HTTP mocking with ``respx``."""

from __future__ import annotations

import httpx
import respx

from machship_sdk import MachShipClient, MachShipConfig


def test_respx_can_mock_machship_ping() -> None:
    """Mock a MachShip request without calling the network."""
    with MachShipClient(
        MachShipConfig(base_url="https://example.com", token="secret"),
    ) as client, respx.mock(base_url="https://example.com") as mock:
        route = mock.post("/apiv2/authenticate/ping").mock(
            return_value=httpx.Response(
                200,
                json={"object": True, "errors": []},
            )
        )

        response = client.ping()

    assert route.called is True
    assert response.object is True
