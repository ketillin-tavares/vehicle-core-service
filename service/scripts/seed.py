"""Popula o banco do vehicle-core-service com o catálogo fixo de demonstração.

O script é idempotente: registros cujo identificador já existe são ignorados.
Os identificadores são fixos e correlacionados com o seed do vehicle-sales-service.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

from pydantic import BaseModel, Field
from sqlalchemy import CursorResult
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import VehicleStatus
from src.environment import get_settings
from src.infrastructure.database import async_engine, async_session_factory
from src.infrastructure.models import VehicleModel
from src.infrastructure.observability.logging import configure_logging, get_logger

logger = get_logger()

SEED_VERSION = 1


class SeedVehicle(BaseModel):
    """Veículo fixo do conjunto de dados de demonstração."""

    id: uuid.UUID = Field(..., description="Identificador fixo do veículo, compartilhado com o serviço de vendas")
    brand: str = Field(..., description="Marca do veículo")
    model: str = Field(..., description="Modelo do veículo")
    year: int = Field(..., description="Ano de fabricação do veículo")
    color: str = Field(..., description="Cor do veículo")
    price: Decimal = Field(..., description="Preço de catálogo do veículo")
    status: VehicleStatus = Field(..., description="Status comercial do veículo no conjunto de demonstração")


SEED_VEHICLES: list[SeedVehicle] = [
    SeedVehicle(
        id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
        brand="Volkswagen",
        model="Gol",
        year=2018,
        color="Branco",
        price=Decimal("30000.00"),
        status=VehicleStatus.AVAILABLE,
    ),
    SeedVehicle(
        id=uuid.UUID("22222222-2222-4222-8222-222222222222"),
        brand="Fiat",
        model="Uno",
        year=2020,
        color="Vermelho",
        price=Decimal("45000.00"),
        status=VehicleStatus.AVAILABLE,
    ),
    SeedVehicle(
        id=uuid.UUID("33333333-3333-4333-8333-333333333333"),
        brand="Hyundai",
        model="HB20",
        year=2021,
        color="Prata",
        price=Decimal("58000.00"),
        status=VehicleStatus.RESERVED,
    ),
    SeedVehicle(
        id=uuid.UUID("44444444-4444-4444-8444-444444444444"),
        brand="Chevrolet",
        model="Onix",
        year=2022,
        color="Preto",
        price=Decimal("62000.00"),
        status=VehicleStatus.AVAILABLE,
    ),
    SeedVehicle(
        id=uuid.UUID("55555555-5555-4555-8555-555555555555"),
        brand="Honda",
        model="Civic",
        year=2019,
        color="Cinza",
        price=Decimal("98000.00"),
        status=VehicleStatus.SOLD,
    ),
    SeedVehicle(
        id=uuid.UUID("66666666-6666-4666-8666-666666666666"),
        brand="Toyota",
        model="Corolla",
        year=2023,
        color="Azul",
        price=Decimal("135000.00"),
        status=VehicleStatus.AVAILABLE,
    ),
]


async def insert_vehicle(session: AsyncSession, vehicle: SeedVehicle, moment: datetime) -> bool:
    """
    Insere um veículo do conjunto fixo, ignorando o registro caso ele já exista.

    Args:
        session: Sessão async do SQLAlchemy usada na transação do seed.
        vehicle: Veículo fixo a ser inserido.
        moment: Carimbo de tempo aplicado a created_at e updated_at.

    Returns:
        True se o veículo foi inserido; False se já existia e foi ignorado.
    """
    stmt = insert(VehicleModel).values(
        id=vehicle.id,
        brand=vehicle.brand,
        model=vehicle.model,
        year=vehicle.year,
        color=vehicle.color,
        price=vehicle.price,
        status=vehicle.status.value,
        version=SEED_VERSION,
        created_at=moment,
        updated_at=moment,
    )
    result = cast(CursorResult[Any], await session.execute(stmt.on_conflict_do_nothing()))
    return result.rowcount > 0


async def main() -> None:
    """Executa o seed do catálogo de veículos e registra o resultado de cada linha."""
    settings = get_settings()
    configure_logging(settings.app.log_level)
    moment = datetime.now(UTC)
    inserted = 0
    skipped = 0

    async with async_session_factory() as session:
        for vehicle in SEED_VEHICLES:
            was_inserted = await insert_vehicle(session, vehicle, moment)
            if was_inserted:
                inserted += 1
                logger.info(
                    "seed_veiculo_inserido",
                    vehicle_id=str(vehicle.id),
                    model=vehicle.model,
                    status=vehicle.status.value,
                )
            else:
                skipped += 1
                logger.info("seed_veiculo_ignorado", vehicle_id=str(vehicle.id), model=vehicle.model)
        await session.commit()

    await async_engine.dispose()
    logger.info("seed_concluido", inserted=inserted, skipped=skipped, total=len(SEED_VEHICLES))


if __name__ == "__main__":
    asyncio.run(main())
