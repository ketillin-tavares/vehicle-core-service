import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos import VehicleResponse, VehicleSnapshot
from src.application.ports import SalesSync
from src.application.use_cases import GetVehicle, RegisterVehicle, UpdateVehicle
from src.infrastructure.database import get_session
from src.interface.controllers.dependencies import get_sales_sync
from src.interface.gateways import SQLAlchemyVehicleRepository
from src.interface.presenters import ConflictResponse, NotFoundResponse, VehicleRequest

router = APIRouter(prefix="/vehicles", tags=["v1"])


def build_snapshot(vehicle: VehicleResponse) -> VehicleSnapshot:
    """
    Monta o snapshot de catálogo a ser replicado no vehicle-sales-service.

    Args:
        vehicle: DTO do veículo recém-cadastrado ou atualizado.

    Returns:
        Snapshot com os campos de catálogo e a versão do Core.
    """
    return VehicleSnapshot(
        vehicle_id=vehicle.id,
        brand=vehicle.brand,
        model=vehicle.model,
        year=vehicle.year,
        color=vehicle.color,
        price=vehicle.price,
        version=vehicle.version,
    )


@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
async def register_vehicle(
    request: VehicleRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    sales_sync: SalesSync = Depends(get_sales_sync),
) -> VehicleResponse:
    """
    Cadastra um veículo no catálogo.

    A publicação do snapshot no serviço de vendas é agendada como background task, executada
    após o commit da sessão e o envio da resposta (best-effort).

    Args:
        request: Dados de catálogo do veículo.
        background_tasks: Coletor de tarefas executadas após a resposta.
        session: Sessão de banco fornecida pela dependência de infraestrutura.
        sales_sync: Port de sincronização de catálogo com o vehicle-sales-service.

    Returns:
        DTO com os dados do veículo cadastrado.
    """
    use_case = RegisterVehicle(vehicle_repository=SQLAlchemyVehicleRepository(session))
    vehicle = await use_case.execute(
        brand=request.brand,
        model=request.model,
        year=request.year,
        color=request.color,
        price=request.price,
    )
    background_tasks.add_task(sales_sync.push_vehicle_snapshot, build_snapshot(vehicle))
    return vehicle


@router.put(
    "/{vehicle_id}",
    response_model=VehicleResponse,
    responses={404: {"model": NotFoundResponse}, 409: {"model": ConflictResponse}},
)
async def update_vehicle(
    vehicle_id: uuid.UUID,
    request: VehicleRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    sales_sync: SalesSync = Depends(get_sales_sync),
) -> VehicleResponse:
    """
    Edita os dados de catálogo de um veículo disponível.

    A publicação do snapshot no serviço de vendas é agendada como background task, executada
    após o commit da sessão e o envio da resposta (best-effort).

    Args:
        vehicle_id: Identificador do veículo a editar.
        request: Novos dados de catálogo do veículo.
        background_tasks: Coletor de tarefas executadas após a resposta.
        session: Sessão de banco fornecida pela dependência de infraestrutura.
        sales_sync: Port de sincronização de catálogo com o vehicle-sales-service.

    Returns:
        DTO com os dados do veículo atualizado.
    """
    use_case = UpdateVehicle(vehicle_repository=SQLAlchemyVehicleRepository(session))
    vehicle = await use_case.execute(
        vehicle_id=vehicle_id,
        brand=request.brand,
        model=request.model,
        year=request.year,
        color=request.color,
        price=request.price,
    )
    background_tasks.add_task(sales_sync.push_vehicle_snapshot, build_snapshot(vehicle))
    return vehicle


@router.get("/{vehicle_id}", response_model=VehicleResponse, responses={404: {"model": NotFoundResponse}})
async def get_vehicle(
    vehicle_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> VehicleResponse:
    """
    Consulta um veículo do catálogo pelo seu identificador.

    Args:
        vehicle_id: Identificador do veículo.
        session: Sessão de banco fornecida pela dependência de infraestrutura.

    Returns:
        DTO com os dados do veículo encontrado.
    """
    use_case = GetVehicle(vehicle_repository=SQLAlchemyVehicleRepository(session))
    return await use_case.execute(vehicle_id)
