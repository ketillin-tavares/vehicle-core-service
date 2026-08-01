import asyncio

import httpx

from src.application.dtos import VehicleSnapshot
from src.application.ports import SalesSync
from src.infrastructure.observability.logging import get_logger

logger = get_logger()

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 0.5


class HttpSalesSync(SalesSync):
    """Adapter que publica snapshots de catálogo no vehicle-sales-service, com retentativa limitada."""

    def __init__(self, client: httpx.AsyncClient, base_url: str, internal_token: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._internal_token = internal_token

    async def push_vehicle_snapshot(self, snapshot: VehicleSnapshot) -> None:
        """
        Envia o snapshot de catálogo ao serviço de vendas, absorvendo qualquer falha.

        Args:
            snapshot: Dados de catálogo e versão a serem replicados.
        """
        url = f"{self._base_url}/internal/v1/vehicles/{snapshot.vehicle_id}"
        headers = {"X-Internal-Token": self._internal_token}
        payload = snapshot.model_dump(mode="json", exclude={"vehicle_id"})

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = await self._client.put(url, json=payload, headers=headers)
                response.raise_for_status()
                logger.info(
                    "catalogo_sincronizado",
                    vehicle_id=str(snapshot.vehicle_id),
                    version=snapshot.version,
                    attempt=attempt,
                )
                return
            except httpx.HTTPError as error:
                logger.warning(
                    "sincronizacao_catalogo_falhou",
                    vehicle_id=str(snapshot.vehicle_id),
                    version=snapshot.version,
                    attempt=attempt,
                    erro=str(error),
                )
                if attempt < MAX_ATTEMPTS:
                    await asyncio.sleep(BACKOFF_SECONDS * attempt)

        logger.error(
            "sincronizacao_catalogo_desistida",
            vehicle_id=str(snapshot.vehicle_id),
            version=snapshot.version,
        )
