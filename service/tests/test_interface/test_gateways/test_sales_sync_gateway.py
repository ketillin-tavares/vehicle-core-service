import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import pytest

from src.application.dtos import VehicleSnapshot
from src.interface.gateways import sales_sync_gateway
from src.interface.gateways.sales_sync_gateway import HttpSalesSync


def _make_snapshot(vehicle_id: uuid.UUID, version: int = 1) -> VehicleSnapshot:
    """
    Constrói um snapshot de catálogo de exemplo para os testes do adapter.

    Args:
        vehicle_id: Identificador do veículo.
        version: Versão do catálogo a ser publicada.

    Returns:
        Snapshot pronto para ser enviado ao vehicle-sales-service.
    """
    return VehicleSnapshot(
        vehicle_id=vehicle_id,
        brand="Toyota",
        model="Corolla",
        year=2022,
        color="Prata",
        price=Decimal("95000.00"),
        version=version,
    )


class TestHttpSalesSyncPushVehicleSnapshot:
    """Tests for HttpSalesSync.push_vehicle_snapshot() retry and best-effort behavior."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self, vehicle_id: uuid.UUID, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a successful PUT on the first attempt calls the sales service exactly once."""
        # Arrange
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json={"applied": True})

        monkeypatch.setattr(sales_sync_gateway.asyncio, "sleep", AsyncMock())
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        sync = HttpSalesSync(client=client, base_url="http://sales:8000", internal_token="tok")

        # Act
        await sync.push_vehicle_snapshot(_make_snapshot(vehicle_id))

        # Assert
        assert call_count == 1
        await client.aclose()

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self, vehicle_id: uuid.UUID, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a transient failure followed by a success stops retrying after two attempts."""
        # Arrange
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ConnectError("boom")
            return httpx.Response(200, json={"applied": True})

        monkeypatch.setattr(sales_sync_gateway.asyncio, "sleep", AsyncMock())
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        sync = HttpSalesSync(client=client, base_url="http://sales:8000", internal_token="tok")

        # Act
        await sync.push_vehicle_snapshot(_make_snapshot(vehicle_id))

        # Assert
        assert call_count == 2
        await client.aclose()

    @pytest.mark.asyncio
    async def test_swallows_failure_after_max_attempts(
        self, vehicle_id: uuid.UUID, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that persistent failures are absorbed (never raised) after exhausting all retry attempts."""
        # Arrange
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(sales_sync_gateway.asyncio, "sleep", AsyncMock())
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        sync = HttpSalesSync(client=client, base_url="http://sales:8000", internal_token="tok")

        # Act
        await sync.push_vehicle_snapshot(_make_snapshot(vehicle_id))

        # Assert
        assert call_count == sales_sync_gateway.MAX_ATTEMPTS
        await client.aclose()


class TestHttpSalesSyncContractPin:
    """Contract-pin tests locking the wire shape of the request sent to vehicle-sales-service."""

    @pytest.mark.asyncio
    async def test_request_matches_the_agreed_contract(self, vehicle_id: uuid.UUID) -> None:
        """Test that push_vehicle_snapshot sends the exact URL, method, header and body agreed with Sales."""
        # Arrange
        captured_requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_requests.append(request)
            return httpx.Response(200, json={"applied": True})

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        sync = HttpSalesSync(client=client, base_url="http://sales:8000/", internal_token="secret-token")

        # Act
        await sync.push_vehicle_snapshot(_make_snapshot(vehicle_id, version=5))

        # Assert
        assert len(captured_requests) == 1
        request = captured_requests[0]
        assert request.method == "PUT"
        assert request.url.path == f"/internal/v1/vehicles/{vehicle_id}"
        assert request.headers["X-Internal-Token"] == "secret-token"
        body = json.loads(request.content)
        assert set(body.keys()) == {"brand", "model", "year", "color", "price", "version"}
        assert body["price"] == "95000.00"
        assert body["version"] == 5
        await client.aclose()
