from decimal import Decimal

from src.application.dtos import VehicleResponse
from src.domain.entities import Vehicle
from src.domain.repositories import VehicleRepository
from src.infrastructure.observability.logging import get_logger

logger = get_logger()


class RegisterVehicle:
    """Caso de uso para cadastrar um veículo no catálogo."""

    def __init__(self, vehicle_repository: VehicleRepository) -> None:
        self._vehicle_repository = vehicle_repository

    async def execute(self, brand: str, model: str, year: int, color: str, price: Decimal) -> VehicleResponse:
        """
        Cadastra um novo veículo disponível, na versão inicial do catálogo.

        Args:
            brand: Marca do veículo.
            model: Modelo do veículo.
            year: Ano de fabricação do veículo.
            color: Cor do veículo.
            price: Preço de catálogo do veículo.

        Returns:
            DTO com os dados do veículo cadastrado.

        Raises:
            InvalidVehicleDataError: Se algum dado de catálogo violar as regras de negócio.
        """
        vehicle = Vehicle(brand=brand, model=model, year=year, color=color, price=price)
        created = await self._vehicle_repository.add(vehicle)

        logger.info("veiculo_cadastrado", vehicle_id=str(created.id), version=created.version)
        return VehicleResponse.from_entity(created)
