import uuid
from decimal import Decimal

import pytest

from src.application.dtos import VehicleResponse
from src.application.use_cases import UpdateVehicle
from src.domain.entities import Vehicle, VehicleStatus
from src.domain.exceptions import VehicleNotEditableError, VehicleNotFoundError
from src.domain.repositories import VehicleRepository


class TestUpdateVehicle:
    """Tests for the UpdateVehicle use case."""

    @pytest.mark.asyncio
    async def test_update_vehicle_happy_path(
        self, mock_vehicle_repository: VehicleRepository, sample_vehicle: Vehicle, vehicle_id: uuid.UUID
    ) -> None:
        """Test that updating an available vehicle bumps its version and persists the change."""
        # Arrange
        mock_vehicle_repository.get_by_id.return_value = sample_vehicle
        mock_vehicle_repository.update.side_effect = lambda vehicle: vehicle
        use_case = UpdateVehicle(vehicle_repository=mock_vehicle_repository)

        # Act
        result = await use_case.execute(
            vehicle_id=vehicle_id,
            brand="Honda",
            model="Civic",
            year=2023,
            color="Preto",
            price=Decimal("120000.00"),
        )

        # Assert
        assert isinstance(result, VehicleResponse)
        assert result.brand == "Honda"
        assert result.version == 2
        mock_vehicle_repository.update.assert_awaited_once()
        updated_vehicle = mock_vehicle_repository.update.await_args.args[0]
        assert updated_vehicle.version == 2
        assert updated_vehicle.brand == "Honda"

    @pytest.mark.asyncio
    async def test_update_vehicle_not_found_raises(
        self, mock_vehicle_repository: VehicleRepository, vehicle_id: uuid.UUID
    ) -> None:
        """Test that updating an unknown vehicle raises VehicleNotFoundError without calling update()."""
        # Arrange
        mock_vehicle_repository.get_by_id.return_value = None
        use_case = UpdateVehicle(vehicle_repository=mock_vehicle_repository)

        # Act / Assert
        with pytest.raises(VehicleNotFoundError):
            await use_case.execute(
                vehicle_id=vehicle_id,
                brand="Honda",
                model="Civic",
                year=2023,
                color="Preto",
                price=Decimal("120000.00"),
            )
        mock_vehicle_repository.update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_vehicle_not_editable_propagates(
        self, mock_vehicle_repository: VehicleRepository, sample_vehicle: Vehicle, vehicle_id: uuid.UUID
    ) -> None:
        """Test that updating a RESERVED/SOLD vehicle propagates VehicleNotEditableError from the entity."""
        # Arrange
        sample_vehicle.status = VehicleStatus.SOLD
        mock_vehicle_repository.get_by_id.return_value = sample_vehicle
        use_case = UpdateVehicle(vehicle_repository=mock_vehicle_repository)

        # Act / Assert
        with pytest.raises(VehicleNotEditableError):
            await use_case.execute(
                vehicle_id=vehicle_id,
                brand="Honda",
                model="Civic",
                year=2023,
                color="Preto",
                price=Decimal("120000.00"),
            )
        mock_vehicle_repository.update.assert_not_awaited()
