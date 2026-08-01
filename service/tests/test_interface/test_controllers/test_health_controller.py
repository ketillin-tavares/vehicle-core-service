import pytest
from httpx import AsyncClient

from src.environment import get_settings


class TestHealthController:
    """Tests for the GET /health route."""

    @pytest.mark.asyncio
    async def test_health_check_returns_ok_status(self, async_client: AsyncClient) -> None:
        """Test that GET /health responds with HTTP 200 and the expected payload."""
        # Arrange
        settings = get_settings()

        # Act
        response = await async_client.get("/health")

        # Assert
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "service": settings.app.service_name,
            "version": "0.1.0",
        }
