import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from src.application.ports import SalesSync
from src.environment import get_settings
from src.infrastructure.http import get_http_client
from src.interface.gateways import HttpSalesSync

UNAUTHORIZED_DETAIL = "Token inválido ou ausente"


def _assert_token(received: str | None, expected: str) -> None:
    """
    Compara o token recebido com o esperado em tempo constante.

    Args:
        received: Token enviado no header da requisição.
        expected: Token configurado no serviço.

    Raises:
        HTTPException: Com status 401 se o token estiver ausente ou for divergente.
    """
    if received is None or not secrets.compare_digest(received, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=UNAUTHORIZED_DETAIL)


async def verify_internal_token(x_internal_token: Annotated[str | None, Header()] = None) -> None:
    """
    Valida o header X-Internal-Token das rotas internas entre serviços.

    Args:
        x_internal_token: Token compartilhado enviado pelo vehicle-sales-service.

    Raises:
        HTTPException: Com status 401 se o token estiver ausente ou for divergente.
    """
    _assert_token(x_internal_token, get_settings().security.internal_api_token)


def get_sales_sync() -> SalesSync:
    """
    Fornece o publicador de snapshots do vehicle-sales-service usando o cliente HTTP compartilhado.

    Returns:
        Implementação HTTP da port SalesSync.
    """
    settings = get_settings()
    return HttpSalesSync(
        client=get_http_client(),
        base_url=settings.sales_service.base_url,
        internal_token=settings.security.internal_api_token,
    )
