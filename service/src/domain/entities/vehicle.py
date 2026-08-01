import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from src.domain.exceptions import InvalidVehicleDataError, VehicleNotEditableError

MIN_VEHICLE_YEAR = 1900
MAX_YEARS_AHEAD = 1


def validate_vehicle_year(year: int) -> int:
    """
    Garante que o ano de fabricação está dentro da faixa aceita pelo negócio.

    Args:
        year: Ano de fabricação informado.

    Returns:
        O ano validado.

    Raises:
        InvalidVehicleDataError: Se o ano estiver fora da faixa 1900..ano atual + 1.
    """
    max_year = datetime.now(UTC).year + MAX_YEARS_AHEAD
    if year < MIN_VEHICLE_YEAR or year > max_year:
        raise InvalidVehicleDataError(f"Ano do veículo deve estar entre {MIN_VEHICLE_YEAR} e {max_year}")
    return year


class VehicleStatus(StrEnum):
    """Status comerciais possíveis de um veículo, espelhados a partir do vehicle-sales-service."""

    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    SOLD = "SOLD"


class Vehicle(BaseModel):
    """Veículo do catálogo, fonte da verdade dos dados cadastrais da plataforma."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Identificador do veículo, cunhado pelo Core")
    brand: str = Field(..., min_length=1, max_length=100, description="Marca do veículo")
    model: str = Field(..., min_length=1, max_length=100, description="Modelo do veículo")
    year: int = Field(..., description="Ano de fabricação do veículo")
    color: str = Field(..., min_length=1, max_length=50, description="Cor do veículo")
    price: Decimal = Field(..., gt=0, description="Preço de catálogo do veículo")
    status: VehicleStatus = Field(
        default=VehicleStatus.AVAILABLE,
        description="Status comercial espelhado do serviço de vendas, usado para bloquear edições",
    )
    version: int = Field(default=1, ge=1, description="Versão do catálogo, incrementada a cada edição")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Momento de cadastro do veículo",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Momento da última alteração do veículo",
    )

    @field_validator("year")
    @classmethod
    def check_year(cls, year: int) -> int:
        """
        Aplica a validação de faixa do ano de fabricação na construção da entidade.

        Args:
            year: Ano de fabricação informado.

        Returns:
            O ano validado.

        Raises:
            InvalidVehicleDataError: Se o ano estiver fora da faixa 1900..ano atual + 1.
        """
        return validate_vehicle_year(year)

    def update_details(self, brand: str, model: str, year: int, color: str, price: Decimal) -> None:
        """
        Atualiza os dados de catálogo do veículo, incrementando a versão.

        Args:
            brand: Nova marca do veículo.
            model: Novo modelo do veículo.
            year: Novo ano de fabricação.
            color: Nova cor do veículo.
            price: Novo preço de catálogo.

        Raises:
            VehicleNotEditableError: Se o veículo não estiver disponível (reservado ou vendido).
            InvalidVehicleDataError: Se o novo ano de fabricação estiver fora da faixa aceita.
        """
        if self.status is not VehicleStatus.AVAILABLE:
            raise VehicleNotEditableError(f"Veículo {self.id} não está disponível e não pode ser editado")

        self.brand = brand
        self.model = model
        self.year = validate_vehicle_year(year)
        self.color = color
        self.price = price
        self.version += 1
        self.updated_at = datetime.now(UTC)

    def apply_status(self, status: VehicleStatus) -> None:
        """
        Espelha localmente o status comercial informado pelo serviço de vendas.

        Args:
            status: Novo status comercial do veículo.
        """
        self.status = status
        self.updated_at = datetime.now(UTC)
