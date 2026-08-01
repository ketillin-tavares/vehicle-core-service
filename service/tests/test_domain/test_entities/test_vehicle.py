import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.domain.entities.vehicle import MIN_VEHICLE_YEAR, Vehicle, VehicleStatus, validate_vehicle_year
from src.domain.exceptions import InvalidVehicleDataError, VehicleNotEditableError

CURRENT_YEAR = datetime.now(UTC).year


def _build_vehicle(**overrides: object) -> Vehicle:
    """
    Constrói um veículo de exemplo, aplicando eventuais overrides de campos.

    Args:
        **overrides: Campos que sobrescrevem os valores padrão do veículo.

    Returns:
        Instância de Vehicle pronta para uso nos testes.
    """
    fields: dict[str, object] = {
        "brand": "Toyota",
        "model": "Corolla",
        "year": 2022,
        "color": "Prata",
        "price": Decimal("95000.00"),
    }
    fields.update(overrides)
    return Vehicle(**fields)


class TestValidateVehicleYear:
    """Tests for the module-scope validate_vehicle_year() function."""

    def test_year_below_minimum_raises(self) -> None:
        """Test that a year before 1900 raises InvalidVehicleDataError."""
        # Arrange / Act / Assert
        with pytest.raises(InvalidVehicleDataError):
            validate_vehicle_year(MIN_VEHICLE_YEAR - 1)

    def test_minimum_year_is_accepted(self) -> None:
        """Test that the minimum accepted year (1900) does not raise."""
        # Arrange / Act
        year = validate_vehicle_year(MIN_VEHICLE_YEAR)

        # Assert
        assert year == MIN_VEHICLE_YEAR

    def test_current_year_plus_one_is_accepted(self) -> None:
        """Test that the current year plus one, the upper boundary, does not raise."""
        # Arrange / Act
        year = validate_vehicle_year(CURRENT_YEAR + 1)

        # Assert
        assert year == CURRENT_YEAR + 1

    def test_current_year_plus_two_raises(self) -> None:
        """Test that a year beyond the current year plus one raises InvalidVehicleDataError."""
        # Arrange / Act / Assert
        with pytest.raises(InvalidVehicleDataError):
            validate_vehicle_year(CURRENT_YEAR + 2)


class TestVehicleConstruction:
    """Tests for Vehicle entity construction and field validation."""

    def test_default_status_is_available(self) -> None:
        """Test that a newly constructed vehicle defaults to AVAILABLE status."""
        # Arrange / Act
        vehicle = _build_vehicle()

        # Assert
        assert vehicle.status is VehicleStatus.AVAILABLE

    def test_default_version_is_one(self) -> None:
        """Test that a newly constructed vehicle starts at version 1."""
        # Arrange / Act
        vehicle = _build_vehicle()

        # Assert
        assert vehicle.version == 1

    def test_id_defaults_to_a_generated_uuid(self) -> None:
        """Test that the id field defaults to a freshly generated UUID."""
        # Arrange / Act
        vehicle = _build_vehicle()

        # Assert
        assert isinstance(vehicle.id, uuid.UUID)

    def test_price_less_than_or_equal_to_zero_raises(self) -> None:
        """Test that a non-positive price fails pydantic validation."""
        # Arrange / Act / Assert
        with pytest.raises(ValidationError):
            _build_vehicle(price=Decimal("0"))

    def test_invalid_year_raises_invalid_vehicle_data_error(self) -> None:
        """Test that constructing a vehicle with an out-of-range year raises InvalidVehicleDataError."""
        # Arrange / Act / Assert
        with pytest.raises(InvalidVehicleDataError):
            _build_vehicle(year=MIN_VEHICLE_YEAR - 1)


class TestVehicleUpdateDetails:
    """Tests for Vehicle.update_details()."""

    def test_update_details_applies_new_fields(self) -> None:
        """Test that update_details() overwrites brand, model, year, color and price."""
        # Arrange
        vehicle = _build_vehicle()

        # Act
        vehicle.update_details(brand="Honda", model="Civic", year=2023, color="Preto", price=Decimal("120000.00"))

        # Assert
        assert vehicle.brand == "Honda"
        assert vehicle.model == "Civic"
        assert vehicle.year == 2023
        assert vehicle.color == "Preto"
        assert vehicle.price == Decimal("120000.00")

    def test_update_details_bumps_version(self) -> None:
        """Test that update_details() increments the version by one."""
        # Arrange
        vehicle = _build_vehicle()
        original_version = vehicle.version

        # Act
        vehicle.update_details(brand="Honda", model="Civic", year=2023, color="Preto", price=Decimal("120000.00"))

        # Assert
        assert vehicle.version == original_version + 1

    def test_update_details_bumps_updated_at(self) -> None:
        """Test that update_details() refreshes updated_at to a later timestamp."""
        # Arrange
        vehicle = _build_vehicle()
        vehicle.updated_at = datetime(2020, 1, 1, tzinfo=UTC)

        # Act
        vehicle.update_details(brand="Honda", model="Civic", year=2023, color="Preto", price=Decimal("120000.00"))

        # Assert
        assert vehicle.updated_at > datetime(2020, 1, 1, tzinfo=UTC)

    @pytest.mark.parametrize("status", [VehicleStatus.RESERVED, VehicleStatus.SOLD])
    def test_update_details_raises_when_not_available(self, status: VehicleStatus) -> None:
        """Test that update_details() raises VehicleNotEditableError when status is RESERVED or SOLD."""
        # Arrange
        vehicle = _build_vehicle(status=status)

        # Act / Assert
        with pytest.raises(VehicleNotEditableError):
            vehicle.update_details(brand="Honda", model="Civic", year=2023, color="Preto", price=Decimal("120000"))

    def test_update_details_with_invalid_year_raises(self) -> None:
        """Test that update_details() with an out-of-range year raises InvalidVehicleDataError."""
        # Arrange
        vehicle = _build_vehicle()

        # Act / Assert
        with pytest.raises(InvalidVehicleDataError):
            vehicle.update_details(
                brand="Honda", model="Civic", year=MIN_VEHICLE_YEAR - 1, color="Preto", price=Decimal("120000.00")
            )


class TestVehicleApplyStatus:
    """Tests for Vehicle.apply_status()."""

    def test_apply_status_changes_status(self) -> None:
        """Test that apply_status() updates the status field to the given value."""
        # Arrange
        vehicle = _build_vehicle()

        # Act
        vehicle.apply_status(VehicleStatus.RESERVED)

        # Assert
        assert vehicle.status is VehicleStatus.RESERVED

    def test_apply_status_does_not_bump_version(self) -> None:
        """Test that apply_status() leaves the version unchanged, unlike update_details()."""
        # Arrange
        vehicle = _build_vehicle()
        original_version = vehicle.version

        # Act
        vehicle.apply_status(VehicleStatus.SOLD)

        # Assert
        assert vehicle.version == original_version

    def test_apply_status_bumps_updated_at(self) -> None:
        """Test that apply_status() refreshes updated_at to a later timestamp."""
        # Arrange
        vehicle = _build_vehicle()
        vehicle.updated_at = datetime(2020, 1, 1, tzinfo=UTC)

        # Act
        vehicle.apply_status(VehicleStatus.RESERVED)

        # Assert
        assert vehicle.updated_at > datetime(2020, 1, 1, tzinfo=UTC)
