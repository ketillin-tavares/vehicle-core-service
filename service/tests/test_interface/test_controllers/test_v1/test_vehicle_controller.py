import uuid
from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos import VehicleResponse
from src.application.ports import SalesSync
from src.domain.entities import VehicleStatus
from src.domain.exceptions import InvalidVehicleDataError, VehicleNotEditableError, VehicleNotFoundError
from src.infrastructure.database import get_session
from src.interface.controllers.dependencies import get_sales_sync
from src.interface.controllers.v1 import vehicle_controller
from src.main import app

VALID_BODY = {"brand": "Toyota", "model": "Corolla", "year": 2022, "color": "Prata", "price": "95000.00"}


def _make_response(
    vehicle_id: uuid.UUID, version: int = 1, status: VehicleStatus = VehicleStatus.AVAILABLE
) -> VehicleResponse:
    """
    Constrói um VehicleResponse de exemplo para simular o retorno dos casos de uso mockados.

    Args:
        vehicle_id: Identificador do veículo.
        version: Versão do catálogo do veículo.
        status: Status comercial do veículo.

    Returns:
        DTO pronto para ser retornado por um AsyncMock que simula um caso de uso.
    """
    now = datetime.now(UTC)
    return VehicleResponse(
        id=vehicle_id,
        brand="Toyota",
        model="Corolla",
        year=2022,
        color="Prata",
        price=Decimal("95000.00"),
        status=status,
        version=version,
        created_at=now,
        updated_at=now,
    )


async def _fake_get_session() -> AsyncGenerator[AsyncSession]:
    """Fornece uma sessão assíncrona falsa, evitando qualquer conexão real com o banco."""
    yield AsyncMock(spec=AsyncSession)


@pytest.fixture(autouse=True)
def _override_dependencies(mock_sales_sync: SalesSync) -> Iterator[SalesSync]:
    """Sobrescreve as dependências de sessão e sincronização de vendas durante os testes de rota."""
    app.dependency_overrides[get_session] = _fake_get_session
    app.dependency_overrides[get_sales_sync] = lambda: mock_sales_sync
    yield mock_sales_sync
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_sales_sync, None)


