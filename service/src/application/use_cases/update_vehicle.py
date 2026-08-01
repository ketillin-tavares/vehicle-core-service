import uuid
from decimal import Decimal

from src.application.dtos import VehicleResponse
from src.domain.exceptions import VehicleNotFoundError
from src.domain.repositories import VehicleRepository
from src.infrastructure.observability.logging import get_logger

logger = get_logger()


class UpdateVehicle:
    """Caso de uso para editar os dados de catálogo de um veículo."""

    def __init__(self, vehicle_repository: VehicleRepository) -> None:
        self._vehicle_repository = vehicle_repository

    async def execute(
        self,
        vehicle_id: uuid.UUID,
        brand: str,
        model: str,
        year: int,
        color: str,
        price: Decimal,
    ) -> VehicleResponse:
        """
        Atualiza os dados de catálogo de um veículo disponível, incrementando sua versão.

        Args:
            vehicle_id: Identificador do veículo a editar.
            brand: Nova marca do veículo.
            model: Novo modelo do veículo.
            year: Novo ano de fabricação.
            color: Nova cor do veículo.
            price: Novo preço de catálogo.

        Returns:
            DTO com os dados do veículo atualizado.

        Raises:
            VehicleNotFoundError: Se o veículo não existe no catálogo.
            VehicleNotEditableError: Se o veículo não está disponível (reservado ou vendido).
            InvalidVehicleDataError: Se algum dado de catálogo violar as regras de negócio.
        """
        vehicle = await self._vehicle_repository.get_by_id(vehicle_id)
        if vehicle is None:
            logger.info("edicao_veiculo_inexistente", vehicle_id=str(vehicle_id))
            raise VehicleNotFoundError(f"Veículo {vehicle_id} não encontrado")

        vehicle.update_details(brand=brand, model=model, year=year, color=color, price=price)
        updated = await self._vehicle_repository.update(vehicle)

        logger.info("veiculo_atualizado", vehicle_id=str(updated.id), version=updated.version)
        return VehicleResponse.from_entity(updated)
