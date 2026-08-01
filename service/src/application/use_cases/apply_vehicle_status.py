import uuid

from src.application.dtos import VehicleResponse
from src.domain.entities import VehicleStatus
from src.domain.exceptions import VehicleNotFoundError
from src.domain.repositories import VehicleRepository
from src.infrastructure.observability.logging import get_logger

logger = get_logger()


class ApplyVehicleStatus:
    """Caso de uso para espelhar o status comercial informado pelo vehicle-sales-service."""

    def __init__(self, vehicle_repository: VehicleRepository) -> None:
        self._vehicle_repository = vehicle_repository

    async def execute(self, vehicle_id: uuid.UUID, status: VehicleStatus) -> VehicleResponse:
        """
        Aplica ao veículo o status comercial notificado pelo serviço de vendas.

        Args:
            vehicle_id: Identificador do veículo.
            status: Status comercial a ser espelhado.

        Returns:
            DTO com os dados do veículo após o espelhamento.

        Raises:
            VehicleNotFoundError: Se o veículo não existe no catálogo.
        """
        vehicle = await self._vehicle_repository.get_by_id(vehicle_id)
        if vehicle is None:
            logger.info("status_veiculo_inexistente", vehicle_id=str(vehicle_id), status=status.value)
            raise VehicleNotFoundError(f"Veículo {vehicle_id} não encontrado")

        vehicle.apply_status(status)
        await self._vehicle_repository.update_status(vehicle_id, status)

        logger.info("status_veiculo_espelhado", vehicle_id=str(vehicle_id), status=status.value)
        return VehicleResponse.from_entity(vehicle)
