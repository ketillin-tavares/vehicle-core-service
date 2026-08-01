from pydantic import BaseModel, Field

from src.domain.entities import VehicleStatus


class VehicleStatusRequest(BaseModel):
    """Corpo da notificação de status comercial enviada pelo vehicle-sales-service."""

    status: VehicleStatus = Field(..., description="Status comercial a ser espelhado no catálogo")
