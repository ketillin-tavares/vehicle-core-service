from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.domain.exceptions import (
    DomainError,
    InvalidVehicleDataError,
    VehicleNotEditableError,
    VehicleNotFoundError,
)
from src.environment import get_settings
from src.infrastructure.database import async_engine
from src.infrastructure.http import start_http_client, stop_http_client
from src.infrastructure.observability import configure_logging, get_logger
from src.interface.controllers import health_router, internal_vehicle_router, vehicle_router

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """
    Gerencia o ciclo de vida da aplicação (startup/shutdown).

    Args:
        app: Instância da aplicação FastAPI gerenciada.

    Yields:
        Controle para o runtime enquanto a aplicação estiver ativa.
    """
    settings = get_settings()
    configure_logging(settings.app.log_level)
    await start_http_client(settings.sales_service.timeout_seconds)
    logger.info("service_iniciando", service_name=settings.app.service_name)
    yield
    logger.info("service_encerrando", service_name=settings.app.service_name)
    await stop_http_client()
    await async_engine.dispose()


app = FastAPI(
    title="vehicle-core-service",
    description="Serviço principal da plataforma de revenda de veículos.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(vehicle_router, prefix="/v1")
app.include_router(internal_vehicle_router)
app.include_router(health_router)


@app.exception_handler(VehicleNotFoundError)
async def vehicle_not_found_handler(request: Request, exc: VehicleNotFoundError) -> JSONResponse:
    """
    Traduz VehicleNotFoundError para HTTP 404.

    Args:
        request: Requisição HTTP que originou o erro.
        exc: Exceção de veículo inexistente.

    Returns:
        Resposta JSON com status 404 e o detalhe do erro.
    """
    logger.info("veiculo_nao_encontrado", path=request.url.path, erro=str(exc))
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(VehicleNotEditableError)
async def vehicle_not_editable_handler(request: Request, exc: VehicleNotEditableError) -> JSONResponse:
    """
    Traduz VehicleNotEditableError para HTTP 409.

    Args:
        request: Requisição HTTP que originou o erro.
        exc: Exceção de veículo bloqueado para edição.

    Returns:
        Resposta JSON com status 409 e o detalhe do erro.
    """
    logger.info("veiculo_nao_editavel", path=request.url.path, erro=str(exc))
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidVehicleDataError)
async def invalid_vehicle_data_handler(request: Request, exc: InvalidVehicleDataError) -> JSONResponse:
    """
    Traduz InvalidVehicleDataError para HTTP 422.

    Args:
        request: Requisição HTTP que originou o erro.
        exc: Exceção de dados de catálogo inválidos.

    Returns:
        Resposta JSON com status 422 e o detalhe do erro.
    """
    logger.info("dados_veiculo_invalidos", path=request.url.path, erro=str(exc))
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """
    Traduz erros de domínio não mapeados especificamente para HTTP 400.

    Args:
        request: Requisição HTTP que originou o erro.
        exc: Exceção de domínio levantada durante o processamento.

    Returns:
        Resposta JSON com status 400 e o detalhe do erro.
    """
    logger.error("erro_de_dominio", path=request.url.path, erro=str(exc))
    return JSONResponse(status_code=400, content={"detail": str(exc)})
