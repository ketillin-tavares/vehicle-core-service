import uuid

import pytest

from src.application.dtos import VehicleResponse
from src.application.use_cases import ApplyVehicleStatus
from src.domain.entities import Vehicle, VehicleStatus
from src.domain.exceptions import VehicleNotFoundError
from src.domain.repositories import VehicleRepository


class TestApplyVehicleStatus:
    """Tests for the ApplyVehicleStatus use case."""

    @pytest.mark.asyncio
    async def test_apply_vehicle_status_happy_path(
        self, mock_vehicle_repository: VehicleRepository, sample_vehicle: Vehicle, vehicle_id: uuid.UUID
    ) -> None:
        """Test that applying a status calls update_status with the right args and returns the updated DTO."""
        # Arrange
        mock_vehicle_repository.get_by_id.return_value = sample_vehicle
        use_case = ApplyVehicleStatus(vehicle_repository=mock_vehicle_repository)

        # Act
        result = await use_case.execute(vehicle_id=vehicle_id, status=VehicleStatus.RESERVED)

        # Assert
        assert isinstance(result, VehicleResponse)
        assert result.status is VehicleStatus.RESERVED
        mock_vehicle_repository.update_status.assert_awaited_once_with(vehicle_id, VehicleStatus.RESERVED)

    @pytest.mark.asyncio
    async def test_apply_vehicle_status_not_found_raises(
        self, mock_vehicle_repository: VehicleRepository, vehicle_id: uuid.UUID
    ) -> None:
        """Test that applying a status to an unknown vehicle raises VehicleNotFoundError."""
        # Arrange
        mock_vehicle_repository.get_by_id.return_value = None
        use_case = ApplyVehicleStatus(vehicle_repository=mock_vehicle_repository)

        # Act / Assert
        with pytest.raises(VehicleNotFoundError):
            await use_case.execute(vehicle_id=vehicle_id, status=VehicleStatus.SOLD)
        mock_vehicle_repository.update_status.assert_not_awaited()
