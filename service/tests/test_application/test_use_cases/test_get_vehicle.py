import uuid

import pytest

from src.application.dtos import VehicleResponse
from src.application.use_cases import GetVehicle
from src.domain.entities import Vehicle
from src.domain.exceptions import VehicleNotFoundError
from src.domain.repositories import VehicleRepository


class TestGetVehicle:
    """Tests for the GetVehicle use case."""

    @pytest.mark.asyncio
    async def test_get_vehicle_happy_path(
        self, mock_vehicle_repository: VehicleRepository, sample_vehicle: Vehicle, vehicle_id: uuid.UUID
    ) -> None:
        """Test that fetching an existing vehicle returns its DTO representation."""
        # Arrange
        mock_vehicle_repository.get_by_id.return_value = sample_vehicle
        use_case = GetVehicle(vehicle_repository=mock_vehicle_repository)

        # Act
        result = await use_case.execute(vehicle_id)

        # Assert
        assert isinstance(result, VehicleResponse)
        assert result.id == vehicle_id
        mock_vehicle_repository.get_by_id.assert_awaited_once_with(vehicle_id)

    @pytest.mark.asyncio
    async def test_get_vehicle_not_found_raises(
        self, mock_vehicle_repository: VehicleRepository, vehicle_id: uuid.UUID
    ) -> None:
        """Test that fetching an unknown vehicle raises VehicleNotFoundError."""
        # Arrange
        mock_vehicle_repository.get_by_id.return_value = None
        use_case = GetVehicle(vehicle_repository=mock_vehicle_repository)

        # Act / Assert
        with pytest.raises(VehicleNotFoundError):
            await use_case.execute(vehicle_id)
