import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos import VehicleResponse
from src.application.use_cases import ApplyVehicleStatus
from src.infrastructure.database import get_session
from src.interface.controllers.dependencies import verify_internal_token
from src.interface.gateways import SQLAlchemyVehicleRepository
from src.interface.presenters import NotFoundResponse, UnauthorizedResponse, VehicleStatusRequest

router = APIRouter(prefix="/internal/v1/vehicles", tags=["internal"])


@router.patch(
    "/{vehicle_id}/status",
    response_model=VehicleResponse,
    dependencies=[Depends(verify_internal_token)],
    responses={401: {"model": UnauthorizedResponse}, 404: {"model": NotFoundResponse}},
)
async def apply_vehicle_status(
    vehicle_id: uuid.UUID,
    request: VehicleStatusRequest,
    session: AsyncSession = Depends(get_session),
) -> VehicleResponse:
    """
    Espelha no catálogo o status comercial notificado pelo vehicle-sales-service.

    Args:
        vehicle_id: Identificador do veículo notificado.
        request: Status comercial a ser espelhado.
        session: Sessão de banco fornecida pela dependência de infraestrutura.

    Returns:
        DTO com os dados do veículo após o espelhamento do status.
    """
    use_case = ApplyVehicleStatus(vehicle_repository=SQLAlchemyVehicleRepository(session))
    return await use_case.execute(vehicle_id=vehicle_id, status=request.status)
