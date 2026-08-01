from decimal import Decimal

from pydantic import BaseModel, Field


class VehicleRequest(BaseModel):
    """Corpo das requisições de cadastro e edição de um veículo do catálogo."""

    brand: str = Field(..., min_length=1, max_length=100, description="Marca do veículo")
    model: str = Field(..., min_length=1, max_length=100, description="Modelo do veículo")
    year: int = Field(..., ge=1900, le=2100, description="Ano de fabricação do veículo")
    color: str = Field(..., min_length=1, max_length=50, description="Cor do veículo")
    price: Decimal = Field(..., gt=0, description="Preço de catálogo do veículo")
