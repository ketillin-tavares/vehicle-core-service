from pydantic import Field
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Configurações gerais da aplicação."""

    service_name: str = Field(
        default="vehicle-core-service",
        validation_alias="SERVICE_NAME",
        description="Nome do serviço usado em logs e no health check",
    )
    debug: bool = Field(
        default=False,
        validation_alias="DEBUG",
        description="Habilita o modo debug (echo de SQL e logs verbosos)",
    )
    log_level: str = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
        description="Nível mínimo de log emitido pela aplicação",
    )


class DatabaseSettings(BaseSettings):
    """Configurações de conexão com o banco de dados PostgreSQL."""

    host: str = Field(
        default="localhost",
        validation_alias="DATABASE_HOST",
        description="Host do servidor PostgreSQL",
    )
    port: int = Field(
        default=5432,
        validation_alias="DATABASE_PORT",
        description="Porta do servidor PostgreSQL",
    )
    user: str = Field(
        default="vehicle_core_user",
        validation_alias="DATABASE_USER",
        description="Usuário de conexão com o PostgreSQL",
    )
    password: str = Field(
        default="vehicle_core_pass",
        validation_alias="DATABASE_PASSWORD",
        description="Senha de conexão com o PostgreSQL",
    )
    name: str = Field(
        default="vehicle_core",
        validation_alias="DATABASE_NAME",
        description="Nome do banco de dados do serviço",
    )

    @property
    def async_url(self) -> str:
        """
        Monta a URL de conexão async para o PostgreSQL.

        Returns:
            URL no formato postgresql+asyncpg://user:password@host:port/name.
        """
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class SalesServiceSettings(BaseSettings):
    """Configurações de acesso ao vehicle-sales-service."""

    base_url: str = Field(
        default="http://vehicle-sales-service:8000",
        validation_alias="SALES_SERVICE_BASE_URL",
        description="URL base do vehicle-sales-service usada na sincronização do catálogo",
    )
    timeout_seconds: float = Field(
        default=5.0,
        validation_alias="SALES_SERVICE_TIMEOUT_SECONDS",
        description="Timeout, em segundos, das chamadas HTTP ao vehicle-sales-service",
    )


class SecuritySettings(BaseSettings):
    """Segredos compartilhados usados na comunicação entre serviços."""

    internal_api_token: str = Field(
        default="internal-token",
        validation_alias="INTERNAL_API_TOKEN",
        description="Token compartilhado exigido no header X-Internal-Token das rotas internas",
    )


class Settings(BaseSettings):
    """Configuração principal que agrupa todas as sub-configurações."""

    app: AppSettings = Field(default_factory=AppSettings, description="Configurações gerais da aplicação")
    database: DatabaseSettings = Field(default_factory=DatabaseSettings, description="Configurações do PostgreSQL")
    sales_service: SalesServiceSettings = Field(
        default_factory=SalesServiceSettings,
        description="Configurações de acesso ao vehicle-sales-service",
    )
    security: SecuritySettings = Field(
        default_factory=SecuritySettings,
        description="Segredos compartilhados entre os serviços",
    )


def get_settings() -> Settings:
    """
    Factory para obter as configurações da aplicação.

    Returns:
        Instância de Settings resolvida a partir das variáveis de ambiente.
    """
    return Settings()
