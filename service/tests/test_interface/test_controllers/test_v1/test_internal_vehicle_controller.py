import uuid
from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos import VehicleResponse
from src.domain.entities import VehicleStatus
from src.domain.exceptions import VehicleNotFoundError
from src.environment import get_settings
from src.infrastructure.database import get_session
from src.interface.controllers.v1 import internal_vehicle_controller
from src.main import app


def _make_response(vehicle_id: uuid.UUID, status: VehicleStatus) -> VehicleResponse:
    """
    Constrói um VehicleResponse de exemplo para simular o retorno do caso de uso mockado.

    Args:
        vehicle_id: Identificador do veículo.
        status: Status comercial aplicado ao veículo.

    Returns:
        DTO pronto para ser retornado por um AsyncMock que simula o caso de uso.
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
        version=1,
        created_at=now,
        updated_at=now,
    )


async def _fake_get_session() -> AsyncGenerator[AsyncSession]:
    """Fornece uma sessão assíncrona falsa, evitando qualquer conexão real com o banco."""
    yield AsyncMock(spec=AsyncSession)


@pytest.fixture(autouse=True)
def _override_session() -> Iterator[None]:
    """Sobrescreve a dependência get_session por uma sessão falsa durante os testes de rota."""
    app.dependency_overrides[get_session] = _fake_get_session
    yield
    app.dependency_overrides.pop(get_session, None)


class TestApplyVehicleStatusRoute:
    """Tests for PATCH /internal/v1/vehicles/{vehicle_id}/status."""

    @pytest.mark.asyncio
    async def test_apply_status_returns_200(self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a valid status notification with the correct token returns 200 with the updated vehicle."""
        # Arrange
        vehicle_id = uuid.uuid4()
        expected = _make_response(vehicle_id, VehicleStatus.RESERVED)
        mock_use_case = AsyncMock()
        mock_use_case.execute.return_value = expected
        monkeypatch.setattr(internal_vehicle_controller, "ApplyVehicleStatus", lambda **kwargs: mock_use_case)
        token = get_settings().security.internal_api_token

        # Act
        response = await async_client.patch(
            f"/internal/v1/vehicles/{vehicle_id}/status",
            json={"status": "RESERVED"},
            headers={"X-Internal-Token": token},
        )

        # Assert
        assert response.status_code == 200
        assert response.json()["status"] == "RESERVED"

    @pytest.mark.asyncio
    async def test_apply_status_not_found_returns_404(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a status notification for an unknown vehicle returns 404."""
        # Arrange
        vehicle_id = uuid.uuid4()
        mock_use_case = AsyncMock()
        mock_use_case.execute.side_effect = VehicleNotFoundError(f"Veículo {vehicle_id} não encontrado")
        monkeypatch.setattr(internal_vehicle_controller, "ApplyVehicleStatus", lambda **kwargs: mock_use_case)
        token = get_settings().security.internal_api_token

        # Act
        response = await async_client.patch(
            f"/internal/v1/vehicles/{vehicle_id}/status",
            json={"status": "SOLD"},
            headers={"X-Internal-Token": token},
        )

        # Assert
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_apply_status_missing_token_returns_401(self, async_client: AsyncClient) -> None:
        """Test that a status notification without X-Internal-Token returns 401."""
        # Arrange
        vehicle_id = uuid.uuid4()

        # Act
        response = await async_client.patch(f"/internal/v1/vehicles/{vehicle_id}/status", json={"status": "SOLD"})

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_apply_status_wrong_token_returns_401(self, async_client: AsyncClient) -> None:
        """Test that a status notification with an invalid X-Internal-Token returns 401."""
        # Arrange
        vehicle_id = uuid.uuid4()

        # Act
        response = await async_client.patch(
            f"/internal/v1/vehicles/{vehicle_id}/status",
            json={"status": "SOLD"},
            headers={"X-Internal-Token": "wrong-token"},
        )

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_apply_status_non_ascii_token_returns_401(self, async_client: AsyncClient) -> None:
        """Test that a status notification with a non-ASCII X-Internal-Token returns a clean 401, not a 500."""
        # Arrange
        vehicle_id = uuid.uuid4()

        # Act
        response = await async_client.patch(
            f"/internal/v1/vehicles/{vehicle_id}/status",
            json={"status": "SOLD"},
            headers={"X-Internal-Token": "ç".encode("latin-1")},
        )

        # Assert
        assert response.status_code == 401
