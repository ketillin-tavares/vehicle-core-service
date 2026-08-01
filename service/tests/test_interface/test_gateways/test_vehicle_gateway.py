import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import Vehicle, VehicleStatus
from src.infrastructure.models import VehicleModel
from src.interface.gateways.vehicle_gateway import SQLAlchemyVehicleRepository, map_vehicle_model_to_entity


def _make_model(vehicle_id: uuid.UUID, status: str = "AVAILABLE", version: int = 1) -> VehicleModel:
    """
    Constrói um VehicleModel de exemplo sem tocar o banco de dados.

    Args:
        vehicle_id: Identificador do veículo.
        status: Status comercial persistido.
        version: Versão do catálogo persistida.

    Returns:
        Instância ORM pronta para uso nos testes.
    """
    now = datetime.now(UTC)
    return VehicleModel(
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


class TestMapVehicleModelToEntity:
    """Tests for the map_vehicle_model_to_entity translation function."""

    def test_maps_all_fields_from_model_to_entity(self, vehicle_id: uuid.UUID) -> None:
        """Test that the mapper translates every ORM field to the equivalent domain entity field."""
        # Arrange
        model = _make_model(vehicle_id, status="RESERVED", version=3)

        # Act
        entity = map_vehicle_model_to_entity(model)

        # Assert
        assert isinstance(entity, Vehicle)
        assert entity.id == vehicle_id
        assert entity.status is VehicleStatus.RESERVED
        assert entity.version == 3
        assert entity.brand == model.brand


class TestSQLAlchemyVehicleRepositoryAdd:
    """Tests for SQLAlchemyVehicleRepository.add()."""

    @pytest.mark.asyncio
    async def test_add_persists_vehicle_and_returns_entity(self, vehicle_id: uuid.UUID) -> None:
        """Test that add stages the ORM model in the session and returns the equivalent domain entity."""
        # Arrange
        session = AsyncMock(spec=AsyncSession)
        session.add = MagicMock()
        repository = SQLAlchemyVehicleRepository(session)
        vehicle = Vehicle(
            id=vehicle_id, brand="Toyota", model="Corolla", year=2022, color="Prata", price=Decimal("95000.00")
        )

        # Act
        created = await repository.add(vehicle)

        # Assert
        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        assert created.id == vehicle_id
        assert created.brand == "Toyota"


class TestSQLAlchemyVehicleRepositoryGetById:
    """Tests for SQLAlchemyVehicleRepository.get_by_id()."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_entity_when_found(self, vehicle_id: uuid.UUID) -> None:
        """Test that get_by_id maps the ORM model to a Vehicle when found."""
        # Arrange
        model = _make_model(vehicle_id)
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = model
        session.execute.return_value = result
        repository = SQLAlchemyVehicleRepository(session)

        # Act
        entity = await repository.get_by_id(vehicle_id)

        # Assert
        assert entity is not None
        assert entity.id == vehicle_id

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_missing(self, vehicle_id: uuid.UUID) -> None:
        """Test that get_by_id returns None when no matching row exists."""
        # Arrange
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result
        repository = SQLAlchemyVehicleRepository(session)

        # Act
        entity = await repository.get_by_id(vehicle_id)

        # Assert
        assert entity is None


class TestSQLAlchemyVehicleRepositoryUpdate:
    """Tests for SQLAlchemyVehicleRepository.update()."""

    @pytest.mark.asyncio
    async def test_update_returns_persisted_entity(self, vehicle_id: uuid.UUID) -> None:
        """Test that update issues an UPDATE..RETURNING statement and maps the returned row."""
        # Arrange
        model = _make_model(vehicle_id, version=2)
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalars.return_value.one.return_value = model
        session.execute.return_value = result
        repository = SQLAlchemyVehicleRepository(session)
        vehicle = Vehicle(
            id=vehicle_id,
            brand="Toyota",
            model="Corolla",
            year=2022,
            color="Prata",
            price=Decimal("95000.00"),
            version=2,
        )

        # Act
        updated = await repository.update(vehicle)

        # Assert
        assert updated.id == vehicle_id
        assert updated.version == 2
        session.execute.assert_awaited_once()


class TestSQLAlchemyVehicleRepositoryUpdateStatus:
    """Tests for SQLAlchemyVehicleRepository.update_status()."""

    @pytest.mark.asyncio
    async def test_update_status_executes_update_statement(self, vehicle_id: uuid.UUID) -> None:
        """Test that update_status issues exactly one UPDATE execution against the session."""
        # Arrange
        session = AsyncMock(spec=AsyncSession)
        repository = SQLAlchemyVehicleRepository(session)

        # Act
        await repository.update_status(vehicle_id, VehicleStatus.SOLD)

        # Assert
        session.execute.assert_awaited_once()