class TestRegisterVehicleRoute:
    """Tests for POST /v1/vehicles."""

    @pytest.mark.asyncio
    async def test_register_vehicle_returns_201_and_schedules_sync(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, mock_sales_sync: SalesSync
    ) -> None:
        """Test that a valid registration returns 201 and schedules a snapshot push with the created data."""
        # Arrange
        vehicle_id = uuid.uuid4()
        expected = _make_response(vehicle_id)
        mock_use_case = AsyncMock()
        mock_use_case.execute.return_value = expected
        monkeypatch.setattr(vehicle_controller, "RegisterVehicle", lambda **kwargs: mock_use_case)

        # Act
        response = await async_client.post("/v1/vehicles", json=VALID_BODY)

        # Assert
        assert response.status_code == 201
        payload = response.json()
        assert payload["id"] == str(vehicle_id)
        assert payload["status"] == "AVAILABLE"
        assert payload["version"] == 1
        mock_sales_sync.push_vehicle_snapshot.assert_awaited_once()
        snapshot = mock_sales_sync.push_vehicle_snapshot.await_args.args[0]
        assert snapshot.vehicle_id == vehicle_id
        assert snapshot.brand == "Toyota"
        assert snapshot.version == 1

    @pytest.mark.asyncio
    async def test_register_vehicle_invalid_data_returns_422(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that InvalidVehicleDataError raised by the use case is translated to HTTP 422."""
        # Arrange
        mock_use_case = AsyncMock()
        mock_use_case.execute.side_effect = InvalidVehicleDataError("ano fora da faixa aceita")
        monkeypatch.setattr(vehicle_controller, "RegisterVehicle", lambda **kwargs: mock_use_case)

        # Act
        response = await async_client.post("/v1/vehicles", json=VALID_BODY)

        # Assert
        assert response.status_code == 422


class TestUpdateVehicleRoute:
    """Tests for PUT /v1/vehicles/{vehicle_id}."""

    @pytest.mark.asyncio
    async def test_update_vehicle_returns_200_and_schedules_sync(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, mock_sales_sync: SalesSync
    ) -> None:
        """Test that a valid update returns 200 and schedules a snapshot push with the updated data."""
        # Arrange
        vehicle_id = uuid.uuid4()
        expected = _make_response(vehicle_id, version=2)
        mock_use_case = AsyncMock()
        mock_use_case.execute.return_value = expected
        monkeypatch.setattr(vehicle_controller, "UpdateVehicle", lambda **kwargs: mock_use_case)

        # Act
        response = await async_client.put(f"/v1/vehicles/{vehicle_id}", json=VALID_BODY)

        # Assert
        assert response.status_code == 200
        payload = response.json()
        assert payload["version"] == 2
        mock_sales_sync.push_vehicle_snapshot.assert_awaited_once()
        snapshot = mock_sales_sync.push_vehicle_snapshot.await_args.args[0]
        assert snapshot.vehicle_id == vehicle_id
        assert snapshot.version == 2

    @pytest.mark.asyncio
    async def test_update_vehicle_not_found_returns_404(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, mock_sales_sync: SalesSync
    ) -> None:
        """Test that VehicleNotFoundError raised by the use case is translated to HTTP 404."""
        # Arrange
        vehicle_id = uuid.uuid4()
        mock_use_case = AsyncMock()
        mock_use_case.execute.side_effect = VehicleNotFoundError(f"Veículo {vehicle_id} não encontrado")
        monkeypatch.setattr(vehicle_controller, "UpdateVehicle", lambda **kwargs: mock_use_case)

        # Act
        response = await async_client.put(f"/v1/vehicles/{vehicle_id}", json=VALID_BODY)

        # Assert
        assert response.status_code == 404
        mock_sales_sync.push_vehicle_snapshot.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_vehicle_not_editable_returns_409(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, mock_sales_sync: SalesSync
    ) -> None:
        """Test that VehicleNotEditableError raised by the use case is translated to HTTP 409."""
        # Arrange
        vehicle_id = uuid.uuid4()
        mock_use_case = AsyncMock()
        mock_use_case.execute.side_effect = VehicleNotEditableError(f"Veículo {vehicle_id} não está disponível")
        monkeypatch.setattr(vehicle_controller, "UpdateVehicle", lambda **kwargs: mock_use_case)

        # Act
        response = await async_client.put(f"/v1/vehicles/{vehicle_id}", json=VALID_BODY)

        # Assert
        assert response.status_code == 409
        mock_sales_sync.push_vehicle_snapshot.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_vehicle_invalid_data_returns_422(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that InvalidVehicleDataError raised by the use case is translated to HTTP 422."""
        # Arrange
        vehicle_id = uuid.uuid4()
        mock_use_case = AsyncMock()
        mock_use_case.execute.side_effect = InvalidVehicleDataError("ano fora da faixa aceita")
        monkeypatch.setattr(vehicle_controller, "UpdateVehicle", lambda **kwargs: mock_use_case)

        # Act
        response = await async_client.put(f"/v1/vehicles/{vehicle_id}", json=VALID_BODY)

        # Assert
        assert response.status_code == 422


class TestGetVehicleRoute:
    """Tests for GET /v1/vehicles/{vehicle_id}."""

    @pytest.mark.asyncio
    async def test_get_vehicle_returns_200(self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that fetching an existing vehicle returns 200 with its data."""
        # Arrange
        vehicle_id = uuid.uuid4()
        expected = _make_response(vehicle_id)
        mock_use_case = AsyncMock()
        mock_use_case.execute.return_value = expected
        monkeypatch.setattr(vehicle_controller, "GetVehicle", lambda **kwargs: mock_use_case)

        # Act
        response = await async_client.get(f"/v1/vehicles/{vehicle_id}")

        # Assert
        assert response.status_code == 200
        assert response.json()["id"] == str(vehicle_id)

    @pytest.mark.asyncio
    async def test_get_vehicle_not_found_returns_404(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that fetching an unknown vehicle returns 404."""
        # Arrange
        vehicle_id = uuid.uuid4()
        mock_use_case = AsyncMock()
        mock_use_case.execute.side_effect = VehicleNotFoundError(f"Veículo {vehicle_id} não encontrado")
        monkeypatch.setattr(vehicle_controller, "GetVehicle", lambda **kwargs: mock_use_case)

        # Act
        response = await async_client.get(f"/v1/vehicles/{vehicle_id}")

        # Assert
        assert response.status_code == 404
