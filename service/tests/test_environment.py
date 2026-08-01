import pytest

from src.environment import (
    AppSettings,
    DatabaseSettings,
    SalesServiceSettings,
    SecuritySettings,
    Settings,
    get_settings,
)

ENV_VARS = [
    "SERVICE_NAME",
    "DEBUG",
    "LOG_LEVEL",
    "DATABASE_HOST",
    "DATABASE_PORT",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
    "DATABASE_NAME",
    "SALES_SERVICE_BASE_URL",
    "SALES_SERVICE_TIMEOUT_SECONDS",
    "INTERNAL_API_TOKEN",
]


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Garante que nenhuma variável de ambiente relevante vaze do shell do host para os testes."""
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


class TestAppSettings:
    """Tests for AppSettings default values and environment variable overrides."""

    def test_default_values(self) -> None:
        """Test that AppSettings resolves to its documented defaults when no env vars are set."""
        # Arrange / Act
        settings = AppSettings()

        # Assert
        assert settings.service_name == "vehicle-core-service"
        assert settings.debug is False
        assert settings.log_level == "INFO"

    def test_override_via_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that AppSettings picks up values from its aliased environment variables."""
        # Arrange
        monkeypatch.setenv("SERVICE_NAME", "custom-service")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        # Act
        settings = AppSettings()

        # Assert
        assert settings.service_name == "custom-service"
        assert settings.debug is True
        assert settings.log_level == "DEBUG"


class TestDatabaseSettings:
    """Tests for DatabaseSettings default values, overrides, and URL composition."""

    def test_default_values(self) -> None:
        """Test that DatabaseSettings resolves to its documented defaults when no env vars are set."""
        # Arrange / Act
        settings = DatabaseSettings()

        # Assert
        assert settings.host == "localhost"
        assert settings.port == 5432
        assert settings.user == "vehicle_core_user"
        assert settings.password == "vehicle_core_pass"
        assert settings.name == "vehicle_core"

    def test_override_via_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that DatabaseSettings picks up values from its aliased environment variables."""
        # Arrange
        monkeypatch.setenv("DATABASE_HOST", "db.internal")
        monkeypatch.setenv("DATABASE_PORT", "6543")
        monkeypatch.setenv("DATABASE_USER", "custom_user")
        monkeypatch.setenv("DATABASE_PASSWORD", "custom_pass")
        monkeypatch.setenv("DATABASE_NAME", "custom_db")

        # Act
        settings = DatabaseSettings()

        # Assert
        assert settings.host == "db.internal"
        assert settings.port == 6543
        assert settings.user == "custom_user"
        assert settings.password == "custom_pass"
        assert settings.name == "custom_db"

    def test_async_url_composition_with_defaults(self) -> None:
        """Test that async_url composes the asyncpg connection string targeting the vehicle_core database."""
        # Arrange
        settings = DatabaseSettings()

        # Act
        url = settings.async_url

        # Assert
        assert url == "postgresql+asyncpg://vehicle_core_user:vehicle_core_pass@localhost:5432/vehicle_core"

    def test_async_url_composition_with_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that async_url reflects overridden host, port, credentials and database name."""
        # Arrange
        monkeypatch.setenv("DATABASE_HOST", "db.internal")
        monkeypatch.setenv("DATABASE_PORT", "6543")
        monkeypatch.setenv("DATABASE_USER", "custom_user")
        monkeypatch.setenv("DATABASE_PASSWORD", "custom_pass")
        monkeypatch.setenv("DATABASE_NAME", "custom_db")
        settings = DatabaseSettings()

        # Act
        url = settings.async_url

        # Assert
        assert url == "postgresql+asyncpg://custom_user:custom_pass@db.internal:6543/custom_db"


class TestSalesServiceSettings:
    """Tests for SalesServiceSettings default values and environment variable overrides."""

    def test_default_values(self) -> None:
        """Test that SalesServiceSettings resolves to its documented defaults when no env vars are set."""
        # Arrange / Act
        settings = SalesServiceSettings()

        # Assert
        assert settings.base_url == "http://vehicle-sales-service:8000"
        assert settings.timeout_seconds == 5.0

    def test_override_via_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that SalesServiceSettings picks up values from its aliased environment variables."""
        # Arrange
        monkeypatch.setenv("SALES_SERVICE_BASE_URL", "http://sales:9000")
        monkeypatch.setenv("SALES_SERVICE_TIMEOUT_SECONDS", "2.5")

        # Act
        settings = SalesServiceSettings()

        # Assert
        assert settings.base_url == "http://sales:9000"
        assert settings.timeout_seconds == 2.5


class TestSecuritySettings:
    """Tests for SecuritySettings default values and environment variable overrides."""

    def test_default_values(self) -> None:
        """Test that SecuritySettings resolves to its documented defaults when no env vars are set."""
        # Arrange / Act
        settings = SecuritySettings()

        # Assert
        assert settings.internal_api_token == "internal-token"

    def test_override_via_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that SecuritySettings picks up values from its aliased environment variable."""
        # Arrange
        monkeypatch.setenv("INTERNAL_API_TOKEN", "custom-internal-token")

        # Act
        settings = SecuritySettings()

        # Assert
        assert settings.internal_api_token == "custom-internal-token"


class TestSettingsAndGetSettings:
    """Tests for the aggregate Settings model and the get_settings factory."""

    def test_settings_aggregates_sub_settings(self) -> None:
        """Test that Settings exposes app, database, sales_service and security sub-settings with their defaults."""
        # Arrange / Act
        settings = Settings()

        # Assert
        assert isinstance(settings.app, AppSettings)
        assert isinstance(settings.database, DatabaseSettings)
        assert isinstance(settings.sales_service, SalesServiceSettings)
        assert isinstance(settings.security, SecuritySettings)
        assert settings.database.name == "vehicle_core"

    def test_get_settings_returns_settings_instance(self) -> None:
        """Test that get_settings returns a fully resolved Settings instance."""
        # Arrange / Act
        settings = get_settings()

        # Assert
        assert isinstance(settings, Settings)
        assert settings.app.service_name == "vehicle-core-service"
