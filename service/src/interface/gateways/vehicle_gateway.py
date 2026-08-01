import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import Vehicle, VehicleStatus
from src.domain.repositories import VehicleRepository
from src.infrastructure.models import VehicleModel


def map_vehicle_model_to_entity(model: VehicleModel) -> Vehicle:
    """
    Converte VehicleModel (ORM) para a entidade de domínio Vehicle.

    Args:
        model: Registro ORM do veículo.

    Returns:
        Entidade de domínio equivalente.
    """
    return Vehicle(
        id=model.id,
        brand=model.brand,
        model=model.model,
        year=model.year,
        color=model.color,
        price=model.price,
        status=VehicleStatus(model.status),
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLAlchemyVehicleRepository(VehicleRepository):
    """Adapter que implementa VehicleRepository usando SQLAlchemy sobre PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, vehicle: Vehicle) -> Vehicle:
        """
        Persiste um novo veículo na transação corrente.

        Args:
            vehicle: Veículo a ser cadastrado.

        Returns:
            O veículo persistido.
        """
        model = VehicleModel(
            id=vehicle.id,
            brand=vehicle.brand,
            model=vehicle.model,
            year=vehicle.year,
            color=vehicle.color,
            price=vehicle.price,
            status=vehicle.status.value,
            version=vehicle.version,
            created_at=vehicle.created_at,
            updated_at=vehicle.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return map_vehicle_model_to_entity(model)

    async def get_by_id(self, vehicle_id: uuid.UUID) -> Vehicle | None:
        """
        Busca um veículo pelo seu identificador.

        Args:
            vehicle_id: Identificador do veículo.

        Returns:
            Veículo encontrado ou None.
        """
        stmt = select(VehicleModel).where(VehicleModel.id == vehicle_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return map_vehicle_model_to_entity(model)

    async def update(self, vehicle: Vehicle) -> Vehicle:
        """
        Atualiza os dados de catálogo e a versão de um veículo já existente.

        Args:
            vehicle: Veículo com os dados já atualizados pela entidade.

        Returns:
            O veículo persistido.
        """
        stmt = (
            update(VehicleModel)
            .where(VehicleModel.id == vehicle.id)
            .values(
                brand=vehicle.brand,
                model=vehicle.model,
                year=vehicle.year,
                color=vehicle.color,
                price=vehicle.price,
                version=vehicle.version,
                updated_at=vehicle.updated_at,
            )
            .returning(VehicleModel)
            .execution_options(synchronize_session=False)
        )
        result = await self._session.execute(stmt)
        return map_vehicle_model_to_entity(result.scalars().one())

    async def update_status(self, vehicle_id: uuid.UUID, status: VehicleStatus) -> None:
        """
        Espelha o status comercial informado pelo serviço de vendas.

        Args:
            vehicle_id: Identificador do veículo.
            status: Novo status comercial.
        """
        stmt = (
            update(VehicleModel)
            .where(VehicleModel.id == vehicle_id)
            .values(status=status.value, updated_at=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )
        await self._session.execute(stmt)
