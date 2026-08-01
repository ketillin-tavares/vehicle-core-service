import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from src.domain.exceptions import DomainError
from src.main import app, lifespan


class TestLifespan:
    """Tests for the application startup/shutdown lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_configures_logging_and_disposes_engine(self) -> None:
        """Test that the lifespan context runs startup/shutdown without raising, disposing the DB engine."""
        # Arrange / Act / Assert
        async with lifespan(app):
            pass


class _ExemploDomainError(DomainError):
    """Exceção de domínio de exemplo usada apenas para exercitar o exception handler global."""


_test_router = APIRouter()


@_test_router.get("/__raise-domain-error")
async def _raise_domain_error() -> None:
    """Rota de teste que sempre levanta uma DomainError para validar o handler global."""
    raise _ExemploDomainError("erro de domínio simulado")


app.include_router(_test_router)


class TestDomainErrorHandler:
    """Tests for the global DomainError -> HTTP 400 exception handler."""

    @pytest.mark.asyncio
    async def test_domain_error_is_translated_to_http_400(self) -> None:
        """Test that a DomainError raised by a route is translated into an HTTP 400 JSON response."""
        # Arrange
        transport = ASGITransport(app=app)

        # Act
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/__raise-domain-error")

        # Assert
        assert response.status_code == 400
        assert response.json() == {"detail": "erro de domínio simulado"}
