from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException

from src.environment import get_settings
from src.interface.controllers import dependencies
from src.interface.gateways import HttpSalesSync


class TestVerifyInternalToken:
    """Tests for the verify_internal_token dependency."""

    @pytest.mark.asyncio
    async def test_valid_token_passes(self) -> None:
        """Test that a matching X-Internal-Token header does not raise."""
        # Arrange
        expected = get_settings().security.internal_api_token

        # Act / Assert
        await dependencies.verify_internal_token(x_internal_token=expected)

    @pytest.mark.asyncio
    async def test_missing_token_raises_401(self) -> None:
        """Test that a missing X-Internal-Token header raises HTTPException 401."""
        # Arrange / Act / Assert
        with pytest.raises(HTTPException) as exc_info:
            await dependencies.verify_internal_token(x_internal_token=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_token_raises_401(self) -> None:
        """Test that a divergent X-Internal-Token header raises HTTPException 401."""
        # Arrange / Act / Assert
        with pytest.raises(HTTPException) as exc_info:
            await dependencies.verify_internal_token(x_internal_token="wrong-token")
        assert exc_info.value.status_code == 401


class TestGetSalesSync:
    """Tests for the get_sales_sync dependency provider."""

    def test_returns_http_sales_sync_wired_with_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that get_sales_sync returns an HttpSalesSync wired from the shared HTTP client and settings."""
        # Arrange
        fake_client = MagicMock(spec=httpx.AsyncClient)
        monkeypatch.setattr(dependencies, "get_http_client", lambda: fake_client)
        settings = get_settings()

        # Act
        sales_sync = dependencies.get_sales_sync()

        # Assert
        assert isinstance(sales_sync, HttpSalesSync)
        assert sales_sync._client is fake_client  # noqa: SLF001
        assert sales_sync._base_url == settings.sales_service.base_url.rstrip("/")  # noqa: SLF001
        assert sales_sync._internal_token == settings.security.internal_api_token  # noqa: SLF001
