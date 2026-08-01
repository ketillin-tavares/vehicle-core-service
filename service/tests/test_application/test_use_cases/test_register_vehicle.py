from decimal import Decimal

import pytest

from src.application.dtos import VehicleResponse
from src.application.use_cases import RegisterVehicle
from src.domain.entities import Vehicle, VehicleStatus
from src.domain.repositories import VehicleRepository


class TestRegisterVehicle:
    """Tests for the RegisterVehicle use case."""

    @pytest.mark.asyncio
    async def test_register_vehicle_happy_path(self, mock_vehicle_repository: VehicleRepository) -> None:
        """Test that registering a vehicle persists it via the repository and returns the DTO."""
        # Arrange
        mock_vehicle_repository.add.side_effect = lambda vehicle: vehicle
        use_case = RegisterVehicle(vehicle_repository=mock_vehicle_repository)

        # Act
        result = await use_case.execute(
            brand="Toyota", model="Corolla", year=2022, color="Prata", price=Decimal("95000.00")
        )

        # Assert
        assert isinstance(result, VehicleResponse)
        assert result.brand == "Toyota"
        assert result.status is VehicleStatus.AVAILABLE
        assert result.version == 1
        mock_vehicle_repository.add.assert_awaited_once()
        added_vehicle = mock_vehicle_repository.add.await_args.args[0]
        assert isinstance(added_vehicle, Vehicle)
        assert added_vehicle.status is VehicleStatus.AVAILABLE
