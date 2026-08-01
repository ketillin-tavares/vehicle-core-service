import os
import uuid
from collections.abc import AsyncGenerator
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

# DATABASE_PASSWORD e INTERNAL_API_TOKEN são obrigatórios em src.environment.Settings; precisam estar
# definidos antes de qualquer import de src.main, que resolve as settings em tempo de import.
os.environ.setdefault("DATABASE_PASSWORD", "vehicle_core_pass")
os.environ.setdefault("INTERNAL_API_TOKEN", "internal-token")

from src.application.ports import SalesSync  # noqa: E402
from src.domain.entities import Vehicle, VehicleStatus  # noqa: E402
from src.domain.repositories import VehicleRepository  # noqa: E402
from src.main import app  # noqa: E402


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient]:
    """
    Fixture para cliente HTTP assíncrono usado nos testes de rotas.

    Yields:
        Cliente httpx configurado com transporte ASGI apontando para a aplicação FastAPI.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def vehicle_id() -> uuid.UUID:
    """Fixture com um UUID de veículo de exemplo."""
    return uuid.uuid4()


@pytest.fixture
def mock_vehicle_repository() -> VehicleRepository:
    """Fixture com mock da interface VehicleRepository."""
    return AsyncMock(spec=VehicleRepository)


@pytest.fixture
def mock_sales_sync() -> SalesSync:
    """Fixture com mock da interface SalesSync."""
    return AsyncMock(spec=SalesSync)


@pytest.fixture
def sample_vehicle(vehicle_id: uuid.UUID) -> Vehicle:
    """Fixture com um veículo de exemplo, disponível para edição."""
    return Vehicle(
        id=vehicle_id,
        brand="Toyota",
        model="Corolla",
        year=2022,
        color="Prata",
        price=Decimal("95000.00"),
        status=VehicleStatus.AVAILABLE,
    )
