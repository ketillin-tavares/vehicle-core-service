import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from src.domain.entities import Vehicle, VehicleStatus


class VehicleResponse(BaseModel):
    """DTO de resposta com os dados completos de um veículo do catálogo."""

    id: uuid.UUID = Field(..., description="Identificador do veículo")
    brand: str = Field(..., description="Marca do veículo")
    model: str = Field(..., description="Modelo do veículo")
    year: int = Field(..., description="Ano de fabricação do veículo")
    color: str = Field(..., description="Cor do veículo")
    price: Decimal = Field(..., description="Preço de catálogo do veículo")
    status: VehicleStatus = Field(..., description="Status comercial espelhado do serviço de vendas")
    version: int = Field(..., description="Versão atual do catálogo do veículo")
    created_at: datetime = Field(..., description="Momento de cadastro do veículo")
    updated_at: datetime = Field(..., description="Momento da última alteração do veículo")

    @classmethod
    def from_entity(cls, vehicle: Vehicle) -> "VehicleResponse":
        """
        Converte a entidade de domínio Vehicle no DTO de resposta.

        Args:
            vehicle: Entidade de domínio do veículo.

        Returns:
            DTO equivalente, pronto para ser serializado pela camada de interface.
        """
        return cls(
            id=vehicle.id,
            brand=vehicle.brand,
            model=vehicle.model,
            year=vehicle.year,
            color=vehicle.color,
            price=vehicle.price,
            status=vehicle.status,
            version=vehicle.version,
            created_at=vehicle.created_at,
            updated_at=vehicle.updated_at,
        )
