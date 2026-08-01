import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities import Vehicle, VehicleStatus
from src.interface.gateways.vehicle_gateway import SQLAlchemyVehicleRepository


def _make_vehicle(vehicle_id: uuid.UUID) -> Vehicle:
    """
    Constrói um veículo de exemplo para os testes de integração.

    Args:
        vehicle_id: Identificador do veículo.

    Returns:
        Instância de Vehicle pronta para ser persistida.
    """
    return Vehicle(id=vehicle_id, brand="Toyota", model="Hilux", year=2022, color="Preto", price=Decimal("180000.00"))


@pytest.mark.integration
class TestSQLAlchemyVehicleRepositoryRoundTrip:
    """Integration tests for SQLAlchemyVehicleRepository against a real PostgreSQL instance."""

    @pytest.mark.asyncio
    async def test_add_then_get_by_id_round_trips(self, db_session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Test that a vehicle added in one session can be fetched back by id from another."""
        # Arrange
        vehicle_id = uuid.uuid4()
        async with db_session_factory() as add_session:
            repository = SQLAlchemyVehicleRepository(add_session)
            await repository.add(_make_vehicle(vehicle_id))
            await add_session.commit()

        # Act
        async with db_session_factory() as get_session:
            repository = SQLAlchemyVehicleRepository(get_session)
            found = await repository.get_by_id(vehicle_id)

        # Assert
        assert found is not None
        assert found.id == vehicle_id
        assert found.brand == "Toyota"
        assert found.status is VehicleStatus.AVAILABLE
        assert found.version == 1

    @pytest.mark.asyncio
    async def test_update_persists_bumped_version(self, db_session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Test that update() persists the new catalog data and the bumped version."""
        # Arrange
        vehicle_id = uuid.uuid4()
        async with db_session_factory() as setup_session:
            repository = SQLAlchemyVehicleRepository(setup_session)
            await repository.add(_make_vehicle(vehicle_id))
            await setup_session.commit()

        # Act
        async with db_session_factory() as update_session:
            repository = SQLAlchemyVehicleRepository(update_session)
            vehicle = await repository.get_by_id(vehicle_id)
            assert vehicle is not None
            vehicle.update_details(brand="Honda", model="Civic", year=2023, color="Branco", price=Decimal("140000"))
            await repository.update(vehicle)
            await update_session.commit()

        # Assert
        async with db_session_factory() as check_session:
            repository = SQLAlchemyVehicleRepository(check_session)
            found = await repository.get_by_id(vehicle_id)
        assert found is not None
        assert found.brand == "Honda"
        assert found.version == 2

    @pytest.mark.asyncio
    async def test_update_status_persists_new_status(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that update_status() persists the mirrored commercial status without bumping the version."""
        # Arrange
        vehicle_id = uuid.uuid4()
        async with db_session_factory() as setup_session:
            repository = SQLAlchemyVehicleRepository(setup_session)
            await repository.add(_make_vehicle(vehicle_id))
            await setup_session.commit()

        # Act
        async with db_session_factory() as status_session:
            repository = SQLAlchemyVehicleRepository(status_session)
            await repository.update_status(vehicle_id, VehicleStatus.SOLD)
            await status_session.commit()

        # Assert
        async with db_session_factory() as check_session:
            repository = SQLAlchemyVehicleRepository(check_session)
            found = await repository.get_by_id(vehicle_id)
        assert found is not None
        assert found.status is VehicleStatus.SOLD
        assert found.version == 1
