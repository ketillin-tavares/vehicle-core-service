import uuid

from src.application.dtos import VehicleResponse
from src.domain.exceptions import VehicleNotFoundError
from src.domain.repositories import VehicleRepository
from src.infrastructure.observability.logging import get_logger

logger = get_logger()


class GetVehicle:
    """Caso de uso para consultar um veículo do catálogo."""

    def __init__(self, vehicle_repository: VehicleRepository) -> None:
        self._vehicle_repository = vehicle_repository

    async def execute(self, vehicle_id: uuid.UUID) -> VehicleResponse:
        """
        Busca um veículo pelo seu identificador.

        Args:
            vehicle_id: Identificador do veículo.

        Returns:
            DTO com os dados do veículo encontrado.

        Raises:
            VehicleNotFoundError: Se o veículo não existe no catálogo.
        """
        vehicle = await self._vehicle_repository.get_by_id(vehicle_id)
        if vehicle is None:
            logger.info("consulta_veiculo_inexistente", vehicle_id=str(vehicle_id))
            raise VehicleNotFoundError(f"Veículo {vehicle_id} não encontrado")

        return VehicleResponse.from_entity(vehicle)
