import abc
import uuid

from src.domain.entities import Vehicle, VehicleStatus


class VehicleRepository(abc.ABC):
    """Port (interface) para persistência do catálogo de veículos."""

    @abc.abstractmethod
    async def add(self, vehicle: Vehicle) -> Vehicle:
        """
        Persiste um novo veículo na transação corrente.

        Args:
            vehicle: Veículo a ser cadastrado.

        Returns:
            O veículo persistido.
        """

    @abc.abstractmethod
    async def get_by_id(self, vehicle_id: uuid.UUID) -> Vehicle | None:
        """
        Busca um veículo pelo seu identificador.

        Args:
            vehicle_id: Identificador do veículo.

        Returns:
            Veículo encontrado ou None.
        """

    @abc.abstractmethod
    async def update(self, vehicle: Vehicle) -> Vehicle:
        """
        Atualiza os dados de catálogo e a versão de um veículo já existente.

        Args:
            vehicle: Veículo com os dados já atualizados pela entidade.

        Returns:
            O veículo persistido.
        """

    @abc.abstractmethod
    async def update_status(self, vehicle_id: uuid.UUID, status: VehicleStatus) -> None:
        """
        Espelha o status comercial informado pelo serviço de vendas.

        Args:
            vehicle_id: Identificador do veículo.
            status: Novo status comercial.
        """
