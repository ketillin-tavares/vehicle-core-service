import abc

from src.application.dtos import VehicleSnapshot


class SalesSync(abc.ABC):
    """Port (interface) para publicar snapshots de catálogo no vehicle-sales-service."""

    @abc.abstractmethod
    async def push_vehicle_snapshot(self, snapshot: VehicleSnapshot) -> None:
        """
        Publica no serviço de vendas o snapshot de catálogo de um veículo.

        Contrato best-effort: a implementação nunca propaga erros para o chamador — falhas de
        rede ou do serviço de vendas são registradas em log e absorvidas, pois a disponibilidade
        de escrita do catálogo não pode depender do serviço de vendas.

        Args:
            snapshot: Dados de catálogo e versão a serem replicados.
        """
